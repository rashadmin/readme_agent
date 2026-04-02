import base64
from pathlib import Path
import re
import pandas as pd
import requests
import os
from pathlib import PurePosixPath
import time


MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
HEX_PREFIX_RE = re.compile(r"^0x0[0-9a-f]+", re.IGNORECASE)

EXCLUDED_DIRS = {
    ".git", ".github", ".ipynb_checkpoints",
    "__pycache__", "node_modules","tests"
    ".venv", "venv", ".idea", ".vscode",
    "dist", "build", "data", "dataset",'logs','migrations','env','lib','test'
}

ALLOWED_EXTENSIONS = {".py", ".ipynb", ".sql"}


EXCLUDED_FILES = {
    ".env", ".env.local", ".env.example",
    ".DS_Store", ".gitignore",
    "package-lock.json", "yarn.lock",
    "poetry.lock", "Pipfile.lock"
}

DATASET_EXTENSIONS = {
    ".csv", ".tsv", ".parquet", ".feather",
    ".h5", ".hdf5", ".arrow",
    ".avro", ".orc",".data",",xlsx"
    ".sqlite", ".db", ".mdb",".tsx",".md",".ts",".json"
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".7z",
    ".mp4", ".mp3", ".wav",
    ".exe", ".bin", ".dll",
    ".pt", ".pth", ".onnx", ".npy", ".npz"
}

def should_skip(path: str, size: int | None = None) -> bool:
    p = Path(path)
    ext = p.suffix.lower()

    # skip paths with hex-like components (0x0n...)
    if any(HEX_PREFIX_RE.match(part) for part in p.parts):
        return True
    
    # skip directories containing excluded names (anywhere)
    for part in p.parts:
        part_lower = part.lower()
        if any(excl in part_lower for excl in EXCLUDED_DIRS):
            return True

    # skip known filenames
    if p.name in EXCLUDED_FILES:
        return True

    # skip datasets
    if ext in DATASET_EXTENSIONS:
        return True

    # skip binaries
    if ext in BINARY_EXTENSIONS:
        return True

    # size-based rule (allow large notebooks only)
    if size is not None and size > MAX_FILE_SIZE and ext != ".ipynb":
        return True
    
    if Path(path).suffix.lower() in ALLOWED_EXTENSIONS:
        return False


    return True



def get_hex_content(file_content_url,HEADERS,params):
    file_response = requests.get(file_content_url, headers=HEADERS, params=params)
    content = file_response.json()['content']
    return content

def decode(content):
    decoded_bytes = base64.b64decode(content)
    decoded_text = decoded_bytes.decode("utf-8", errors="ignore")
    return decoded_text
def ipynb_to_py(decoded_text):
    import json
    code_cells = []
    for cell in json.loads(decoded_text)['cells']:
        if cell['cell_type']=='code':
            code_cells.extend(cell['source'])
    return ''.join(code_cells)


import os
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from pathlib import PurePosixPath
import pandas as pd
from pydantic import BaseModel,Field
from typing_extensions import Optional,List,Dict

class File(BaseModel):
    # filename:str = Field(description='The exact filename extracted from the marker.')
    context : str = Field(description='What role this file plays in the overall system or application.')
    problem : str = Field(description=' What problem(s) this file is trying to solve.')
    tools_or_frameworks_used : str = Field(description='Libraries, frameworks, or platforms used (e.g. Flask, SQLAlchemy, Redis, psycopg, LangGraph).')


class Repository(BaseModel):
    repository: Dict[str, File] = Field(description="Mapping of filename from extracted filename from the marker to its semantic summary")






class GitExtractor:
    def __init__(self):
        self.BASE_URL = "https://api.github.com"
        GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
        self.HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}"}
        self.params = {"per_page": 100,"visibility": "all", "affiliation": "owner"}
        self.prompt = '''You are given a single string that contains the contents of multiple source code files.
        The string follows this exact structure:
        - Each file starts with a marker:
          # ===== FILE: filename =====
        - Everything below that marker until the next marker belongs to that file.
        Your task is to:
        1. Detect and separate each file.
        2. For EACH file, extract:- filename and at most 200 words semantic summary (i.e it can be less if neccesary) of the file content using the structured schema below.
        
        Do NOT merge files.Do NOT skip files. Do NOT hallucinate functionality not present in the file. Base your analysis strictly on the file’s content.
        ---
        ### 🔍 Semantic Summary Schema (REQUIRED)
        For each file, produce the following fields:
        - **filename** :The exact filename extracted from the marker, do not make another name only (filename).
        - **context** : What role this file plays in the overall system or application.
        - **problem** : What problem(s) this file is trying to solve.
        - **tools_or_frameworks_used** : Libraries, frameworks, or platforms used (e.g. Flask, SQLAlchemy, Redis, psycopg, LangGraph).
        ---
        ### 📤 Output Format (STRICT)
        Return the result as a JSON array.
        Each element represents ONE file.
        Example structure:
        [{{"filename": "app/__init__.py","context": "...", "problem": "...",  "tools_or_frameworks_used": ["...", "..."}}]
        ---
        ### Constraints
        - Keep explanations concise but meaningful.
        - Prefer bullet points inside arrays.
        - Do not include code unless necessary for explanation.
        - If a field is not applicable, return an empty array ([]) — never null.
        ---
        ###  Input String:
        '''

    def extract_files(self,repo): 
        repourl = f'{self.BASE_URL}/repos/rashadmin/{repo}'
        self.extract_file_blob(repourl) 

    def extract_file_blob(self,repo_url):
        url = f"{self.BASE_URL}/user/repos"
        repo_response = requests.get(repo_url, headers=self.HEADERS, params=self.params)
        print(repo_response)
        repo_name = repo_url.split('/')[-1]
        #get the branch of the url
        repo_branch = repo_response.json()['default_branch']
        date_created = repo_response.json()['created_at']
        date_modified =repo_response.json()['pushed_at']
        latest_commit_url = f'{repo_url}/git/ref/heads/{repo_branch}'
        latest_commit_response = requests.get(latest_commit_url, headers=self.HEADERS, params=self.params)
        if latest_commit_response.status_code==409:
            return            
        latest_commit_sha=latest_commit_response.json()['object']['sha']
        file_tree_url = f'{repo_url}/git/trees/{latest_commit_sha}?recursive=1'
        file_tree_response = requests.get(file_tree_url, headers=self.HEADERS, params=self.params)
        if file_tree_response.status_code != 200:
            print(file_tree_response.json())
                #filter the file type and get content
        files_content = [{'filename':file.get('path'),'content':get_hex_content(f'{repo_url}/git/blobs/{file['sha']}',HEADERS=self.HEADERS,params=self.params)} for file in file_tree_response.json()['tree']  if file["type"] == "blob" and not should_skip(file["path"], file.get("size"))]

        self.files_content = files_content
    
    

    
    def merge_with_headers(self,paths, contents):
        blocks = []
        for p, c in zip(paths, contents):
            blocks.append(f"# ===== FILE: {p} =====\n{c}")
        return "\n\n".join(blocks)
    
    def merge_with_index(self,path,index):
        blocks = []
        for p, i in zip(path, index):
            blocks.append({p:i})
        return blocks  
    
    def get_semantic(self,semantic):
        blocks = []
        for s in semantic:
            blocks.append(s)
        return list(set(blocks))[0]

    
    def group(self):
        df = pd.DataFrame(self.files_content)
        df["directory"] = df["filename"].apply(lambda p: str(PurePosixPath(p).parent))
        df["extension"] = df["filename"].apply(lambda p: PurePosixPath(p).suffix.lower())
        df['decoded_text']=df.apply(lambda x : ipynb_to_py(decode(x['content'])) if x['extension']=='.ipynb' else decode(x['content']),axis=1)
        withdot = df[df['directory']=='.'].groupby(["directory", "extension"], as_index=False).agg({
                  "decoded_text": lambda x: self.merge_with_headers(df.loc[x.index, "filename"], x),
                  "filename": lambda x:self.merge_with_index(df.loc[x.index,'filename'],x.index),
              })
        self.alldir = pd.concat([df[df['directory']!='.'].groupby(["directory", "extension"], as_index=False).agg({
                  "decoded_text": lambda x: self.merge_with_headers(df.loc[x.index, "filename"], x),
                  "filename": lambda x:self.merge_with_index(df.loc[x.index,'filename'],x.index),
              }),withdot])


    def generate(self):
        import time
        count = 0 
        complete = {}
        llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai")
        prompt_template = ChatPromptTemplate([('system',self.prompt),('human','{text_string}')])
        for i in range(self.alldir.shape[0]):
            if count<10:
                file_prompt = prompt_template.invoke({'text_string':self.alldir.iloc[i]['decoded_text']})
                structured_llm = llm.with_structured_output(schema=Repository)
                extracted_summary = structured_llm.invoke(file_prompt)
                summaries = extracted_summary.model_dump()['repository']
                complete.update(summaries)
                print(count)
                count+=1
            else:
                time.sleep(60)
                count = 0
                file_prompt = prompt_template.invoke({'text_string':self.alldir.iloc[i]['decoded_text']})
                structured_llm = llm.with_structured_output(schema=Repository)
                summaries = extracted_summary.model_dump()['repository']
                extracted_summary = structured_llm.invoke(file_prompt)
                complete.update(summaries)
                print(count)
        return complete

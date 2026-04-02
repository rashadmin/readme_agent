import os
import asyncio
import logging
import sys
from contextlib import asynccontextmanager
from git import GitExtractor
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
 
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.genai import types as genai_types
from dotenv import load_dotenv
load_dotenv()
#
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log"),  # logs saved here
    ],
)

logger = logging.getLogger("readme_agent_api")





BASE_DIR = os.path.dirname(__file__)
skill_path = os.path.join(BASE_DIR, "SKILL.md")
content_path = os.path.join(BASE_DIR, "content_metadata.csv")




with open(skill_path, "r") as f:
    readme_formatting_guide = f.read()

# ── Tool definitions ──────────────────────────────────────────────────────────a

# ── GitHub MCP Toolset ────────────────────────────────────────────────────────
# Provides tools to interact with GitHub — including creating and updating files.
# Requires a GitHub token with `repo` scope (read + write access).
# Get one at: https://github.com/settings/tokens
 
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_OWNER = os.getenv("GITHUB_OWNER", "rashadmin")  # override via env var
MCP_MAX_RETRIES = int(os.getenv("MCP_MAX_RETRIES", "3"))
MCP_RETRY_DELAY = float(os.getenv("MCP_RETRY_DELAY", "2.0"))  # seconds
 
if not GITHUB_TOKEN:
    logger.warning("GITHUB_TOKEN is not set — GitHub MCP calls will fail")
 

def get_summary_tool(repo: str) -> list[dict]:
    """
    Retrieves semantic summaries for all files in a repository.

    Args:
        repo: Repository name

    Returns:
        List of dicts with filename and summary
        e.g. [{"filename": "main.py", "summary": "Entry point..."}]
    """
    logger.info(f"[TOOL] get_summary_tool called with repo={repo}")
    try:
        df = pd.read_csv(content_path)
        df = df.copy()  # avoid SettingWithCopyWarning

        result = df[df["repo"] == repo][["filename", "summary"]].to_dict("records")
        
        logger.info(f"[TOOL] get_summary_tool returned {len(result)} records")
        if not result:
            return [{"error": f"No summaries found for repo '{repo}'"}]

        return result

    except FileNotFoundError:
        logger.exception("[TOOL] content_metadata.csv not foundd")
        return [{"error": "content_metadata.csv not found"}]
    except Exception as e:
        logger.exception("[TOOL] get_summary_tool failed")
        return [{"error": str(e)}]


def call_code_tool(files: list[str], repo: str) -> list[dict]:
    """
    Retrieves raw source code for the specified files in a repository.
 
    Args:
        files: List of filenames to retrieve, e.g. ["agent.py", "utils/parser.py"]
        repo:  Repository name
 
    Returns:
        List of dicts with 'filename' and 'decoded_text' keys — only for
        the requested files.
        e.g. [{"filename": "agent.py", "decoded_text": "import os\\n..."}]
    """
    logger.info(f"[TOOL] call_code_tool called | repo={repo} | files={files}")
    try:
        df = pd.read_csv(content_path)
        mask = (df["repo"] == repo) & (df["filename"].isin(files))
        result = df[mask][["filename", "decoded_text"]].to_dict("records")
 
        found = [r["filename"] for r in result]
        missing = [f for f in files if f not in found]
        if missing:
            logger.warning(f"[TOOL] call_code_tool — files not found: {missing}")
 
        logger.info(f"[TOOL] call_code_tool returned {len(result)} files")
        return result
    except FileNotFoundError:
        logger.exception("[TOOL] content_metadata.csv not found")
        return [{"error": "content_metadata.csv not found"}]
    except Exception as e:
        logger.exception("[TOOL] call_code_tool failed")
        return [{"error": str(e)}]
 
def extract_repo_tool(repo: str) -> str: 
    """ Fallback tool. Extracts the full codebase from GitHub using GitExtractor and returns trimmed structured summaries for every file. Only call this if get_summary_tool returned an empty list. Do NOT call this just because individual file summaries are vague — use call_code_tool for that. Args: repo: Repository name e.g. "my-project" Returns: A formatted string where each file block contains: - context: what the file does and its role - tools_or_frameworks_used: libraries and frameworks used - learning_resources: links to relevant official docs Treat this as your complete understanding of the codebase and skip directly to Step 3 — no need to call call_code_tool after this. """ 
    logger.info(f"[TOOL] extract_repo_tool called | repo={repo}") 
    try: 
        extract = GitExtractor() 
        extract.extract_files(repo) 
        extract.group() 
        summary = extract.generate() 
        formatted = [] 
        for filename, file_summary in summary.items(): 
            formatted.append( f"File: {filename}\n" f"Purpose: {file_summary.get('context', '')}\n" f"Problem: {file_summary.get('problem', '')}\n" f"Tools: {file_summary.get('tools_or_frameworks_used', '')}\n" ) 
            result = "\n".join(formatted) 
            logger.info( f"[TOOL] extract_repo_tool returned formatted summary " f"for {len(summary)} files" ) 
            return result 
    except Exception as e: 
        logger.exception("[TOOL] extract_repo_tool failed") 
        return f"ERROR: GitExtractor failed — {str(e)}"


github_toolset = McpToolset(
    connection_params=StreamableHTTPServerParams(
        url="https://api.githubcopilot.com/mcp/",
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "X-MCP-Toolsets": "repos",
        },
        timeout=120,        # seconds before giving up on a request
        sse_read_timeout=120,
    ),

)



        
instruction = f"""
you are a README generation agent. Your job is to analyse a codebase and produce
a polished, accurate GitHub README.md file.

## Input
You will receive ONLY:
- repo: the repository name

## CRITICAL RULES
- You MUST complete the full workflow before giving a final response.
- Do NOT stop early.
- Do NOT explain what you will do.
- Do NOT return a final answer until the README has been successfully created or updated on GitHub.
- If the README is not yet pushed, continue calling tools.



You will receive a list of dictionaries, where each dict has exactly two keys:
  - "filename": the relative path of the file
  - "summary":  a short semantic description of what the file does

Example input:
[
  {{"filename": "main.py",           "summary": "Entry point that starts the FastAPI server."}},
  {{"filename": "agent.py",          "summary": "Unclear."}},
  {{"filename": "utils/parser.py",   "summary": "Some parsing logic."}}
]
 
## Your workflow
### Step 0 — Retrieve summaries
Call get_summary_tool with the repo name.

It returns:
- A list of dicts: 
- OR an empty list [] if the repo is not found

---

### Step 0.5 — Fallback (IMPORTANT)

If get_summary_tool returns an EMPTY list:
→ You MUST call extract_repo_tool immediately.

This tool will return structured summaries for the entire repository.

After calling extract_repo_tool:
- Treat its output as your complete understanding of the codebase
- Skip Step 1 and Step 2
- Go directly to Step 3

DO NOT call call_code_tool after extract_repo_tool.

### Step 1 — Evaluate summaries
Go through every item in the list. For each one, decide if the summary is
SUFFICIENT or VAGUE.
 
A summary is SUFFICIENT if it clearly tells you:
- What the file does
- Its role in the project
- Any key functions, classes, or patterns it introduces
 
A summary is VAGUE if it uses filler language ("some logic", "unclear", "handles stuff"),
is a single generic word, or leaves the file's purpose ambiguous.
 
### Step 2 — Retrieve vague files
Collect ALL filenames whose summaries are vague into a single list and call
call_code_tool once with that list. Do not make multiple separate calls — batch them.
 
If the retrieved code still delegates heavily to another file whose summary is also
vague, call call_code_tool again for those dependencies.
 
Do NOT call call_code_tool for files whose summaries are already clear.
 
### Step 3 — Build understanding
From the summaries and any code retrieved, extract:
- Project name (from filenames, pyproject.toml, package.json, etc.)
- What the project does and why
- Architecture and design decisions
- Full tech stack (every import, framework, API, service)
- How to install and run it (from requirements.txt, Makefile, Dockerfile, etc.) if necessary
- Usage patterns (from main.py, cli.py, tests, or example scripts)
- All frameworks and libraries (to link their docs in Resources)
 
### Step 4 — Write the README
Use the formatting guide below to write the README. Infer everything from the
code — do not invent details that are not supported by what you have read.
 

### Step 5 — Upload to GitHub
Use the GitHub MCP tool to create or update README.md in the repository.
- File path: "README.md"
- Target the branch provided in the input if not provided use `master` as default if that doesn't work , then try main
- owner:  the GitHub username or organisation default is rashadmin
- Commit message: "docs: add README generated by readme-agent"
- If a README.md already exists in the repo, use the update file tool instead of create,
  passing the existing file's SHA to avoid conflicts.


## README Formatting Guide
 
{readme_formatting_guide}
"""




session_service = InMemorySessionService()
APP_NAME = "readme_agent_app"


app = FastAPI(title="README Agent API")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


readme_agent = Agent(
    name="readme_agent",
    model="gemini-2.5-flash",
    description="Generates a GitHub README.md from codebase analysis.",
    instruction=instruction,
    tools=[
        FunctionTool(get_summary_tool),
        FunctionTool(call_code_tool),
        FunctionTool(extract_repo_tool),
        github_toolset,
    ],
)


runner = Runner(
    agent=readme_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

# Request schema
class ChatRequest(BaseModel):
    repo: str

class ToolCallEvent(BaseModel):
    tool: str
    input: dict
    output: str | None = None

async def run_agent_with_retry(repo, session_id, user_message):
    last_exc = None
    readme_pushed = False

    for attempt in range(1, MCP_MAX_RETRIES + 1):
        tool_calls: list[dict] = []
        final_response = ""

        try:
            async for event in runner.run_async(
                user_id=repo+'qe',
                session_id=session_id,
                new_message=user_message,
            ):
                if event.get_function_calls():
                    for fn in event.get_function_calls():
                        call_info = {"tool": fn.name, "input": fn.args}
                        logger.info(f"[AGENT] Tool call: {call_info}")
                        tool_calls.append(call_info)

                if event.get_function_responses():
                    for fn in event.get_function_responses():
                        result_text = str(fn.response)[:500]
                        if tool_calls:
                            tool_calls[-1]["output"] = result_text
                        logger.info(f"[AGENT] Tool result: {result_text[:200]}")

                        # Detect successful README push
                        if "create_or_update_file" in str(tool_calls[-1].get("tool", "")) and \
                           "sha" in result_text and "isError" not in result_text:
                            readme_pushed = True
                            logger.info("[AGENT] README successfully pushed to GitHub")

                if event.is_final_response():
                    if event.content and event.content.parts:
                        final_response = "".join(
                            p.text for p in event.content.parts if hasattr(p, "text")
                        )
                    logger.info(f"[AGENT] Final response length: {len(final_response)}")

            return tool_calls, final_response  # clean exit

        except ConnectionError as exc:
            last_exc = exc

            # README was already pushed — don't retry, just return what we have
            if readme_pushed:
                logger.info("[AGENT] README was pushed successfully — ignoring post-push MCP timeout")
                return tool_calls, final_response or "README successfully generated and pushed to GitHub."

            wait = MCP_RETRY_DELAY * (2 ** (attempt - 1))
            logger.warning(
                f"[AGENT] MCP connection dropped on attempt {attempt}/{MCP_MAX_RETRIES} "
                f"— retrying in {wait:.1f}s"
            )
            await asyncio.sleep(wait)

        except Exception as exc:
            logger.exception(f"[AGENT] Non-retryable error | repo={repo}")
            raise

    raise RuntimeError(f"Agent failed after {MCP_MAX_RETRIES} retries") from last_exc


@app.post("/generate-readme")
async def generate_readme(request: ChatRequest):
    logger.info(f"[API] /generate-readme called | repo={request.repo}")

    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=request.repo+'qe',
    )

    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=request.repo)],
    )

    try:
        tool_calls, final_response = await run_agent_with_retry(
            repo=request.repo,
            session_id=session.id,
            user_message=user_message,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": "success",
        "repo": request.repo,
        "tool_calls": tool_calls,
        "response": final_response,
    }
 
@app.get("/health")
async def health():
    return {"status": "ok"}

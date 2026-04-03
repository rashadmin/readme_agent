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
import time
from google.adk.agents import Agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.genai import types as genai_types
from dotenv import load_dotenv
load_dotenv()
from fastapi.responses import StreamingResponse

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
content_path = os.path.join(BASE_DIR, "content_metadata.csv.zip")




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
 


CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

CACHE_TTL_SECONDS = 60 * 60 * 24  # 24 hours


def extract_repo_tool(repo: str) -> str:
    """
    Cached fallback tool using GitExtractor.
    """

    logger.info(f"[TOOL] extract_repo_tool called | repo={repo}")

    cache_file = os.path.join(CACHE_DIR, f"{repo}.json")

    try:
        # ── Check cache ─────────────────────────────────────────────
        if os.path.exists(cache_file):
            age = time.time() - os.path.getmtime(cache_file)

            if age < CACHE_TTL_SECONDS:
                logger.info(f"[CACHE] HIT for repo={repo}")

                with open(cache_file, "r") as f:
                    cached = json.load(f)

                return cached["result"]

            else:
                logger.info(f"[CACHE] STALE for repo={repo}")

        # ── Cache miss → run extractor ──────────────────────────────
        logger.info(f"[CACHE] MISS for repo={repo}")

        from git import GitExtractor

        extract = GitExtractor()
        extract.extract_files(repo)
        extract.group()
        summary = extract.generate()

        formatted = []
        for filename, file_summary in summary.items():
            formatted.append(
                f"File: {filename}\n"
                f"Purpose: {file_summary.get('context', '')}\n"
                f"Problem: {file_summary.get('problem', '')}\n"
                f"Tools: {file_summary.get('tools_or_frameworks_used', '')}\n"
            )

        result = "\n".join(formatted)

        # ── Save cache ──────────────────────────────────────────────
        with open(cache_file, "w") as f:
            json.dump({"result": result, "timestamp": time.time()}, f)

        logger.info(f"[CACHE] SAVED for repo={repo}")

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

# ── SSE helper ────────────────────────────────────────────────────────────────
import json
def sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
 
 
# Human-readable labels for each tool shown in the frontend progress feed
TOOL_LABELS = {
    "get_summary_tool":      "Fetching file summaries offline",
    "call_code_tool":        "Reading source files",
    "extract_repo_tool":     "Fetching the file summaries online",
    "get_file_contents":     "Checking existing README",
    "create_or_update_file": "Pushing README to GitHub",
}

 
async def stream_agent(repo: str):
    """Async generator — runs the agent and yields SSE events in real time."""
 
    yield sse({"type": "status", "message": "Agent starting..."})
 
    session = await session_service.create_session(
        app_name=APP_NAME,
        user_id=repo,
    )
 
    user_message = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=repo)],
    )
 
    pending_tool: str | None = None
 
    try:
        async for event in runner.run_async(
            user_id=repo,
            session_id=session.id,
            new_message=user_message,
        ):
            # Tool call fired by the agent
            if event.get_function_calls():
                for fn in event.get_function_calls():
                    pending_tool = fn.name
                    label = TOOL_LABELS.get(fn.name, fn.name)
                    logger.info(f"[AGENT] Tool call: {fn.name} | args: {fn.args}")
                    yield sse({
                        "type":  "tool_start",
                        "tool":  fn.name,
                        "label": label,
                        "input": fn.args,
                    })
 
            # Tool call returned a result
            if event.get_function_responses():
                for fn in event.get_function_responses():
                    result_preview = str(fn.response)[:300]
                    label = TOOL_LABELS.get(pending_tool or "", pending_tool or "")
                    logger.info(f"[AGENT] Tool result: {result_preview[:200]}")
                    yield sse({
                        "type":   "tool_done",
                        "tool":   pending_tool,
                        "label":  label,
                        "output": result_preview,
                    })
                    pending_tool = None
 
            # Agent finished
            if event.is_final_response():
                final_text = ""
                if event.content and event.content.parts:
                    final_text = "".join(
                        p.text for p in event.content.parts if hasattr(p, "text")
                    )
                logger.info(f"[AGENT] Final response length: {len(final_text)}")
                yield sse({"type": "done", "response": final_text})
 
    except Exception as e:
        logger.exception(f"[AGENT] Error | repo={repo}")
        yield sse({"type": "error", "message": str(e)})
 
@app.get("/generate-readme")
async def generate_readme(repo: str):
    """
    SSE endpoint. Streams agent progress events in real time.
    Usage: GET /generate-readme?repo=my-repo
    """
    logger.info(f"[API] /generate-readme called | repo={repo}")
    return StreamingResponse(
        stream_agent(repo),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",  # prevents Nginx/Render from buffering the stream
        },
    )

# async def run_agent_with_retry(repo, session_id, user_message):
#     last_exc = None
#     readme_pushed = False

#     for attempt in range(1, MCP_MAX_RETRIES + 1):
#         tool_calls: list[dict] = []
#         final_response = ""

#         try:
#             async for event in runner.run_async(
#                 user_id=repo+'qe',
#                 session_id=session_id,
#                 new_message=user_message,
#             ):
#                 if event.get_function_calls():
#                     for fn in event.get_function_calls():
#                         call_info = {"tool": fn.name, "input": fn.args}
#                         logger.info(f"[AGENT] Tool call: {call_info}")
#                         tool_calls.append(call_info)

#                 if event.get_function_responses():
#                     for fn in event.get_function_responses():
#                         result_text = str(fn.response)[:500]
#                         if tool_calls:
#                             tool_calls[-1]["output"] = result_text
#                         logger.info(f"[AGENT] Tool result: {result_text[:200]}")

#                         # Detect successful README push
#                         if "create_or_update_file" in str(tool_calls[-1].get("tool", "")) and \
#                            "sha" in result_text and "isError" not in result_text:
#                             readme_pushed = True
#                             logger.info("[AGENT] README successfully pushed to GitHub")

#                 if event.is_final_response():
#                     if event.content and event.content.parts:
#                         final_response = "".join(
#                             p.text for p in event.content.parts if hasattr(p, "text")
#                         )
#                     logger.info(f"[AGENT] Final response length: {len(final_response)}")

#             return tool_calls, final_response  # clean exit

#         except ConnectionError as exc:
#             last_exc = exc

#             # README was already pushed — don't retry, just return what we have
#             if readme_pushed:
#                 logger.info("[AGENT] README was pushed successfully — ignoring post-push MCP timeout")
#                 return tool_calls, final_response or "README successfully generated and pushed to GitHub."

#             wait = MCP_RETRY_DELAY * (2 ** (attempt - 1))
#             logger.warning(
#                 f"[AGENT] MCP connection dropped on attempt {attempt}/{MCP_MAX_RETRIES} "
#                 f"— retrying in {wait:.1f}s"
#             )
#             await asyncio.sleep(wait)

#         except Exception as exc:
#             logger.exception(f"[AGENT] Non-retryable error | repo={repo}")
#             raise

#     raise RuntimeError(f"Agent failed after {MCP_MAX_RETRIES} retries") from last_exc


# @app.post("/generate-readme")
# async def generate_readme(request: ChatRequest):
#     logger.info(f"[API] /generate-readme called | repo={request.repo}")

#     session = await session_service.create_session(
#         app_name=APP_NAME,
#         user_id=request.repo+'qe',
#     )

#     user_message = genai_types.Content(
#         role="user",
#         parts=[genai_types.Part(text=request.repo)],
#     )

#     try:
#         tool_calls, final_response = await run_agent_with_retry(
#             repo=request.repo,
#             session_id=session.id,
#             user_message=user_message,
#         )
#     except RuntimeError as exc:
#         raise HTTPException(status_code=503, detail=str(exc))
#     except Exception as exc:
#         raise HTTPException(status_code=500, detail=str(exc))

#     return {
#         "status": "success",
#         "repo": request.repo,
#         "tool_calls": tool_calls,
#         "response": final_response,
#     }
 
@app.get("/health")
async def health():
    return {"status": "ok"}

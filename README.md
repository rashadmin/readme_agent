# README Agent

> A FastAPI-based agent that generates comprehensive GitHub READMEs by analyzing repository code and structure.

## 🧠 Overview

This project provides a web API for an intelligent agent designed to automate the creation of detailed GitHub `README.md` files. By analyzing the codebase of a specified repository, the agent extracts semantic summaries for each file, understands the project's purpose and architecture, and then constructs a well-structured and informative README. It allows users to initiate README generation and receive real-time updates on the agent's progress via Server-Sent Events (SSE).

## 🔨 What I Built

The core of this project is a FastAPI application that serves as the interface for a README generation agent. Key functionalities include:

-   **Repository Analysis:** Utilizes a `GitExtractor` to clone and analyze GitHub repositories, generating semantic summaries for individual files.
-   **Intelligent README Generation:** An AI agent (powered by Google ADK and Gemini) synthesizes information from file summaries to create a comprehensive `README.md`.
-   **Real-time Progress Streaming:** Provides live updates on the README generation process to the client using Server-Sent Events (SSE).
-   **Modular Design:** Separates concerns into an `agent.py` for API and agent orchestration, and `git.py` for repository extraction logic.

## 💭 Thought Process

My approach focused on building a robust, AI-powered documentation tool. I decided to leverage FastAPI for the API layer due to its speed and asynchronous capabilities, which are crucial for real-time progress streaming. The choice of Google ADK and Gemini for the agent framework allowed for sophisticated code understanding and natural language generation. A significant design decision was the creation of the `GitExtractor` component. This dedicated module handles the complexities of fetching and analyzing repository files, providing structured semantic summaries to the main agent. This separation ensures that the core README generation logic receives clean, pre-processed input, making the agent more focused and effective. The use of SSE for progress updates was a deliberate choice to provide a smooth and responsive user experience, allowing users to track the status of potentially long-running generation tasks.

## 🛠️ Tools & Tech Stack

| Layer       | Technology            |
|-------------|-----------------------|
| Language    | Python 3.11+          |
| Web Framework | FastAPI               |
| AI / LLM    | Google ADK, Google GenAI (Gemini) |
| Agent       | LangChain             |
| Web Server  | Uvicorn               |
| Data Analysis | Pandas                |
| HTTP Client | Requests              |
| Environment | python-dotenv         |

## 🚀 Getting Started

### Prerequisites
-   Python 3.11 or higher
-   A Google Cloud project with the Gemini API enabled.
-   A GitHub Personal Access Token (PAT) with repository read access (if working with private repos or needing higher API limits).

### Installation

```bash
git clone https://github.com/rashadmin/readme_agent.git
cd readme_agent
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the root of the project:

```env
GEMINI_API_KEY=your_gemini_api_key_here
# Optional:
GITHUB_TOKEN=your_github_pat_here
```

### Run

```bash
uvicorn agent:app --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`.

## 📖 Usage

### Example: Generate a README for a GitHub Repository

You can interact with the API using a tool like `curl` or a Python `requests` library.
To generate a README, send a POST request to the `/generate-readme` endpoint.

```bash
curl -X POST "http://localhost:8000/generate-readme" \
     -H "Content-Type: application/json" \
     -d '{ 
           "repo_url": "https://github.com/octocat/Spoon-Knife",
           "branch": "main"
         }'
```

The API will return an SSE stream. You can consume this stream to see real-time updates:

```javascript
const eventSource = new EventSource("http://localhost:8000/generate-readme/events");

eventSource.onmessage = function(event) {
  console.log(event.data);
};

eventSource.onerror = function(err) {
  console.error("EventSource failed:", err);
  eventSource.close();
};
```
*(Note: The actual event endpoint might be tied to the generation request, this example is illustrative.)*

## 📚 Resources

-   [FastAPI Documentation](https://fastapi.tiangolo.com/) — High-performance web framework
-   [Google ADK Documentation](https://google.github.io/adk-docs/) — Agent Development Kit
-   [Google AI for Developers](https://ai.google.dev/docs) — Gemini API documentation
-   [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction) — Framework for developing applications powered by language models
-   [Uvicorn Documentation](https://www.uvicorn.org/) — ASGI server for Python
-   [Pandas Documentation](https://pandas.pydata.org/docs/) — Data analysis and manipulation library
-   [Requests Documentation](https://requests.readthedocs.io/en/latest/) — HTTP library for Python

## 📄 License

MIT © [rashadmin](https://github.com/rashadmin)

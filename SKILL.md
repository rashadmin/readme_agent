# GitHub README Formatting Guide

A reference for generating clear, technical, and user-friendly README.md files.
Output should feel written by a thoughtful developer — not generic boilerplate.

---

## Section Structure

Always follow this order. Omit a section only if the information is genuinely unavailable.

---

### 1. Header

```markdown
# Project Name

> One-line tagline describing what the project does and for whom.

![badge](optional) ![badge](optional)
```

- Tagline should be punchy and specific — not "a tool for developers"
- Add shields.io badges only if relevant (language, license, status)

---

### 2. Overview

```markdown
## 🧠 Overview

2–4 sentences. What is this project? What problem does it solve?
Who would find it useful?
```

- Lead with the "what" and "why", not the tech
- Avoid jargon in the first two sentences — make it accessible

---

### 3. What I Built

```markdown
## 🔨 What I Built

Describe the project in more depth. What are its core features?
What can it do? What makes it interesting or different?

- Feature 1
- Feature 2
- Feature 3
```

- Use bullet points for features but prose for context
- Be specific — "generates structured JSON from natural language" beats "processes input"

---

### 4. Thought Process

```markdown
## 💭 Thought Process

Walk through how you approached the problem. What decisions did you make and why?
Were there any trade-offs, pivots, or lessons learned?
```

- Write in first person — "I decided to...", "I chose X over Y because..."
- Include architecture or flow descriptions if relevant
- Highlight any interesting patterns or non-obvious design choices found in the code

---

### 5. Tools & Tech Stack

```markdown
## 🛠️ Tools & Tech Stack

| Layer      | Technology          |
|------------|---------------------|
| Language   | Python 3.11         |
| Framework  | FastAPI             |
| AI / LLM   | Gemini 2.0 Flash    |
| Database   | Supabase            |
| Deployment | Railway             |
```

- Group by layer: Language, Framework, AI/ML, Database, Auth, Deployment, etc.
- Add a brief note after the table if any tool choice needs explanation

---

### 6. Getting Started

~~~markdown
## 🚀 Getting Started

### Prerequisites
- Python >= 3.10
- A Gemini API key

### Installation

```bash
git clone https://github.com/username/project-name.git
cd project-name
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_key_here
DATABASE_URL=your_db_url
```

### Run

```bash
python main.py
```
~~~

- Use code blocks for every terminal command
- List all env vars, even if values are redacted
- Keep steps in the correct order

---

### 7. Usage Examples

~~~markdown
## 📖 Usage

### Example 1: Basic Usage

```python
from myproject import Agent

agent = Agent(api_key="...")
result = agent.run("Summarize this document")
print(result)
```

### Example 2: CLI

```bash
python main.py --input data.csv --output report.md
```
~~~

- Show at least 1–2 real, working examples inferred from the codebase
- For CLI tools: show full command with flags
- For APIs: show a request/response pair
- For AI agents: show a sample prompt and output

---

### 8. Resources & References

```markdown
## 📚 Resources

- [Google ADK Docs](https://google.github.io/adk-docs/) — Agent framework
- [Gemini API Docs](https://ai.google.dev/docs) — LLM API reference
- [FastAPI Tutorial](https://fastapi.tiangolo.com/tutorial/) — API setup
```

- Link to actual docs pages, not just homepages
- Include every framework and library detected in the codebase

---

### 9. License *(optional)*

```markdown
## 📄 License

MIT © [Your Name](https://github.com/yourusername)
```

Include only if the repo is public or open source.

---

## Writing Style Rules

- **Technical but readable** — use correct terminology, explain it when needed
- **First person for Thought Process** — neutral tone everywhere else
- **No filler phrases** — never "powerful tool" or "robust solution" — say what it does
- **One emoji per section header** — none in body text
- **Code blocks for everything** — commands, snippets, env vars — always fenced with a language tag
- **Concrete over vague** — "parses JSON from Claude's response" beats "handles output"
- **Infer, don't invent** — only include what can be supported by the code or summaries

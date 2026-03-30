# GitHub Repository Agent
### Week 7 Assignment — MCP + A2A Agentic Protocols

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        A2A MESSAGE BUS                          │
│   (All agents communicate exclusively through this bus)         │
└──────┬──────────────┬──────────────┬──────────────┬────────────┘
       │              │              │              │
  ┌────▼─────┐  ┌─────▼────┐  ┌────▼─────┐  ┌────▼──────┐
  │ REVIEWER │  │ PLANNER  │  │  WRITER  │  │GATEKEEPER │
  │          │  │          │  │          │  │           │
  │ Analyzes │  │ Decides  │  │ Drafts   │  │ Enforces  │
  │ git diff │  │ action   │  │ Issue/PR │  │ approval  │
  │ + files  │  │ + plan   │  │ content  │  │ gate      │
  └────┬─────┘  └─────┬────┘  └────┬─────┘  └────┬──────┘
       │              │              │              │
  ┌────▼──────────────▼──────────────▼──────────────▼────────────┐
  │                    MCP TOOL REGISTRY                          │
  │  git_diff │ git_log │ read_file │ list_files                  │
  │  github_get_issue │ github_get_pr                             │
  │  github_create_issue │ github_create_pr                       │
  └───────────────────────────────────────────────────────────────┘
```

## Patterns Implemented

| Pattern      | Where                                    |
|-------------|------------------------------------------|
| Planning    | `PlannerAgent` — explicit plan steps before action |
| Tool Use    | `MCPToolRegistry` — all I/O via named tools |
| Reflection  | `ReviewerAgent._reflect()` — critic step produces artifact |
| Multi-Agent | 4 separate agents: Reviewer, Planner, Writer, Gatekeeper |

## Agentic Protocols

| Protocol | Implementation |
|----------|---------------|
| **MCP**  | `mcp/tools.py` — `MCPToolRegistry` with 8 real tools |
| **A2A**  | `a2a/bus.py` — `AgentBus` routes structured messages between agents |

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Install and start Ollama
Download and install Ollama from [https://ollama.com](https://ollama.com), then pull your desired model:
```bash
ollama pull llama3
ollama serve
```

### 3. Set your Ollama model (optional)
By default the agent uses `llama3`. Override with:
```bash
export OLLAMA_MODEL=mistral
```

### 4. Create a sample test repo
```bash
python setup_sample_repo.py
```

### 5. Run the agent
```bash
python main.py
```

---

## Tasks Supported

### Task 1 — Review Changes
- Reads real `git diff` via MCP
- Categorizes change (feature/bugfix/refactor/etc.)
- Assesses risk (low/medium/high)
- Recommends: Create Issue, Create PR, or No Action
- Runs Reflection (critic) and produces a reflection artifact

### Task 2 — Draft and Create Issue or PR
- From explicit instruction: you describe what you want
- Drafts with all required fields (title, problem, evidence, acceptance criteria, risk)
- **Human approval required before anything is created on GitHub**

### Task 3 — Improve Existing Issue or PR
- Fetches real item from GitHub via MCP
- Critiques first (unclear language, missing sections, vague criteria)
- Suggests improved structured version
- Read-only — never silently changes anything

---

## Agent Roles

**Reviewer** — Uses MCP tools to read git diff and files. Sends diff to Ollama for analysis. Runs reflection/critic step. Produces `ReviewArtifact`.

**Planner** — Receives `ReviewArtifact`. Decides action. Produces structured `PlanArtifact` with explicit plan steps and rationale.

**Writer** — Receives `PlanArtifact`. Drafts Issue or PR content using Ollama. Produces `DraftArtifact`.

**Gatekeeper** — Receives `DraftArtifact`. Runs policy check. Shows full draft to user. Requires explicit approval. Only agent that calls `github_create_*` tools.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OLLAMA_MODEL` | ❌ | Ollama model to use (default: `llama3`) |
| `OLLAMA_BASE_URL` | ❌ | Ollama API base URL (default: `http://localhost:11434`) |

Your GitHub PAT is entered interactively at runtime (not stored in env).

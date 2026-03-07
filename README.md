# AI Agentic SDLC Assistant

> A production-ready multi-agent AI system that monitors Jira for tickets entering **"Ready for Dev"**, validates their completeness, scouts your GitHub repository, searches Confluence for architecture context, and autonomously generates implementation plans, code proposals, test suggestions, and a GitHub Draft PR — all for human review and approval.

---

## Table of Contents

- [How It Works](#how-it-works)
- [Agent Pipeline](#agent-pipeline)
- [Live Demo Results](#live-demo-results)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the System](#running-the-system)
- [Dashboard](#dashboard)
- [Metrics API](#metrics-api)
- [POC Success Criteria (KPIs)](#poc-success-criteria-kpis)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Security](#security)
- [Architecture Deep Dive](#architecture-deep-dive)

---

## How It Works

The system connects to your live Jira, GitHub, and Confluence via **Model Context Protocol (MCP)** — a standardised tool interface that lets AI agents call external APIs as native tools.

When a ticket enters **"Ready for Dev"** in Jira, a 9-node LangGraph workflow fires automatically:

```
Jira "Ready for Dev" ticket
         |
         v
  [1] Ticket Fetcher ---------- pulls full ticket via Jira MCP
         |
         v
  [2] Completeness Check ------ LLM scores ticket across 8 dimensions
         |
    .----+--------------------------------------------.
    | INCOMPLETE (score < 35%)                        | COMPLETE (score >= 35%)
    v                                                 v
  [3a] Post Clarification                         [3b] Repo Scout
    |   posts Jira comment                              |  GitHub MCP: reads codebase
    |   adds label                                      v
    |                                             [4] Confluence Docs
    |                                                  |  searches architecture docs
    |                                                  v
    |                                             [5] Planner
    |                                                  |  step-by-step implementation plan
    |                                                  v
    |                                             [6] Code Proposal
    |                                                  |  per-file code changes
    |                                                  v
    |                                             [7] Test Suggestion
    |                                                  |  named test cases with AAA structure
    |                                                  v
    |                                             [8] PR Composer
    |                                                  |  GitHub MCP: creates Draft PR
    '------------------.                               |
                       v                               v
                    [9] End Workflow (DB finalised, metrics updated)
```

**Incomplete path (~20 seconds):** The AI posts a specific clarification comment to the Jira ticket listing exactly what is missing, and applies a `needs-clarification` label. No developer time is wasted.

**Complete path (~3-5 minutes):** All 7 downstream agents run in sequence. A Draft PR is opened on GitHub containing an implementation plan, proposed code changes, and test suggestions. The engineer starts from a working draft, not a blank screen.

---

## Agent Pipeline

| # | Agent | What It Does | Tools Used |
|---|-------|--------------|------------|
| 1 | **Ticket Fetcher** | Fetches the full Jira ticket — title, description, acceptance criteria, metadata | Jira MCP |
| 2 | **Completeness Agent** | Scores the ticket across 8 dimensions (problem clarity, scope, testability, technical detail, etc.) and decides complete or incomplete | LLM |
| 3a | **Post Clarification** | Posts a detailed clarification comment to Jira listing what is missing; applies `needs-clarification` label | Jira MCP |
| 3b | **Repo Scout** | Reads the GitHub repo directory, identifies the most relevant files, fetches their content for downstream context | GitHub MCP + LLM |
| 4 | **Confluence Agent** | Searches Confluence for architecture docs, ADRs, and runbooks relevant to the ticket | Confluence MCP + LLM |
| 5 | **Planner** | Generates a step-by-step implementation plan with affected files, risk level, and deployment considerations | LLM |
| 6 | **Code Proposal** | Proposes specific code changes per file, with rationale and confidence score | LLM |
| 7 | **Test Agent** | Suggests named test cases in arrange/act/assert format, covering happy paths and edge cases | LLM |
| 8 | **PR Composer** | Assembles all outputs into a structured GitHub Draft PR with an AI disclaimer requiring human review | GitHub MCP |

---

## Live Demo Results

| Ticket | Description | Result | Duration |
|--------|-------------|--------|----------|
| SCRUM-1 | "chatbot testing" — vague, no acceptance criteria | Flagged incomplete (20%), clarification comment posted to Jira | ~25 sec |
| SCRUM-4 | "Add rate limiting to /api/users endpoint" — full AC + technical detail | 100% completeness, Draft PR created with plan, code, and tests | ~3.5 min |

**Draft PR output for SCRUM-4:**
- Implementation plan: 6 steps with affected files and risk assessment
- Code changes: 5 files with proposed implementations
- Test suggestions: 5 named test cases in AAA format
- Confluence references and doc update suggestions
- AI confidence scores: Plan 85%, Code 90%, Tests 90%

**Current KPI status:**

| KPI | Target | Current |
|-----|--------|---------|
| PR Approval Rate | >= 33% | 100% (1/1 resolved) |
| Incomplete Detection | >= 50% | 100% (ground-truth validated) |
| Consecutive Error-Free Runs | >= 10 | Building toward target |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Agent Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) StateGraph with conditional routing |
| **LLM (primary)** | OpenAI GPT-4o-mini via `langchain-openai` |
| **LLM (alternative)** | AWS Bedrock Claude 3.5 Sonnet via `langchain-aws` |
| **Tool Integration** | [Model Context Protocol (MCP)](https://modelcontextprotocol.io) via stdio transport |
| **Jira + Confluence** | `mcp-atlassian` Python subprocess — 74 tools |
| **GitHub** | `@modelcontextprotocol/server-github` Node.js subprocess — 24 tools |
| **MCP Adapter** | `langchain-mcp-adapters` bridges MCP tools into LangChain format |
| **Persistence** | SQLite via SQLAlchemy (schema upgradeable to PostgreSQL) |
| **Scheduler** | APScheduler with IntervalTrigger |
| **Dashboard** | Streamlit on port 8501 |
| **Metrics API** | FastAPI + Uvicorn on port 8080 |
| **Retry Logic** | Tenacity — 3 attempts with exponential backoff on LLM and MCP failures |
| **PII Protection** | Regex sanitiser strips emails, phone numbers, and API tokens before LLM calls |
| **Logging** | Structured JSON Lines (JSONL) — queryable audit trail for every event |

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.12+ | |
| Node.js | 20+ | Required for `@modelcontextprotocol/server-github` |
| `uv` | Latest | Required for `uvx mcp-atlassian` |
| OpenAI account | — | API key with GPT-4o-mini access |
| AWS account | — | Optional — only needed if using Bedrock instead of OpenAI |
| Jira Cloud | — | API token with project read/write access |
| GitHub | — | Personal Access Token with `repo` scope |
| Confluence | — | Same Atlassian API token works for both Jira and Confluence |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Loki1920/agentic_sdlc_assistant.git
cd agentic_sdlc_assistant
```

### 2. Create Python virtual environment

```bash
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Install MCP servers

```bash
# GitHub MCP server (Node.js)
npm install -g @modelcontextprotocol/server-github

# Atlassian MCP server (installs via uv on first run)
pip install uv
uvx mcp-atlassian --help      # confirms installation
```

### 5. Configure environment

```bash
cp .env.example .env
# Open .env and fill in all required values — see Configuration section below
```

---

## Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and fill in the values.

### LLM Provider

```env
# Options: openai (default) or bedrock
LLM_PROVIDER=openai
```

### OpenAI (default)

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL_ID=gpt-4o-mini
OPENAI_MAX_TOKENS=8000
OPENAI_TEMPERATURE=0.1
```

### AWS Bedrock (alternative)

```env
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
BEDROCK_MODEL_ID=us.anthropic.claude-3-5-sonnet-20241022-v2:0
```

### Jira

```env
JIRA_URL=https://yourorg.atlassian.net
JIRA_USERNAME=you@company.com
JIRA_API_TOKEN=your_jira_api_token
JIRA_PROJECTS_FILTER=PROJ                    # comma-separated project keys
JIRA_POLL_JQL=project in (PROJ) AND status = "Ready for Dev" ORDER BY created DESC
JIRA_POLL_INTERVAL_SECONDS=300               # 5 minutes
```

### Confluence

```env
CONFLUENCE_URL=https://yourorg.atlassian.net/wiki
CONFLUENCE_SPACE_KEYS=ENGINEERING
CONFLUENCE_MAX_PAGES=10
```

### GitHub

```env
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_...
GITHUB_REPO_OWNER=your-org-or-username
GITHUB_REPO_NAME=your-repo
GITHUB_BASE_BRANCH=main
GITHUB_DEFAULT_REVIEWERS=alice,bob           # comma-separated
```

### Agent Behaviour

```env
REPO_SCOUT_MAX_FILES=20                      # max files the scout reads in full
COMPLETENESS_THRESHOLD=0.35                  # score below which a ticket is flagged
LLM_PARSE_RETRY_COUNT=3                      # retries on structured output parse failure
```

### Metrics API

```env
METRICS_PORT=8080
METRICS_API_KEY=your-secret-key             # protects approve/reject endpoints
PR_RECONCILE_INTERVAL_SECONDS=3600          # hourly GitHub PR status sync
```

### Safety

```env
DRY_RUN=false    # set true to skip Jira comments and GitHub PR creation
```

---

## Running the System

### Single ticket (testing and demos)

```bash
# Full live run
python main.py --mode single --ticket PROJ-123

# Dry run — no Jira comments, no GitHub PRs
python main.py --mode single --ticket PROJ-123 --dry-run
```

Sample output:

```
============================================================
  Ticket: PROJ-123
  Phase:  WorkflowPhase.COMPLETED
  Completeness: 100% (complete)
  PR:     https://github.com/your-org/your-repo/pull/42
============================================================
```

### Scheduler (production)

```bash
python main.py --mode scheduler
```

Polls Jira every `JIRA_POLL_INTERVAL_SECONDS` seconds and processes every new "Ready for Dev" ticket automatically. Runs an hourly PR reconciliation job. Stop with `Ctrl+C`.

### KPI metrics

```bash
python main.py --mode metrics
```

### Metrics API server

```bash
python main.py --mode metrics-server
# Listening at http://0.0.0.0:8080
```

### Reprocess a ticket

```bash
python -c "
from persistence.repository import TicketRepository
TicketRepository().request_reprocess('PROJ-123')
print('Reset — ready to reprocess')
"
```

---

## Dashboard

```bash
streamlit run dashboard.py
# Opens at http://localhost:8501
```

**Workflow Runs tab** — Every ticket run: status, completeness score, PR link, duration, token usage. Filter by status or date.

**LLM Call Log tab** — Every LLM invocation: agent, model, tokens, latency, parse success. Cost and compliance audit trail.

**PR Actions tab** — Approve or reject AI-generated PRs to feed KPI 1. Buttons call the metrics API directly.

KPI pass/fail badges update live as data changes.

---

## Metrics API

Interactive Swagger UI: **http://localhost:8080/docs**

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | None | `{"status":"ok"}` liveness check |
| `/metrics` | GET | None | Full KPI payload as JSON |
| `/pr/{run_id}/approve` | POST | `X-Api-Key` | Record a PR as approved |
| `/pr/{run_id}/reject` | POST | `X-Api-Key` | Record a PR as rejected |

```bash
curl http://localhost:8080/health
curl http://localhost:8080/metrics | python -m json.tool
curl -X POST http://localhost:8080/pr/<run_id>/approve -H "X-Api-Key: your-key"
```

Compatible with Grafana, Datadog, or any tool that polls a REST endpoint.

---

## POC Success Criteria (KPIs)

### KPI 1 — PR Approval Rate (target: >= 33%)

Tracks whether engineers approve the AI-generated Draft PRs. Record outcomes via the dashboard or API. PR status is also auto-synced from GitHub hourly.

### KPI 2 — Incomplete Ticket Detection Rate (target: >= 50%)

Tracks accuracy of the completeness check against human ground-truth labels.

```bash
# Label a ticket as truly incomplete
python -m metrics.label_ticket PROJ-123 --truly-incomplete --labeled-by "alice"

# Label as complete
python -m metrics.label_ticket PROJ-123 --complete --labeled-by "alice"
```

### KPI 3 — Consecutive Error-Free Runs (target: >= 10)

Counts clean end-to-end runs without unhandled exceptions. Tracked automatically.

All three KPIs are visible in real time at `python main.py --mode metrics` and `http://localhost:8080/metrics`.

---

## Project Structure

```
agentic_sdlc_assistant/
|
+-- main.py                        CLI entry point
+-- dashboard.py                   Streamlit dashboard (port 8501)
+-- requirements.txt
+-- .env.example                   Config template
+-- Dockerfile
+-- docker-compose.yml
|
+-- agents/
|   +-- base_agent.py              Abstract base class for all agents
|   +-- supervisor.py              LangGraph graph definition + run_workflow()
|   +-- ticket_fetcher.py          Agent 1 — Jira ticket fetch
|   +-- completeness_agent.py      Agent 2 — completeness scoring + Agent 3a clarification
|   +-- repo_scout_agent.py        Agent 3b — GitHub repo analysis
|   +-- confluence_agent.py        Agent 4 — Confluence documentation search
|   +-- planner_agent.py           Agent 5 — implementation plan generation
|   +-- code_proposal_agent.py     Agent 6 — code change proposals
|   +-- test_agent.py              Agent 7 — test case suggestions
|   +-- pr_composer_agent.py       Agent 8 — GitHub Draft PR creation
|
+-- schemas/
|   +-- workflow_state.py          WorkflowState TypedDict + WorkflowPhase enum
|   +-- completeness.py            CompletenessResult, CompletenessDecision
|   +-- plan.py                    ImplementationPlan, ImplementationStep
|   +-- code_proposal.py           CodeProposal, FileDiff
|   +-- test_suggestion.py         TestSuggestions, TestCase
|   +-- pr.py                      PRCompositionResult, PRStatus
|   +-- repo.py                    RepoContext, FileInfo
|   +-- confluence.py              ConfluenceContext, ConfluencePage
|   +-- ticket.py                  JiraTicket
|
+-- config/
|   +-- settings.py                Pydantic-settings, SecretStr for all tokens
|   +-- logging_config.py          Structlog configuration
|
+-- mcp_client/
|   +-- client_factory.py          get_mcp_client() async context manager
|
+-- llm/
|   +-- bedrock_client.py          get_llm() — returns ChatOpenAI or ChatBedrock
|   +-- llm_logger.py              invoke_and_log() — records every LLM call
|
+-- persistence/
|   +-- database.py                SQLAlchemy engine + get_db_session()
|   +-- models.py                  TicketRun, LLMCallLog, ProcessedTicket, TicketGroundTruth
|   +-- repository.py              TicketRepository — finalize_run(), set_pr_outcome()
|
+-- scheduler/
|   +-- poller.py                  APScheduler Jira polling loop
|   +-- pr_reconciler.py           Hourly GitHub PR status reconciliation
|
+-- metrics/
|   +-- poc_metrics.py             POCMetricsCollector — KPI computation
|   +-- server.py                  FastAPI metrics REST API (port 8080)
|   +-- label_ticket.py            CLI for human ground-truth labelling
|
+-- prompts/                       LLM prompt templates (one file per agent)
|
+-- utils/
|   +-- retry.py                   Tenacity wrappers for LLM and MCP calls
|   +-- sanitizer.py               PII redaction before LLM calls
|   +-- mcp_helpers.py             find_tool(), unwrap_tool_result()
|   +-- text_helpers.py            Text utilities
|
+-- app_logging/
|   +-- activity_logger.py         Structured JSONL event logger
|
+-- tests/
    +-- conftest.py                Shared fixtures (fresh_db, etc.)
    +-- unit/                      17 unit tests — no credentials required
    +-- integration/               2 integration tests — require valid .env
```

---

## Testing

### Unit tests (no credentials required)

All 17 unit tests mock LLM, MCP, and database. Run fully offline.

```bash
pytest tests/unit/ -v
```

### Integration tests (require valid .env)

```bash
pytest tests/integration/ -v -s
```

### End-to-end test against a real ticket

```bash
TEST_JIRA_TICKET_ID=PROJ-123 pytest tests/integration/test_workflow_e2e.py -v -s
```

### Coverage

```bash
pytest tests/unit/ --cov=. --cov-report=html
open htmlcov/index.html
```

---

## Security

**Secrets as SecretStr** — All tokens and API keys (`JIRA_API_TOKEN`, `GITHUB_PERSONAL_ACCESS_TOKEN`, `OPENAI_API_KEY`, `AWS_SECRET_ACCESS_KEY`) are stored as Pydantic `SecretStr`. They are never logged, printed, or serialised. Only accessed via `.get_secret_value()` at the point of use. The `.env` file is in `.gitignore`.

**PII sanitisation** — `utils/sanitizer.py` redacts email addresses, phone numbers, and API token patterns from all ticket content before it is sent to any LLM.

**Protected endpoints** — The metrics API approve/reject endpoints require an `X-Api-Key` header matching `METRICS_API_KEY`. Unauthenticated requests return HTTP 401.

**No auto-merge** — Every GitHub PR is created as a **Draft PR**. GitHub prevents Draft PRs from being merged until a human manually converts it and obtains a review approval. The AI system cannot merge code under any circumstances.

**Error isolation** — LLM and MCP calls use Tenacity retry decorators. On exhausted retries the run is marked `FAILED` in the database — no partial or corrupted state is written.

---

## Architecture Deep Dive

### LangGraph StateGraph

The workflow graph is built in `agents/supervisor.py`. All state flows through `WorkflowState`, a TypedDict that accumulates results from each agent. A single conditional edge decides the complete/incomplete branch:

```python
def route_after_completeness(state) -> Literal["repo_scout", "post_clarification"]:
    if state.get("should_stop") or not state.get("is_complete_ticket"):
        return "post_clarification"
    return "repo_scout"
```

### MCP Integration

Two MCP server subprocesses are started per run:

| Server | Startup Command | Tools |
|--------|----------------|-------|
| `mcp-atlassian` | `uvx mcp-atlassian` | 74 Jira + Confluence tools |
| `server-github` | `npx @modelcontextprotocol/server-github` | 24 GitHub tools |

`langchain-mcp-adapters` wraps these into LangChain-compatible tools with `.ainvoke()`. `get_mcp_client()` is an async context manager that manages subprocess lifecycle.

### LLM Provider Switching

`get_llm()` in `llm/bedrock_client.py` reads `LLM_PROVIDER` from settings and returns either `ChatOpenAI` or `ChatBedrock`. All agents call `self.invoke_llm_structured(prompt, schema)` inherited from `BaseAgent`. Switching providers is a one-line `.env` change.

### Structured Outputs

Every LLM call uses `.with_structured_output(PydanticSchema)` to enforce typed responses. Failed parses trigger up to `LLM_PARSE_RETRY_COUNT` retries. All outcomes are logged to `llm_call_logs` in the database.

### Database Schema

| Table | Purpose |
|-------|---------|
| `ticket_runs` | One row per processing attempt — primary KPI source of truth |
| `llm_call_logs` | One row per LLM call (FK to `ticket_runs`) |
| `processed_tickets` | Deduplication — prevents re-processing the same ticket |
| `ticket_ground_truth` | Human labels used for KPI 2 accuracy computation |

---

## Docker Compose

```bash
cp .env.example .env
docker compose up --build -d
docker compose logs -f sdlc_assistant
curl http://localhost:8080/metrics | python -m json.tool
docker compose down
```

---

## Logging

Logs are written as JSON Lines to two files:

| File | Content |
|------|---------|
| `logs/activity.jsonl` | Workflow events, agent lifecycle, MCP calls, errors |
| `logs/llm_calls.jsonl` | Every LLM call with model, tokens, latency, and parse result |

```bash
# Stream live (Windows PowerShell)
Get-Content logs\activity.jsonl -Wait | ForEach-Object { $_ | python -m json.tool }

# Filter errors
Select-String '"level": "ERROR"' logs\activity.jsonl

# Linux / macOS
tail -f logs/activity.jsonl | python -m json.tool
grep '"level": "ERROR"' logs/activity.jsonl
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

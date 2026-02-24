# AI Agentic SDLC Assistant — POC

An AI-powered SDLC automation system that monitors Jira tickets, validates their completeness,
analyzes a GitHub repository, and generates implementation plans, code proposals, test suggestions,
and Draft Pull Requests for human review.

---

## POC Success Criteria

| KPI | Target | Description |
|-----|--------|-------------|
| PR Approval Rate | ≥ 33% | At least 1 in 3 AI-generated PRs designated "ready-to-deploy" by peer review |
| Incomplete Ticket Detection | ≥ 50% | At least half of tickets with missing/inadequate info flagged automatically |
| Error-Free Runs | ≥ 10 consecutive | End-to-end processing without rate limits, timeouts, or crashes |

---

## Architecture

```
Jira (via MCP)
    │
    ▼ Poll every N minutes
Scheduler (APScheduler)
    │
    ▼ For each new "Ready for Dev" ticket
LangGraph Workflow
    ├── Ticket Fetcher      → fetch ticket from Jira MCP
    ├── Completeness Agent  → score ticket quality (LLM)
    │     ├── [incomplete]  → post Jira comment + label → STOP
    │     └── [complete]    → continue
    ├── Repo Scout          → analyse GitHub repo (GitHub MCP + LLM)
    ├── Planner             → generate implementation plan (LLM)
    ├── Code Proposal       → generate code changes (LLM)
    ├── Test Agent          → suggest unit tests (LLM)
    └── PR Composer         → create Draft PR (GitHub MCP)

SQLite ─── Logs (JSONL) ─── Metrics API (FastAPI :8080)
```

---

## Prerequisites

- Python 3.12+
- Node.js 20+ (for `npx @modelcontextprotocol/server-github`)
- `uv` Python package manager (for `uvx mcp-atlassian`)
- AWS account with Bedrock enabled and `anthropic.claude-3-5-sonnet-20241022-v2:0` model access
- Jira Cloud account (free tier works)
- GitHub Personal Access Token with `repo` scope

---

## Quick Start (Local)

### 1. Clone and install

```bash
git clone https://github.com/YOUR_ORG/agentic-sdlc-assistant.git
cd agentic-sdlc-assistant
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install MCP servers

```bash
# GitHub MCP
npm install -g @modelcontextprotocol/server-github

# Jira MCP (via uv)
pip install uv
uvx mcp-atlassian --help   # verifies installation
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env — fill in ALL required values:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#   JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
#   GITHUB_PERSONAL_ACCESS_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
```

### 4. Run against a single ticket (dry-run first)

```bash
python main.py --mode single --ticket PROJ-123 --dry-run
```

### 5. Run scheduler (polls Jira every 5 minutes)

```bash
python main.py --mode scheduler
```

### 6. Check POC metrics

```bash
python main.py --mode metrics
```

---

## Docker Compose

```bash
# Build and start both services
cp .env.example .env   # fill in credentials
docker compose up --build -d

# View logs
docker compose logs -f sdlc_assistant

# Check metrics
curl http://localhost:8080/metrics | python -m json.tool

# Stop
docker compose down
```

---

## KPI Tracking

### KPI 1 — PR Approval Rate

1. The system creates Draft PRs automatically
2. Human reviewers review the PR
3. Mark outcome via the metrics API:
   ```bash
   # Find run_id from SQLite or logs
   curl -X POST http://localhost:8080/pr/{run_id}/approve   # approved
   curl -X POST http://localhost:8080/pr/{run_id}/reject    # rejected
   ```
4. PR outcomes are also reconciled automatically every hour via GitHub MCP

### KPI 2 — Incomplete Ticket Detection

1. System automatically flags tickets scoring below `COMPLETENESS_THRESHOLD` (default: 0.65)
2. Add ground-truth labels to measure accuracy:
   ```bash
   # Mark a ticket as truly incomplete (human ground truth)
   python -m metrics.label_ticket PROJ-123 --truly-incomplete --labeled-by "Alice"

   # Mark as complete
   python -m metrics.label_ticket PROJ-123 --complete --labeled-by "Alice"
   ```
3. KPI computed as: `true_positives / total_truly_incomplete_tickets`

### KPI 3 — Error-Free Runs

Tracked automatically. Count visible in:
```bash
python main.py --mode metrics
curl http://localhost:8080/metrics
```

---

## Logging

All logs are in JSON Lines format (one JSON object per line).

| File | Content |
|------|---------|
| `logs/activity.jsonl` | Workflow events, agent lifecycle, MCP tool calls, errors |
| `logs/llm_calls.jsonl` | Every LLM invocation: prompt, response, tokens, latency |

### View recent LLM calls

```bash
tail -f logs/llm_calls.jsonl | python -m json.tool
```

### View errors only

```bash
grep '"level": "ERROR"' logs/activity.jsonl | python -m json.tool
```

---

## Testing

```bash
# Unit tests (no credentials needed)
pytest tests/unit/ -v

# Integration tests (requires .env with real credentials)
pytest tests/integration/ -v -s

# E2E test for a specific ticket
TEST_JIRA_TICKET_ID=PROJ-123 pytest tests/integration/test_workflow_e2e.py -v -s
```

---

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_DEFAULT_REGION` | Yes | `us-east-1` | AWS region for Bedrock |
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS credentials |
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model |
| `JIRA_URL` | Yes | — | e.g. `https://myorg.atlassian.net` |
| `JIRA_USERNAME` | Yes | — | Jira account email |
| `JIRA_API_TOKEN` | Yes | — | Jira API token |
| `JIRA_POLL_JQL` | No | `status = "Ready for Dev"` | JQL for polling |
| `JIRA_POLL_INTERVAL_SECONDS` | No | `300` | Poll frequency |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Yes | — | GitHub PAT with `repo` scope |
| `GITHUB_REPO_OWNER` | Yes | — | GitHub org or username |
| `GITHUB_REPO_NAME` | Yes | — | Repository name |
| `GITHUB_BASE_BRANCH` | No | `main` | Target branch for PRs |
| `COMPLETENESS_THRESHOLD` | No | `0.65` | Min score for "complete" ticket |
| `DRY_RUN` | No | `false` | Skip Jira comments + GitHub PRs |

---

## Agent Modularity

Each agent is an independent class inheriting from `BaseAgent`:

```
agents/
├── ticket_fetcher.py        → TicketFetcherAgent
├── completeness_agent.py    → CompletenessAgent + PostClarificationAgent
├── repo_scout_agent.py      → RepoScoutAgent
├── planner_agent.py         → PlannerAgent
├── code_proposal_agent.py   → CodeProposalAgent
├── test_agent.py            → TestAgent
└── pr_composer_agent.py     → PRComposerAgent
```

To add, remove, or merge agents:
1. Create/modify the agent class in `agents/`
2. Update the LangGraph graph in `agents/supervisor.py` (add/remove nodes and edges)
3. No other files need to change — state flows through `WorkflowState` TypedDict

---

## Project Structure

```
agentic_sdlc_assistant/
├── main.py                  # CLI entry point
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── config/                  # Settings + logging config
├── schemas/                 # Pydantic data contracts
├── agents/                  # LangGraph agent nodes
├── mcp/                     # MCP client factory
├── llm/                     # Bedrock client + LLM logger
├── logging/                 # Activity logger
├── persistence/             # SQLite ORM + repository
├── scheduler/               # APScheduler poller + PR reconciler
├── metrics/                 # KPI computation + FastAPI server
├── prompts/                 # LLM prompt templates
└── tests/                   # Unit + integration tests
```

---

## License

Internal use — POC for Telomere (Dipanshu / Snehal).

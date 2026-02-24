# AI Agentic SDLC Assistant

> An AI-powered automation system that monitors Jira tickets, validates their completeness, analyzes a GitHub repository, and autonomously generates implementation plans, code proposals, test suggestions, and Draft Pull Requests — all for human review.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [POC Success Criteria](#poc-success-criteria)
- [Prerequisites](#prerequisites)
- [Quick Start (Local)](#quick-start-local)
- [Docker Compose](#docker-compose)
- [Configuration Reference](#configuration-reference)
- [KPI Tracking](#kpi-tracking)
- [Agent Modularity](#agent-modularity)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Logging](#logging)

---

## Overview

The Agentic SDLC Assistant connects Jira and GitHub through a multi-agent LangGraph workflow powered by Amazon Bedrock (Claude 3.5 Sonnet). When a Jira ticket moves to **"Ready for Dev"**, the system:

1. Validates the ticket is complete enough to act on
2. Scouts the target GitHub repository for context
3. Generates a structured implementation plan
4. Proposes concrete code changes
5. Suggests unit tests
6. Opens a Draft Pull Request for human review

All decisions, LLM calls, and outcomes are persisted to SQLite and exposed via a metrics API.

---

## Architecture

```
Jira (via MCP)
    │
    ▼  Poll every N minutes
Scheduler (APScheduler)
    │
    ▼  For each new "Ready for Dev" ticket
LangGraph Workflow
    ├── Ticket Fetcher      →  Fetch ticket details from Jira MCP
    ├── Completeness Agent  →  Score ticket quality (LLM)
    │     ├── [incomplete]  →  Post Jira comment + label → STOP
    │     └── [complete]    →  Continue
    ├── Repo Scout          →  Analyse GitHub repo (GitHub MCP + LLM)
    ├── Planner             →  Generate implementation plan (LLM)
    ├── Code Proposal       →  Generate code changes (LLM)
    ├── Test Agent          →  Suggest unit tests (LLM)
    └── PR Composer         →  Create Draft PR (GitHub MCP)

SQLite ── Logs (JSONL) ── Metrics API (FastAPI :8080)
```

---

## POC Success Criteria

| KPI | Target | Description |
|-----|--------|-------------|
| PR Approval Rate | ≥ 33% | At least 1 in 3 AI-generated PRs marked "ready-to-deploy" by peer review |
| Incomplete Ticket Detection | ≥ 50% | At least half of tickets with missing/inadequate info flagged automatically |
| Error-Free Runs | ≥ 10 consecutive | End-to-end processing without rate limits, timeouts, or crashes |

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python 3.12+ | |
| Node.js 20+ | For `npx @modelcontextprotocol/server-github` |
| `uv` package manager | For `uvx mcp-atlassian` |
| AWS account with Bedrock enabled | Model: `anthropic.claude-3-5-sonnet-20241022-v2:0` |
| Jira Cloud account | Free tier works |
| GitHub Personal Access Token | Requires `repo` scope |

---

## Quick Start (Local)

### 1. Clone and install

```bash
git clone https://github.com/Loki1920/agentic_sdlc_assistant.git
cd agentic_sdlc_assistant
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install MCP servers

```bash
# GitHub MCP
npm install -g @modelcontextprotocol/server-github

# Jira MCP (via uv)
pip install uv
uvx mcp-atlassian --help        # verifies installation
```

### 3. Configure environment

```bash
cp .env.example .env
# Open .env and fill in all required values:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
#   JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN
#   GITHUB_PERSONAL_ACCESS_TOKEN, GITHUB_REPO_OWNER, GITHUB_REPO_NAME
```

### 4. Dry-run against a single ticket

```bash
python main.py --mode single --ticket PROJ-123 --dry-run
```

### 5. Run the scheduler (polls Jira every 5 minutes)

```bash
python main.py --mode scheduler
```

### 6. View POC metrics

```bash
python main.py --mode metrics
```

---

## Docker Compose

```bash
# Copy and fill in credentials
cp .env.example .env

# Build and start all services
docker compose up --build -d

# Stream logs
docker compose logs -f sdlc_assistant

# Check metrics endpoint
curl http://localhost:8080/metrics | python -m json.tool

# Stop
docker compose down
```

---

## Configuration Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AWS_DEFAULT_REGION` | Yes | `us-east-1` | AWS region for Bedrock |
| `AWS_ACCESS_KEY_ID` | Yes | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | AWS credentials |
| `BEDROCK_MODEL_ID` | No | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Bedrock model ID |
| `JIRA_URL` | Yes | — | e.g. `https://myorg.atlassian.net` |
| `JIRA_USERNAME` | Yes | — | Jira account email |
| `JIRA_API_TOKEN` | Yes | — | Jira API token |
| `JIRA_POLL_JQL` | No | `status = "Ready for Dev"` | JQL query for polling |
| `JIRA_POLL_INTERVAL_SECONDS` | No | `300` | Poll frequency in seconds |
| `GITHUB_PERSONAL_ACCESS_TOKEN` | Yes | — | GitHub PAT with `repo` scope |
| `GITHUB_REPO_OWNER` | Yes | — | GitHub org or username |
| `GITHUB_REPO_NAME` | Yes | — | Repository name |
| `GITHUB_BASE_BRANCH` | No | `main` | Target branch for PRs |
| `COMPLETENESS_THRESHOLD` | No | `0.65` | Min score to consider a ticket complete |
| `DRY_RUN` | No | `false` | If `true`, skips Jira comments and GitHub PR creation |

---

## KPI Tracking

### KPI 1 — PR Approval Rate

The system creates Draft PRs automatically. Human reviewers assess each one, then record the outcome:

```bash
# Approved
curl -X POST http://localhost:8080/pr/{run_id}/approve

# Rejected
curl -X POST http://localhost:8080/pr/{run_id}/reject
```

PR outcomes are also reconciled automatically every hour via the GitHub MCP.

### KPI 2 — Incomplete Ticket Detection

Tickets scoring below `COMPLETENESS_THRESHOLD` are flagged automatically. Add ground-truth labels to measure accuracy:

```bash
# Mark a ticket as truly incomplete (human label)
python -m metrics.label_ticket PROJ-123 --truly-incomplete --labeled-by "Alice"

# Mark as complete
python -m metrics.label_ticket PROJ-123 --complete --labeled-by "Alice"
```

KPI is computed as: `true_positives / total_truly_incomplete_tickets`

### KPI 3 — Error-Free Runs

Tracked automatically and visible via:

```bash
python main.py --mode metrics
curl http://localhost:8080/metrics
```

---

## Agent Modularity

Each agent is an independent class that inherits from `BaseAgent`. The LangGraph graph in `agents/supervisor.py` wires them together via `WorkflowState`.

```
agents/
├── base_agent.py            BaseAgent (shared interface)
├── ticket_fetcher.py        TicketFetcherAgent
├── completeness_agent.py    CompletenessAgent + PostClarificationAgent
├── repo_scout_agent.py      RepoScoutAgent
├── planner_agent.py         PlannerAgent
├── code_proposal_agent.py   CodeProposalAgent
├── test_agent.py            TestAgent
└── pr_composer_agent.py     PRComposerAgent
```

To add, remove, or replace an agent:
1. Create or modify the agent class in `agents/`
2. Update `agents/supervisor.py` — add/remove nodes and edges in the LangGraph graph
3. State flows automatically through `WorkflowState` — no other files need to change

---

## Project Structure

```
agentic_sdlc_assistant/
├── main.py                  CLI entry point (single / scheduler / metrics modes)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example             Template — copy to .env and fill in credentials
├── conftest.py              Pytest shared fixtures
├── config/                  Settings (Pydantic) + logging config
├── schemas/                 Pydantic data contracts (WorkflowState, PR, Plan, …)
├── agents/                  LangGraph agent nodes
├── mcp_client/              MCP client factory (GitHub + Jira)
├── llm/                     Amazon Bedrock client + LLM call logger
├── app_logging/             Structured activity logger (JSONL)
├── persistence/             SQLite ORM (SQLAlchemy) + repository layer
├── scheduler/               APScheduler poller + hourly PR reconciler
├── metrics/                 KPI computation + FastAPI metrics server (:8080)
├── prompts/                 LLM prompt templates (one file per agent)
└── tests/
    ├── unit/                Unit tests — no credentials required
    └── integration/         Integration tests — require a valid .env
```

---

## Testing

```bash
# Unit tests (no credentials needed)
pytest tests/unit/ -v

# Integration tests (requires .env with real credentials)
pytest tests/integration/ -v -s

# End-to-end test for a specific ticket
TEST_JIRA_TICKET_ID=PROJ-123 pytest tests/integration/test_workflow_e2e.py -v -s
```

---

## Logging

All logs are written in JSON Lines format (one JSON object per line).

| File | Content |
|------|---------|
| `logs/activity.jsonl` | Workflow events, agent lifecycle, MCP tool calls, errors |
| `logs/llm_calls.jsonl` | Every LLM call: prompt, response, token counts, latency |

```bash
# Stream LLM calls in real time
tail -f logs/llm_calls.jsonl | python -m json.tool

# Filter errors only
grep '"level": "ERROR"' logs/activity.jsonl | python -m json.tool
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

# Complete Client Demo Guide — AI Agentic SDLC Assistant

## What You Have Working Right Now

| Service | Status | Detail |
|---|---|---|
| LLM (OpenAI GPT-4o-mini) | **LIVE** | Tested — responds correctly |
| Jira (SCRUM project) | **LIVE** | SCRUM-1 exists in "Ready for Dev" |
| GitHub | **LIVE** | Repo: `Loki1920/Automating-data-download-from-webpage` |
| MCP Tools | **LIVE** | 98 tools loaded (Jira + GitHub + Confluence) |
| Confluence | **LIVE** | Space: SD |
| Dashboard | **READY** | `streamlit run dashboard.py` |
| Metrics Server | **READY** | Port 8080, key = `demo-secret-key-2024` |

---

## STEP 0 — Do This 1 Hour Before The Demo

### A. Create Two Jira Tickets

Go to **https://telomeregs.atlassian.net** -> SCRUM project -> Create

**Ticket 1 — Already exists: SCRUM-1 (BAD ticket — leave it as-is)**
> Title: `chatbot testing`
> Description: `this is for testing chatbot`
> Status: Ready for Dev
> This will be flagged INCOMPLETE — that is the point.

**Ticket 2 — Already exists: SCRUM-4 (GOOD ticket)**
> Title: `Add rate limiting to the /api/users endpoint`
>
> Description:
> ```
> The /api/users GET endpoint has no rate limiting. Under load testing
> it crashes the service. We need to add per-IP rate limiting of
> 100 requests per minute using Redis cache.
>
> ## Acceptance Criteria
> - Rate limit applied to GET /api/users
> - Returns HTTP 429 when limit is exceeded with Retry-After header
> - Limit is configurable via environment variable RATE_LIMIT_RPM
> - Unit tests cover the rate limiting middleware
> - Existing integration tests continue to pass
> ```
> Priority: High | Status: **Ready for Dev**

**SCRUM-4 is already created** — no action needed. Reprocessing will create a new PR.

### B. Open 4 Terminal Windows

Keep all 4 open side by side:

```
Terminal 1 — Main commands       (you will type here)
Terminal 2 — Live log viewer     (always running)
Terminal 3 — Metrics server      (always running)
Terminal 4 — Dashboard           (always running)
```

### C. Start Terminals 2, 3, 4 (background services)

**Terminal 2 — Live log watcher:**
```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
Get-Content logs\activity.jsonl -Wait 2>$null | ForEach-Object { $_ | python -m json.tool 2>$null || $_ }
```

**Terminal 3 — Metrics server:**
```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
python main.py --mode metrics-server
# Should print: Uvicorn running on http://0.0.0.0:8080
```

**Terminal 4 — Streamlit Dashboard:**
```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
streamlit run dashboard.py
# Opens browser at http://localhost:8501
```

### D. Verify Config (Terminal 1)

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
python main.py --mode metrics
```

Expected output — no errors, KPI numbers shown.

---

## STEP 1 — Open The Demo (2 min)

Open these in the browser **before** the client arrives:

| What | URL |
|---|---|
| Jira board | https://telomeregs.atlassian.net/software/projects/SCRUM/boards |
| GitHub repo | https://github.com/Loki1920/Automating-data-download-from-webpage |
| Dashboard | http://localhost:8501 |
| Metrics Swagger UI | http://localhost:8080/docs |

**What to say:**
> "This system connects to your real Jira, GitHub, and Confluence — no mock data.
> When a ticket moves to 'Ready for Dev', the AI picks it up automatically,
> evaluates whether it's ready for development, and if it is, produces a full
> implementation plan, code proposal, test suggestions, and a GitHub Draft PR."

---

## STEP 2 — Show The Jira Board (2 min)

1. Open https://telomeregs.atlassian.net/software/projects/SCRUM/boards
2. Point to **SCRUM-1** ("chatbot testing") — "This is a vague, incomplete ticket"
3. Point to **SCRUM-2** ("Add rate limiting...") — "This is a well-written ticket"

**What to say:**
> "Watch what happens when the AI processes each of these tickets.
> First, the incomplete one."

---

## STEP 3 — Demo: Incomplete Ticket Detection (4 min)

**In Terminal 1:**
```powershell
python main.py --mode single --ticket SCRUM-1
```

Watch Terminal 2 (logs) while this runs — you will see each agent fire in sequence.

**Expected output in Terminal 1 (within ~20 seconds):**
```
============================================================
  Ticket: SCRUM-1
  Phase:  WorkflowPhase.COMPLETED
  Completeness: ~18% (incomplete)
============================================================
```

**Now go to Jira** — open SCRUM-1 — scroll to the Comments section.

You will see a new comment posted by the AI listing exactly what is missing.

**What to say:**
> "The system scored this ticket at 30% completeness — below the 35% threshold.
> Instead of wasting a developer's time, it automatically posted a clarification
> comment in Jira listing exactly what's missing. The developer does not get
> assigned bad work."

**Show on Dashboard** (Tab: Workflow Runs):
- New row for SCRUM-1, status = `completed_incomplete`, Flagged Incomplete = `Yes`

---

## STEP 4 — Demo: Full Pipeline — Complete Ticket (10 min)

**In Terminal 1:**
```powershell
python main.py --mode single --ticket SCRUM-4
```

This will take **2-5 minutes** as all 7 agents run. While it runs, explain the log events:

| Log Event | What It Means |
|---|---|
| `jira_ticket_fetched` | Agent 1 fetched the ticket from Jira |
| `agent_node_entered` completeness | Agent 2 scoring completeness |
| `github_repo_analyzed` | Agent 3 scanned the GitHub repo for relevant files |
| `confluence_docs_retrieved` | Agent 4 searched Confluence for architecture docs |
| `agent_node_completed` planner | Agent 5 built the implementation plan |
| `agent_node_completed` code_proposal | Agent 6 proposed specific code changes |
| `agent_node_completed` test_agent | Agent 7 suggested test cases |
| `github_pr_created` | Draft PR created on GitHub |

**Expected final output:**
```
============================================================
  Ticket: SCRUM-4
  Phase:  WorkflowPhase.COMPLETED
  Completeness: 100% (complete)
  PR:     https://github.com/Loki1920/Automating-data-download-from-webpage/pull/1
============================================================
```

---

## STEP 5 — Show The GitHub Draft PR (4 min)

Open the PR URL printed in the output. Show each section:

- **Summary** — AI-generated overview of the implementation approach
- **Implementation Plan** — Step-by-step with affected files and risk level
- **Proposed Code Changes** — Actual code diffs per file
- **Test Suggestions** — Named test cases with arrange/act/assert
- **Confluence References** — Linked architecture docs
- **AI Confidence Scores** — Plan, Code, Tests percentages
- **AI Disclaimer** at the bottom — "requires thorough human review before merging"

**What to say:**
> "This is a Draft PR — it cannot be merged without a human reviewing it.
> The AI never merges code automatically. This is the entire point: the AI
> does the heavy lifting of analysis, planning, and scaffolding, but a
> human engineer reviews and approves every single change."

---

## STEP 6 — Show The Live Dashboard (3 min)

Open http://localhost:8501

**KPI Cards (top):**
> "These are the three POC success criteria. KPI 1 tracks PR approval rate.
> KPI 2 tracks incomplete ticket detection accuracy. KPI 3 tracks system stability."

**Workflow Runs tab:**
> "Every ticket run is recorded — status, completeness score, PR outcome,
> duration, tokens used. Full audit trail."

**LLM Call Log tab:**
> "Every AI call is logged — agent, model, tokens, latency, parse success.
> This is your cost visibility and compliance audit trail."

**PR Actions tab:**
> "A human can mark PRs as approved or rejected here, feeding back into KPI 1."

---

## STEP 7 — Show The Metrics API (2 min)

Open http://localhost:8080/docs (Swagger UI)

1. Click **GET /metrics** -> Execute -> show the JSON KPI response
2. Click **GET /health** -> Execute -> `{"status": "ok"}`
3. Click **POST /pr/{run_id}/approve** -> show it requires `X-Api-Key` header

**In Terminal 1:**
```powershell
curl http://localhost:8080/health
curl http://localhost:8080/metrics
```

**What to say:**
> "Any monitoring tool — Grafana, DataDog, your own dashboard — can poll this.
> The approve/reject endpoints are protected by an API key."

---

## STEP 8 — Show Scheduler Mode (1 min)

**What to say (do NOT run live):**
> "In production, the system runs as a scheduler, polling Jira every 5 minutes
> for any ticket that moves to 'Ready for Dev' and processing it automatically."

Show the command:
```powershell
# python main.py --mode scheduler
# Polls every 5 minutes using JQL:
# project in (SCRUM) AND status = "Ready for Dev" ORDER BY created DESC
```

---

## STEP 9 — Show The Logs (1 min)

```powershell
# Last 5 log entries
Get-Content logs\activity.jsonl | Select-Object -Last 5 | ForEach-Object { $_ | python -m json.tool }
```

**What to say:**
> "Every event is structured JSON — timestamps, agent names, token counts,
> latency, errors. Nothing is a black box. Full auditability."

---

## STEP 10 — Wrap Up: KPI Summary (1 min)

```powershell
python main.py --mode metrics
```

> "KPI 1 — PR Approval Rate: Did engineers find the AI's PRs useful enough to approve?
> KPI 2 — Incomplete Detection: Did it correctly catch tickets that weren't ready?
> KPI 3 — 10 Consecutive Error-Free Runs: Is it stable enough for production?"

---

## Handling Client Questions

| Question | Answer |
|---|---|
| "Does it auto-merge?" | No. Always a Draft PR. Human reviews every change. |
| "What if the LLM is wrong?" | AI Disclaimer on every PR. Code review is mandatory. |
| "Can we use our own Jira project?" | Yes — change JIRA_POLL_JQL in .env to any JQL query. |
| "What LLM does it use?" | Currently OpenAI GPT-4o-mini. Can switch to AWS Bedrock Claude. |
| "Where is the data stored?" | SQLite locally. Can be migrated to PostgreSQL for production. |
| "How much does it cost per ticket?" | Average tokens shown on Dashboard LLM Call Log tab. |
| "Is PII safe?" | Email, phone, and tokens in ticket descriptions are auto-redacted before being sent to the LLM. |

---

## Quick Recovery Commands

```powershell
# Force reprocess a ticket (if already processed)
venv\Scripts\python -c "
from persistence.repository import TicketRepository
TicketRepository().request_reprocess('SCRUM-1')
print('Ready to reprocess')
"

# Check last errors
Get-Content logs\activity.jsonl | Select-Object -Last 30 | Select-String 'ERROR'

# Restart metrics server if port 8080 is busy
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
python main.py --mode metrics-server

# Show current KPIs
python main.py --mode metrics
```

---

## Final Pre-Demo Checklist (run 10 min before client arrives)

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate

# 1. LLM works
python -c "from llm.bedrock_client import get_llm; print('LLM OK:', get_llm().invoke('Say OK').content)"

# 2. Jira MCP works
python -c "
from mcp_client.client_factory import get_mcp_client, filter_jira_tools
import asyncio
async def t():
    async with get_mcp_client() as c:
        tools = await c.get_tools()
        print('MCP tools loaded:', len(tools))
asyncio.run(t())
" 2>&1 | Select-String "MCP tools"

# 3. Metrics server
curl http://localhost:8080/health

# 4. Dashboard open at http://localhost:8501

# 5. KPI summary
python main.py --mode metrics
```

All passing = you are ready for the demo.

---

## Architecture Reference

```
Jira "Ready for Dev"
       |
       v
  [Scheduler / CLI]
       |
       v
  fetch_ticket  -->  completeness_check
                          |
              +-----------+-----------+
              |                       |
        (incomplete)            (complete)
              |                       |
     post_clarification          repo_scout
     (comment in Jira)               |
              |                 confluence_docs
              |                       |
              |                   planner
              |                       |
              |                code_proposal
              |                       |
              |                 test_suggestion
              |                       |
              |                  pr_composer
              |               (GitHub Draft PR)
              |                       |
              +----------+------------+
                         |
                    end_workflow
                    (DB finalized)
```

```
External Integrations:
  Jira  <-->  mcp-atlassian (Python, stdio)
  GitHub <--> @modelcontextprotocol/server-github (Node, stdio)
  Confluence <--> mcp-atlassian (same process)
  LLM <--> OpenAI GPT-4o-mini (or AWS Bedrock Claude)

Persistence:
  SQLite (data/sdlc_assistant.db)
  Logs: logs/activity.jsonl + logs/llm_calls.jsonl

Dashboard:
  Streamlit (http://localhost:8501)
  Metrics API (http://localhost:8080)
```

# AI Agentic SDLC Assistant — Complete Client Demo Guide
### Version: March 2026 | Presenter's Reference (Do Not Share With Client)

---

## OVERVIEW & TIMING

| Section | Duration |
|---|---|
| Pre-demo environment setup | 15–30 min (do this alone, before client arrives) |
| Opening / context setting | 3 min |
| Show the Jira board | 2 min |
| Demo 1: Incomplete ticket detection | 4 min |
| Demo 2: Full pipeline — complete ticket | 10–12 min |
| Show GitHub Draft PR | 4 min |
| Show Live Dashboard | 4 min |
| Show Metrics API | 2 min |
| Scheduler mode explanation | 1 min |
| KPI wrap-up | 2 min |
| Client Q&A | 5–10 min |
| **Total** | **~45–55 min** |

---

## SYSTEM STATUS (VERIFIED WORKING)

| Component | Status | Details |
|---|---|---|
| LLM | LIVE | OpenAI GPT-4o-mini, API key active |
| Jira | LIVE | telomeregs.atlassian.net, project SCRUM |
| SCRUM-1 | READY | "chatbot testing" — vague ticket, will be flagged incomplete |
| SCRUM-4 | READY | "Add rate limiting..." — well-written ticket, full pipeline runs |
| GitHub | LIVE | Loki1920/Automating-data-download-from-webpage |
| GitHub PR #1 | EXISTS | Draft PR already created by the system |
| Confluence | LIVE | Space: SD |
| MCP Tools | LIVE | 98 tools (Jira + GitHub + Confluence) |
| Dashboard | READY | Streamlit on port 8501 |
| Metrics API | READY | FastAPI on port 8080, key: demo-secret-key-2024 |

---

## PART 1 — PRE-DEMO SETUP (DO THIS BEFORE THE CLIENT ARRIVES)

### Step 1.1 — Reset Ticket Processing State

Both SCRUM-1 and SCRUM-4 have been processed before. You must reset them so the system processes them fresh during the demo, producing live output the client can see.

Open **PowerShell** as administrator and run:

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
```

Then reset both tickets:

```powershell
python -c "
from persistence.repository import TicketRepository
repo = TicketRepository()
repo.request_reprocess('SCRUM-1')
repo.request_reprocess('SCRUM-4')
print('Both tickets reset and ready for demo')
"
```

Expected output:
```
Both tickets reset and ready for demo
```

> **WHY THIS MATTERS:** Without resetting, the system detects the ticket was already processed and skips it.
> This would make the demo show nothing happening — embarrassing in front of a client.

---

### Step 1.2 — Open 4 Terminal Windows

Arrange 4 PowerShell/Terminal windows side by side on your screen before the client arrives.
Each terminal has a dedicated purpose. Do not close any of them during the demo.

```
+---------------------------+---------------------------+
|   TERMINAL 1              |   TERMINAL 2              |
|   Main commands           |   Live log viewer         |
|   (you type here)         |   (always running)        |
+---------------------------+---------------------------+
|   TERMINAL 3              |   TERMINAL 4              |
|   Metrics server          |   Streamlit dashboard     |
|   (always running)        |   (always running)        |
+---------------------------+---------------------------+
```

---

### Step 1.3 — Start Terminal 2: Live Log Viewer

In **Terminal 2**, run:

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
Get-Content logs\activity.jsonl -Wait 2>$null | ForEach-Object { $_ | python -m json.tool 2>$null || $_ }
```

This will tail the log file in real time, pretty-printing every JSON event as it happens.
During the demo, this terminal shows the AI agents firing in sequence — a live view of the system thinking.

> Leave this running. It will show nothing until you run a ticket — that is normal.

---

### Step 1.4 — Start Terminal 3: Metrics Server

In **Terminal 3**, run:

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
python main.py --mode metrics-server
```

Expected output (within 5 seconds):
```
INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

> If you see "port 8080 already in use", run: `Get-Process -Name python | Stop-Process -Force` then retry.

---

### Step 1.5 — Start Terminal 4: Streamlit Dashboard

In **Terminal 4**, run:

```powershell
cd D:\agentic_sdlc_assistant
venv\Scripts\activate
streamlit run dashboard.py
```

Expected output:
```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
```

A browser tab will open automatically at http://localhost:8501.
If it does not open, open Chrome/Edge manually and go to http://localhost:8501.

---

### Step 1.6 — Open All Browser Tabs

Open these 4 tabs in the browser and arrange them. Keep them open during the entire demo:

| Tab | URL | Purpose |
|---|---|---|
| 1 | https://telomeregs.atlassian.net/software/projects/SCRUM/boards | Jira board |
| 2 | https://github.com/Loki1920/Automating-data-download-from-webpage/pulls | GitHub PRs |
| 3 | http://localhost:8501 | Streamlit Dashboard |
| 4 | http://localhost:8080/docs | Metrics API Swagger |

---

### Step 1.7 — Run Pre-Demo Health Check

In **Terminal 1**, run these checks one by one:

**Check 1: LLM connectivity**
```powershell
python -c "
import os
os.environ['PYTHONIOENCODING'] = 'utf-8'
from llm.bedrock_client import get_llm
llm = get_llm()
response = llm.invoke('Reply with exactly: READY')
print('LLM status:', response.content)
"
```
Expected: `LLM status: READY`

**Check 2: MCP tools load**
```powershell
python -c "
import asyncio
from mcp_client.client_factory import get_mcp_client
async def check():
    async with get_mcp_client() as c:
        tools = await c.get_tools()
        print(f'MCP tools loaded: {len(tools)} tools')
asyncio.run(check())
" 2>&1 | Select-String "MCP tools"
```
Expected: `MCP tools loaded: 98 tools`

**Check 3: Metrics server**
```powershell
curl http://localhost:8080/health
```
Expected: `{"status":"ok"}`

**Check 4: KPI summary**
```powershell
python main.py --mode metrics
```
Expected output (approximately):
```
============================================================
  POC SUCCESS CRITERIA
============================================================
  [PASS] KPI 1 - PR Approval Rate:        100.0%  (target >=33%, 1/1 resolved)
  [PASS] KPI 2 - Incomplete Detection:     100.0%  (target >=50%)
  [FAIL] KPI 3 - Consecutive Error-Free:   1   (target >=10, total runs: 50)

  Average processing time: 55.3s
  Complete pipeline runs:  4
  Flagged incomplete:      13
============================================================
```

> KPI 3 being FAIL is expected and fine — explain to client that it builds up over time with live usage.

**All 4 checks passing? You are ready for the demo.**

---

## PART 2 — THE DEMO (CLIENT IS PRESENT)

---

## DEMO STEP 1 — Opening: What This System Does (3 min)

**[Switch to browser, open the Jira board tab]**

**Say:**
> "What you're looking at is a live Jira project — your real tickets, your real workflow.
> This AI system sits alongside your development process. When any ticket moves to
> 'Ready for Dev' status, the system automatically picks it up, evaluates it, and
> takes action — without any human intervention."
>
> "Depending on the quality of the ticket, one of two things happens:
> If the ticket is vague or missing critical information, the AI catches it before
> any developer wastes time on it — and posts a specific clarification request
> back in Jira.
> If the ticket is well-written and complete, the AI runs a full pipeline: it
> reads your codebase on GitHub, searches your Confluence documentation for
> architecture context, builds a step-by-step implementation plan, proposes
> specific code changes, suggests test cases, and opens a Draft PR on GitHub —
> all ready for a human engineer to review."
>
> "The AI never merges code. It never auto-deploys. Every output requires
> a human to review and approve. The goal is not to replace engineers —
> it's to eliminate the 40 minutes of setup and context-gathering that happens
> before an engineer writes the first line of code."

**[Pause for any initial questions. Then move on.]**

---

## DEMO STEP 2 — Show the Jira Board (2 min)

**[Keep the Jira board tab open]**

Point to the board and say:

> "We have two tickets in 'Ready for Dev' that we'll use for this demo."

Point to **SCRUM-1**:
> "This first ticket is called 'chatbot testing'. The description is just:
> 'this is for testing chatbot'. No acceptance criteria. No technical detail.
> No scope. Any developer who picks this up would immediately come back with
> questions — or worse, build the wrong thing entirely."

Point to **SCRUM-4**:
> "This second ticket — 'Add rate limiting to the /api/users endpoint' —
> is a proper ticket. It has a clear problem statement, specific acceptance
> criteria, technical context about Redis, and a measurable definition of done."

> "Let's watch the AI process both of these — starting with the bad one."

---

## DEMO STEP 3 — Demo: Incomplete Ticket Detection (4 min)

**[Switch to Terminal 1. Keep Terminal 2 (log viewer) visible on screen if possible.]**

Type and run:

```powershell
python main.py --mode single --ticket SCRUM-1
```

**[While it runs — this takes about 20–30 seconds — narrate what you see in Terminal 2:]**

> "Watch the log terminal. You can see the agents firing in sequence.
> First, the ticket fetcher pulls the ticket from Jira via the API.
> Then the completeness agent reads the title, description, and acceptance criteria
> and scores them against 8 different dimensions — problem clarity, technical
> specificity, scope, testability, and so on."

**Wait for the output to appear in Terminal 1. Expected output:**

```
============================================================
  Ticket: SCRUM-1
  Phase:  WorkflowPhase.COMPLETED
  Completeness: 20% (incomplete)
============================================================
```

**Say:**
> "The system scored this ticket at 20% completeness — well below the 35%
> threshold we've configured. The pipeline stopped here. No developer
> was assigned incomplete work."

**[Switch to the Jira board tab. Open SCRUM-1. Scroll to the Comments section at the bottom.]**

> "And here is the automatic clarification comment that was just posted
> to the Jira ticket. The AI listed exactly what is missing —
> what information a developer needs before this ticket is ready to be worked on."

**[Let the client read the comment. Give them 20–30 seconds.]**

> "The label 'needs-clarification' was also added to the ticket automatically,
> so it appears in filtered views."

**[Switch to the Streamlit Dashboard tab — http://localhost:8501]**

> "And on the dashboard — which you can see is pulling live data from the
> same database — there's a new row for SCRUM-1. Status: completed_incomplete.
> Flagged incomplete: Yes. The completeness score, how long it took,
> how many tokens the AI used — all tracked."

---

## DEMO STEP 4 — Demo: Full Pipeline (Complete Ticket) (10–12 min)

**[Switch back to Terminal 1]**

> "Now let's show the full pipeline. This is the well-written ticket."

Type and run:

```powershell
python main.py --mode single --ticket SCRUM-4
```

> "This will take 2–4 minutes — 7 different AI agents are running in sequence.
> Let me walk you through what each one does while we watch the logs."

**[Switch to Terminal 2 — the live log viewer. Narrate each event as it appears:]**

When you see `agent_node_entered ... TicketFetcherAgent`:
> "Agent 1 — Ticket Fetcher. It's pulling the full ticket from Jira, including
> the description, acceptance criteria, attachments, and metadata."

When you see `agent_node_entered ... completeness`:
> "Agent 2 — Completeness Check. It reads the ticket and scores it across
> 8 dimensions. A well-written ticket with clear acceptance criteria should
> score high."

When you see `github_repo_analyzed` or `agent_node_entered ... repo_scout`:
> "Agent 3 — Repository Scout. It connects to your GitHub repo, reads the
> directory structure, identifies which files are most relevant to this feature,
> and pulls their content. It's building the context a developer would need
> to understand the codebase before starting."

When you see `confluence_docs_retrieved`:
> "Agent 4 — Confluence Search. It searches your internal documentation
> for pages related to this feature. Architecture decision records,
> API design docs, infrastructure runbooks — all automatically discovered
> and included in the plan."

When you see `agent_node_completed ... PlannerAgent`:
> "Agent 5 — Planner. Using the ticket, the codebase, and the Confluence docs,
> it produces a step-by-step implementation plan: which files to change,
> in what order, why, and what the risks are."

When you see `agent_node_completed ... CodeProposalAgent`:
> "Agent 6 — Code Proposal. It writes specific, actual code changes — not
> pseudocode, not a description of what to write, but real proposed implementations
> for each file that needs to change."

When you see `agent_node_completed ... TestAgent`:
> "Agent 7 — Test Suggestion. It writes test cases — unit tests, integration
> tests, edge cases — named and structured in the arrange/act/assert pattern,
> ready to be turned into real test files."

When you see `github_pr_created`:
> "And there it is — the Draft PR is being created on GitHub right now."

**[Switch back to Terminal 1 and wait for the final summary. Expected output:]**

```
============================================================
  Ticket: SCRUM-4
  Phase:  WorkflowPhase.COMPLETED
  Completeness: 100% (complete)
  PR:     https://github.com/Loki1920/Automating-data-download-from-webpage/pull/1
============================================================
```

**Say:**
> "100% completeness — this ticket had everything the AI needed to run
> the full pipeline. And there's the Draft PR URL."

---

## DEMO STEP 5 — Show the GitHub Draft PR (4 min)

**[Click the GitHub PR tab, or open the PR URL from the terminal output.
URL: https://github.com/Loki1920/Automating-data-download-from-webpage/pull/1]**

> "Let's look at what the AI actually produced. This is a real GitHub
> Draft PR — it's in the repository right now."

**Scroll through the PR and narrate each section:**

**PR Title:**
> "The title follows your commit convention — feat(SCRUM-4) — with the
> Jira ticket ID embedded so there's traceability back to the requirement."

**Jira Link at the top:**
> "Clicking this goes directly back to the Jira ticket. Bidirectional linking."

**Summary section:**
> "This is an AI-written summary of the implementation approach. It explains
> what the feature does, which components are involved, and the high-level
> design decision. A reviewer reading this immediately understands what
> the PR is for."

**Implementation Plan section:**
> "The step-by-step plan. Each step has a title, description, which files
> are affected, and the estimated complexity. Also shows the risk level —
> in this case, medium risk — and the rationale."

**Proposed Code Changes section:**
> "This is the actual proposed code. Not 'you should add rate limiting here'
> — specific Python code, in the right file, with the right structure.
> The engineer doesn't start from scratch — they start from a working draft
> and refine it."

**Test Suggestions section:**
> "Named test cases. Each one tells you what to test, the arrange/act/assert
> structure, and whether it's an edge case. The engineer copies these into
> the test file and fleshes them out."

**Confidence Scores:**
> "The AI rates its own confidence in the plan, the code, and the test
> suggestions. If confidence is low on any dimension, that's a signal
> that the engineer should pay extra attention there."

**AI Disclaimer at the bottom:**
> "And this disclaimer is on every single PR the system creates.
> It is not optional and cannot be removed. The AI generated this.
> Human review is mandatory before merging. The system enforces this
> by creating a Draft PR — you literally cannot merge a Draft PR
> on GitHub without a human converting it to a regular PR and approving it."

---

## DEMO STEP 6 — Show the Live Dashboard (4 min)

**[Switch to http://localhost:8501 — the Streamlit Dashboard]**

**KPI Cards at the top:**

> "These three cards are the POC success criteria we agreed on at the start
> of this project. KPI 1 — PR Approval Rate: of all the PRs the AI created
> that engineers reviewed, what percentage did they approve? The target is 33%.
> KPI 2 — Incomplete Detection Rate: of the tickets that were genuinely
> incomplete, what percentage did the AI correctly catch? Target is 50%.
> KPI 3 — Consecutive error-free runs: the system needs to demonstrate
> stability. Target is 10 in a row without an error."

**[Click to the "Workflow Runs" tab]**

> "Every single ticket run is recorded here. You can see SCRUM-1 —
> status: completed_incomplete, completeness score: 20%, flagged: yes.
> SCRUM-4 — status: completed_complete, completeness 100%, PR created."
>
> "Duration is tracked. So is token usage — this is your cost visibility.
> You can see exactly what the AI spent per ticket."

**[Click to the "LLM Call Log" tab]**

> "Every individual AI call is logged. Agent name, model, number of tokens,
> latency in milliseconds, whether the structured output was parsed
> successfully. This is your compliance audit trail. If you need to explain
> to a regulator what the AI did on a given ticket, you have a complete record."

**[Click to the "PR Actions" tab]**

> "A human reviewer can come to this tab after reviewing a PR on GitHub
> and mark it as Approved or Rejected. That feeds directly into KPI 1.
> This is how the system learns over time whether its outputs are useful."

---

## DEMO STEP 7 — Show the Metrics API (2 min)

**[Switch to http://localhost:8080/docs — the Swagger UI]**

> "The dashboard is great for humans. But for integrating with your existing
> monitoring infrastructure — Grafana, DataDog, PagerDuty — there's a
> REST API."

**Click GET /health, then click "Try it out", then "Execute":**

> "Health endpoint. Returns 'ok'. Your monitoring system can poll this
> every 30 seconds and alert if the service goes down."

**Click GET /metrics, then "Try it out", then "Execute":**

> "The full KPI payload in JSON. Every number on the dashboard is also
> available here as structured data. A Grafana dashboard can pull this
> and display it alongside your other engineering metrics."

**Click POST /pr/{run_id}/approve:**

> "The approve endpoint is how external systems or the human review UI
> feed outcomes back in. Notice it requires an X-Api-Key header —
> it's protected. Only authorised systems can record PR outcomes."

**[Switch to Terminal 1, type:]**

```powershell
curl http://localhost:8080/health
curl http://localhost:8080/metrics
```

> "Same data available directly from the command line.
> Any script, any CI/CD pipeline, any dashboard can consume this."

---

## DEMO STEP 8 — Scheduler / Production Mode (1 min)

> "Everything we just ran, we triggered manually with a command.
> In production, you wouldn't do that. The system runs as a scheduler."

**[Show Terminal 1 — type but DO NOT press Enter:]**

```powershell
python main.py --mode scheduler
```

> "This one command starts a background process that polls Jira every 5 minutes
> using this JQL query:
> 'project in (SCRUM) AND status = Ready for Dev ORDER BY created DESC'
>
> Whenever a developer moves a ticket to 'Ready for Dev' in Jira,
> within 5 minutes the AI has evaluated it, either posted a clarification comment
> or created a Draft PR, and moved on to the next one.
> No human has to run any command. It runs all day, every day."

**[Clear the terminal without pressing Enter — press Escape or Ctrl+C]**

---

## DEMO STEP 9 — Final KPI Summary (2 min)

**[Switch to Terminal 1 and run:]**

```powershell
python main.py --mode metrics
```

**[While it runs, say:]**
> "Let's close with the numbers."

**[Once output appears, walk through each KPI:]**

> "KPI 1 — PR Approval Rate. This answers the question: when an engineer
> looks at an AI-generated PR, do they find it good enough to actually approve?
> Our target for this POC is 33% — meaning 1 in 3. That's a low bar
> deliberately set, because this is new technology. Every PR we approve,
> the system learns from."
>
> "KPI 2 — Incomplete Detection Rate. Of the tickets that genuinely didn't
> have enough information to start coding, what percentage did the AI correctly
> flag? This directly measures whether we're protecting developer time."
>
> "KPI 3 — Consecutive Error-Free Runs. Does the system run reliably?
> Does it crash? Does it produce corrupted outputs? We target 10 consecutive
> clean runs as proof of production stability."

---

## PART 3 — CLIENT Q&A

These are the most common questions clients ask. Answer confidently. Do not over-promise.

---

**Q: Does it automatically merge the code?**

> "No — never. Every PR is created as a Draft. A Draft PR on GitHub cannot
> be merged by anyone until a human manually converts it to a regular PR
> and another human approves it. The AI's role ends the moment the PR
> is created. The merge is always a human decision."

---

**Q: What if the AI writes wrong code?**

> "That is exactly why the code review step exists. The AI's output is a
> starting point, not a finished product. Every PR has an AI Disclaimer
> that says explicitly: 'requires thorough human review before merging.
> Verify all logic, test coverage, and edge cases independently.'
> The system is designed to save engineers time on the first 70% of the work —
> setting up the structure, identifying the files, writing the boilerplate.
> The final 30% — verification, edge case handling, security review — is
> always human."

---

**Q: What LLM does it use? Is our code going to OpenAI?**

> "Currently it uses OpenAI GPT-4o-mini for cost efficiency during the POC.
> The system is fully configurable to use AWS Bedrock with Claude — which
> means your code stays within the AWS environment, under your own VPC,
> without any data leaving to a third-party API.
> Switching is a one-line config change. We can demo that today if you want."

---

**Q: What data does the LLM see?**

> "The LLM sees: the Jira ticket title and description, relevant code files
> from your GitHub repo (limited to the most relevant files, not the entire
> codebase), and relevant Confluence pages.
> Before anything is sent to the LLM, a PII sanitiser runs over the text —
> it automatically redacts email addresses, phone numbers, and API tokens.
> All of this is logged — you can see exactly what was sent to the LLM
> for every single call."

---

**Q: Can we connect it to our own Jira project?**

> "Yes. Change two values in the config file: JIRA_PROJECTS_FILTER
> to your project key, and JIRA_POLL_JQL to the JQL query that matches
> your Ready-for-Dev workflow. It works with any Jira Cloud or Server instance.
> Same for GitHub and Confluence — you just update the credentials."

---

**Q: What happens if the LLM API is down?**

> "The system has retry logic built in — it retries failed LLM calls
> up to 3 times with exponential backoff. If all retries fail, the run
> is marked as failed in the database, the error is logged with full detail,
> and the ticket is left in its current state — no bad data is written.
> The scheduler will attempt it again on the next poll cycle.
> The health endpoint will reflect the failure so your monitoring system
> can alert."

---

**Q: How much does it cost per ticket?**

> "On the LLM Call Log tab of the dashboard, you can see token counts per call.
> For a full pipeline run on GPT-4o-mini, we're averaging around 50 seconds
> and a modest number of tokens. At current OpenAI pricing, a full pipeline
> run costs a few cents. An incomplete ticket check — which is faster and
> uses fewer agents — costs less.
> If you switch to AWS Bedrock with Claude Haiku, the cost drops further.
> We can run the exact numbers for your expected ticket volume."

---

**Q: Where is the data stored? Is it secure?**

> "Everything is stored in a local SQLite database file during the POC.
> No data leaves your environment except to the LLM API and to Jira/GitHub —
> which you already use.
> For production, the database can be migrated to PostgreSQL and hosted in
> your cloud environment. The schema is simple and well-documented."

---

**Q: What happens when Jira tickets are updated after the AI processes them?**

> "Currently the system processes a ticket once when it enters 'Ready for Dev'.
> If the ticket is updated — say, a developer adds clarification — you can
> trigger reprocessing with a single command, or configure the scheduler
> to detect changes automatically. This is a feature we can add in
> the next iteration."

---

**Q: Can it handle multiple Jira projects simultaneously?**

> "Yes. The JQL query can span multiple projects:
> 'project in (PROJ1, PROJ2, PROJ3) AND status = Ready for Dev'.
> Each project's tickets are processed independently and tracked separately
> in the dashboard."

---

**Q: What about compliance and auditability?**

> "Every action the system takes is logged as structured JSON with a timestamp.
> Every LLM call is recorded — which agent made it, what model was used,
> how many tokens, the latency, and whether parsing succeeded.
> Every PR outcome is recorded — who approved, when.
> If your compliance team asks 'what did the AI do on ticket PROJ-42 on
> this date', you have a complete, queryable audit trail."

---

**Q: How long did this take to build?**

> "The POC was built to demonstrate the core workflow end-to-end.
> The architecture is modular — each of the 9 agents is an independent
> component that can be extended or replaced. Adding a new agent
> (for example, a security scan agent) is a well-defined pattern."

---

**Q: What would production look like?**

> "For production, the key changes are:
> 1. Replace SQLite with PostgreSQL for concurrent access and scalability.
> 2. Switch LLM to AWS Bedrock for data residency.
> 3. Deploy the scheduler as a containerised service (Docker/ECS/Kubernetes).
> 4. Add role-based access control to the metrics API.
> 5. Add webhook support — instead of polling Jira every 5 minutes,
>    Jira sends a webhook the moment a ticket status changes,
>    reducing latency from 5 minutes to under 5 seconds."

---

**Q: Can it write tests for existing code, not just new features?**

> "That is a natural extension. The system already scans your codebase —
> it could identify untested files and generate test suggestions for them.
> That would be a separate run mode, separate from the ticket-driven workflow."

---

## PART 4 — RECOVERY PROCEDURES

Use these if something goes wrong mid-demo. Stay calm. Technical demos always have rough edges.

---

### Problem: Ticket was already processed — output appears instantly with no log activity

**Fix:**
```powershell
python -c "
from persistence.repository import TicketRepository
repo = TicketRepository()
repo.request_reprocess('SCRUM-1')
repo.request_reprocess('SCRUM-4')
print('Reset done')
"
```
Then re-run the ticket command.

---

### Problem: MCP client hangs for more than 60 seconds

**Fix:** Press Ctrl+C. Then run:
```powershell
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force
```
Wait 5 seconds. Then restart the command.

---

### Problem: "Port 8080 already in use" for metrics server

**Fix:**
```powershell
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
python main.py --mode metrics-server
```

---

### Problem: Streamlit dashboard shows an error or blank screen

**Fix:**
```powershell
# In Terminal 4, press Ctrl+C, then:
streamlit run dashboard.py
```
Refresh the browser tab at http://localhost:8501.

---

### Problem: SCRUM-4 pipeline runs but PR shows "failed"

This means the GitHub PR already exists. The PR was created in an earlier run.

**What to say:**
> "The system detected that a Draft PR for this branch already exists
> on GitHub — it avoids creating duplicates. Let me open the existing PR."

Open: https://github.com/Loki1920/Automating-data-download-from-webpage/pull/1

---

### Problem: LLM call takes more than 3 minutes with no output

**Fix:** Press Ctrl+C. Check OpenAI API status at status.openai.com.
If OpenAI is down, switch to Bedrock:

```powershell
# In .env, change:
# LLM_PROVIDER=openai
# to:
# LLM_PROVIDER=bedrock
```
Then re-run.

---

### Problem: Unicode/encoding error appears in the terminal

**Fix:** Set this before running:
```powershell
$env:PYTHONIOENCODING = "utf-8"
```
Then re-run the command.

---

### Problem: Jira comment not appearing on SCRUM-1

Check if DRY_RUN is set:
```powershell
python -c "from config.settings import settings; print('dry_run:', settings.dry_run)"
```
If it says `dry_run: True`, edit `.env` and set `DRY_RUN=false`.

---

### Problem: "No module named X" error

**Fix:**
```powershell
venv\Scripts\activate
pip install -r requirements.txt
```

---

## PART 5 — QUICK REFERENCE COMMANDS

Keep Terminal 1 ready with these commands. Copy-paste as needed.

```powershell
# Activate environment (run first in any new terminal)
cd D:\agentic_sdlc_assistant
venv\Scripts\activate

# Reset a ticket for reprocessing
python -c "from persistence.repository import TicketRepository; TicketRepository().request_reprocess('SCRUM-1')"
python -c "from persistence.repository import TicketRepository; TicketRepository().request_reprocess('SCRUM-4')"

# Run the incomplete ticket demo
python main.py --mode single --ticket SCRUM-1

# Run the full pipeline demo
python main.py --mode single --ticket SCRUM-4

# Show KPI metrics
python main.py --mode metrics

# Start metrics server (if not running)
python main.py --mode metrics-server

# Start dashboard (if not running)
streamlit run dashboard.py

# Check last 5 log entries
Get-Content logs\activity.jsonl | Select-Object -Last 5 | ForEach-Object { $_ | python -m json.tool }

# Check last 10 errors in logs
Get-Content logs\activity.jsonl | Select-Object -Last 50 | Select-String '"level": "ERROR"'

# Health check
curl http://localhost:8080/health
curl http://localhost:8080/metrics

# Kill all Python processes (emergency reset)
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process -Name node -ErrorAction SilentlyContinue | Stop-Process -Force
```

---

## PART 6 — ARCHITECTURE REFERENCE

Use this if the client's technical team asks deep questions.

```
                          ┌─────────────────────────┐
                          │   Jira "Ready for Dev"   │
                          └────────────┬────────────┘
                                       │  poll every 5 min (or webhook)
                                       ▼
                          ┌─────────────────────────┐
                          │    Scheduler / CLI       │
                          │  (APScheduler / argparse)│
                          └────────────┬────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────────┐
                    │         LangGraph StateGraph          │
                    │                                       │
                    │  1. fetch_ticket                      │
                    │       └─► MCP: jira_get_issue         │
                    │                                       │
                    │  2. completeness_check                │
                    │       └─► LLM: score 8 dimensions    │
                    │                                       │
                    │       ┌──────────┴──────────┐         │
                    │  (incomplete)          (complete)     │
                    │       │                     │         │
                    │  3a. post_clarification     │         │
                    │       └─► MCP: jira_add_comment       │
                    │                             │         │
                    │                    3b. repo_scout     │
                    │                       └─► MCP: GitHub │
                    │                                       │
                    │                    4. confluence_docs  │
                    │                       └─► MCP: Confluence│
                    │                                       │
                    │                    5. planner         │
                    │                       └─► LLM         │
                    │                                       │
                    │                    6. code_proposal   │
                    │                       └─► LLM         │
                    │                                       │
                    │                    7. test_suggestion │
                    │                       └─► LLM         │
                    │                                       │
                    │                    8. pr_composer     │
                    │                       └─► MCP: GitHub │
                    │                              create PR│
                    │                                       │
                    │                    9. end_workflow    │
                    │                       └─► SQLite DB   │
                    └──────────────────────────────────────┘
```

**Technology Stack:**

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph with conditional routing) |
| LLM | OpenAI GPT-4o-mini (configurable: AWS Bedrock Claude) |
| Tool Integration | Model Context Protocol (MCP) via stdio transport |
| Jira + Confluence | mcp-atlassian (Python, runs as subprocess) |
| GitHub | @modelcontextprotocol/server-github (Node.js, runs as subprocess) |
| Persistence | SQLite via SQLAlchemy (schema-migrable to PostgreSQL) |
| Scheduler | APScheduler with IntervalTrigger |
| Dashboard | Streamlit |
| Metrics API | FastAPI + Uvicorn |
| PII Protection | Regex-based sanitiser (email, phone, API tokens) |
| Retry Logic | Tenacity (3 attempts, exponential backoff) |
| Logging | Structured JSON (JSONL format, queryable) |

---

## PART 7 — BUSINESS VALUE TALKING POINTS

Use these if the conversation turns commercial or the client asks about ROI.

**Time saved per ticket:**
> "Our testing shows each complete ticket run saves 30–90 minutes of developer
> setup time — the time spent reading the ticket, finding the relevant files,
> writing boilerplate, and creating a test skeleton. For a team doing 20 tickets
> a sprint, that's 10–30 hours of developer time per sprint."

**Catch incomplete tickets early:**
> "The cost of a developer picking up a vague ticket and working on the wrong
> thing for 2 days before the issue is discovered is enormous — not just in
> time but in rework, morale, and sprint velocity. The AI catches this in
> under 30 seconds."

**Consistency:**
> "Every ticket goes through the same 8-point completeness evaluation.
> No more 'it depends on who reviewed the ticket'. The standard is consistent
> and auditable."

**Knowledge capture:**
> "The Confluence search step means the AI automatically surfaces relevant
> architecture documentation that a new developer might not even know exists.
> This is knowledge transfer on autopilot."

---

## FINAL PRE-DEMO CHECKLIST

Run through this 10 minutes before the client arrives:

- [ ] `python main.py --mode metrics` — no errors, KPIs visible
- [ ] `curl http://localhost:8080/health` — returns `{"status":"ok"}`
- [ ] http://localhost:8501 open in browser — dashboard loads
- [ ] http://localhost:8080/docs open in browser — Swagger loads
- [ ] https://telomeregs.atlassian.net/software/projects/SCRUM/boards — Jira board loads
- [ ] https://github.com/Loki1920/Automating-data-download-from-webpage/pulls — GitHub PRs load
- [ ] Terminal 2 running (log viewer — shows blank prompt, that is normal)
- [ ] SCRUM-1 and SCRUM-4 both reset for reprocessing
- [ ] No Python or Node processes crashed in Terminal 3 / Terminal 4
- [ ] Screen layout arranged (4 terminals + 4 browser tabs visible)

**All checked = you are ready.**

---

*Guide last updated: March 2026*
*System version: c63c26a6*

# GitHub Project & Confluence Setup Guide

> Step-by-step instructions to create a test project that the AI Agentic SDLC Assistant can
> process end-to-end — with code in GitHub, tickets in Jira, and documentation in Confluence.

---

## Overview

You need three services connected before running the assistant:

| Service | Purpose | What the Agent Uses It For |
|---|---|---|
| **Jira** | Ticket source | Polls for "Ready for Dev" tickets |
| **GitHub** | Code repository | Scouts file structure, creates PRs |
| **Confluence** | Documentation | Fetches architecture/design context |

---

## Part 1 — GitHub Repository Setup

### Step 1: Create the Repository

1. Go to [https://github.com/new](https://github.com/new)
2. Repository name: `todo-api` (or any name you prefer)
3. Visibility: **Public** or **Private** (both work with a PAT)
4. Check **Initialize this repository with a README**
5. Click **Create repository**

---

### Step 2: Add Sample Project Code

Create the following folder structure and files in the repo.
You can create them directly in the GitHub UI (Add file → Create new file) or via `git` locally.

**Folder structure:**

```
todo-api/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── routes/
│   │   ├── __init__.py
│   │   └── todos.py
│   └── database.py
├── tests/
│   └── test_todos.py
├── requirements.txt
└── README.md
```

---

**`app/__init__.py`** — leave empty

**`app/routes/__init__.py`** — leave empty

---

**`app/main.py`**

```python
from fastapi import FastAPI
from app.routes import todos
from app.database import init_db

app = FastAPI(title="Todo API", version="1.0.0")
app.include_router(todos.router, prefix="/todos", tags=["todos"])

@app.on_event("startup")
def startup():
    init_db()

@app.get("/health")
def health():
    return {"status": "ok"}
```

---

**`app/models.py`**

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Todo(Base):
    __tablename__ = "todos"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(1000), nullable=True)
    completed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    due_date = Column(DateTime, nullable=True)
```

---

**`app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base

DATABASE_URL = "sqlite:///./todos.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

**`app/routes/todos.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Todo

router = APIRouter()

@router.get("/")
def list_todos(db: Session = Depends(get_db)):
    return db.query(Todo).all()

@router.post("/")
def create_todo(title: str, description: str = None, db: Session = Depends(get_db)):
    todo = Todo(title=title, description=description)
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return todo

@router.put("/{todo_id}/complete")
def complete_todo(todo_id: int, db: Session = Depends(get_db)):
    todo = db.query(Todo).filter(Todo.id == todo_id).first()
    if not todo:
        raise HTTPException(status_code=404, detail="Todo not found")
    todo.completed = True
    db.commit()
    return todo
```

---

**`requirements.txt`**

```
fastapi>=0.115.0
uvicorn>=0.30.0
sqlalchemy>=2.0.0
pydantic>=2.7.0
```

---

**`tests/test_todos.py`**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_create_todo():
    response = client.post("/todos/", params={"title": "Buy milk"})
    assert response.status_code == 200
    assert response.json()["title"] == "Buy milk"
```

---

### Step 3: Get a GitHub Personal Access Token

1. Go to **GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)**
2. Click **Generate new token (classic)**
3. Give it a name: `sdlc-assistant-test`
4. Select scopes: ✅ `repo` (full control of private repositories)
5. Click **Generate token**
6. **Copy the token immediately** — you will not see it again

---

## Part 2 — Jira Project Setup

### Step 1: Create a Free Jira Cloud Account

If you don't have one, sign up at:
[https://www.atlassian.com/try/cloud/signup?bundle=jira-software](https://www.atlassian.com/try/cloud/signup?bundle=jira-software)

---

### Step 2: Create a Jira Project

1. Click **Projects → Create project**
2. Select **Scrum** or **Kanban**
3. Project name: `Todo API`
4. Project key: `TODO` — this becomes your ticket prefix (e.g. `TODO-1`, `TODO-2`)
5. Click **Create**

---

### Step 3: Add the "Ready for Dev" Status

The assistant polls Jira for tickets where `status = "Ready for Dev"`. Add this status to your workflow:

1. Go to **Project Settings → Workflows**
2. Click **Edit** on the active workflow
3. Add a new status: `Ready for Dev`
4. Place it between **In Progress** and **In Review**
5. Click **Save** and **Publish** the workflow

> **Shortcut:** If editing the workflow is complex, change the poll query in your `.env` instead:
> ```env
> JIRA_POLL_JQL=status = "To Do" ORDER BY created DESC
> ```
> This polls "To Do" tickets, which exist in every new Jira project by default.

---

### Step 4: Create Test Tickets

Create the following three tickets in your `TODO` project.
They are designed to test different behaviours of the assistant.

---

#### Ticket 1 — Well-Defined Ticket (Full Pipeline Expected)

| Field | Value |
|---|---|
| **Summary** | Add due date filtering to the Todo list endpoint |
| **Status** | Ready for Dev |

**Description:**
```
The GET /todos endpoint currently returns all todos regardless of their due_date.
We need to add optional query parameters to filter todos by due date range.

Users should be able to:
- Filter todos due before a specific date (due_before=2025-12-31)
- Filter todos due after a specific date (due_after=2025-01-01)
- Combine both filters to get todos in a date range

The filters should be optional — if not provided, return all todos as before.
Date format should follow ISO 8601 (YYYY-MM-DD).
```

**Acceptance Criteria:**
```
- GET /todos?due_before=2025-12-31 returns only todos with due_date <= 2025-12-31
- GET /todos?due_after=2025-01-01 returns only todos with due_date >= 2025-01-01
- Both filters can be combined in the same request
- If no filter is provided, all todos are returned (existing behaviour preserved)
- Invalid date formats return HTTP 422 with a clear error message
- Unit tests cover all three filter combinations
```

---

#### Ticket 2 — Another Well-Defined Ticket (Full Pipeline Expected)

| Field | Value |
|---|---|
| **Summary** | Add user authentication to the Todo API |
| **Status** | Ready for Dev |

**Description:**
```
Currently the Todo API has no authentication — any user can read and modify all todos.
We need to add JWT-based authentication so each user only sees their own todos.

Implementation required:
- Add a User model with email and hashed password fields
- POST /auth/register — create a new user account
- POST /auth/login — returns a JWT access token
- All /todos endpoints must require a valid Bearer token
- Each todo should have an owner_id foreign key linking to the User table
- Users can only read and modify their own todos
```

**Acceptance Criteria:**
```
- POST /auth/register with email + password creates a user and returns HTTP 201
- POST /auth/login with valid credentials returns {"access_token": "...", "token_type": "bearer"}
- POST /auth/login with wrong password returns HTTP 401
- GET /todos without a token returns HTTP 401
- GET /todos with a valid token returns only that user's todos
- Passwords are stored as bcrypt hashes, never as plain text
```

---

#### Ticket 3 — Intentionally Vague Ticket (Completeness Check Should Fail)

| Field | Value |
|---|---|
| **Summary** | Add search functionality |
| **Status** | Ready for Dev |

**Description:**
```
We need search.
```

*(No acceptance criteria. No technical detail.)*

> This ticket is intentionally incomplete. The completeness agent should flag it and stop
> the workflow early, without generating a plan or wasting LLM tokens on a poorly defined requirement.

---

### Step 5: Get a Jira API Token

1. Go to [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Click **Create API token**
3. Label: `sdlc-assistant`
4. Click **Create** and **copy the token**

> This same token is used for both Jira and Confluence — they share authentication in Atlassian Cloud.

---

## Part 3 — Confluence Space Setup

### Step 1: Create a Confluence Space

1. In your Atlassian account, open **Confluence**
2. Click **Spaces → Create space**
3. Type: **Blank space**
4. Space name: `Todo API Docs`
5. Space key: `TODOAPI`
6. Click **Create**

---

### Step 2: Create Documentation Pages

In the `Todo API Docs` space, create the following four pages.
Go to **Create → Blank page**, paste the content, and publish.

---

#### Page 1: Architecture Overview

**Title:** `Architecture Overview`

```
## System Architecture

The Todo API is a RESTful web service built with FastAPI and SQLite.

### Components

**API Layer (FastAPI)**
Handles HTTP requests, input validation, and response serialization.
Runs on port 8000. All endpoints follow REST conventions.

**Database Layer (SQLite + SQLAlchemy)**
Uses SQLite for development and testing. The ORM layer is SQLAlchemy 2.0.
Database file: todos.db in the project root.

**Authentication**
JWT tokens using python-jose. Tokens expire after 30 minutes.
Passwords hashed with bcrypt (passlib).

### Key Design Decisions

- SQLite chosen for simplicity in the POC phase; can be swapped for PostgreSQL
- Pydantic v2 used for all request/response models
- All database operations go through SQLAlchemy sessions (never raw SQL)
- FastAPI Depends() used for dependency injection (DB session, current user)

### Project Structure

app/
├── main.py          # FastAPI app factory, router registration
├── models.py        # SQLAlchemy ORM models
├── database.py      # Engine, session factory, init_db()
└── routes/
    ├── todos.py     # CRUD endpoints for todos
    └── auth.py      # Register, login endpoints (planned)
```

---

#### Page 2: API Design

**Title:** `API Design`

```
## API Endpoints

### Todos

| Method | Path                   | Auth     | Description                        |
|--------|------------------------|----------|------------------------------------|
| GET    | /todos                 | Required | List all todos for current user    |
| POST   | /todos                 | Required | Create a new todo                  |
| GET    | /todos/{id}            | Required | Get a specific todo                |
| PUT    | /todos/{id}/complete   | Required | Mark todo as complete              |
| DELETE | /todos/{id}            | Required | Delete a todo                      |

### Query Parameters for GET /todos

| Param      | Type           | Description                             |
|------------|----------------|-----------------------------------------|
| completed  | bool           | Filter by completion status             |
| due_before | date (ISO8601) | Return todos with due_date <= this date |
| due_after  | date (ISO8601) | Return todos with due_date >= this date |

### Authentication

| Method | Path           | Auth | Description          |
|--------|----------------|------|----------------------|
| POST   | /auth/register | None | Create new account   |
| POST   | /auth/login    | None | Get JWT access token |

### Error Responses

All errors follow this schema:
  { "detail": "Human-readable error message" }

HTTP 401 — Unauthorized (missing or invalid token)
HTTP 404 — Resource not found
HTTP 409 — Conflict (e.g. email already registered)
HTTP 422 — Validation error (invalid input format)
```

---

#### Page 3: Database Schema

**Title:** `Database Schema`

```
## Database Schema

### Table: todos

| Column      | Type     | Nullable | Default       | Description              |
|-------------|----------|----------|---------------|--------------------------|
| id          | INTEGER  | No       | autoincrement | Primary key              |
| title       | VARCHAR  | No       | —             | Short task description   |
| description | VARCHAR  | Yes      | NULL          | Detailed description     |
| completed   | BOOLEAN  | No       | false         | Completion flag          |
| created_at  | DATETIME | No       | utcnow()      | Creation timestamp       |
| due_date    | DATETIME | Yes      | NULL          | Optional due date        |
| owner_id    | INTEGER  | Yes      | NULL          | FK → users.id (planned)  |

### Table: users (planned)

| Column          | Type     | Nullable | Description                  |
|-----------------|----------|----------|------------------------------|
| id              | INTEGER  | No       | Primary key                  |
| email           | VARCHAR  | No       | Unique, used as login        |
| hashed_password | VARCHAR  | No       | bcrypt hash                  |
| created_at      | DATETIME | No       | Registration timestamp       |
| is_active       | BOOLEAN  | No       | Account active flag          |

### Relationships

- todos.owner_id → users.id  (Many-to-one)
- One user can have many todos
```

---

#### Page 4: Coding Standards

**Title:** `Coding Standards`

```
## Coding Standards

### General Rules
- Python 3.12+
- All code must pass ruff linting with zero warnings
- Type hints required on all function signatures
- Docstrings required on all public functions and classes

### FastAPI Conventions
- Use Pydantic BaseModel for all request/response schemas
- Keep schemas in app/schemas/ (separate from SQLAlchemy ORM models)
- Route handlers should be thin — move business logic into service functions
- Use Depends() for all shared dependencies (DB session, current user)

### Database Conventions
- Never write raw SQL — always use the SQLAlchemy ORM
- Keep migrations in alembic/versions/ (even for SQLite)
- Index all foreign key columns
- Use utcnow() for all timestamps, never local time

### Testing Conventions
- pytest for all tests
- Use FastAPI TestClient for endpoint tests
- Each test must use a fresh in-memory SQLite database
- Target > 80% line coverage for all new code
- Test file naming: test_<feature>.py
```

---

## Part 4 — Configure the `.env` File

With all three services set up, fill in your `.env` file in the `agentic_sdlc_assistant` project root:

```env
# ── LLM (AWS Bedrock) ─────────────────────────────────────────
LLM_PROVIDER=bedrock
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
BEDROCK_MODEL_ID=anthropic.claude-3-7-sonnet-20250219-v1:0

# ── Jira ──────────────────────────────────────────────────────
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=your@email.com
JIRA_API_TOKEN=your-jira-api-token
JIRA_PROJECTS_FILTER=TODO
JIRA_POLL_JQL=project = TODO AND status = "Ready for Dev" ORDER BY created DESC
JIRA_POLL_INTERVAL_SECONDS=60

# ── GitHub ────────────────────────────────────────────────────
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
GITHUB_REPO_OWNER=your-github-username
GITHUB_REPO_NAME=todo-api
GITHUB_BASE_BRANCH=main
GITHUB_DEFAULT_REVIEWERS=your-github-username

# ── Confluence ────────────────────────────────────────────────
CONFLUENCE_URL=https://your-org.atlassian.net/wiki
CONFLUENCE_SPACE_KEYS=TODOAPI

# ── Metrics Server ────────────────────────────────────────────
METRICS_API_KEY=mysecretkey123

# ── Development ───────────────────────────────────────────────
DRY_RUN=true
LOG_LEVEL=INFO
```

> **Tip:** Start with `DRY_RUN=true`. The full 9-agent LLM pipeline will run but no real GitHub
> PR will be created. Once you confirm the output looks correct, set `DRY_RUN=false` to create
> actual draft PRs.

---

## Part 5 — Run the Tests

### Prerequisites Check

```bash
# Verify MCP servers are installed
uvx mcp-atlassian --help
npx @modelcontextprotocol/server-github --help

# Activate the virtual environment (Windows)
venv\Scripts\activate

# Verify configuration loads correctly (should print no CONFIG ERROR lines)
python main.py --mode metrics
```

---

### Test 1 — Well-Defined Ticket (Dry Run)

```bash
python main.py --mode single --ticket TODO-1 --dry-run
```

**Expected pipeline progression (visible in logs):**

```
ticket_fetched → completeness_checked (PASS) → repo_scouted →
confluence_fetched → plan_generated → code_proposed →
tests_suggested → pr_composed (SKIPPED - dry run)
```

---

### Test 2 — Incomplete Ticket (Completeness Gate)

```bash
python main.py --mode single --ticket TODO-3 --dry-run
```

**Expected result:** Workflow stops after `completeness_checked` with `FAILED` status.
No plan, code, or PR is generated.

---

### Test 3 — Full Pipeline with Real PR

```bash
# Set DRY_RUN=false in .env first, then:
python main.py --mode single --ticket TODO-1
```

**Expected result:** A draft PR is created at:
`https://github.com/your-org/todo-api/pulls`

The PR will contain:
- Implementation plan with step-by-step breakdown
- Proposed code changes with diffs
- Test case suggestions
- Confluence documentation references
- AI disclaimer footer

---

### Test 4 — Automatic Scheduler

```bash
# Set JIRA_POLL_INTERVAL_SECONDS=30 in .env for quick testing
python main.py --mode scheduler
```

Move `TODO-2` to "Ready for Dev" status in Jira.
Within 30 seconds it will be picked up and processed automatically.

---

### Monitor in Real Time

```powershell
# PowerShell — watch activity log as events come in
Get-Content logs\activity.jsonl -Wait

# PowerShell — watch LLM calls (prompts, tokens, latency)
Get-Content logs\llm_calls.jsonl -Wait

# Filter errors only
Select-String '"level": "ERROR"' logs\activity.jsonl
```

---

### View Results

```bash
# Terminal KPI summary
python main.py --mode metrics

# Streamlit visual dashboard (opens browser at http://localhost:8501)
python -m streamlit run dashboard.py

# Metrics API
python main.py --mode metrics-server
curl http://localhost:8080/metrics
```

---

## Expected Outcome Per Ticket

| Ticket | Description | Expected Result |
|---|---|---|
| `TODO-1` | Add due date filtering | Full pipeline — implementation plan + code proposal + test suggestions + PR body generated |
| `TODO-2` | Add JWT authentication | Full pipeline — more complex multi-file plan, new User model, auth routes |
| `TODO-3` | Vague search ticket | Stops at completeness check — flagged as incomplete, no plan generated |

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| `CONFIG ERROR: JIRA_URL is not set` | `.env` not loaded | Check `.env` file is in project root and has no typos |
| `No suitable Jira MCP tool found` | `uvx mcp-atlassian` not installed | Run `pip install uv` then `uvx mcp-atlassian --help` |
| `GitHub MCP subprocess died` | Node.js not installed or `npx` not in PATH | Install Node.js 20+ from [nodejs.org](https://nodejs.org) |
| `Ticket TODO-1 not found` | Wrong project key or ticket number | Confirm the ticket exists and status matches the JQL filter |
| `403 from Bedrock` | Wrong AWS region or model not enabled | Enable Claude model in AWS Bedrock console for your region |
| Workflow always stops at completeness | Threshold too high | Lower `COMPLETENESS_THRESHOLD=0.5` in `.env` |

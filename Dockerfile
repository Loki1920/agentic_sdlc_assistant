FROM python:3.12-slim

# ── Environment ───────────────────────────────────────────────
# Prevents Python from buffering stdout/stderr (logs appear immediately)
# Forces UTF-8 encoding so Unicode content in tickets never crashes the app
ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── System dependencies ───────────────────────────────────────
# curl: health checks inside container
# git:  some langchain/mcp packages inspect git at import time
# Node 20: required for @modelcontextprotocol/server-github (npx)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── uv (required to run uvx mcp-atlassian) ───────────────────
RUN pip install uv

# ── Pre-warm MCP servers to reduce cold-start latency ────────
# Failures here are non-fatal — servers need auth to run fully
RUN npx --yes @modelcontextprotocol/server-github --help 2>/dev/null || true
RUN uvx mcp-atlassian --help 2>/dev/null || true

# ── Application working directory ────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ───────────────────────
# Copy only requirements first so this layer is rebuilt only when
# requirements.txt changes, not on every code change.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ── Application code ──────────────────────────────────────────
COPY . .

# ── Runtime directories ───────────────────────────────────────
RUN mkdir -p /app/data /app/logs

# ── Non-root user for security ───────────────────────────────
RUN useradd --no-create-home --shell /bin/false appuser \
    && chown -R appuser:appuser /app
USER appuser

# ── Expose metrics API port ───────────────────────────────────
EXPOSE 8080

# ── Default: run the Jira scheduler ──────────────────────────
# Override with:
#   docker run ... python main.py --mode metrics-server
#   docker run ... python main.py --mode single --ticket PROJ-123
CMD ["python", "main.py", "--mode", "scheduler"]

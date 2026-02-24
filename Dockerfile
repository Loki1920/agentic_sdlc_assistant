FROM python:3.12-slim

# ── System dependencies ───────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── uv (required for uvx mcp-atlassian) ─────────────────────
RUN pip install --no-cache-dir uv

# ── Pre-warm MCP servers to avoid cold-start latency ─────────
# Errors here are non-fatal (servers may need auth to run fully)
RUN npx --yes @modelcontextprotocol/server-github --help 2>/dev/null || true
RUN uvx mcp-atlassian --help 2>/dev/null || true

# ── Python dependencies ───────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────
COPY . .

# ── Runtime directories ───────────────────────────────────────
RUN mkdir -p /app/data /app/logs

# ── Default: run the scheduler ───────────────────────────────
CMD ["python", "main.py", "--mode", "scheduler"]

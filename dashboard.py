"""Streamlit dashboard for the AI Agentic SDLC Assistant.

Run with:
    streamlit run dashboard.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select

from metrics.poc_metrics import POCMetricsCollector
from persistence.database import get_db_session
from persistence.models import TicketRun

st.set_page_config(page_title="SDLC Assistant", layout="wide")
st.title("AI Agentic SDLC Assistant — Dashboard")

# ── KPI metrics ───────────────────────────────────────────────────────────────

m = POCMetricsCollector().compute()

success_rate = (
    (m.total_runs - m.total_error_runs) / m.total_runs if m.total_runs > 0 else 0.0
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Runs", m.total_runs)
col2.metric(
    "Error-Free Rate",
    f"{success_rate:.1%}",
    help="(total_runs - error_runs) / total_runs",
)
col3.metric(
    "Avg Tokens / Run",
    f"{m.average_tokens_per_run:,.0f}" if m.average_tokens_per_run else "—",
)
col4.metric("PR Approval Rate", f"{m.pr_approval_rate:.1%}", help="KPI 1 target: ≥ 33%")

# ── KPI status badges ─────────────────────────────────────────────────────────

st.subheader("KPI Status")
kpi_col1, kpi_col2, kpi_col3 = st.columns(3)
kpi_col1.success("KPI 1 ✓ PR Approval ≥ 33%" if m.kpi1_met else "KPI 1 ✗ PR Approval < 33%")
kpi_col2.success(
    "KPI 2 ✓ Incomplete Detection ≥ 50%"
    if m.kpi2_met
    else "KPI 2 ✗ Incomplete Detection < 50%"
)
kpi_col3.success(
    f"KPI 3 ✓ {m.consecutive_error_free_runs} consecutive error-free"
    if m.kpi3_met
    else f"KPI 3 ✗ Only {m.consecutive_error_free_runs} consecutive error-free (need 10)"
)

# ── Run history ───────────────────────────────────────────────────────────────

st.subheader("Recent Workflow Runs (last 50)")

with get_db_session() as session:
    rows = (
        session.execute(
            select(TicketRun).order_by(TicketRun.started_at.desc()).limit(50)
        )
        .scalars()
        .all()
    )
    # Read all attributes inside the session to avoid DetachedInstanceError
    run_data = [
        {
            "Ticket": r.ticket_id,
            "Status": r.status.value,
            "LLM Calls": r.total_llm_calls or 0,
            "Tokens": r.total_tokens_used or 0,
            "PR": r.pr_outcome.value if r.pr_outcome else "—",
            "Error": "✓" if r.error_occurred else "",
            "Started": str(r.started_at)[:19] if r.started_at else "",
        }
        for r in rows
    ]

if run_data:
    df = pd.DataFrame(run_data)
    st.dataframe(df, use_container_width=True)

    # ── Status breakdown chart ────────────────────────────────────────────────
    st.subheader("Status Breakdown")
    status_counts = df["Status"].value_counts()
    st.bar_chart(status_counts)
else:
    st.info("No workflow runs recorded yet.")

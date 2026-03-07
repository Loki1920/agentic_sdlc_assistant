"""Streamlit dashboard for the AI Agentic SDLC Assistant.

Run with:
    streamlit run dashboard.py
    # or from project root:
    venv\\Scripts\\activate && streamlit run dashboard.py
"""
from __future__ import annotations

import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
from sqlalchemy import select

from metrics.poc_metrics import POCMetricsCollector
from persistence.database import get_db_session, init_db
from persistence.models import LLMCallLog, PROutcome, RunStatus, TicketRun

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI SDLC Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure DB tables exist (safe to call repeatedly)
init_db()

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Controls")

    if st.button("Refresh Now", use_container_width=True):
        st.rerun()

    auto_refresh = st.toggle("Auto-Refresh", value=False)
    refresh_interval = st.selectbox(
        "Refresh Interval",
        options=[15, 30, 60, 120],
        index=1,
        format_func=lambda s: f"{s}s",
        disabled=not auto_refresh,
    )

    st.divider()

    st.subheader("PR Actions")
    metrics_base_url = st.text_input(
        "Metrics API URL",
        value="http://localhost:8080",
        help="Base URL of the running metrics server",
    )
    api_key_input = st.text_input(
        "API Key (X-Api-Key)",
        type="password",
        help="Set via METRICS_API_KEY in .env",
    )

    st.caption(f"Last loaded: {datetime.now().strftime('%H:%M:%S')}")


# ── Helpers ───────────────────────────────────────────────────────────────────


@st.cache_data(ttl=15)
def load_metrics():
    return POCMetricsCollector().compute()


@st.cache_data(ttl=15)
def load_runs(limit: int = 100):
    with get_db_session() as session:
        rows = (
            session.execute(
                select(TicketRun).order_by(TicketRun.started_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "run_id": r.id,
                "ticket_id": r.ticket_id,
                "status": r.status.value if r.status else "",
                "completeness_score": (
                    f"{r.completeness_score:.0%}" if r.completeness_score is not None else "—"
                ),
                "incomplete": "Yes" if r.ticket_deemed_incomplete else "No",
                "plan": "Yes" if r.implementation_plan_generated else "No",
                "code": "Yes" if r.code_proposal_generated else "No",
                "tests": "Yes" if r.tests_suggested else "No",
                "pr_outcome": r.pr_outcome.value if r.pr_outcome else "—",
                "pr_url": r.pr_url or "",
                "duration_s": (
                    f"{r.total_duration_seconds:.1f}" if r.total_duration_seconds else "—"
                ),
                "llm_calls": r.total_llm_calls or 0,
                "tokens": r.total_tokens_used or 0,
                "error": "Yes" if r.error_occurred else "No",
                "error_msg": r.error_message or "",
                "started_at": str(r.started_at)[:19] if r.started_at else "",
            }
            for r in rows
        ]


@st.cache_data(ttl=15)
def load_llm_calls(limit: int = 200):
    with get_db_session() as session:
        rows = (
            session.execute(
                select(LLMCallLog).order_by(LLMCallLog.invoked_at.desc()).limit(limit)
            )
            .scalars()
            .all()
        )
        return [
            {
                "invoked_at": str(r.invoked_at)[:19] if r.invoked_at else "",
                "ticket_id": r.ticket_id,
                "agent": r.agent_name,
                "model": r.model_id,
                "prompt_tokens": r.prompt_token_count or 0,
                "completion_tokens": r.completion_token_count or 0,
                "total_tokens": r.total_token_count or 0,
                "latency_ms": f"{r.latency_ms:.0f}" if r.latency_ms else "—",
                "parsed_ok": "Yes" if r.parsed_successfully else "No",
                "error": "Yes" if r.error_occurred else "No",
                "error_type": r.error_type or "",
                "run_id": r.run_id,
            }
            for r in rows
        ]


def _kpi_badge(label: str, met: bool) -> None:
    if met:
        st.success(f"PASS — {label}")
    else:
        st.error(f"FAIL — {label}")


# ── Header ────────────────────────────────────────────────────────────────────

st.title("AI Agentic SDLC Assistant")
st.caption("Live dashboard — reads from SQLite DB")

m = load_metrics()
runs = load_runs()
llm_calls = load_llm_calls()

# ── KPI Cards ─────────────────────────────────────────────────────────────────

st.subheader("POC Success Criteria")

kpi_cols = st.columns(3)

with kpi_cols[0]:
    st.metric(
        label="KPI 1 — PR Approval Rate",
        value=f"{m.pr_approval_rate:.1%}",
        delta="Target: ≥ 33%",
        delta_color="normal" if m.kpi1_met else "inverse",
        help=f"{m.total_prs_approved} approved / {m.total_prs_resolved} resolved PRs",
    )
    _kpi_badge(
        f"Approval {m.pr_approval_rate:.1%} ({m.total_prs_approved}/{m.total_prs_resolved} resolved)",
        m.kpi1_met,
    )

with kpi_cols[1]:
    st.metric(
        label="KPI 2 — Incomplete Detection",
        value=f"{m.incomplete_detection_rate:.1%}",
        delta="Target: ≥ 50%",
        delta_color="normal" if m.kpi2_met else "inverse",
        help=(
            m.kpi2_note
            if m.kpi2_note
            else f"{m.true_positive_detections} true positives / {m.total_ground_truth_incomplete} ground-truth incomplete"
        ),
    )
    _kpi_badge(
        f"Detection {m.incomplete_detection_rate:.1%} ({m.true_positive_detections}/{m.total_ground_truth_incomplete} TP)",
        m.kpi2_met,
    )
    if m.kpi2_note:
        st.caption(m.kpi2_note)

with kpi_cols[2]:
    st.metric(
        label="KPI 3 — Consecutive Error-Free",
        value=str(m.consecutive_error_free_runs),
        delta="Target: ≥ 10",
        delta_color="normal" if m.kpi3_met else "inverse",
        help=f"Total runs: {m.total_runs} | Error runs: {m.total_error_runs}",
    )
    _kpi_badge(
        f"{m.consecutive_error_free_runs} consecutive error-free (need 10)",
        m.kpi3_met,
    )

# ── Performance Stats ─────────────────────────────────────────────────────────

st.divider()
st.subheader("Performance Overview")

perf_cols = st.columns(5)
perf_cols[0].metric("Total Runs", m.total_runs)
perf_cols[1].metric("Complete Pipeline", m.runs_complete_pipeline)
perf_cols[2].metric("Flagged Incomplete", m.runs_flagged_incomplete)
perf_cols[3].metric(
    "Avg Duration",
    f"{m.average_duration_seconds:.1f}s" if m.average_duration_seconds else "—",
)
perf_cols[4].metric(
    "Avg Tokens / Run",
    f"{m.average_tokens_per_run:,.0f}" if m.average_tokens_per_run else "—",
)

# ── Tabs ──────────────────────────────────────────────────────────────────────

st.divider()
tab_runs, tab_llm, tab_pr = st.tabs(["Workflow Runs", "LLM Call Log", "PR Actions"])

# ── Tab 1: Workflow Runs ───────────────────────────────────────────────────────

with tab_runs:
    if not runs:
        st.info("No workflow runs recorded yet. Run: `python main.py --mode single --ticket YOUR-1`")
    else:
        df = pd.DataFrame(runs)

        # Filters
        filter_cols = st.columns(3)
        status_opts = ["All"] + sorted(df["status"].unique().tolist())
        selected_status = filter_cols[0].selectbox("Filter by Status", status_opts)

        pr_opts = ["All"] + sorted(df["pr_outcome"].unique().tolist())
        selected_pr = filter_cols[1].selectbox("Filter by PR Outcome", pr_opts)

        error_opts = ["All", "Yes", "No"]
        selected_error = filter_cols[2].selectbox("Filter by Error", error_opts)

        filtered = df.copy()
        if selected_status != "All":
            filtered = filtered[filtered["status"] == selected_status]
        if selected_pr != "All":
            filtered = filtered[filtered["pr_outcome"] == selected_pr]
        if selected_error != "All":
            filtered = filtered[filtered["error"] == selected_error]

        st.caption(f"Showing {len(filtered)} of {len(df)} runs")

        display_cols = [
            "started_at", "ticket_id", "status", "completeness_score",
            "incomplete", "plan", "code", "tests",
            "pr_outcome", "duration_s", "llm_calls", "tokens", "error",
        ]
        st.dataframe(
            filtered[display_cols].rename(columns={
                "started_at": "Started",
                "ticket_id": "Ticket",
                "status": "Status",
                "completeness_score": "Completeness",
                "incomplete": "Flagged Incomplete",
                "plan": "Plan",
                "code": "Code",
                "tests": "Tests",
                "pr_outcome": "PR Outcome",
                "duration_s": "Duration(s)",
                "llm_calls": "LLM Calls",
                "tokens": "Tokens",
                "error": "Error",
            }),
            use_container_width=True,
            height=400,
        )

        # ── Status breakdown chart ────────────────────────────────────────────
        chart_cols = st.columns(2)
        with chart_cols[0]:
            st.caption("Status Breakdown")
            st.bar_chart(df["status"].value_counts(), height=200)
        with chart_cols[1]:
            st.caption("PR Outcome Breakdown")
            st.bar_chart(df["pr_outcome"].value_counts(), height=200)

        # ── Error detail expander ─────────────────────────────────────────────
        error_rows = filtered[filtered["error"] == "Yes"]
        if not error_rows.empty:
            with st.expander(f"Error Details ({len(error_rows)} runs)"):
                for _, row in error_rows.iterrows():
                    st.markdown(f"**{row['ticket_id']}** ({row['started_at']})")
                    st.code(row["error_msg"] or "No message", language=None)

        # ── PR URL links ──────────────────────────────────────────────────────
        pr_rows = filtered[filtered["pr_url"] != ""]
        if not pr_rows.empty:
            with st.expander(f"GitHub PR Links ({len(pr_rows)} PRs)"):
                for _, row in pr_rows.iterrows():
                    st.markdown(f"- **{row['ticket_id']}** [{row['pr_url']}]({row['pr_url']}) — `{row['pr_outcome']}`")

# ── Tab 2: LLM Call Log ────────────────────────────────────────────────────────

with tab_llm:
    if not llm_calls:
        st.info("No LLM calls logged yet.")
    else:
        llm_df = pd.DataFrame(llm_calls)

        agent_opts = ["All"] + sorted(llm_df["agent"].unique().tolist())
        col_a, col_b = st.columns(2)
        selected_agent = col_a.selectbox("Filter by Agent", agent_opts)
        selected_llm_error = col_b.selectbox("Filter by Error", ["All", "Yes", "No"], key="llm_err")

        llm_filtered = llm_df.copy()
        if selected_agent != "All":
            llm_filtered = llm_filtered[llm_filtered["agent"] == selected_agent]
        if selected_llm_error != "All":
            llm_filtered = llm_filtered[llm_filtered["error"] == selected_llm_error]

        st.caption(f"Showing {len(llm_filtered)} of {len(llm_df)} calls (last 200)")

        display_llm_cols = [
            "invoked_at", "ticket_id", "agent", "model",
            "prompt_tokens", "completion_tokens", "total_tokens",
            "latency_ms", "parsed_ok", "error", "error_type",
        ]
        st.dataframe(
            llm_filtered[display_llm_cols].rename(columns={
                "invoked_at": "Time",
                "ticket_id": "Ticket",
                "agent": "Agent",
                "model": "Model",
                "prompt_tokens": "Prompt Tok",
                "completion_tokens": "Completion Tok",
                "total_tokens": "Total Tok",
                "latency_ms": "Latency(ms)",
                "parsed_ok": "Parsed OK",
                "error": "Error",
                "error_type": "Error Type",
            }),
            use_container_width=True,
            height=400,
        )

        # ── Token usage by agent bar chart ────────────────────────────────────
        if len(llm_df) > 0:
            st.caption("Total Tokens by Agent")
            tokens_by_agent = llm_df.groupby("agent")["total_tokens"].sum().sort_values(ascending=False)
            st.bar_chart(tokens_by_agent, height=200)

# ── Tab 3: PR Actions ─────────────────────────────────────────────────────────

with tab_pr:
    st.markdown(
        "Manually approve or reject PRs for **KPI 1** tracking. "
        "Requires the metrics API server to be running (`python main.py --mode metrics-server`) "
        "and a valid `METRICS_API_KEY`."
    )

    if not runs:
        st.info("No runs found.")
    else:
        df_all = pd.DataFrame(runs)
        pending_df = df_all[df_all["pr_outcome"] == PROutcome.PENDING.value]

        if pending_df.empty:
            st.success("No pending PRs to review.")
        else:
            st.caption(f"{len(pending_df)} pending PR(s)")
            for _, row in pending_df.iterrows():
                with st.container(border=True):
                    pr_cols = st.columns([3, 2, 1, 1])
                    pr_cols[0].markdown(f"**{row['ticket_id']}**  \n`{row['run_id'][:8]}...`")
                    if row["pr_url"]:
                        pr_cols[1].markdown(f"[View PR]({row['pr_url']})")
                    else:
                        pr_cols[1].markdown("No PR URL")

                    approve_key = f"approve_{row['run_id']}"
                    reject_key = f"reject_{row['run_id']}"

                    if pr_cols[2].button("Approve", key=approve_key, type="primary"):
                        if not api_key_input:
                            st.error("Enter an API key in the sidebar first.")
                        else:
                            resp = requests.post(
                                f"{metrics_base_url}/pr/{row['run_id']}/approve",
                                headers={"X-Api-Key": api_key_input},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                st.success(f"Approved {row['ticket_id']}")
                                load_runs.clear()
                                st.rerun()
                            else:
                                st.error(f"Error {resp.status_code}: {resp.text}")

                    if pr_cols[3].button("Reject", key=reject_key):
                        if not api_key_input:
                            st.error("Enter an API key in the sidebar first.")
                        else:
                            resp = requests.post(
                                f"{metrics_base_url}/pr/{row['run_id']}/reject",
                                headers={"X-Api-Key": api_key_input},
                                timeout=5,
                            )
                            if resp.status_code == 200:
                                st.success(f"Rejected {row['ticket_id']}")
                                load_runs.clear()
                                st.rerun()
                            else:
                                st.error(f"Error {resp.status_code}: {resp.text}")

    st.divider()
    st.subheader("All Resolved PRs")
    resolved_df = pd.DataFrame(runs) if runs else pd.DataFrame()
    if not resolved_df.empty:
        resolved = resolved_df[
            resolved_df["pr_outcome"].isin([
                PROutcome.APPROVED.value, PROutcome.REJECTED.value, PROutcome.MERGED.value
            ])
        ]
        if resolved.empty:
            st.info("No resolved PRs yet.")
        else:
            st.dataframe(
                resolved[["started_at", "ticket_id", "pr_outcome", "pr_url", "duration_s", "tokens"]],
                use_container_width=True,
            )

# ── Auto-refresh ──────────────────────────────────────────────────────────────

if auto_refresh:
    time.sleep(refresh_interval)
    load_metrics.clear()
    load_runs.clear()
    load_llm_calls.clear()
    st.rerun()

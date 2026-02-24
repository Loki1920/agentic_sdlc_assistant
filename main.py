"""
AI Agentic SDLC Assistant — Entry Point

Usage:
    # Run as scheduler (polls Jira on a schedule)
    python main.py --mode scheduler

    # Run against a single ticket manually
    python main.py --mode single --ticket PROJ-123

    # Dry-run (no Jira comments, no GitHub PRs)
    python main.py --mode single --ticket PROJ-123 --dry-run

    # Show current POC metrics
    python main.py --mode metrics

    # Start the metrics HTTP server
    python main.py --mode metrics-server
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time


def _configure() -> None:
    from config.logging_config import configure_logging
    configure_logging()
    from persistence.database import init_db
    init_db()


def run_scheduler() -> None:
    _configure()
    from apscheduler.triggers.interval import IntervalTrigger
    from config.settings import settings
    from app_logging.activity_logger import ActivityLogger
    from scheduler.poller import start_scheduler, stop_scheduler
    from scheduler.pr_reconciler import reconcile_pr_outcomes

    logger = ActivityLogger("main")

    sched = start_scheduler()

    # Add PR reconciler job
    sched.add_job(
        reconcile_pr_outcomes,
        trigger=IntervalTrigger(seconds=settings.pr_reconcile_interval_seconds),
        id="pr_reconcile",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )

    logger.info("main_scheduler_running", pid=os.getpid())
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        stop_scheduler()
        logger.info("main_scheduler_stopped")


def run_single(ticket_id: str, dry_run: bool) -> None:
    if dry_run:
        os.environ["DRY_RUN"] = "true"
    _configure()

    from agents.supervisor import run_workflow
    from app_logging.activity_logger import ActivityLogger

    logger = ActivityLogger("main")
    logger.info("single_run_started", ticket_id=ticket_id, dry_run=dry_run)

    final_state = run_workflow(ticket_id)

    # Pretty-print summary
    phase = final_state.get("current_phase", "unknown")
    errors = final_state.get("errors", [])
    pr = final_state.get("pr_result")

    print("\n" + "=" * 60)
    print(f"  Ticket: {ticket_id}")
    print(f"  Phase:  {phase}")
    if errors:
        print(f"  Errors: {'; '.join(errors)}")
    if pr and hasattr(pr, "pr_url") and pr.pr_url:
        print(f"  PR:     {pr.pr_url}")
    elif pr and hasattr(pr, "status"):
        print(f"  PR:     {pr.status.value}")
    completeness = final_state.get("completeness_result")
    if completeness:
        print(f"  Completeness: {completeness.completeness_score:.0%} ({completeness.decision.value})")
    print("=" * 60 + "\n")


def show_metrics() -> None:
    _configure()
    from metrics.poc_metrics import POCMetricsCollector

    m = POCMetricsCollector().compute()

    print("\n" + "=" * 60)
    print("  POC SUCCESS CRITERIA")
    print("=" * 60)
    kpi1_icon = "✅" if m.kpi1_met else "❌"
    kpi2_icon = "✅" if m.kpi2_met else "❌"
    kpi3_icon = "✅" if m.kpi3_met else "❌"

    print(f"  {kpi1_icon} KPI 1 — PR Approval Rate:         {m.pr_approval_rate:.1%}  (target ≥33%, {m.total_prs_approved}/{m.total_prs_resolved} resolved)")
    print(f"  {kpi2_icon} KPI 2 — Incomplete Detection:      {m.incomplete_detection_rate:.1%}  (target ≥50%)")
    if m.kpi2_note:
        print(f"           Note: {m.kpi2_note}")
    print(f"  {kpi3_icon} KPI 3 — Consecutive Error-Free:    {m.consecutive_error_free_runs}   (target ≥10, total runs: {m.total_runs})")
    print()
    if m.average_duration_seconds is not None:
        print(f"  Average processing time: {m.average_duration_seconds:.1f}s")
    if m.average_tokens_per_run is not None:
        print(f"  Average tokens/run:      {m.average_tokens_per_run:.0f}")
    print(f"  Complete pipeline runs:  {m.runs_complete_pipeline}")
    print(f"  Flagged incomplete:      {m.runs_flagged_incomplete}")
    print("=" * 60 + "\n")


def start_metrics_server() -> None:
    import uvicorn
    from config.settings import settings
    _configure()
    uvicorn.run("metrics.server:app", host="0.0.0.0", port=settings.metrics_port, reload=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Agentic SDLC Assistant")
    parser.add_argument(
        "--mode",
        choices=["scheduler", "single", "metrics", "metrics-server"],
        default="scheduler",
        help="Run mode",
    )
    parser.add_argument("--ticket", help="Jira ticket ID (required for --mode single)")
    parser.add_argument("--dry-run", action="store_true", help="Skip Jira comments and GitHub PR creation")

    args = parser.parse_args()

    if args.mode == "scheduler":
        run_scheduler()
    elif args.mode == "single":
        if not args.ticket:
            print("ERROR: --ticket is required with --mode single", file=sys.stderr)
            sys.exit(1)
        run_single(args.ticket, args.dry_run)
    elif args.mode == "metrics":
        show_metrics()
    elif args.mode == "metrics-server":
        start_metrics_server()


if __name__ == "__main__":
    main()

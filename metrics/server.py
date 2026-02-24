from __future__ import annotations

import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from config.settings import settings
from metrics.poc_metrics import POCMetrics, POCMetricsCollector
from persistence.database import init_db
from persistence.repository import TicketRepository

app = FastAPI(title="AI SDLC Assistant — POC Metrics", version="1.0.0")
_collector = POCMetricsCollector()
_repo = TicketRepository()


@app.on_event("startup")
def startup():
    init_db()


@app.get("/metrics", response_model=None)
def get_metrics():
    """Return current POC KPI metrics as JSON."""
    m: POCMetrics = _collector.compute()
    return JSONResponse(
        content={
            "computed_at": m.computed_at,
            "kpi_summary": {
                "kpi1_pr_approval_rate": {
                    "target": "≥ 33%",
                    "current": f"{m.pr_approval_rate:.1%}",
                    "met": m.kpi1_met,
                    "total_prs_created": m.total_prs_created,
                    "total_prs_approved": m.total_prs_approved,
                    "total_prs_resolved": m.total_prs_resolved,
                },
                "kpi2_incomplete_detection_rate": {
                    "target": "≥ 50%",
                    "current": f"{m.incomplete_detection_rate:.1%}",
                    "met": m.kpi2_met,
                    "total_tickets_processed": m.total_tickets_processed,
                    "total_detected_incomplete": m.total_detected_incomplete,
                    "total_ground_truth_incomplete": m.total_ground_truth_incomplete,
                    "true_positive_detections": m.true_positive_detections,
                    "note": m.kpi2_note,
                },
                "kpi3_error_free_runs": {
                    "target": "≥ 10 consecutive",
                    "current": m.consecutive_error_free_runs,
                    "met": m.kpi3_met,
                    "total_runs": m.total_runs,
                    "total_error_runs": m.total_error_runs,
                },
            },
            "performance": {
                "average_duration_seconds": m.average_duration_seconds,
                "average_tokens_per_run": m.average_tokens_per_run,
                "runs_complete_pipeline": m.runs_complete_pipeline,
                "runs_flagged_incomplete": m.runs_flagged_incomplete,
            },
        }
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/pr/{run_id}/approve")
def mark_pr_approved(run_id: str):
    """Manually mark a PR run as approved (for KPI 1 tracking)."""
    from persistence.models import PROutcome
    _repo.set_pr_outcome(run_id, PROutcome.APPROVED)
    return {"run_id": run_id, "outcome": "approved"}


@app.post("/pr/{run_id}/reject")
def mark_pr_rejected(run_id: str):
    """Manually mark a PR run as rejected."""
    from persistence.models import PROutcome
    _repo.set_pr_outcome(run_id, PROutcome.REJECTED)
    return {"run_id": run_id, "outcome": "rejected"}


if __name__ == "__main__":
    uvicorn.run(
        "metrics.server:app",
        host="0.0.0.0",
        port=settings.metrics_port,
        reload=False,
    )

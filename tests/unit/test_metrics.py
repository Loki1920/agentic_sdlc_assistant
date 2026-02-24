"""Unit tests for POC metrics computation."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from persistence.database import engine, init_db
from persistence.models import Base, PROutcome, RunStatus, TicketRun


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory-style SQLite DB."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("SQLITE_DB_PATH", db_path)

    # Patch the engine in database module
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import persistence.database as db_mod

    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(test_engine)
    db_mod.engine = test_engine
    db_mod.SessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    yield

    Base.metadata.drop_all(test_engine)


def _insert_run(session, run_id, ticket_id, status, pr_outcome=PROutcome.NOT_CREATED,
                pr_url=None, ticket_deemed_incomplete=None, error_occurred=False):
    session.add(TicketRun(
        id=run_id,
        ticket_id=ticket_id,
        status=status,
        started_at=datetime.now(timezone.utc),
        pr_outcome=pr_outcome,
        pr_url=pr_url,
        ticket_deemed_incomplete=ticket_deemed_incomplete,
        error_occurred=error_occurred,
    ))
    session.commit()


def test_kpi1_zero_prs():
    from metrics.poc_metrics import POCMetricsCollector
    m = POCMetricsCollector().compute()
    assert m.total_prs_created == 0
    assert m.pr_approval_rate == 0.0
    assert m.kpi1_met is False


def test_kpi1_approved_rate_above_33():
    from persistence.database import get_db_session
    from metrics.poc_metrics import POCMetricsCollector

    with get_db_session() as session:
        _insert_run(session, "r1", "T-1", RunStatus.COMPLETED_COMPLETE,
                    PROutcome.APPROVED, pr_url="https://github.com/pr/1")
        _insert_run(session, "r2", "T-2", RunStatus.COMPLETED_COMPLETE,
                    PROutcome.APPROVED, pr_url="https://github.com/pr/2")
        _insert_run(session, "r3", "T-3", RunStatus.COMPLETED_COMPLETE,
                    PROutcome.REJECTED, pr_url="https://github.com/pr/3")

    m = POCMetricsCollector().compute()
    assert m.total_prs_approved == 2
    assert m.total_prs_resolved == 3
    assert abs(m.pr_approval_rate - 2/3) < 0.01
    assert m.kpi1_met is True


def test_kpi3_consecutive_error_free():
    from persistence.database import get_db_session
    from metrics.poc_metrics import POCMetricsCollector
    import time

    with get_db_session() as session:
        # 1 failed run, then 10 successful ones
        _insert_run(session, "r0", "T-0", RunStatus.FAILED, error_occurred=True)
        for i in range(10):
            time.sleep(0.001)  # Ensure ordering by started_at
            _insert_run(session, f"r{i+1}", f"T-{i+1}", RunStatus.COMPLETED_COMPLETE)

    m = POCMetricsCollector().compute()
    assert m.consecutive_error_free_runs == 10
    assert m.kpi3_met is True


def test_kpi3_not_met_with_error():
    from persistence.database import get_db_session
    from metrics.poc_metrics import POCMetricsCollector
    import time

    with get_db_session() as session:
        for i in range(5):
            time.sleep(0.001)
            _insert_run(session, f"r{i}", f"T-{i}", RunStatus.COMPLETED_COMPLETE)
        time.sleep(0.001)
        _insert_run(session, "rfail", "T-fail", RunStatus.FAILED, error_occurred=True)

    m = POCMetricsCollector().compute()
    assert m.consecutive_error_free_runs == 0
    assert m.kpi3_met is False

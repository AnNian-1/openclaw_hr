#!/usr/bin/env python3
"""HCM 月报冻结：从事实计算、幂等、无冻结、禁止宽表。"""

from __future__ import annotations

import sys
import unittest
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from models import (
    CandidateStageEvent,
    EmploymentEvent,
    MonthlyReportMetricSnapshot,
    MonthlyReportRun,
    OnboardingTask,
    RecruitingCostLine,
    Requisition,
    TrainingEnrollment,
)
from monthly_metrics import (
    METRIC_VERSION,
    freeze_period,
    get_month,
    get_working,
    list_frozen_months,
    save_working,
)
from routers.nodes import _reject_metrics


def _dt(month: str, day: int = 10) -> datetime:
    y, m = (int(x) for x in month.split("-"))
    return datetime(y, m, day, 12, 0, 0)


def _seed_facts(db, *, include_july: bool = True) -> None:
    db.add(
        Requisition(
            requisition_id="REQ-1",
            position_title="后端",
            category="技术",
            approved_hc=2,
            opened_at=_dt("2026-05", 1),
        )
    )
    months = ["2026-06", "2026-07"] if include_july else ["2026-06"]
    for month, apps in (("2026-06", 8), ("2026-07", 10)):
        if month not in months:
            continue
        for i in range(apps):
            db.add(
                CandidateStageEvent(
                    requisition_id="REQ-1",
                    candidate_ref=f"{month}-a-{i}",
                    stage="apply",
                    occurred_at=_dt(month, 2),
                )
            )
        for i in range(5):
            db.add(
                CandidateStageEvent(
                    requisition_id="REQ-1",
                    candidate_ref=f"{month}-s-{i}",
                    stage="screen",
                    occurred_at=_dt(month, 4),
                )
            )
        db.add(
            CandidateStageEvent(
                requisition_id="REQ-1",
                candidate_ref=f"{month}-h-0",
                stage="hired",
                occurred_at=_dt(month, 12),
            )
        )
        emp = f"{month}-h-0"
        db.add(
            EmploymentEvent(
                employee_id=emp,
                event_type="hire",
                occurred_at=_dt(month, 12),
            )
        )
        db.add(
            OnboardingTask(
                employee_id=emp,
                task_type="probation",
                hired_at=_dt(month, 12),
                result="pass" if month == "2026-06" else None,
                completed_at=_dt(month, 20) if month == "2026-06" else None,
            )
        )
        db.add(
            TrainingEnrollment(
                employee_id=f"t-{month}",
                assigned_at=_dt(month, 1),
                due_at=_dt(month, 28),
                required_flag=1,
                completed_at=_dt(month, 15),
                satisfaction=4.2,
            )
        )
        db.add(
            RecruitingCostLine(
                requisition_id="REQ-1",
                amount=1000,
                invoice_date=_dt(month, 5),
                accounting_period=month,
            )
        )
    db.add(
        EmploymentEvent(
            employee_id="2026-07-h-0",
            event_type="terminate",
            reason_code="salary",
            voluntary=1,
            occurred_at=_dt("2026-07", 20),
        )
    )
    db.commit()


class FreezeTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        _seed_facts(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_freeze_computes_from_facts(self):
        a = freeze_period(self.db, "2026-07")
        self.assertEqual(a["source"], "HCM")
        self.assertEqual(a["metric_version"], METRIC_VERSION)
        self.assertTrue(a["report_run_id"].startswith("2026-07-"))
        july = next(r for r in a["recruitment_funnel"] if r["月份"] == "2026-07")
        self.assertEqual(july["投递数"], 10)
        self.assertEqual(july["初筛通过"], 5)
        self.assertEqual(july["投递转初筛率"], "50.0%")
        self.assertEqual(july["入职"], 1)
        pos = a["positions_progress"][0]
        self.assertEqual(pos["已入职"], 2)
        run = self.db.query(MonthlyReportRun).one()
        self.assertNotIn("payload_json", MonthlyReportRun.__table__.columns.keys())
        snaps = self.db.query(MonthlyReportMetricSnapshot).all()
        themes = {s.theme for s in snaps}
        self.assertIn("recruitment_funnel", themes)
        self.assertIn("_audit", themes)

    def test_freeze_idempotent(self):
        a = freeze_period(self.db, "2026-07")
        b = freeze_period(self.db, "2026-07")
        self.assertEqual(a["report_run_id"], b["report_run_id"])
        self.assertEqual(self.db.query(MonthlyReportRun).count(), 1)

    def test_get_unfrozen_is_none(self):
        self.assertIsNone(get_month("2026-08", self.db))
        self.assertEqual(list_frozen_months(self.db), [])

    def test_missing_period_raises(self):
        with self.assertRaises(ValueError):
            freeze_period(self.db, "2026-08")

    def test_working_save_then_freeze(self):
        empty = get_working(self.db, "2026-08")
        self.assertTrue(empty["editable"])
        empty["recruitment_funnel"][0]["投递数"] = 3
        empty["recruitment_funnel"][0]["初筛通过"] = 1
        saved = save_working(self.db, "2026-08", empty)
        self.assertEqual(saved["status"], "draft")
        frozen = freeze_period(self.db, "2026-08")
        self.assertEqual(frozen["status"], "frozen")
        self.assertEqual(frozen["recruitment_funnel"][0]["投递数"], 3)
        with self.assertRaises(ValueError):
            save_working(self.db, "2026-08", empty)


class NodePolicyTests(unittest.TestCase):
    def test_reject_metric_keys(self):
        with self.assertRaises(HTTPException) as ctx:
            _reject_metrics({"完成率": "90%"})
        self.assertEqual(ctx.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()

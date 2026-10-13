"""DEMO ONLY：从 stub-state 与月报 fixture 灌演示库。

生产出报不依赖本脚本。月报权威是日常事实表 + POST freeze（freeze 按事实计算，不读 fixture 宽表）。
本 seed 把 monthly-report CSV **展开成事件行**，禁止再写入月度汇总宽表。

Usage:
    cd hcm/backend
    python seed.py
    HCM_SEED_FIXTURES=1 python seed.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from database import SessionLocal
from models import (
    Candidate,
    CandidateStageEvent,
    EmploymentEvent,
    MonthlyReportMetricSnapshot,
    MonthlyReportRun,
    OnboardingTask,
    PrepNode,
    RecruitingCostLine,
    Requisition,
    TrainingEnrollment,
)
from schema_migrate import migrate_schema

PROFILE = Path(__file__).resolve().parent.parent.parent
WORKSPACE = PROFILE / "workspace-onboarding"
FIXTURES_STUB = PROFILE / "fixtures" / "onboarding-stub-state"
STUB_STATE_DIR = WORKSPACE / "stub-state"
CSV_DIR = PROFILE / "workspace-er-admin" / "report-system" / "tests" / "fixtures" / "monthly-report"

STAGE_MAP = [
    ("投递数", "apply"),
    ("初筛通过", "screen"),
    ("面试", "interview"),
    ("Offer", "offer"),
    ("入职", "hired"),
]
REASON_KEYS = [
    ("薪资原因", "salary"),
    ("发展原因", "growth"),
    ("管理原因", "mgmt"),
    ("家庭原因", "family"),
    ("不胜任", "unfit"),
]


def resolve_seed_dir() -> Path:
    if os.environ.get("HCM_SEED_FIXTURES", "").lower() in ("1", "true", "yes"):
        return FIXTURES_STUB
    stub_override = os.environ.get("HCM_SEED_STUB_STATE")
    if stub_override:
        return Path(stub_override)
    return STUB_STATE_DIR


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _month_dt(month: str, day: int = 15, hour: int = 12) -> datetime:
    y, m = (int(x) for x in month.split("-"))
    return datetime(y, m, min(max(day, 1), 28), hour, 0, 0)


def _read_csv(name: str) -> list[dict[str, str]]:
    path = CSV_DIR / name
    if not path.is_file():
        print(f"❌ 缺少月报 CSV: {path}")
        sys.exit(1)
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _clear_facts(db) -> None:
    for model in (
        MonthlyReportMetricSnapshot,
        MonthlyReportRun,
        CandidateStageEvent,
        OnboardingTask,
        TrainingEnrollment,
        RecruitingCostLine,
        EmploymentEvent,
        Requisition,
    ):
        db.query(model).delete()
    db.commit()


def seed_monthly_facts(db) -> None:
    """把 fixture 宽表展开为日常事实。出报只 freeze 这些事实。"""
    print("ℹ️  seed 把 fixture 展开为事实行（demo only），不是生产月报入口")
    if not CSV_DIR.is_dir():
        print(f"❌ 月报 CSV 目录不存在: {CSV_DIR}")
        sys.exit(1)
    _clear_facts(db)

    pos_rows = _read_csv("positions-progress.csv")
    req_ids: list[str] = []
    for i, row in enumerate(pos_rows, start=1):
        rid = f"REQ-{i:03d}"
        req_ids.append(rid)
        db.add(
            Requisition(
                requisition_id=rid,
                position_title=row["岗位"],
                category=row["所属类别"],
                approved_hc=int(row["HC"]),
                opened_at=_month_dt("2025-11", 1),
                status="open" if int(row["在招中"]) > 0 else "closed",
            )
        )
    db.flush()

    funnel_rows = _read_csv("recruitment-funnel.csv")
    hires_by_month: dict[str, list[str]] = {}
    for row in funnel_rows:
        month = row["月份"]
        hired_ids: list[str] = []
        for col, stage in STAGE_MAP:
            n = int(row[col])
            for i in range(n):
                cref = f"{month}-{stage}-{i}"
                db.add(
                    CandidateStageEvent(
                        requisition_id=req_ids[i % len(req_ids)],
                        candidate_ref=cref,
                        stage=stage,
                        channel="demo",
                        occurred_at=_month_dt(month, 1 + (i % 27)),
                    )
                )
                if stage == "hired":
                    hired_ids.append(cref)
                    db.add(
                        EmploymentEvent(
                            employee_id=cref,
                            event_type="hire",
                            reason_code="new_hire",
                            voluntary=None,
                            occurred_at=_month_dt(month, 1 + (i % 27), 14),
                        )
                    )
        hires_by_month[month] = hired_ids

    for i in range(120):
        db.add(
            EmploymentEvent(
                employee_id=f"base-{i}",
                event_type="hire",
                reason_code="new_hire",
                occurred_at=_month_dt("2024-06", 1 + (i % 27)),
            )
        )

    for row in _read_csv("onboarding-retention.csv"):
        month = row["月份"]
        emps = list(hires_by_month.get(month, []))
        pass_n = int(row["试用期通过"])
        fail_n = int(row["试用期未通过"])
        leave_n = int(row["45天内离职"])
        idx = 0
        for _ in range(fail_n):
            if idx >= len(emps):
                break
            emp = emps[idx]
            idx += 1
            db.add(
                OnboardingTask(
                    employee_id=emp,
                    task_type="probation",
                    owner_system="hcm",
                    hired_at=_month_dt(month, 10),
                    completed_at=_month_dt(month, 20),
                    result="fail",
                )
            )
        for _ in range(pass_n):
            if idx >= len(emps):
                break
            emp = emps[idx]
            idx += 1
            db.add(
                OnboardingTask(
                    employee_id=emp,
                    task_type="probation",
                    owner_system="hcm",
                    hired_at=_month_dt(month, 10),
                    completed_at=_month_dt(month, 25),
                    result="pass",
                )
            )
        for j in range(leave_n):
            if j >= len(emps):
                break
            db.add(
                EmploymentEvent(
                    employee_id=emps[j],
                    event_type="terminate",
                    reason_code="unfit",
                    voluntary=1,
                    occurred_at=_month_dt(month, 20),
                )
            )

    for row in _read_csv("training-completion.csv"):
        month = row["月份"]
        expected = int(row["应参训人数"])
        completed = int(row["完成人数"])
        sat = float(row["培训满意度"])
        for i in range(expected):
            done = i < completed
            db.add(
                TrainingEnrollment(
                    employee_id=f"train-{month}-{i}",
                    course_id=row["主要培训内容"] or "onboarding",
                    required_flag=1,
                    assigned_at=_month_dt(month, 1),
                    due_at=_month_dt(month, 28),
                    completed_at=_month_dt(month, 20) if done else None,
                    satisfaction=sat if done else None,
                )
            )

    for row in _read_csv("hiring-cost.csv"):
        month = row["月份"]
        db.add(
            RecruitingCostLine(
                requisition_id=req_ids[0],
                amount=int(row["招聘渠道费用"]),
                expense_type="channel",
                invoice_date=_month_dt(month, 5),
                accounting_period=month,
            )
        )

    leave45_by_month = {r["月份"]: int(r["45天内离职"]) for r in _read_csv("onboarding-retention.csv")}
    for row in _read_csv("attrition.csv"):
        month = row["月份"]
        already = leave45_by_month.get(month, 0)
        reasons: list[str] = []
        for zh, code in REASON_KEYS:
            reasons.extend([code] * int(row[zh]))
        vol = int(row["主动离职"])
        extra = max(int(row["离职总人数"]) - already, 0)
        for i in range(extra):
            code = reasons[min(already + i, len(reasons) - 1)] if reasons else "other"
            db.add(
                EmploymentEvent(
                    employee_id=f"base-{month}-{i}",
                    event_type="terminate",
                    reason_code=code,
                    voluntary=1 if i < vol else 0,
                    occurred_at=_month_dt(month, 18),
                )
            )

    db.commit()
    print("✅ 已展开招聘/入职/培训/费用/离职事实；旧冻结已清空，需重新 freeze")


def seed_candidates(db) -> int:
    stub_dir = resolve_seed_dir()

    if not stub_dir.exists():
        print(f"ℹ️  stub-state 目录不存在，跳过候选人: {stub_dir}")
        return 0

    candidate_dirs = [d for d in sorted(stub_dir.iterdir()) if d.is_dir()]
    if not candidate_dirs:
        print(f"ℹ️  {stub_dir} 无候选人子目录，跳过候选人 seed。")
        print("  QA 演示: HCM_SEED_FIXTURES=1 python seed.py")
        return 0

    candidates_found = 0
    for candidate_dir in candidate_dirs:
        if not candidate_dir.is_dir():
            continue

        pinyin = candidate_dir.name
        workflow_path = candidate_dir / "workflow.json"
        if workflow_path.exists():
            wf = json.loads(workflow_path.read_text(encoding="utf-8"))
            name = wf.get("candidate", pinyin)
            role = wf.get("role", "未知岗位")
            salary = wf.get("salary", "面议")
            started_at = parse_dt(wf.get("started_at"))
            wf_status = wf.get("status", "")
            wf_status_map = {
                "completed": "completed",
                "cancelled": "cancelled",
                "rejected": "cancelled",
            }
            candidate_status = wf_status_map.get(wf_status, "onboarding")
        else:
            contract_path = candidate_dir / "contract.json"
            if contract_path.exists():
                ct = json.loads(contract_path.read_text(encoding="utf-8"))
                name = ct.get("candidate", pinyin)
                role = ct.get("role", "未知岗位")
                salary = ct.get("salary", "面议")
            else:
                name = pinyin
                role = "未知岗位"
                salary = "面议"
            started_at = None
            candidate_status = "onboarding"

        existing = db.query(Candidate).filter(Candidate.pinyin == pinyin).first()
        if existing:
            print(f"⏭  跳过 {name} ({pinyin}) — 已存在")
            continue

        candidate = Candidate(
            name=name,
            pinyin=pinyin,
            role=role,
            salary=salary,
            status=candidate_status,
            started_at=started_at,
        )
        db.add(candidate)
        db.flush()

        node_map = {
            "contract": "contract.json",
            "account": "account.json",
            "device": "device.json",
            "training": "training.json",
            "buddy": "buddy.json",
        }

        for node_type, filename in node_map.items():
            json_path = candidate_dir / filename
            if json_path.exists():
                node_data = json.loads(json_path.read_text(encoding="utf-8"))
                status_str = node_data.get("status", "pending")
                status_map = {
                    "待审批": "paused",
                    "已审批": "completed",
                    "已通过": "completed",
                    "已配齐": "completed",
                    "已排期": "completed",
                    "已匹配": "completed",
                    "已开通": "completed",
                    "已创建": "completed",
                }
                status = status_map.get(status_str, "in_progress")
                data_str = json.dumps(node_data, ensure_ascii=False)
            else:
                status = "pending"
                data_str = "{}"

            db.add(
                PrepNode(
                    candidate_id=candidate.id,
                    node_type=node_type,
                    status=status,
                    data=data_str,
                )
            )

        db.commit()
        candidates_found += 1
        print(f"✅ 导入 {name} ({pinyin}) — {role} {salary}")

    return candidates_found


def seed():
    migrate_schema()
    db = SessionLocal()
    try:
        seed_monthly_facts(db)
        candidates_found = seed_candidates(db)
        print(f"\n🎉 完成！候选人 {candidates_found} 位；演示事实已同步（出报请 HCM freeze）")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

"""日常事实 CRUD。禁止写入月报最终指标。"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import (
    CandidateStageEvent,
    EmploymentEvent,
    OnboardingTask,
    RecruitingCostLine,
    Requisition,
    TrainingEnrollment,
)

router = APIRouter(prefix="/api/nodes", tags=["nodes"])

LEGACY_WIDE = {
    "recruitment-funnel",
    "positions-progress",
    "onboarding-retention",
    "training-completion",
    "hiring-cost",
    "attrition",
}

FACTS = {
    "requisitions": Requisition,
    "candidate-stage-events": CandidateStageEvent,
    "onboarding-tasks": OnboardingTask,
    "training-enrollments": TrainingEnrollment,
    "recruiting-cost-lines": RecruitingCostLine,
    "employment-events": EmploymentEvent,
}

METRIC_KEYS = {
    "完成率",
    "月离职率",
    "投递转初筛率",
    "面试转Offer率",
    "Offer接受率",
    "人均招聘成本",
    "45天内离职率",
    "投递数",
    "入职人数",
    "应参训人数",
    "screen_rate",
    "monthly_rate",
    "cost_per_hire",
    "leave_45d_rate",
    "offer_accept_rate",
}

DT_FIELDS = {
    "opened_at",
    "occurred_at",
    "due_at",
    "completed_at",
    "waived_at",
    "hired_at",
    "assigned_at",
    "invoice_date",
    "created_at",
    "updated_at",
}


def _reject_metrics(body: dict) -> None:
    hits = [k for k in body if k in METRIC_KEYS]
    if hits:
        raise HTTPException(
            status_code=422,
            detail="禁止直接填写月报最终指标: " + ", ".join(hits),
        )


def _parse(body: dict) -> dict:
    _reject_metrics(body)
    out = dict(body)
    out.pop("id", None)
    for key in DT_FIELDS:
        raw = out.get(key)
        if isinstance(raw, str) and raw:
            out[key] = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return out


def _row_dict(obj) -> dict:
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            data[col.name] = val.isoformat()
        else:
            data[col.name] = val
    return data


def _legacy_or_spec(node: str):
    if node in LEGACY_WIDE:
        raise HTTPException(
            status_code=410,
            detail="旧月度宽表已移除。请读写 requisitions / candidate-stage-events 等事实表，不要 PUT 本月招聘人数或完成率。",
        )
    model = FACTS.get(node)
    if not model:
        raise HTTPException(status_code=404, detail="未知事实表")
    return model


@router.get("/{node}")
def list_node(node: str, db: Session = Depends(get_db)):
    model = _legacy_or_spec(node)
    rows = db.query(model).order_by(model.id).limit(500).all()
    total = db.query(model).count()
    return {"node": node, "source": "HCM", "kind": "fact", "total": total, "rows": [_row_dict(r) for r in rows]}


@router.post("/{node}")
def create_node(node: str, body: dict, db: Session = Depends(get_db)):
    model = _legacy_or_spec(node)
    row = model(**_parse(body))
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"node": node, "row": _row_dict(row)}


@router.put("/{node}/{ident}")
def upsert_node(node: str, ident: str, body: dict, db: Session = Depends(get_db)):
    model = _legacy_or_spec(node)
    try:
        pk = int(ident)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="事实主键应为整数 id") from exc
    kwargs = _parse(body)
    row = db.query(model).filter(model.id == pk).first()
    if row:
        for k, v in kwargs.items():
            setattr(row, k, v)
    else:
        raise HTTPException(status_code=404, detail="事实不存在")
    db.commit()
    db.refresh(row)
    return {"node": node, "row": _row_dict(row)}

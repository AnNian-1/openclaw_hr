"""Monthly report API: 工作稿可写；GET 无冻结仍 409；出报只读冻结快照。"""

import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from monthly_metrics import (
    freeze_period,
    get_month,
    get_working,
    list_draft_months,
    list_frozen_months,
    save_working,
)

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
router = APIRouter(prefix="/api/reports", tags=["reports"])


def _require_period(month: str) -> None:
    if not MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="月份格式应为 YYYY-MM")


def _require_freeze_auth(x_hcm_freeze_token: str | None) -> None:
    expected = os.environ.get("HCM_FREEZE_TOKEN", "").strip()
    if not expected:
        return
    if (x_hcm_freeze_token or "").strip() != expected:
        raise HTTPException(status_code=403, detail="无权冻结月报")


@router.get("/monthly")
def list_months(db: Session = Depends(get_db)):
    frozen = list_frozen_months(db)
    drafts = list_draft_months(db)
    months = sorted(set(frozen) | set(drafts))
    return {"months": months, "frozen": frozen, "drafts": drafts, "source": "HCM"}


@router.get("/monthly/{month}/working")
def get_monthly_working(month: str, db: Session = Depends(get_db)):
    _require_period(month)
    return get_working(db, month)


@router.put("/monthly/{month}/working")
def put_monthly_working(month: str, body: dict, db: Session = Depends(get_db)):
    _require_period(month)
    try:
        return save_working(db, month, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/monthly/{month}")
def get_monthly(month: str, db: Session = Depends(get_db)):
    _require_period(month)
    payload = get_month(month, db)
    if not payload:
        raise HTTPException(
            status_code=409,
            detail=(
                f"月份 {month} 尚未冻结。请 POST /api/reports/monthly/{month}/freeze。"
                "禁止回退 CSV，禁止填 0。"
            ),
        )
    return payload


@router.post("/monthly/{month}/freeze")
def freeze_monthly(
    month: str,
    db: Session = Depends(get_db),
    x_hcm_freeze_token: str | None = Header(default=None, alias="X-HCM-Freeze-Token"),
):
    """受控冻结。同一 period 再次调用返回既有 run。有工作稿则冻结工作稿。"""
    _require_period(month)
    _require_freeze_auth(x_hcm_freeze_token)
    try:
        return freeze_period(db, month)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

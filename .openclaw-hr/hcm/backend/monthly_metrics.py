"""从 HCM 日常事实表按 period 计算月报，写入不可变主题快照。禁止读 CSV / 宽表。"""

from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from models import (
    CandidateStageEvent,
    EmploymentEvent,
    MonthlyReportDraft,
    MonthlyReportMetricSnapshot,
    MonthlyReportRun,
    OnboardingTask,
    RecruitingCostLine,
    Requisition,
    TrainingEnrollment,
)
from report_columns import (
    ATTRITION_COLS,
    COST_COLS,
    FUNNEL_COLS,
    POSITIONS_COLS,
    RETENTION_COLS,
    TRAINING_COLS,
)

METRIC_VERSION = "2026.09-hcm-v2"
THEMES = (
    "recruitment_funnel",
    "positions_progress",
    "onboarding_retention",
    "training_completion",
    "hiring_cost",
    "attrition",
)
STAGES = ("apply", "screen", "interview", "offer", "hired")


def _ym(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m")


def period_end(period: str) -> datetime:
    y, m = (int(x) for x in period.split("-"))
    last = monthrange(y, m)[1]
    return datetime(y, m, last, 23, 59, 59, tzinfo=timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _pct(n: int, d: int) -> str:
    if d <= 0:
        return "n/a"
    return f"{(n / d) * 100:.1f}%"


def _months_through(period: str, observed: set[str]) -> list[str]:
    return sorted(m for m in observed if m and m <= period)


def compute_payload(db: Session, period: str) -> dict:
    cutoff = period_end(period)
    stages = db.query(CandidateStageEvent).all()
    reqs = db.query(Requisition).all()
    tasks = db.query(OnboardingTask).all()
    enrolls = db.query(TrainingEnrollment).all()
    costs = db.query(RecruitingCostLine).all()
    events = db.query(EmploymentEvent).all()

    by_month_stage: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    hired_dates: dict[str, list[datetime]] = defaultdict(list)
    for ev in stages:
        occurred = _aware(ev.occurred_at)
        month = _ym(occurred)
        if not month or month > period:
            continue
        by_month_stage[month][ev.stage] += 1
        if ev.stage == "hired" and occurred:
            hired_dates[ev.requisition_id].append(occurred)

    funnel_months = _months_through(period, set(by_month_stage))
    funnel = []
    for month in funnel_months:
        c = by_month_stage[month]
        apps, screen, interviews, offers, hired = (c.get(s, 0) for s in STAGES)
        funnel.append(
            {
                "月份": month,
                "投递数": apps,
                "初筛通过": screen,
                "面试": interviews,
                "Offer": offers,
                "入职": hired,
                "投递转初筛率": _pct(screen, apps),
                "面试转Offer率": _pct(offers, interviews),
                "Offer接受率": _pct(hired, offers),
            }
        )

    positions = []
    for req in reqs:
        opened = _aware(req.opened_at)
        if opened and _ym(opened) and _ym(opened) > period:
            continue
        hired_n = sum(1 for d in hired_dates.get(req.requisition_id, []) if _ym(d) and _ym(d) <= period)
        open_hc = max(req.approved_hc - hired_n, 0)
        tth_days = []
        for d in hired_dates.get(req.requisition_id, []):
            if opened and _ym(d) and _ym(d) <= period:
                tth_days.append((d - opened).days)
        avg_days = int(sum(tth_days) / len(tth_days)) if tth_days else int((cutoff - opened).days) if opened else 0
        status = "已完成" if open_hc == 0 else "进行中"
        positions.append(
            {
                "岗位": req.position_title,
                "所属类别": req.category,
                "HC": req.approved_hc,
                "已入职": hired_n,
                "在招中": open_hc,
                "平均在招天数": avg_days,
                "招聘状态": status,
            }
        )

    hires_by_month: dict[str, list[EmploymentEvent]] = defaultdict(list)
    terms: list[EmploymentEvent] = []
    for ev in events:
        occurred = _aware(ev.occurred_at)
        month = _ym(occurred)
        if not month or month > period:
            continue
        if ev.event_type == "hire":
            hires_by_month[month].append(ev)
        elif ev.event_type == "terminate":
            terms.append(ev)

    tasks_by_emp: dict[str, list[OnboardingTask]] = defaultdict(list)
    for t in tasks:
        tasks_by_emp[t.employee_id].append(t)

    retention = []
    for month in _months_through(period, set(hires_by_month)):
        hired_list = hires_by_month.get(month, [])
        hired_count = len(hired_list)
        pass_n = fail_n = leave45 = 0
        pending_45 = False
        for hire in hired_list:
            hired_at = _aware(hire.occurred_at)
            if not hired_at:
                continue
            window_end = hired_at + timedelta(days=45)
            for t in tasks_by_emp.get(hire.employee_id, []):
                if t.task_type != "probation":
                    continue
                if (t.result or "") == "fail":
                    fail_n += 1
                elif (t.result or "") == "pass" or t.completed_at:
                    pass_n += 1
            if cutoff < window_end:
                pending_45 = True
            else:
                for tev in terms:
                    if tev.employee_id != hire.employee_id:
                        continue
                    tocc = _aware(tev.occurred_at)
                    if tocc and hired_at <= tocc <= window_end:
                        leave45 += 1
                        break
        note = "仍在试用期/45天观察期内" if pending_45 else ""
        leave_rate = "统计中" if pending_45 else _pct(leave45, hired_count)
        retention.append(
            {
                "月份": month,
                "入职人数": hired_count,
                "试用期通过": pass_n,
                "试用期未通过": fail_n,
                "45天内离职": 0 if pending_45 else leave45,
                "45天内离职率": leave_rate,
                "备注": note,
            }
        )

    train_months: dict[str, list[TrainingEnrollment]] = defaultdict(list)
    for en in enrolls:
        due = _aware(en.due_at) or _aware(en.assigned_at)
        month = _ym(due)
        if month and month <= period:
            train_months[month].append(en)
    training = []
    for month in _months_through(period, set(train_months)):
        rows = train_months[month]
        expected = sum(1 for r in rows if r.required_flag)
        completed = sum(1 for r in rows if r.required_flag and _aware(r.completed_at) and _ym(_aware(r.completed_at)) <= period)
        sats = [r.satisfaction for r in rows if r.satisfaction is not None and r.completed_at]
        sat = round(sum(sats) / len(sats), 1) if sats else 0.0
        training.append(
            {
                "月份": month,
                "应参训人数": expected,
                "完成人数": completed,
                "完成率": _pct(completed, expected),
                "培训满意度": sat,
                "主要培训内容": "/".join(sorted({r.course_id for r in rows if r.course_id})),
            }
        )

    cost_months: dict[str, list[RecruitingCostLine]] = defaultdict(list)
    for line in costs:
        if line.accounting_period and line.accounting_period <= period:
            cost_months[line.accounting_period].append(line)
    hiring_cost = []
    for month in _months_through(period, set(cost_months)):
        lines = cost_months[month]
        amount = sum(l.amount for l in lines)
        hired_n = by_month_stage.get(month, {}).get("hired", 0)
        tths = []
        for req in reqs:
            opened = _aware(req.opened_at)
            for d in hired_dates.get(req.requisition_id, []):
                if _ym(d) == month and opened:
                    tths.append((d - opened).days)
        hiring_cost.append(
            {
                "月份": month,
                "招聘渠道费用": amount,
                "入职人数": hired_n,
                "人均招聘成本": int(amount / hired_n) if hired_n else "n/a",
                "平均TimeToHire天数": int(sum(tths) / len(tths)) if tths else "n/a",
                "主要费用构成": ",".join(sorted({l.expense_type for l in lines})),
            }
        )

    term_months: dict[str, list[EmploymentEvent]] = defaultdict(list)
    for ev in terms:
        month = _ym(_aware(ev.occurred_at))
        if month and month <= period:
            term_months[month].append(ev)

    hires_all = [e for e in events if e.event_type == "hire" and _ym(_aware(e.occurred_at)) and _ym(_aware(e.occurred_at)) <= period]
    terms_all = [e for e in events if e.event_type == "terminate" and _ym(_aware(e.occurred_at)) and _ym(_aware(e.occurred_at)) <= period]

    attrition = []
    attr_months = set(term_months)
    if hires_by_month or term_months:
        attr_months.add(period)
    for month in _months_through(period, attr_months):
        rows = term_months.get(month, [])
        total = len(rows)
        vol = sum(1 for r in rows if r.voluntary == 1)
        inv = total - vol
        eom_hires = sum(1 for e in hires_all if _ym(_aware(e.occurred_at)) <= month)
        eom_terms = sum(1 for e in terms_all if _ym(_aware(e.occurred_at)) <= month)
        eom = max(eom_hires - eom_terms, 0)
        reasons = defaultdict(int)
        for r in rows:
            reasons[r.reason_code or "other"] += 1
        attrition.append(
            {
                "月份": month,
                "离职总人数": total,
                "主动离职": vol,
                "被动离职": inv,
                "月离职率": _pct(total, eom + total) if (eom + total) else "n/a",
                "薪资原因": reasons.get("salary", 0),
                "发展原因": reasons.get("growth", 0),
                "管理原因": reasons.get("mgmt", 0),
                "家庭原因": reasons.get("family", 0),
                "不胜任": reasons.get("unfit", 0),
            }
        )

    missing = []
    if period not in {r["月份"] for r in funnel}:
        missing.append("招聘阶段事实 candidate_stage_events")
    if not (hires_by_month or term_months):
        missing.append("人事事实 employment_events")
    if period not in {r["月份"] for r in retention}:
        missing.append("入职事实 employment_events/onboarding_tasks")
    if period not in {r["月份"] for r in training}:
        missing.append("培训报名事实 training_enrollments")
    if period not in {r["月份"] for r in hiring_cost}:
        missing.append("招聘费用事实 recruiting_cost_lines")
    if not positions:
        missing.append("编制事实 requisitions")
    if missing:
        raise ValueError("HCM 事实不足，无法冻结: " + "; ".join(missing))

    return {
        "month": period,
        "source": "HCM",
        "metric_version": METRIC_VERSION,
        "data_as_of": cutoff.date().isoformat(),
        "recruitment_funnel": funnel,
        "positions_progress": positions,
        "onboarding_retention": retention,
        "training_completion": training,
        "hiring_cost": hiring_cost,
        "attrition": attrition,
        "node_audit": {
            "recruitment_funnel": "candidate_stage_events.occurred_at 按阶段计数",
            "positions_progress": "requisitions + hired 阶段事件",
            "onboarding_retention": "employment_events hire + onboarding_tasks",
            "training_completion": "training_enrollments due_at/completed_at",
            "hiring_cost": "recruiting_cost_lines.accounting_period",
            "attrition": "employment_events terminate",
        },
    }


def _run_id(period: str, payload: dict) -> str:
    body = json.dumps({k: payload[k] for k in THEMES}, ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    return f"{period}-{METRIC_VERSION}-{digest}"


def assemble_payload(run: MonthlyReportRun, db: Session) -> dict:
    snaps = {
        s.theme: json.loads(s.payload_json)
        for s in db.query(MonthlyReportMetricSnapshot).filter_by(run_id=run.run_id)
    }
    payload = {
        "month": run.period,
        "source": "HCM",
        "metric_version": run.metric_version,
        "report_run_id": run.run_id,
        "frozen_at": run.frozen_at.isoformat(),
        "data_as_of": run.data_as_of,
        "node_audit": snaps.get("_audit") or {},
    }
    for theme in THEMES:
        payload[theme] = snaps.get(theme) or []
    return payload


def _write_freeze(db: Session, period: str, payload: dict) -> dict:
    run_id = _run_id(period, payload)
    now = datetime.now(timezone.utc)
    run = MonthlyReportRun(
        period=period,
        run_id=run_id,
        metric_version=METRIC_VERSION,
        frozen_at=now,
        status="frozen",
        data_as_of=payload.get("data_as_of") or period_end(period).date().isoformat(),
    )
    db.add(run)
    for theme in THEMES:
        db.add(
            MonthlyReportMetricSnapshot(
                run_id=run_id,
                theme=theme,
                payload_json=json.dumps(payload.get(theme) or [], ensure_ascii=False),
            )
        )
    db.add(
        MonthlyReportMetricSnapshot(
            run_id=run_id,
            theme="_audit",
            payload_json=json.dumps(payload.get("node_audit") or {"source": "draft"}, ensure_ascii=False),
        )
    )
    db.commit()
    out = assemble_payload(run, db)
    out["editable"] = False
    out["status"] = "frozen"
    return out


def freeze_period(db: Session, period: str) -> dict:
    existing = (
        db.query(MonthlyReportRun)
        .filter(MonthlyReportRun.period == period, MonthlyReportRun.status == "frozen")
        .first()
    )
    if existing:
        payload = assemble_payload(existing, db)
        payload["editable"] = False
        payload["status"] = "frozen"
        return payload

    draft = _load_draft(db, period)
    if draft:
        payload = dict(draft)
        payload["month"] = period
        payload["source"] = "HCM"
        payload["metric_version"] = METRIC_VERSION
        payload["data_as_of"] = period_end(period).date().isoformat()
        payload["node_audit"] = {"source": "monthly_report_drafts"}
        return _write_freeze(db, period, payload)

    payload = compute_payload(db, period)
    return _write_freeze(db, period, payload)


def get_month(period: str, db: Session) -> dict | None:
    run = (
        db.query(MonthlyReportRun)
        .filter(MonthlyReportRun.period == period, MonthlyReportRun.status == "frozen")
        .first()
    )
    if not run:
        return None
    return assemble_payload(run, db)


def list_frozen_months(db: Session) -> list[str]:
    rows = (
        db.query(MonthlyReportRun.period)
        .filter(MonthlyReportRun.status == "frozen")
        .order_by(MonthlyReportRun.period)
        .all()
    )
    return [r[0] for r in rows]


def list_draft_months(db: Session) -> list[str]:
    rows = db.query(MonthlyReportDraft.period).order_by(MonthlyReportDraft.period).all()
    return [r[0] for r in rows]


THEME_COLS = {
    "recruitment_funnel": FUNNEL_COLS,
    "positions_progress": POSITIONS_COLS,
    "onboarding_retention": RETENTION_COLS,
    "training_completion": TRAINING_COLS,
    "hiring_cost": COST_COLS,
    "attrition": ATTRITION_COLS,
}


def _blank_row(cols: list, period: str) -> dict:
    row = {}
    for zh, _en, kind in cols:
        if zh == "月份":
            row[zh] = period
        elif kind == "str":
            row[zh] = ""
        else:
            row[zh] = 0
    return row


def empty_working_payload(period: str) -> dict:
    payload = {
        "month": period,
        "source": "HCM",
        "metric_version": METRIC_VERSION,
        "status": "empty",
        "editable": True,
        "node_audit": {},
    }
    for theme, cols in THEME_COLS.items():
        payload[theme] = [_blank_row(cols, period)]
    return payload


def _load_draft(db: Session, period: str) -> dict | None:
    row = db.query(MonthlyReportDraft).filter_by(period=period).first()
    if not row:
        return None
    data = json.loads(row.payload_json)
    data["month"] = period
    data["source"] = "HCM"
    data["metric_version"] = METRIC_VERSION
    data["status"] = "draft"
    data["editable"] = True
    data["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return data


def _as_int(val, default: int = 0) -> int:
    try:
        if val in ("", None, "n/a"):
            return default
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _fill_derived(themes: dict) -> dict:
    for row in themes.get("recruitment_funnel") or []:
        apps = _as_int(row.get("投递数"))
        screen = _as_int(row.get("初筛通过"))
        interviews = _as_int(row.get("面试"))
        offers = _as_int(row.get("Offer"))
        hired = _as_int(row.get("入职"))
        if not row.get("投递转初筛率"):
            row["投递转初筛率"] = _pct(screen, apps)
        if not row.get("面试转Offer率"):
            row["面试转Offer率"] = _pct(offers, interviews)
        if not row.get("Offer接受率"):
            row["Offer接受率"] = _pct(hired, offers)
    for row in themes.get("training_completion") or []:
        expected = _as_int(row.get("应参训人数"))
        completed = _as_int(row.get("完成人数"))
        if not row.get("完成率"):
            row["完成率"] = _pct(completed, expected)
    for row in themes.get("hiring_cost") or []:
        amount = _as_int(row.get("招聘渠道费用"))
        hired = _as_int(row.get("入职人数"))
        if not row.get("人均招聘成本"):
            row["人均招聘成本"] = int(amount / hired) if hired else "n/a"
    for row in themes.get("onboarding_retention") or []:
        hired = _as_int(row.get("入职人数"))
        leave = _as_int(row.get("45天内离职"))
        if not row.get("45天内离职率"):
            row["45天内离职率"] = _pct(leave, hired)
    return themes


def save_working(db: Session, period: str, body: dict) -> dict:
    if get_month(period, db):
        raise ValueError(f"月份 {period} 已冻结，不能再改。")
    themes = {}
    for theme in THEMES:
        rows = body.get(theme)
        if not isinstance(rows, list):
            raise ValueError(f"缺少主题 {theme}")
        themes[theme] = rows
    _fill_derived(themes)
    row = db.query(MonthlyReportDraft).filter_by(period=period).first()
    blob = json.dumps(themes, ensure_ascii=False)
    now = datetime.now(timezone.utc)
    if row:
        row.payload_json = blob
        row.updated_at = now
    else:
        db.add(MonthlyReportDraft(period=period, payload_json=blob, updated_at=now))
    db.commit()
    loaded = _load_draft(db, period)
    assert loaded is not None
    return loaded


def get_working(db: Session, period: str) -> dict:
    frozen = get_month(period, db)
    if frozen:
        frozen["editable"] = False
        frozen["status"] = "frozen"
        return frozen
    draft = _load_draft(db, period)
    if draft:
        return draft
    try:
        live = compute_payload(db, period)
        live["editable"] = True
        live["status"] = "live"
        return live
    except ValueError:
        return empty_working_payload(period)

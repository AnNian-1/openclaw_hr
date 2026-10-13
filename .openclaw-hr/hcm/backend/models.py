"""SQLAlchemy ORM models for the HCM system."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    pinyin = Column(String(50), unique=True, nullable=False, index=True)
    role = Column(String(100), nullable=False)
    salary = Column(String(20), nullable=False, default="面议")
    status = Column(String(20), nullable=False, default="onboarding")
    started_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    nodes = relationship("PrepNode", back_populates="candidate", cascade="all, delete-orphan")


class PrepNode(Base):
    __tablename__ = "prep_nodes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    node_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    data = Column(Text, nullable=False, default="{}")
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    candidate = relationship("Candidate", back_populates="nodes")


class Requisition(Base):
    """招聘需求/编制事实。"""

    __tablename__ = "requisitions"

    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(String(80), unique=True, nullable=False, index=True)
    position_title = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, default="")
    org_id = Column(String(40), nullable=False, default="org-demo")
    approved_hc = Column(Integer, nullable=False, default=0)
    opened_at = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class CandidateStageEvent(Base):
    """候选人阶段变更事实。禁止按姓名关联。"""

    __tablename__ = "candidate_stage_events"

    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(String(80), nullable=False, index=True)
    candidate_ref = Column(String(80), nullable=False, index=True)
    stage = Column(String(20), nullable=False, index=True)
    channel = Column(String(40), nullable=False, default="")
    occurred_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class OnboardingTask(Base):
    """入职任务事实。"""

    __tablename__ = "onboarding_tasks"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(80), nullable=False, index=True)
    task_type = Column(String(40), nullable=False)
    owner_system = Column(String(20), nullable=False, default="hcm")
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    waived_at = Column(DateTime, nullable=True)
    hired_at = Column(DateTime, nullable=True)
    result = Column(String(20), nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class TrainingEnrollment(Base):
    """培训报名/完成事实。"""

    __tablename__ = "training_enrollments"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(80), nullable=False, index=True)
    course_id = Column(String(80), nullable=False, default="onboarding")
    required_flag = Column(Integer, nullable=False, default=1)
    assigned_at = Column(DateTime, nullable=False)
    due_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    score = Column(Float, nullable=True)
    satisfaction = Column(Float, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class RecruitingCostLine(Base):
    """招聘费用明细。金额走账期，不是月报人均成本。"""

    __tablename__ = "recruiting_cost_lines"

    id = Column(Integer, primary_key=True, index=True)
    requisition_id = Column(String(80), nullable=False, default="")
    cost_center = Column(String(40), nullable=False, default="")
    amount = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=False, default="CNY")
    expense_type = Column(String(40), nullable=False, default="channel")
    invoice_date = Column(DateTime, nullable=False)
    accounting_period = Column(String(7), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class EmploymentEvent(Base):
    """入职/离职/调动事实。"""

    __tablename__ = "employment_events"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(80), nullable=False, index=True)
    event_type = Column(String(20), nullable=False, index=True)
    reason_code = Column(String(40), nullable=False, default="")
    voluntary = Column(Integer, nullable=True)
    occurred_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class MonthlyReportRun(Base):
    """不可变冻结批次。明细只存在 MonthlyReportMetricSnapshot。"""

    __tablename__ = "monthly_report_runs"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(7), unique=True, nullable=False, index=True)
    run_id = Column(String(80), unique=True, nullable=False, index=True)
    metric_version = Column(String(40), nullable=False)
    frozen_at = Column(DateTime, nullable=False, default=_utcnow)
    status = Column(String(20), nullable=False, default="frozen")
    data_as_of = Column(String(32), nullable=False, default="")


class MonthlyReportDraft(Base):
    """未冻结月报工作稿。冻结后改快照，不再改这里。"""

    __tablename__ = "monthly_report_drafts"

    id = Column(Integer, primary_key=True, index=True)
    period = Column(String(7), unique=True, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class MonthlyReportMetricSnapshot(Base):
    __tablename__ = "monthly_report_metric_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(80), ForeignKey("monthly_report_runs.run_id"), nullable=False, index=True)
    theme = Column(String(40), nullable=False)
    payload_json = Column(Text, nullable=False)

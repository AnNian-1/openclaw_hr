"""启动时丢掉旧月度宽表，并重建缺 data_as_of 的冻结表。"""

from sqlalchemy import inspect, text

from database import engine
from models import Base

OLD_WIDE_TABLES = (
    "recruitment_funnels",
    "recruitment_funnel",
    "positions_progress",
    "onboarding_retentions",
    "onboarding_retention",
    "training_completions",
    "training_completion",
    "hiring_costs",
    "hiring_cost",
    "attritions",
    "attrition",
)


def migrate_schema() -> None:
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in OLD_WIDE_TABLES:
            if table in names:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
        if "reviews" in names:
            conn.execute(text("DROP TABLE IF EXISTS reviews"))
        if "monthly_report_runs" in names:
            cols = {c["name"] for c in inspector.get_columns("monthly_report_runs")}
            if "payload_json" in cols or "data_as_of" not in cols:
                conn.execute(text("DROP TABLE IF EXISTS monthly_report_metric_snapshots"))
                conn.execute(text("DROP TABLE IF EXISTS monthly_report_runs"))
        if "onboarding_tasks" in names:
            cols = {c["name"] for c in inspector.get_columns("onboarding_tasks")}
            if "result" not in cols:
                conn.execute(text("DROP TABLE IF EXISTS onboarding_tasks"))
    Base.metadata.create_all(bind=engine)

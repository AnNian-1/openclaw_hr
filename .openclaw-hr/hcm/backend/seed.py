"""Seed the database from stub-state JSON files.

Usage:
    cd hcm/backend
    python seed.py                    # 生产默认：仅当 workspace stub-state 有数据时导入
    HCM_SEED_FIXTURES=1 python seed.py  # QA：从 .openclaw-hr/fixtures/onboarding-stub-state 导入
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from database import engine, Base, SessionLocal
from models import Candidate, PrepNode, Review

PROFILE = Path(__file__).resolve().parent.parent.parent
WORKSPACE = PROFILE / "workspace-onboarding"
FIXTURES_STUB = PROFILE / "fixtures" / "onboarding-stub-state"
FIXTURES_REVIEW = PROFILE / "fixtures" / "onboarding-review-state"
STUB_STATE_DIR = WORKSPACE / "stub-state"
REVIEW_STATE_DIR = WORKSPACE / "review-state"


def resolve_seed_dirs() -> tuple[Path, Path]:
    """Return (stub-state, review-state) dirs for seeding."""
    if os.environ.get("HCM_SEED_FIXTURES", "").lower() in ("1", "true", "yes"):
        return FIXTURES_STUB, FIXTURES_REVIEW
    stub_override = os.environ.get("HCM_SEED_STUB_STATE")
    if stub_override:
        review_override = os.environ.get("HCM_SEED_REVIEW_STATE", str(FIXTURES_REVIEW))
        return Path(stub_override), Path(review_override)
    return STUB_STATE_DIR, REVIEW_STATE_DIR

NODE_TYPES = ["contract", "account", "device", "training", "buddy"]
REVIEW_TYPES = ["day7", "day30", "day60", "day90"]


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    stub_dir, review_dir = resolve_seed_dirs()

    if not stub_dir.exists():
        print(f"❌ stub-state 目录不存在: {stub_dir}")
        sys.exit(1)

    candidate_dirs = [d for d in sorted(stub_dir.iterdir()) if d.is_dir()]
    if not candidate_dirs:
        print(f"ℹ️  {stub_dir} 无候选人子目录，跳过 seed。")
        print("  QA 演示: HCM_SEED_FIXTURES=1 python seed.py")
        db.close()
        return

    candidates_found = 0
    for candidate_dir in candidate_dirs:
        if not candidate_dir.is_dir():
            continue

        pinyin = candidate_dir.name
        # Read workflow.json for basic info
        workflow_path = candidate_dir / "workflow.json"
        if workflow_path.exists():
            wf = json.loads(workflow_path.read_text(encoding="utf-8"))
            name = wf.get("candidate", pinyin)  # workflow.json uses 'candidate', not 'name'
            role = wf.get("role", "未知岗位")
            salary = wf.get("salary", "面议")
            started_at = parse_dt(wf.get("started_at"))
            # Map workflow status to candidate status
            wf_status = wf.get("status", "")
            wf_status_map = {
                "completed": "completed",
                "cancelled": "cancelled",
                "rejected": "cancelled",
            }
            candidate_status = wf_status_map.get(wf_status, "onboarding")
        else:
            # Fallback: read contract.json
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

        # Check if already exists
        existing = db.query(Candidate).filter(Candidate.pinyin == pinyin).first()
        if existing:
            print(f"⏭  跳过 {name} ({pinyin}) — 已存在")
            continue

        # Create candidate
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

        # Create prep nodes from JSON files
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
                # Map Chinese status to English
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

            db.add(PrepNode(
                candidate_id=candidate.id,
                node_type=node_type,
                status=status,
                data=data_str,
            ))

        # Create review slots
        for rt in REVIEW_TYPES:
            # Reviews are stored as review-state/review-<中文名>-<type>.json
            review_path = review_dir / f"review-{name}-{rt}.json"
            if review_path.exists():
                rv = json.loads(review_path.read_text(encoding="utf-8"))
                review_status = "completed" if rv.get("status") in ("completed", "已跟进") else "pending"
                # Build content from focus + prep_nodes summary
                focus = rv.get("focus", "")
                reviewed_at = rv.get("reviewedAt", "")
                content = f"{focus} (跟进时间: {reviewed_at})" if reviewed_at else focus
                triggered_at = parse_dt(rv.get("triggered_at"))
                completed_at = parse_dt(rv.get("completed_at"))
            else:
                review_status = "pending"
                content = None
                triggered_at = None
                completed_at = None

            db.add(Review(
                candidate_id=candidate.id,
                review_type=rt,
                status=review_status,
                content=content,
                triggered_at=triggered_at,
                completed_at=completed_at,
            ))

        db.commit()
        candidates_found += 1
        print(f"✅ 导入 {name} ({pinyin}) — {role} {salary}")

    db.close()
    print(f"\n🎉 完成！共导入 {candidates_found} 位候选人")


if __name__ == "__main__":
    seed()

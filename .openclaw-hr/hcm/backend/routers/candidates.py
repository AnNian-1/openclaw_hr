"""Candidate CRUD endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Candidate, PrepNode, Review
from schemas import (
    CandidateCreate, CandidateOut, CandidateBrief, CandidateWithNodes,
    PrepNodeUpdate, PrepNodeOut,
)
from websocket import manager

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

# Default prep node types created for every new candidate
NODE_TYPES = ["contract", "account", "device", "training", "buddy"]
REVIEW_TYPES = ["day7", "day30", "day60", "day90"]

# 部门角色 → 唯一可写节点。overview / 缺头 / 错配一律 403（不能只靠前端藏按钮）。
ROLE_TO_NODE = {
    "hr": "contract",
    "it": "account",
    "admin": "device",
    "training": "training",
    "buddy": "buddy",
}


def _require_dept_can_write_node(node_type: str, x_department_role: Optional[str]) -> None:
    role = (x_department_role or "").strip().lower()
    allowed = ROLE_TO_NODE.get(role)
    if allowed is None or allowed != node_type:
        raise HTTPException(
            status_code=403,
            detail="当前部门无权修改该节点",
        )


@router.get("", response_model=list[CandidateWithNodes])
def list_candidates(db: Session = Depends(get_db)):
    """List all candidates with their prep nodes and reviews."""
    candidates = db.query(Candidate).all()
    return candidates


@router.get("/{candidate_id}", response_model=CandidateOut)
def get_candidate(candidate_id: int, db: Session = Depends(get_db)):
    """Get a single candidate with full details."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return candidate


@router.put("/{candidate_id}", response_model=CandidateBrief)
def update_candidate(
    candidate_id: int,
    body: dict = Body(...),
    db: Session = Depends(get_db),
):
    """Update candidate basic info (name, role, salary, status)."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")

    for field in ("name", "role", "salary", "status"):
        if field in body and body[field] is not None:
            setattr(candidate, field, body[field])

    db.commit()
    db.refresh(candidate)
    return candidate


@router.post("", response_model=CandidateOut, status_code=201)
def create_candidate(body: CandidateCreate, db: Session = Depends(get_db)):
    """Create a new candidate and auto-generate all prep nodes + reviews."""
    # Check pinyin uniqueness
    existing = db.query(Candidate).filter(Candidate.pinyin == body.pinyin).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"拼音 '{body.pinyin}' 已存在")

    candidate = Candidate(
        name=body.name,
        pinyin=body.pinyin,
        role=body.role,
        salary=body.salary,
        started_at=body.started_at,
    )
    db.add(candidate)
    db.flush()  # get candidate.id

    # Auto-create 5 prep nodes
    for nt in NODE_TYPES:
        db.add(PrepNode(candidate_id=candidate.id, node_type=nt, status="pending", data="{}"))

    # Auto-create 4 review slots
    for rt in REVIEW_TYPES:
        db.add(Review(candidate_id=candidate.id, review_type=rt, status="pending"))

    db.commit()
    db.refresh(candidate)
    return candidate


@router.put("/{candidate_id}/prep/{node_type}", response_model=PrepNodeOut)
async def update_prep_node(
    candidate_id: int,
    node_type: str,
    body: PrepNodeUpdate,
    db: Session = Depends(get_db),
    x_department_role: Optional[str] = Header(default=None, alias="X-Department-Role"),
):
    """Update a specific prep node status/data. Called by department frontends."""
    if node_type not in NODE_TYPES:
        raise HTTPException(status_code=400, detail=f"无效节点类型: {node_type}")
    _require_dept_can_write_node(node_type, x_department_role)

    node = (
        db.query(PrepNode)
        .filter(PrepNode.candidate_id == candidate_id, PrepNode.node_type == node_type)
        .first()
    )
    if not node:
        raise HTTPException(status_code=404, detail="节点不存在")

    if body.status is not None:
        node.status = body.status
    if body.data is not None:
        # Merge: existing data + new fields (new values overwrite old)
        existing = json.loads(node.data) if node.data else {}
        existing.update(body.data)
        node.data = json.dumps(existing, ensure_ascii=False)

    db.commit()
    db.refresh(node)

    # Broadcast real-time update to dashboard
    await manager.broadcast("node_updated", {
        "candidate_id": candidate_id,
        "node_type": node_type,
        "status": node.status,
        "data": json.loads(node.data) if node.data else {},
    })

    return node


@router.get("/{candidate_id}/nodes", response_model=list[PrepNodeOut])
def list_nodes(candidate_id: int, db: Session = Depends(get_db)):
    """List all prep nodes for a candidate."""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return candidate.nodes

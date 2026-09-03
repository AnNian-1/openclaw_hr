"""Pydantic schemas for request/response validation."""

import json
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ── PrepNode ──────────────────────────────────────────────

class PrepNodeBase(BaseModel):
    node_type: str = Field(..., pattern="^(contract|account|device|training|buddy)$")
    status: str = Field(default="pending", pattern="^(pending|in_progress|completed|paused|rejected)$")
    data: dict = Field(default_factory=dict)


class PrepNodeUpdate(BaseModel):
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|paused|rejected)$")
    data: Optional[dict] = None


class PrepNodeOut(PrepNodeBase):
    id: int
    candidate_id: int
    updated_at: datetime

    @field_validator("data", mode="before")
    @classmethod
    def parse_data(cls, v: Any) -> dict:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        return v if isinstance(v, dict) else {}

    class Config:
        from_attributes = True


# ── Candidate ─────────────────────────────────────────────

class CandidateCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    pinyin: str = Field(..., min_length=1, max_length=50)
    role: str = Field(..., min_length=1, max_length=100)
    salary: str = Field(default="面议", max_length=20)
    started_at: Optional[datetime] = None


class CandidateOut(BaseModel):
    id: int
    name: str
    pinyin: str
    role: str
    salary: str
    status: str
    started_at: Optional[datetime] = None
    created_at: datetime
    nodes: list[PrepNodeOut] = []

    class Config:
        from_attributes = True


class CandidateBrief(BaseModel):
    """Lightweight candidate info for list views."""
    id: int
    name: str
    pinyin: str
    role: str
    salary: str
    status: str
    started_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CandidateWithNodes(CandidateBrief):
    nodes: list[PrepNodeOut] = []

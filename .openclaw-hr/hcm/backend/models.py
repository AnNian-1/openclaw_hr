"""SQLAlchemy ORM models for the HCM system."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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
    node_type = Column(String(20), nullable=False)  # contract/account/device/training/buddy
    status = Column(String(20), nullable=False, default="pending")
    data = Column(Text, nullable=False, default="{}")  # JSON string
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    candidate = relationship("Candidate", back_populates="nodes")


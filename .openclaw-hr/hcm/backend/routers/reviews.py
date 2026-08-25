"""Review management endpoints."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Review
from schemas import ReviewOut, ReviewUpdate
from websocket import manager

router = APIRouter(prefix="/api/candidates", tags=["reviews"])


@router.get("/{candidate_id}/reviews", response_model=list[ReviewOut])
def list_reviews(candidate_id: int, db: Session = Depends(get_db)):
    """List all reviews for a candidate."""
    reviews = db.query(Review).filter(Review.candidate_id == candidate_id).all()
    return reviews


@router.put("/{candidate_id}/reviews/{review_type}", response_model=ReviewOut)
async def update_review(
    candidate_id: int,
    review_type: str,
    body: ReviewUpdate,
    db: Session = Depends(get_db),
):
    """Update a review status/content. Called by department frontends."""
    if review_type not in ("day7", "day30", "day60", "day90"):
        raise HTTPException(status_code=400, detail=f"无效 review 类型: {review_type}")

    review = (
        db.query(Review)
        .filter(Review.candidate_id == candidate_id, Review.review_type == review_type)
        .first()
    )
    if not review:
        raise HTTPException(status_code=404, detail="Review 不存在")

    if body.status is not None:
        review.status = body.status
        if body.status == "completed":
            review.completed_at = datetime.now(timezone.utc)
    if body.content is not None:
        review.content = body.content

    db.commit()
    db.refresh(review)

    # Broadcast real-time update to dashboard
    await manager.broadcast("review_updated", {
        "candidate_id": candidate_id,
        "review_type": review_type,
        "status": review.status,
        "content": review.content,
    })

    return review

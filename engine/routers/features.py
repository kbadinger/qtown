"""Features router — feature submissions and voting."""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from engine.auth import require_admin
from engine.db import get_db
from engine.models import Feature, Vote
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/features", tags=["features"])


class FeatureCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class FeatureResponse(BaseModel):
    id: int
    title: str
    description: str | None
    submitted_by_ip: str | None
    status: str
    vote_count: int
    prd_story_id: str | None
    prd_title: str | None
    prd_description: str | None
    prd_test_file: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/")
def list_features(db: Session = Depends(get_db)):
    from engine.models import Feature
    features = db.query(Feature).order_by(Feature.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "submitted_by_ip": f.submitted_by_ip,
            "status": f.status,
            "vote_count": f.vote_count,
            "created_at": f.created_at.isoformat(),
            "updated_at": f.updated_at.isoformat(),
        }
        for f in features
    ]


@router.get("/{feature_id}")
def get_feature(feature_id: int, db: Session = Depends(get_db)):
    from engine.models import Feature
    feature = db.query(Feature).filter_by(id=feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return {
        "id": feature.id,
        "title": feature.title,
        "description": feature.description,
        "submitted_by_ip": feature.submitted_by_ip,
        "status": feature.status,
        "vote_count": feature.vote_count,
        "created_at": feature.created_at.isoformat(),
        "updated_at": feature.updated_at.isoformat(),
    }


@router.post("/", status_code=201)
def create_feature(
    data: FeatureCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    from engine.models import Feature
    voter_ip = request.client.host if request.client else None
    feature = Feature(
        title=data.title,
        description=data.description,
        submitted_by_ip=voter_ip,
        status="submitted",
        vote_count=0,
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return {
        "id": feature.id,
        "title": feature.title,
        "description": feature.description,
        "submitted_by_ip": feature.submitted_by_ip,
        "status": feature.status,
        "vote_count": feature.vote_count,
        "created_at": feature.created_at.isoformat(),
        "updated_at": feature.updated_at.isoformat(),
    }


@router.post("/{feature_id}/vote")
def vote_for_feature(
    feature_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    from engine.models import Feature, Vote
    from sqlalchemy.exc import IntegrityError

    feature = db.query(Feature).filter_by(id=feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    voter_ip = request.client.host if request.client else None
    if not voter_ip:
        raise HTTPException(status_code=400, detail="Could not determine voter IP")

    # Check if vote already exists for this feature + IP combination
    existing_vote = (
        db.query(Vote)
        .filter(Vote.feature_id == feature_id, Vote.voter_ip == voter_ip)
        .first()
    )

    if existing_vote:
        raise HTTPException(status_code=409, detail="Vote already recorded from this IP")

    # Create new vote
    vote = Vote(feature_id=feature_id, voter_ip=voter_ip)
    db.add(vote)

    # Increment feature vote count
    feature.vote_count += 1

    db.commit()
    db.refresh(feature)

    return {
        "id": feature.id,
        "title": feature.title,
        "vote_count": feature.vote_count,
        "message": "Vote recorded successfully",
    }


@router.post("/{feature_id}/approve", status_code=200)
def approve_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import Feature
    feature = db.query(Feature).filter_by(id=feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    feature.status = "approved"
    db.commit()
    db.refresh(feature)

    return {
        "id": feature.id,
        "title": feature.title,
        "status": feature.status,
        "vote_count": feature.vote_count,
    }


@router.post("/{feature_id}/reject", status_code=200)
def reject_feature(
    feature_id: int,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin),
):
    from engine.models import Feature
    feature = db.query(Feature).filter_by(id=feature_id).first()
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")

    feature.status = "rejected"
    db.commit()
    db.refresh(feature)

    return {
        "id": feature.id,
        "title": feature.title,
        "status": feature.status,
        "vote_count": feature.vote_count,
    }
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from engine.db import get_db

router = APIRouter(prefix="/api/features", tags=["features"])


class FeatureCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str | None = None


class FeatureResponse(BaseModel):
    id: int
    title: str
    description: str | None
    vote_count: int
    status: str
    created_at: str

    class Config:
        from_attributes = True


@router.get("/")
def list_features(db: Session = Depends(get_db)):
    from engine.models import Feature
    features = db.query(Feature).all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "description": f.description,
            "vote_count": f.vote_count,
            "status": f.status,
            "created_at": f.created_at.isoformat(),
        }
        for f in features
    ]


@router.post("/", status_code=201)
def create_feature(
    data: FeatureCreate,
    db: Session = Depends(get_db),
):
    from engine.models import Feature
    feature = Feature(
        title=data.title,
        description=data.description,
    )
    db.add(feature)
    db.commit()
    db.refresh(feature)
    return {
        "id": feature.id,
        "title": feature.title,
        "description": feature.description,
        "vote_count": feature.vote_count,
        "status": feature.status,
        "created_at": feature.created_at.isoformat(),
    }
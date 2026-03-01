"""All data models — single source of truth for the DB schema."""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from engine.db import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Tile(Base):
    __tablename__ = "tiles"

    id = Column(Integer, primary_key=True, index=True)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    terrain = Column(String(32), nullable=False, default="grass")

    __table_args__ = (UniqueConstraint("x", "y", name="uq_tile_xy"),)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False)
    key_hash = Column(String(128), nullable=False)
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    submitted_by_ip = Column(String(45), nullable=True)
    status = Column(String(20), nullable=False, default="submitted")
    vote_count = Column(Integer, default=0)

    # PRD staging fields — populated when admin converts to a story
    prd_story_id = Column(String(10), nullable=True)
    prd_title = Column(String(200), nullable=True)
    prd_description = Column(Text, nullable=True)
    prd_test_file = Column(String(200), nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    votes = relationship("Vote", back_populates="feature", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    feature_id = Column(Integer, ForeignKey("features.id"), nullable=False)
    voter_ip = Column(String(45), nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    feature = relationship("Feature", back_populates="votes")

    __table_args__ = (
        UniqueConstraint("feature_id", "voter_ip", name="uq_vote_feature_ip"),
    )

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


class WorldState(Base):
    __tablename__ = "world_state"

    id = Column(Integer, primary_key=True, index=True)
    tick = Column(Integer, default=0)
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


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    building_type = Column(String(64), nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    capacity = Column(Integer, default=10)
    created_at = Column(DateTime, default=_utcnow)


class NPC(Base):
    __tablename__ = "npcs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    role = Column(String(64), nullable=False)
    x = Column(Integer, nullable=False)
    y = Column(Integer, nullable=False)
    gold = Column(Integer, default=0)
    hunger = Column(Integer, default=0)
    energy = Column(Integer, default=100)
    home_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    work_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    target_x = Column(Integer, nullable=True)
    target_y = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    home_building = relationship("Building", foreign_keys=[home_building_id])
    work_building = relationship("Building", foreign_keys=[work_building_id])


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("npcs.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("npcs.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    sender = relationship("NPC", foreign_keys=[sender_id])
    receiver = relationship("NPC", foreign_keys=[receiver_id])
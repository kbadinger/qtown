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
    day = Column(Integer, default=1)
    time_of_day = Column(String(32), default="morning")
    weather = Column(String(32), nullable=True)
    base_wage = Column(Integer, default=10)
    last_wage_adjustment_tick = Column(Integer, default=0)
    inflation_rate = Column(Float, default=0.0)
    economic_status = Column(String(32), default="normal")
    tax_rate = Column(Float, default=0.10)
    drought_active = Column(Integer, default=0)
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
    happiness = Column(Integer, default=50)
    age = Column(Integer, default=20)
    max_age = Column(Integer, default=80)
    is_dead = Column(Integer, default=0)
    illness_severity = Column(Integer, default=0)
    home_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    work_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    target_x = Column(Integer, nullable=True)
    target_y = Column(Integer, nullable=True)
    personality = Column(String(256), nullable=True, default='{}')
    skill = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    home_building = relationship("Building", foreign_keys=[home_building_id])
    work_building = relationship("Building", foreign_keys=[work_building_id])


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("npcs.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("npcs.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    reason = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    sender = relationship("NPC", foreign_keys=[sender_id])
    receiver = relationship("NPC", foreign_keys=[receiver_id])


class Resource(Base):
    __tablename__ = "resources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(64), nullable=False)
    quantity = Column(Integer, default=0)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    is_saturated = Column(Integer, default=0)
    consecutive_oversupply_ticks = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow)

    building = relationship("Building", foreign_keys=[building_id])


class Treasury(Base):
    __tablename__ = "treasuries"

    id = Column(Integer, primary_key=True, index=True)
    gold_stored = Column(Integer, default=0)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    building = relationship("Building", foreign_keys=[building_id])


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(64), nullable=False)
    description = Column(String(256), nullable=False)
    tick = Column(Integer, nullable=False)
    severity = Column(String(16), nullable=False, default="info")
    affected_npc_id = Column(Integer, ForeignKey("npcs.id"), nullable=True)
    affected_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow)

    affected_npc = relationship("NPC", foreign_keys=[affected_npc_id])
    affected_building = relationship("Building", foreign_keys=[affected_building_id])


class Relationship(Base):
    __tablename__ = "relationships"
    
    id = Column(Integer, primary_key=True, index=True)
    npc_id = Column(Integer, ForeignKey("npcs.id"), nullable=False, index=True)
    target_npc_id = Column(Integer, ForeignKey("npcs.id"), nullable=False, index=True)
    relationship_type = Column(String(20), nullable=False)  # e.g., "friend", "rival", "family"
    strength = Column(Integer, default=0)  # 0 to 100
    
    # Unique constraint to prevent duplicate relationships between the same pair
    __table_args__ = (
        UniqueConstraint('npc_id', 'target_npc_id', name='unique_relationship_pair'),
    )


class PriceHistory(Base):
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    resource_name = Column(String(64), nullable=False, index=True)
    price = Column(Float, nullable=False)
    supply = Column(Integer, nullable=False)
    demand = Column(Integer, nullable=False)
    tick = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        UniqueConstraint("resource_name", "tick", name="uq_price_history_resource_tick"),
    )

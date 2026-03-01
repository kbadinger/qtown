"""Database setup — supports SQLite (dev/test) and Postgres (production via Neon)."""

import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Production uses PROD_DATABASE_URL (Neon Postgres), local uses DATABASE_URL (SQLite)
_env = os.getenv("QTOWN_ENV", "development")
if _env == "production":
    DATABASE_URL = os.getenv("PROD_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./town.db"))
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./town.db")

# SQLite needs check_same_thread=False for FastAPI
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite (better concurrent read performance)
if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_wal(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session, closes on completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables. Safe to call multiple times."""
    Base.metadata.create_all(bind=engine)

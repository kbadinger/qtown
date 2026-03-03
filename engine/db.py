"""Database setup — supports SQLite (dev/test) and Postgres (production via Neon)."""

import os

from sqlalchemy import create_engine, event, inspect, text
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


def _auto_migrate():
    """Add missing columns to existing tables.

    create_all() creates new tables but won't add columns to existing ones.
    This scans for columns defined in models but missing from the DB and
    runs ALTER TABLE ADD COLUMN for each. Safe for both SQLite and Postgres.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # New table — create_all() will handle it

        existing_cols = {c["name"] for c in inspector.get_columns(table_name)}

        for col in table.columns:
            if col.name in existing_cols:
                continue

            # Build column type for this dialect
            col_type = col.type.compile(dialect=engine.dialect)

            # Build default clause
            default_clause = ""
            if col.default is not None:
                val = col.default.arg
                if callable(val):
                    pass  # Can't express callable defaults in ALTER TABLE
                elif isinstance(val, str):
                    default_clause = f" DEFAULT '{val}'"
                else:
                    default_clause = f" DEFAULT {val}"

            nullable = "" if col.nullable else " NOT NULL"
            # Can't add NOT NULL without default on existing rows
            if not col.nullable and not default_clause:
                nullable = ""  # Skip NOT NULL to avoid breaking existing rows

            sql = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}{default_clause}{nullable}'
            try:
                with engine.begin() as conn:
                    conn.execute(text(sql))
                print(f"[qtown] Auto-migrate: added {table_name}.{col.name} ({col_type})")
            except Exception as e:
                # Column might already exist (race condition) or syntax issue
                print(f"[qtown] Auto-migrate skip {table_name}.{col.name}: {e}")


def init_db():
    """Create all tables and migrate missing columns. Safe to call multiple times."""
    Base.metadata.create_all(bind=engine)
    _auto_migrate()

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


# Columns added to existing tables after their initial release. `create_all()`
# only creates missing *tables*, never new columns on a table that already
# exists, so an already-running database would be missing these. Rather than
# pull in a full migration tool (this is a toy app), we self-heal on startup:
# `ensure_columns()` adds any that are absent. The DDL types are chosen to be
# valid on both SQLite (tests) and PostgreSQL (dev/prod).
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    # (table, column, column_type) — the emotion-targeting mood profile.
    ("users", "mood", "VARCHAR"),
    # Which reaction wave a job belongs to, for the bot-to-bot "dead internet" loop.
    ("bot_reaction_jobs", "generation", "INTEGER"),
]


def ensure_columns(bind: Engine = engine) -> None:
    """Idempotently backfill post-release columns onto existing tables.

    A no-op on a freshly created database (create_all already made the columns)
    and safe to run on every startup.
    """
    inspector = inspect(bind)
    tables = set(inspector.get_table_names())
    for table, column, column_type in _ADDED_COLUMNS:
        if table not in tables:
            continue  # a fresh DB gets the table (with the column) from create_all
        existing = {col["name"] for col in inspector.get_columns(table)}
        if column not in existing:
            with bind.begin() as conn:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}"))


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

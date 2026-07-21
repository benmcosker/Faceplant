from sqlalchemy import create_engine, inspect, text

from app.db import ensure_columns


def _columns(engine, table):
    return {col["name"] for col in inspect(engine).get_columns(table)}


def test_ensure_columns_adds_missing_mood(tmp_path):
    # Simulate an older database whose users table predates the mood column.
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR)"))
    assert "mood" not in _columns(engine, "users")

    ensure_columns(engine)
    assert "mood" in _columns(engine, "users")


def test_ensure_columns_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR)"))

    ensure_columns(engine)
    # A second run must not error (column already present).
    ensure_columns(engine)
    assert "mood" in _columns(engine, "users")


def test_ensure_columns_noop_without_table(tmp_path):
    # No users table yet (fresh DB before create_all) — must not raise.
    engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
    ensure_columns(engine)
    assert "users" not in set(inspect(engine).get_table_names())


def test_ensure_columns_adds_missing_email(tmp_path):
    # Simulate an older database that predates magic-link auth.
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR)"))
    assert "email" not in _columns(engine, "users")

    ensure_columns(engine)
    assert "email" in _columns(engine, "users")

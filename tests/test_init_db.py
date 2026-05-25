import json
import sqlite3
from pathlib import Path

import pytest

from scripts.init_db import _ALL_TABLES, db_summary, init_db, reset_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

def test_init_db_creates_all_tables(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    tables = _table_names(conn)
    conn.close()
    for table in _ALL_TABLES:
        assert table in tables, f"Missing table: {table}"


def test_init_db_creates_file(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.close()
    assert db_path.exists()


def test_init_db_is_idempotent(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.close()
    conn = init_db(db_path)
    tables = _table_names(conn)
    conn.close()
    for table in _ALL_TABLES:
        assert table in tables


def test_init_db_idempotent_preserves_data(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sources (id, name, site_url, source_type) VALUES (?, ?, ?, ?)",
        ("test_src", "Test Source", "https://example.com", "blog"),
    )
    conn.commit()
    conn.close()

    conn = init_db(db_path)
    (count,) = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    conn.close()
    assert count == 1


def test_init_db_creates_parent_dirs(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "test.sqlite"
    conn = init_db(db_path)
    conn.close()
    assert db_path.exists()


# ---------------------------------------------------------------------------
# reset_db
# ---------------------------------------------------------------------------

def test_reset_db_recreates_tables(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sources (id, name, site_url, source_type) VALUES (?, ?, ?, ?)",
        ("src1", "Src One", "https://example.com", "magazine"),
    )
    conn.commit()
    conn.close()

    conn = reset_db(db_path)
    tables = _table_names(conn)
    (count,) = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    conn.close()

    for table in _ALL_TABLES:
        assert table in tables
    assert count == 0


def test_reset_db_on_nonexistent_file(tmp_path):
    db_path = tmp_path / "fresh.sqlite"
    assert not db_path.exists()
    conn = reset_db(db_path)
    tables = _table_names(conn)
    conn.close()
    for table in _ALL_TABLES:
        assert table in tables


# ---------------------------------------------------------------------------
# items — url_hash uniqueness
# ---------------------------------------------------------------------------

def test_items_url_hash_unique_constraint(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)

    conn.execute(
        "INSERT INTO items (title, url_hash) VALUES (?, ?)",
        ("Item A", "abc123"),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO items (title, url_hash) VALUES (?, ?)",
            ("Item B", "abc123"),
        )
        conn.commit()

    conn.close()


def test_items_null_url_hash_allowed(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)

    conn.execute(
        "INSERT INTO items (title, url_hash) VALUES (?, NULL)",
        ("Editor note A",),
    )
    conn.execute(
        "INSERT INTO items (title, url_hash) VALUES (?, NULL)",
        ("Editor note B",),
    )
    conn.commit()

    (count,) = conn.execute("SELECT COUNT(*) FROM items").fetchone()
    conn.close()
    assert count == 2


# ---------------------------------------------------------------------------
# db_summary
# ---------------------------------------------------------------------------

def test_db_summary_returns_all_tables(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    summary = db_summary(conn)
    conn.close()

    assert "tables" in summary
    for table in _ALL_TABLES:
        assert table in summary["tables"], f"Missing in summary: {table}"


def test_db_summary_counts_are_integers(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    summary = db_summary(conn)
    conn.close()

    for table, count in summary["tables"].items():
        assert isinstance(count, int), f"Count for {table} is not int"


def test_db_summary_reflects_inserted_rows(tmp_path):
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.execute(
        "INSERT INTO sources (id, name, site_url, source_type) VALUES (?, ?, ?, ?)",
        ("s1", "Source One", "https://example.com", "blog"),
    )
    conn.commit()
    summary = db_summary(conn)
    conn.close()

    assert summary["tables"]["sources"] == 1

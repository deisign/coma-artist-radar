import sqlite3
from pathlib import Path

import pytest

from scripts.init_db import init_db
from scripts.sync_sources_to_db import sync_sources


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _source_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    (n,) = conn.execute("SELECT COUNT(*) FROM sources").fetchone()
    conn.close()
    return n


def _get_source(db_path: Path, source_id: str) -> dict | None:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT id, name, priority, active FROM sources WHERE id = ?",
        (source_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return {"id": row[0], "name": row[1], "priority": row[2], "active": row[3]}


# ---------------------------------------------------------------------------
# Import from real sources_music.yaml
# ---------------------------------------------------------------------------

def test_sync_imports_all_sources(tmp_path):
    db_path = tmp_path / "test.sqlite"
    summary = sync_sources(db_path=db_path)

    assert summary["total_in_yaml"] >= 25
    assert summary["inserted"] == summary["total_in_yaml"]
    assert summary["updated"] == 0
    assert _source_count(db_path) == summary["total_in_yaml"]


def test_sync_second_run_does_not_duplicate(tmp_path):
    db_path = tmp_path / "test.sqlite"
    s1 = sync_sources(db_path=db_path)
    s2 = sync_sources(db_path=db_path)

    assert s2["inserted"] == 0
    assert s2["updated"] == s1["total_in_yaml"]
    assert _source_count(db_path) == s1["total_in_yaml"]


def test_sync_active_inactive_counts(tmp_path):
    db_path = tmp_path / "test.sqlite"
    summary = sync_sources(db_path=db_path)

    assert summary["active"] + summary["inactive"] == summary["total_in_yaml"]
    assert summary["active"] > 0


# ---------------------------------------------------------------------------
# Update behaviour
# ---------------------------------------------------------------------------

def test_sync_updates_changed_name(tmp_path):
    db_path = tmp_path / "test.sqlite"
    sync_sources(db_path=db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE sources SET name = 'Old Name' WHERE id = 'norton_records'"
    )
    conn.commit()
    conn.close()

    sync_sources(db_path=db_path)

    src = _get_source(db_path, "norton_records")
    assert src is not None
    assert src["name"] == "Norton Records"


def test_sync_updates_changed_priority(tmp_path):
    db_path = tmp_path / "test.sqlite"
    sync_sources(db_path=db_path)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE sources SET priority = 'low' WHERE id = 'bandcamp_daily'"
    )
    conn.commit()
    conn.close()

    sync_sources(db_path=db_path)

    src = _get_source(db_path, "bandcamp_daily")
    assert src is not None
    assert src["priority"] == "high"


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_required_keys(tmp_path):
    db_path = tmp_path / "test.sqlite"
    summary = sync_sources(db_path=db_path)

    for key in ("total_in_yaml", "inserted", "updated", "active", "inactive"):
        assert key in summary, f"Missing key: {key}"


def test_summary_counts_are_integers(tmp_path):
    db_path = tmp_path / "test.sqlite"
    summary = sync_sources(db_path=db_path)

    for key in ("total_in_yaml", "inserted", "updated", "active", "inactive"):
        assert isinstance(summary[key], int), f"{key} should be int"


# ---------------------------------------------------------------------------
# DB is initialised automatically if absent
# ---------------------------------------------------------------------------

def test_sync_creates_db_if_absent(tmp_path):
    db_path = tmp_path / "auto_created.sqlite"
    assert not db_path.exists()
    sync_sources(db_path=db_path)
    assert db_path.exists()
    assert _source_count(db_path) > 0

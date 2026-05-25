#!/usr/bin/env python3
"""Initialize (or reset) data/coma_radar.sqlite with the full Radar schema.

Usage:
    python3 scripts/init_db.py                # create if absent, safe on re-run
    python3 scripts/init_db.py --reset        # drop existing db and recreate
    python3 scripts/init_db.py --summary      # print JSON with table list and row counts
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

_DDL_ARTISTS = """
CREATE TABLE IF NOT EXISTS artists (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    artist_raw       TEXT    NOT NULL,
    artist_canonical TEXT    NOT NULL,
    track_count      INTEGER NOT NULL DEFAULT 0,
    monitor_priority TEXT,
    ignore           INTEGER NOT NULL DEFAULT 0,
    notes            TEXT,
    created_at       TEXT,
    updated_at       TEXT
)
"""

_DDL_SOURCES = """
CREATE TABLE IF NOT EXISTS sources (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    site_url    TEXT NOT NULL,
    feed_url    TEXT,
    source_type TEXT NOT NULL,
    language    TEXT,
    region      TEXT,
    genre_tags  TEXT,
    priority    TEXT,
    active      INTEGER,
    paywall     TEXT,
    notes       TEXT,
    created_at  TEXT,
    updated_at  TEXT
)
"""

_DDL_LABELS = """
CREATE TABLE IF NOT EXISTS labels (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL UNIQUE,
    site_url   TEXT,
    region     TEXT,
    notes      TEXT,
    created_at TEXT,
    updated_at TEXT
)
"""

_DDL_ITEMS = """
CREATE TABLE IF NOT EXISTS items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT    NOT NULL,
    url                 TEXT,
    canonical_url       TEXT,
    url_hash            TEXT    UNIQUE,
    title_hash          TEXT,
    source_id           TEXT,
    source_name         TEXT,
    source_type         TEXT,
    published_at        TEXT,
    first_seen_at       TEXT,
    last_seen_at        TEXT,
    matched_artists     TEXT,
    matched_tags        TEXT,
    matched_genres      TEXT,
    score               INTEGER NOT NULL DEFAULT 0,
    included_in_issue   INTEGER NOT NULL DEFAULT 0,
    issue_id            TEXT,
    created_at          TEXT,
    updated_at          TEXT
)
"""

_DDL_SEEN_URLS = """
CREATE TABLE IF NOT EXISTS seen_urls (
    url_hash      TEXT PRIMARY KEY,
    canonical_url TEXT,
    first_seen_at TEXT,
    last_seen_at  TEXT,
    source_id     TEXT,
    item_id       INTEGER
)
"""

_DDL_ISSUES = """
CREATE TABLE IF NOT EXISTS issues (
    id          TEXT PRIMARY KEY,
    issue_date  TEXT NOT NULL,
    lang        TEXT NOT NULL,
    title       TEXT,
    status      TEXT,
    path        TEXT,
    item_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT,
    updated_at  TEXT
)
"""

_DDL_HUMAN_SUBMISSIONS = """
CREATE TABLE IF NOT EXISTS human_submissions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at     TEXT    NOT NULL,
    submitted_by     TEXT    NOT NULL DEFAULT 'Vadim',
    source_type      TEXT    NOT NULL,
    url              TEXT,
    title            TEXT    NOT NULL,
    notes            TEXT,
    suggested_genres  TEXT,
    suggested_artists TEXT,
    priority         TEXT    NOT NULL DEFAULT 'normal',
    status           TEXT    NOT NULL DEFAULT 'new',
    used_in_issue    INTEGER NOT NULL DEFAULT 0,
    issue_date       TEXT,
    created_by       TEXT    NOT NULL DEFAULT 'Vadim',
    entry_hash       TEXT    NOT NULL UNIQUE
)
"""

_ALL_DDL = [
    _DDL_ARTISTS,
    _DDL_SOURCES,
    _DDL_LABELS,
    _DDL_ITEMS,
    _DDL_SEEN_URLS,
    _DDL_ISSUES,
    _DDL_HUMAN_SUBMISSIONS,
]

_ALL_TABLES = [
    "artists",
    "sources",
    "labels",
    "items",
    "seen_urls",
    "issues",
    "human_submissions",
]


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def init_db(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Open (or create) the database and apply all DDL idempotently.

    Returns an open connection. Caller is responsible for closing it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    for ddl in _ALL_DDL:
        conn.execute(ddl)
    conn.commit()
    return conn


def reset_db(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    """Delete the existing database file and create a fresh one."""
    if path.exists():
        path.unlink()
    return init_db(path)


def db_summary(conn: sqlite3.Connection) -> dict:
    """Return a dict with table names and row counts."""
    tables = {}
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    for (name,) in rows:
        (count,) = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()
        tables[name] = count
    return {"tables": tables}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Initialize the coma.fm Radar SQLite database."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to the SQLite database (default: data/coma_radar.sqlite)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the existing database and create a fresh one",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print JSON summary of tables and row counts, then exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.reset:
        conn = reset_db(args.db)
        print(f"Reset: {args.db}")
    else:
        conn = init_db(args.db)
        print(f"Ready: {args.db}")

    if args.summary:
        summary = db_summary(conn)
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

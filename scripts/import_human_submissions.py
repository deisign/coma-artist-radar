#!/usr/bin/env python3
"""Import editorial inbox entries from inbox/manual.md into data/coma_radar.sqlite.

Usage:
    python3 scripts/import_human_submissions.py
    python3 scripts/import_human_submissions.py --dry-run
    python3 scripts/import_human_submissions.py --inbox inbox/manual.md --db data/coma_radar.sqlite
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INBOX = _REPO_ROOT / "inbox" / "manual.md"
DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"
DEFAULT_SUBMITTED_BY = "Vadim"

VALID_PRIORITIES = {"low", "normal", "high", "must_use"}
VALID_STATUSES = {"new", "reviewed", "accepted", "rejected", "used", "archived"}
VALID_SOURCE_TYPES = {"link", "editor_note"}

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS human_submissions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    submitted_at     TEXT    NOT NULL,
    submitted_by     TEXT    NOT NULL DEFAULT 'Vadim',
    source_type      TEXT    NOT NULL,
    url              TEXT,
    title            TEXT    NOT NULL,
    notes            TEXT,
    suggested_genres TEXT,
    suggested_artists TEXT,
    priority         TEXT    NOT NULL DEFAULT 'normal',
    status           TEXT    NOT NULL DEFAULT 'new',
    used_in_issue    INTEGER NOT NULL DEFAULT 0,
    issue_date       TEXT,
    created_by       TEXT    NOT NULL DEFAULT 'Vadim',
    entry_hash       TEXT    NOT NULL UNIQUE
)
"""

_INSERT = """
INSERT OR IGNORE INTO human_submissions
    (submitted_at, submitted_by, source_type, url, title, notes,
     suggested_genres, suggested_artists, priority, status,
     used_in_issue, issue_date, created_by, entry_hash)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?)
"""


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_inbox(path: Path) -> list[dict]:
    """Parse manual.md into a list of raw entry dicts."""
    text = path.read_text(encoding="utf-8")
    blocks = re.split(r"(?m)^---\s*$", text)
    entries: list[dict] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            data = yaml.safe_load(stripped)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            entries.append(data)
    return entries


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _normalize_list_field(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if v)
    return str(value).strip()


def validate_submission(entry: dict) -> dict:
    """Normalise and validate a raw entry dict.

    Raises ValueError with a descriptive message on invalid priority, status,
    source_type, or missing title.
    """
    source_type = str(entry.get("type", "link")).strip().lower()
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(
            f"Invalid source_type {source_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}"
        )

    title = str(entry.get("title", "")).strip()
    if not title:
        raise ValueError("Missing required field: title")

    priority = str(entry.get("priority", "normal")).strip().lower()
    if priority not in VALID_PRIORITIES:
        raise ValueError(
            f"Invalid priority {priority!r}. "
            f"Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
        )

    status = str(entry.get("status", "new")).strip().lower()
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    url = str(entry.get("url", "") or "").strip() or None

    return {
        "source_type": source_type,
        "title": title,
        "url": url,
        "notes": str(entry.get("notes", "") or "").strip() or None,
        "suggested_genres": _normalize_list_field(entry.get("suggested_genres")),
        "suggested_artists": _normalize_list_field(entry.get("suggested_artists")),
        "priority": priority,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def _entry_hash(entry: dict) -> str:
    url = entry.get("url") or ""
    key = url if url else f"{entry['source_type']}::{entry['title']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def open_db(path: Path) -> sqlite3.Connection:
    """Open (or create) the SQLite database and ensure the table exists."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(_CREATE_TABLE)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def import_submissions(
    submissions: list[dict],
    db_path: Path,
    submitted_by: str = DEFAULT_SUBMITTED_BY,
    dry_run: bool = False,
) -> dict:
    """Validate and import submissions into the database.

    In dry_run mode the database is never opened or modified.
    Returns a summary dict with counts.
    """
    validated = [validate_submission(entry) for entry in submissions]

    summary: dict[str, object] = {
        "total_in_file": len(validated),
        "new": 0,
        "skipped_duplicate": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    if dry_run:
        summary["new"] = len(validated)
        return summary

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = open_db(db_path)
    try:
        for entry in validated:
            cur = conn.execute(
                _INSERT,
                (
                    now,
                    submitted_by,
                    entry["source_type"],
                    entry["url"],
                    entry["title"],
                    entry["notes"],
                    entry["suggested_genres"],
                    entry["suggested_artists"],
                    entry["priority"],
                    entry["status"],
                    submitted_by,
                    _entry_hash(entry),
                ),
            )
            if cur.rowcount > 0:
                summary["new"] = int(summary["new"]) + 1
            else:
                summary["skipped_duplicate"] = int(summary["skipped_duplicate"]) + 1
        conn.commit()
    finally:
        conn.close()

    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import editorial inbox (manual.md) into coma_radar.sqlite."
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=DEFAULT_INBOX,
        help="Path to inbox/manual.md",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to SQLite database",
    )
    parser.add_argument(
        "--submitted-by",
        default=DEFAULT_SUBMITTED_BY,
        help="Submitter name stored in the database",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate without writing to the database",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.inbox.exists():
        print(f"ERROR: inbox not found: {args.inbox}", file=sys.stderr)
        return 1

    try:
        raw = parse_inbox(args.inbox)
    except Exception as exc:
        print(f"ERROR parsing inbox: {exc}", file=sys.stderr)
        return 1

    try:
        summary = import_submissions(
            raw,
            db_path=args.db,
            submitted_by=args.submitted_by,
            dry_run=args.dry_run,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

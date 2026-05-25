#!/usr/bin/env python3
"""Synchronise sources from data/sources_music.yaml into the SQLite sources table.

Usage:
    python3 scripts/sync_sources_to_db.py
    python3 scripts/sync_sources_to_db.py --sources data/sources_music.yaml --db data/coma_radar.sqlite
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
DEFAULT_SOURCES = _REPO_ROOT / "data" / "sources_music.yaml"
DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"

_UPSERT = """
INSERT INTO sources
    (id, name, site_url, feed_url, source_type, language, region,
     genre_tags, priority, active, paywall, notes, created_at, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    name        = excluded.name,
    site_url    = excluded.site_url,
    feed_url    = excluded.feed_url,
    source_type = excluded.source_type,
    language    = excluded.language,
    region      = excluded.region,
    genre_tags  = excluded.genre_tags,
    priority    = excluded.priority,
    active      = excluded.active,
    paywall     = excluded.paywall,
    notes       = excluded.notes,
    updated_at  = excluded.updated_at
"""


def load_sources_yaml(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("sources", [])


def _genre_tags_str(source: dict) -> str:
    tags = source.get("genre_tags") or []
    if isinstance(tags, list):
        return ", ".join(str(t) for t in tags)
    return str(tags)


def sync_sources(
    sources_path: Path = DEFAULT_SOURCES,
    db_path: Path = DEFAULT_DB,
) -> dict:
    """Upsert all sources from YAML into the database.

    Returns a summary dict.
    """
    from scripts.init_db import init_db

    sources = load_sources_yaml(sources_path)
    conn = init_db(db_path)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_ids: set[str] = {
        row[0]
        for row in conn.execute("SELECT id FROM sources").fetchall()
    }

    inserted = 0
    updated = 0

    try:
        for source in sources:
            sid = str(source.get("id", "")).strip()
            if not sid:
                continue

            active_val = source.get("active")
            active_int = 1 if active_val is True or str(active_val).lower() == "true" else 0

            created_at = now if sid not in existing_ids else conn.execute(
                "SELECT created_at FROM sources WHERE id = ?", (sid,)
            ).fetchone()[0]

            conn.execute(
                _UPSERT,
                (
                    sid,
                    str(source.get("name", "")).strip(),
                    str(source.get("site_url", "") or "").strip(),
                    str(source.get("feed_url", "") or "") or None,
                    str(source.get("source_type", "")).strip(),
                    str(source.get("language", "") or "") or None,
                    str(source.get("region", "") or "") or None,
                    _genre_tags_str(source) or None,
                    str(source.get("priority", "") or "") or None,
                    active_int,
                    str(source.get("paywall", "") or "") or None,
                    str(source.get("notes", "") or "") or None,
                    created_at,
                    now,
                ),
            )
            if sid in existing_ids:
                updated += 1
            else:
                inserted += 1

        conn.commit()
    finally:
        conn.close()

    active_count = sum(
        1 for s in sources
        if s.get("active") is True or str(s.get("active", "")).lower() == "true"
    )
    inactive_count = len(sources) - active_count

    return {
        "total_in_yaml": len(sources),
        "inserted": inserted,
        "updated": updated,
        "active": active_count,
        "inactive": inactive_count,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync sources_music.yaml into the SQLite sources table."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="Path to sources_music.yaml",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to SQLite database",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}", file=sys.stderr)
        return 1

    try:
        summary = sync_sources(args.sources, args.db)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

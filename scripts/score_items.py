#!/usr/bin/env python3
"""Score items in coma_radar.sqlite using artist matches, tags, and genre signals.

Usage:
    python3 scripts/score_items.py --dry-run --limit 20
    python3 scripts/score_items.py --limit 20
    python3 scripts/score_items.py --min-score 30
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"
DEFAULT_ARTISTS = _REPO_ROOT / "data" / "artists_registry.csv"
DEFAULT_REPORT = _REPO_ROOT / "reports" / "scored_items_report.csv"
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_RULES = _REPO_ROOT / "data" / "tag_rules.yaml"
DEFAULT_GENRE_RADAR = _REPO_ROOT / "data" / "genre_radar.yaml"
DEFAULT_UNKNOWN_REPORT = _REPO_ROOT / "reports" / "unknown_tags.csv"

# Scoring constants
_ARTIST_BONUS = {"high": 50, "medium": 30, "low": 15}
_SOURCE_BONUS = {"high": 20, "medium": 10}
_CONTENT_TYPE_BONUS = frozenset({
    "reissue", "archive_release", "interview", "review",
    "new_release", "label_profile", "scene_report",
})
_SOFT_PENALTY_TAGS = frozenset({"seo_listicle", "press_release_only"})
_EDITORIAL_PENALTY_TAGS = frozenset({"weak_source"})

REPORT_FIELDS = [
    "item_id", "title", "url", "source_name",
    "matched_artists", "matched_tags", "matched_genres",
    "score", "why_score",
]

_UPDATE_ITEM = """
UPDATE items
SET matched_artists=?, matched_tags=?, matched_genres=?, score=?, updated_at=?
WHERE id=?
"""


# ---------------------------------------------------------------------------
# Artists
# ---------------------------------------------------------------------------

def load_artists(path: Path) -> list[dict]:
    """Load artists_registry.csv, skipping ignored entries."""
    artists: list[dict] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            if str(row.get("ignore", "false")).strip().lower() == "true":
                continue
            canonical = str(row.get("artist_canonical", "")).strip()
            if not canonical:
                continue
            artists.append({
                "artist_canonical": canonical,
                "monitor_priority": str(row.get("monitor_priority", "low")).strip().lower(),
            })
    return artists


_AMBIGUOUS_ARTIST_NAMES = frozenset({
    "them",
    "love",
})


def _norm_artist_name(name: str) -> str:
    """Normalize artist name for duplicate containment checks."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()


def _is_contained_artist(shorter: str, longer: str) -> bool:
    """True if shorter artist name is contained inside a longer matched artist."""
    s = _norm_artist_name(shorter)
    l = _norm_artist_name(longer)
    return bool(s and l and s != l and re.search(r"\b" + re.escape(s) + r"\b", l))


def _match_artists(text: str, artists: list[dict]) -> list[dict]:
    """Return artists found in text with safer boundaries and duplicate suppression."""
    text_lower = text.lower()
    candidates: list[dict] = []

    for artist in artists:
        canonical = str(artist.get("artist_canonical", "") or "").strip()
        if not canonical:
            continue

        name_lower = canonical.lower()
        if name_lower in _AMBIGUOUS_ARTIST_NAMES:
            continue

        found = bool(re.search(r"\b" + re.escape(name_lower) + r"\b", text_lower))

        # Substring fallback is only safe for multi-word names. It handles punctuation
        # and possessive edge cases without matching America inside American Songwriter.
        if not found and len(name_lower) >= 5 and " " in name_lower:
            found = name_lower in text_lower

        if found:
            candidates.append(artist)

    candidates.sort(
        key=lambda a: len(_norm_artist_name(str(a.get("artist_canonical", "")))),
        reverse=True,
    )

    matched: list[dict] = []
    for artist in candidates:
        name = str(artist.get("artist_canonical", "") or "")
        if any(_is_contained_artist(name, str(existing.get("artist_canonical", "") or "")) for existing in matched):
            continue
        matched.append(artist)

    return matched


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_score(
    tags: dict,
    matched_artists: list[dict],
    source_priority: str | None,
) -> tuple[int, str]:
    """Return (clamped_score, why_score_string)."""
    raw = 0
    why: list[str] = []

    for artist in matched_artists:
        p = str(artist.get("monitor_priority", "low")).lower()
        bonus = _ARTIST_BONUS.get(p, 0)
        if bonus:
            raw += bonus
            why.append(f"artist:{artist['artist_canonical']}+{bonus}")

    for tag in tags.get("genre", []):
        raw += 25
        why.append(f"genre:{tag}+25")

    for tag in tags.get("subgenre", []):
        raw += 15
        why.append(f"subgenre:{tag}+15")

    for tag in tags.get("aesthetic", []):
        raw += 10
        why.append(f"aesthetic:{tag}+10")

    for tag in tags.get("content_type", []):
        if tag in _CONTENT_TYPE_BONUS:
            raw += 15
            why.append(f"content:{tag}+15")

    src_bonus = _SOURCE_BONUS.get(str(source_priority or ""), 0)
    if src_bonus:
        raw += src_bonus
        why.append(f"source:{source_priority}+{src_bonus}")

    for tag in tags.get("negative", []):
        if tag in _SOFT_PENALTY_TAGS:
            raw -= 30
            why.append(f"penalty:{tag}-30")
        else:
            raw -= 50
            why.append(f"negative:{tag}-50")

    for tag in tags.get("editorial", []):
        if tag in _EDITORIAL_PENALTY_TAGS:
            raw -= 30
            why.append(f"penalty:{tag}-30")

    return max(0, min(100, raw)), ("; ".join(why) if why else "no_signal")


def score_item(
    item: dict,
    source_priority: str | None,
    artists: list[dict],
    tag_registry: dict,
    rules: list,
    genre_data: dict,
    report_unknown_path: Path = DEFAULT_UNKNOWN_REPORT,
) -> dict:
    """Score one item. Returns dict with score, matched_* and why_score."""
    from scripts.tag_item import match_tags
    from scripts.match_genres import match_text

    title = str(item.get("title", "") or "").strip()
    source_name = str(item.get("source_name", "") or "").strip()
    text = " ".join(filter(None, [title, source_name]))

    tag_result = match_tags(
        text, rules, tag_registry,
        manual_tags=None,
        report_unknown_path=report_unknown_path,
    )
    genre_result = match_text(text, genre_data)
    matched_genres = genre_result.get("matched_genres", [])
    matched_artists = _match_artists(text, artists)

    score, why_score = _compute_score(
        tag_result["tags"], matched_artists, source_priority
    )

    all_tags = [
        tag
        for type_list in tag_result["tags"].values()
        for tag in type_list
    ]

    return {
        "score": score,
        "matched_artists": [a["artist_canonical"] for a in matched_artists],
        "matched_tags": all_tags,
        "matched_genres": matched_genres,
        "why_score": why_score,
    }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _write_report(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def score_items(
    db_path: Path = DEFAULT_DB,
    artists_path: Path = DEFAULT_ARTISTS,
    report_path: Path = DEFAULT_REPORT,
    tags_path: Path = DEFAULT_TAGS,
    rules_path: Path = DEFAULT_RULES,
    genre_radar_path: Path = DEFAULT_GENRE_RADAR,
    unknown_report_path: Path = DEFAULT_UNKNOWN_REPORT,
    dry_run: bool = False,
    limit: int | None = None,
    min_score: int = 0,
    include_used: bool = False,
) -> dict:
    """Score items in the database. Returns summary dict."""
    from scripts.init_db import init_db
    from scripts.tag_item import load_tags, load_tag_rules
    from scripts.match_genres import load_genre_radar

    tag_registry = load_tags(tags_path)
    rules = load_tag_rules(rules_path)
    genre_data = load_genre_radar(genre_radar_path)
    artists = load_artists(artists_path) if artists_path.exists() else []

    conn = init_db(db_path)

    source_priorities: dict[str, str] = {
        row[0]: (row[1] or "")
        for row in conn.execute("SELECT id, priority FROM sources").fetchall()
    }

    (items_total,) = conn.execute("SELECT COUNT(*) FROM items").fetchone()

    where = "" if include_used else "WHERE included_in_issue = 0"
    limit_clause = f" LIMIT {limit}" if limit is not None else ""
    rows = conn.execute(
        f"SELECT id, title, url, source_id, source_name, source_type, included_in_issue "
        f"FROM items {where} ORDER BY id{limit_clause}"
    ).fetchall()
    cols = ["id", "title", "url", "source_id", "source_name", "source_type", "included_in_issue"]
    items = [dict(zip(cols, row)) for row in rows]

    items_checked = 0
    updated = 0
    errors = 0
    report_rows: list[dict] = []
    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        for item in items:
            items_checked += 1
            try:
                src_priority = source_priorities.get(str(item.get("source_id") or ""), "")
                result = score_item(
                    item,
                    source_priority=src_priority,
                    artists=artists,
                    tag_registry=tag_registry,
                    rules=rules,
                    genre_data=genre_data,
                    report_unknown_path=unknown_report_path,
                )
            except Exception:
                errors += 1
                continue

            matched_artists_str = ", ".join(result["matched_artists"])
            matched_tags_str = ", ".join(result["matched_tags"])
            matched_genres_str = ", ".join(result["matched_genres"])

            if result["score"] >= min_score:
                report_rows.append({
                    "item_id": item["id"],
                    "title": item["title"],
                    "url": item.get("url") or "",
                    "source_name": item.get("source_name") or "",
                    "matched_artists": matched_artists_str,
                    "matched_tags": matched_tags_str,
                    "matched_genres": matched_genres_str,
                    "score": result["score"],
                    "why_score": result["why_score"],
                })

            if not dry_run:
                conn.execute(
                    _UPDATE_ITEM,
                    (
                        matched_artists_str,
                        matched_tags_str,
                        matched_genres_str,
                        result["score"],
                        now,
                        item["id"],
                    ),
                )
                updated += 1

        if not dry_run:
            conn.commit()
    finally:
        conn.close()

    _write_report(report_rows, report_path)

    top_candidates = sorted(
        [
            {
                "id": r["item_id"],
                "title": r["title"],
                "score": r["score"],
                "url": r["url"],
                "source_name": r.get("source_name", ""),
                "matched_artists": r.get("matched_artists", ""),
                "matched_tags": r.get("matched_tags", ""),
                "matched_genres": r.get("matched_genres", ""),
                "why_score": r.get("why_score", ""),
            }
            for r in report_rows
            if r["score"] > 0
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:10]

    return {
        "items_total": items_total,
        "items_checked": items_checked,
        "updated": updated,
        "skipped": items_total - items_checked,
        "errors": errors,
        "dry_run": dry_run,
        "top_candidates": top_candidates,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score items in coma_radar.sqlite."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--artists", type=Path, default=DEFAULT_ARTISTS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of items to process")
    parser.add_argument("--dry-run", action="store_true",
                        help="Score items but do not update the database")
    parser.add_argument("--min-score", type=int, default=0,
                        help="Only include items with score >= N in the report")
    parser.add_argument("--include-used", action="store_true",
                        help="Re-score items already included in an issue")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 1

    summary = score_items(
        db_path=args.db,
        artists_path=args.artists,
        report_path=args.report,
        dry_run=args.dry_run,
        limit=args.limit,
        min_score=args.min_score,
        include_used=args.include_used,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

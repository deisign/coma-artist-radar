#!/usr/bin/env python3
"""Audit per-source yield and diversity after a daily draft run."""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

DEFAULT_DB = Path("data/coma_radar.sqlite")
DEFAULT_CONTENT_DIR = Path("content/issues")
DEFAULT_MIN_SCORE = 30

REPORT_FIELDS = [
    "source_id",
    "source_name",
    "active",
    "has_feed",
    "priority",
    "source_type",
    "genre_tags",
    "items_total",
    "scored_ge_min",
    "top_candidates",
    "selected",
    "skipped_by_source_cap",
    "skipped_by_artist_cap",
    "max_score",
    "avg_score",
    "newest_first_seen_at",
    "oldest_first_seen_at",
    "newest_published_at",
    "archive_noise_flag",
    "saturation_flag",
    "low_yield_flag",
    "notes",
]


def _norm_name(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _date_sort_key(value: str | None) -> tuple[int, str]:
    text = str(value or "").strip()
    if not text:
        return (0, "")

    iso_candidates = [text]
    if text.endswith("Z"):
        iso_candidates.append(text[:-1] + "+00:00")

    for candidate in iso_candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return (1, parsed.isoformat(timespec="seconds"))

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return (0, text)

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return (1, parsed.isoformat(timespec="seconds"))


def _load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _counter_from_items(items: Any) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not isinstance(items, list):
        return counts
    for item in items:
        if not isinstance(item, dict):
            continue
        source_name = _norm_name(item.get("source_name"))
        if source_name:
            counts[source_name] += 1
    return counts


def _load_review_counts(review_json: Path | None) -> tuple[Counter[str], Counter[str], Counter[str]]:
    data = _load_json(review_json)
    score_summary = data.get("score_summary") if isinstance(data.get("score_summary"), dict) else data
    issue_summary = data.get("issue_summary") if isinstance(data.get("issue_summary"), dict) else data
    diversity = (
        issue_summary.get("diversity_evidence")
        if isinstance(issue_summary.get("diversity_evidence"), dict)
        else {}
    )

    top_candidates = _counter_from_items(score_summary.get("top_candidates"))
    skipped_source = _counter_from_items(diversity.get("skipped_by_source_cap"))
    skipped_artist = _counter_from_items(diversity.get("skipped_by_artist_cap"))
    return top_candidates, skipped_source, skipped_artist


def _load_selected_counts(date: str, content_dir: Path) -> Counter[str]:
    for lang in ("en", "uk"):
        issue_path = content_dir / f"{date}.{lang}.json"
        if issue_path.exists():
            return _counter_from_items(_load_json(issue_path).get("items"))
    return Counter()


def _load_sources(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, name, feed_url, source_type, genre_tags, priority, active
        FROM sources
        ORDER BY name COLLATE NOCASE
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _item_metrics(conn: sqlite3.Connection, min_score: int, sources: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    by_id = {str(src["id"]): str(src["id"]) for src in sources}
    by_name = {_norm_name(src["name"]): str(src["id"]) for src in sources}
    metrics = {
        str(src["id"]): {
            "items_total": 0,
            "scored_ge_min": 0,
            "max_score": 0,
            "score_sum": 0,
            "newest_first_seen_at": "",
            "oldest_first_seen_at": "",
            "newest_published_at": "",
        }
        for src in sources
    }

    rows = conn.execute(
        """
        SELECT source_id, source_name, score, first_seen_at, published_at
        FROM items
        """
    ).fetchall()
    for row in rows:
        source_id = str(row["source_id"] or "")
        key = by_id.get(source_id) or by_name.get(_norm_name(row["source_name"]))
        if not key:
            continue

        score = int(row["score"] or 0)
        item = metrics[key]
        item["items_total"] += 1
        item["score_sum"] += score
        item["scored_ge_min"] += 1 if score >= min_score else 0
        item["max_score"] = max(item["max_score"], score)

        first_seen = str(row["first_seen_at"] or "")
        if first_seen:
            if not item["newest_first_seen_at"] or first_seen > item["newest_first_seen_at"]:
                item["newest_first_seen_at"] = first_seen
            if not item["oldest_first_seen_at"] or first_seen < item["oldest_first_seen_at"]:
                item["oldest_first_seen_at"] = first_seen

        published = str(row["published_at"] or "")
        if published and (
            not item["newest_published_at"]
            or _date_sort_key(published) > _date_sort_key(item["newest_published_at"])
        ):
            item["newest_published_at"] = published

    return metrics


def _notes(row: dict[str, Any], min_score: int) -> str:
    notes: list[str] = []
    if row["skipped_by_source_cap"] > 0:
        notes.append("source cap saturation")
    if row["top_candidates"] >= 3:
        notes.append("top candidate saturation")
    if row["selected"] > 0:
        notes.append(f"selected {row['selected']}")
    if row["skipped_by_source_cap"] > 0:
        notes.append(f"{row['skipped_by_source_cap']} skipped by source cap")
    if row["skipped_by_artist_cap"] > 0:
        notes.append(f"{row['skipped_by_artist_cap']} skipped by artist cap")
    if row["archive_noise_flag"]:
        notes.append("archive/noise candidate")
        if row["items_total"] >= 20 and row["avg_score"] < min_score:
            notes.append("avg score below threshold")
        elif row["scored_ge_min"] == 0:
            notes.append("no scored candidates")
    if row["low_yield_flag"]:
        notes.append("low yield active feed")
    return "; ".join(notes)


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            -row["selected"],
            -row["skipped_by_source_cap"],
            -row["top_candidates"],
            -row["scored_ge_min"],
            -row["items_total"],
            row["source_name"].casefold(),
        ),
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def audit_source_yield(
    date: str,
    review_json: Path | None,
    db_path: Path,
    content_dir: Path,
    out_base: Path,
    min_score: int = DEFAULT_MIN_SCORE,
) -> dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    try:
        sources = _load_sources(conn)
        metrics = _item_metrics(conn, min_score, sources)
    finally:
        conn.close()

    top_counts, skipped_source_counts, skipped_artist_counts = _load_review_counts(review_json)
    selected_counts = _load_selected_counts(date, content_dir)

    rows: list[dict[str, Any]] = []
    for source in sources:
        source_id = str(source["id"])
        source_name = str(source["name"] or "")
        source_key = _norm_name(source_name)
        item = metrics[source_id]
        items_total = int(item["items_total"])
        avg_score = round(item["score_sum"] / items_total, 2) if items_total else 0

        row = {
            "source_id": source_id,
            "source_name": source_name,
            "active": bool(source["active"]),
            "has_feed": bool(str(source["feed_url"] or "").strip()),
            "priority": source["priority"] or "",
            "source_type": source["source_type"] or "",
            "genre_tags": source["genre_tags"] or "",
            "items_total": items_total,
            "scored_ge_min": int(item["scored_ge_min"]),
            "top_candidates": int(top_counts[source_key]),
            "selected": int(selected_counts[source_key]),
            "skipped_by_source_cap": int(skipped_source_counts[source_key]),
            "skipped_by_artist_cap": int(skipped_artist_counts[source_key]),
            "max_score": int(item["max_score"]),
            "avg_score": avg_score,
            "newest_first_seen_at": item["newest_first_seen_at"],
            "oldest_first_seen_at": item["oldest_first_seen_at"],
            "newest_published_at": item["newest_published_at"],
        }
        row["archive_noise_flag"] = (
            items_total >= 10
            and row["selected"] == 0
            and row["top_candidates"] == 0
            and row["scored_ge_min"] == 0
        ) or (items_total >= 20 and avg_score < min_score)
        row["saturation_flag"] = row["skipped_by_source_cap"] > 0 or row["top_candidates"] >= 3
        row["low_yield_flag"] = row["active"] and row["has_feed"] and items_total > 0 and row["scored_ge_min"] == 0
        row["notes"] = _notes(row, min_score)
        rows.append(row)

    rows = _sort_rows(rows)
    report = {
        "date": date,
        "min_score": min_score,
        "sources_total": len(sources),
        "active_sources": sum(1 for src in sources if src["active"]),
        "feed_sources": sum(1 for src in sources if str(src["feed_url"] or "").strip()),
        "rows": rows,
        "summary": {
            "total_items": sum(row["items_total"] for row in rows),
            "total_scored_ge_min": sum(row["scored_ge_min"] for row in rows),
            "total_selected": sum(row["selected"] for row in rows),
            "sources_with_selection": sum(1 for row in rows if row["selected"] > 0),
            "saturation_sources": sum(1 for row in rows if row["saturation_flag"]),
            "archive_noise_sources": sum(1 for row in rows if row["archive_noise_flag"]),
            "low_yield_sources": sum(1 for row in rows if row["low_yield_flag"]),
        },
    }

    out_base.parent.mkdir(parents=True, exist_ok=True)
    csv_path = out_base.with_suffix(".csv")
    json_path = out_base.with_suffix(".json")
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows({key: _csv_value(row[key]) for key in REPORT_FIELDS} for row in rows)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit per-source yield and diversity.")
    parser.add_argument("--date", required=True, help="Issue date YYYY-MM-DD")
    parser.add_argument("--review-json", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR)
    parser.add_argument("--out", type=Path, required=True, help="Output path without extension")
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 1

    report = audit_source_yield(
        date=args.date,
        review_json=args.review_json,
        db_path=args.db,
        content_dir=args.content_dir,
        out_base=args.out,
        min_score=args.min_score,
    )
    print(json.dumps({
        "date": report["date"],
        "csv": str(args.out.with_suffix(".csv")),
        "json": str(args.out.with_suffix(".json")),
        **report["summary"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

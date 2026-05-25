#!/usr/bin/env python3
"""Fetch RSS/Atom feeds from active sources and store new items in SQLite.

Usage:
    python3 scripts/fetch_sources.py --dry-run --limit 5
    python3 scripts/fetch_sources.py --limit 5
    python3 scripts/fetch_sources.py --offline-fixture path/to/feed.xml --limit 1
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_SOURCES = _REPO_ROOT / "data" / "sources_music.yaml"
DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"
DEFAULT_REPORT = _REPO_ROOT / "reports" / "fetch_sources_report.csv"

_HTTP_UA = "coma-radar/1.0 (+https://radar.coma.fm)"
_HTTP_TIMEOUT = 15
_ATOM_NS = "http://www.w3.org/2005/Atom"

REPORT_FIELDS = [
    "source_id", "source_name", "feed_url", "status",
    "items_found", "inserted", "skipped_duplicate", "error",
]

_INSERT_ITEM = """
INSERT OR IGNORE INTO items (
    title, url, canonical_url, url_hash, title_hash,
    source_id, source_name, source_type,
    published_at, first_seen_at, last_seen_at, created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

_UPSERT_SEEN_URL = """
INSERT INTO seen_urls (url_hash, canonical_url, first_seen_at, last_seen_at, source_id, item_id)
VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(url_hash) DO UPDATE SET
    last_seen_at = excluded.last_seen_at
"""


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Feed fetch (isolated for monkeypatching in tests)
# ---------------------------------------------------------------------------

def _fetch_feed(url: str, timeout: int = _HTTP_TIMEOUT) -> tuple[int, bytes]:
    """Return (HTTP status, body). Returns (0, b'') on any error."""
    try:
        req = Request(url, headers={"User-Agent": _HTTP_UA})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except Exception:
        return 0, b""


def _get_feed_content(
    url: str,
    offline_fixture: Path | None = None,
    timeout: int = _HTTP_TIMEOUT,
) -> tuple[int, bytes]:
    if offline_fixture is not None:
        return 200, offline_fixture.read_bytes()
    return _fetch_feed(url, timeout=timeout)


# ---------------------------------------------------------------------------
# XML parsing
# ---------------------------------------------------------------------------

def _parse_rss(root: ET.Element) -> list[dict]:
    channel = root.find("channel")
    if channel is None:
        return []
    items = []
    for el in channel.findall("item"):
        title = (el.findtext("title") or "").strip()
        if not title:
            continue
        items.append({
            "title": title,
            "url": (el.findtext("link") or "").strip() or None,
            "published_at": (el.findtext("pubDate") or "").strip() or None,
            "excerpt": (el.findtext("description") or "").strip() or None,
        })
    return items


def _parse_atom(root: ET.Element) -> list[dict]:
    ns = _ATOM_NS
    items = []
    for entry in root.findall(f"{{{ns}}}entry"):
        title_el = entry.find(f"{{{ns}}}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        if not title:
            continue
        link = ""
        for link_el in entry.findall(f"{{{ns}}}link"):
            if link_el.get("rel", "alternate") in ("alternate", ""):
                link = link_el.get("href", "").strip()
                break
        pub = (
            entry.findtext(f"{{{ns}}}published")
            or entry.findtext(f"{{{ns}}}updated")
            or ""
        ).strip() or None
        summary_el = entry.find(f"{{{ns}}}summary")
        if summary_el is None:
            summary_el = entry.find(f"{{{ns}}}content")
        excerpt = (summary_el.text or "").strip() if summary_el is not None else ""
        items.append({
            "title": title,
            "url": link or None,
            "published_at": pub,
            "excerpt": excerpt or None,
        })
    return items


def parse_feed_xml(content: bytes) -> list[dict]:
    """Auto-detect RSS 2.0 or Atom. Raises ET.ParseError on broken XML."""
    root = ET.fromstring(content)
    tag = root.tag
    if tag == "rss" or (tag.startswith("{") and tag.endswith("}rss")):
        return _parse_rss(root)
    if tag == f"{{{_ATOM_NS}}}feed":
        return _parse_atom(root)
    items = _parse_rss(root)
    return items if items else _parse_atom(root)


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_sources_yaml(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("sources", [])


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
# Core
# ---------------------------------------------------------------------------

def fetch_and_store(
    sources: list[dict],
    db_path: Path,
    dry_run: bool = False,
    limit: int | None = None,
    offline_fixture: Path | None = None,
    report_path: Path = DEFAULT_REPORT,
) -> dict:
    """Fetch feeds, parse items, store new ones in SQLite. Returns summary dict."""
    from scripts.init_db import init_db

    sources_total = len(sources)
    active_with_feed = [
        s for s in sources
        if (s.get("active") is True or str(s.get("active", "")).lower() == "true")
        and str(s.get("feed_url", "") or "").strip()
    ]
    sources_with_feed = len(active_with_feed)
    to_check = active_with_feed[:limit] if limit is not None else active_with_feed

    summary: dict[str, object] = {
        "sources_total": sources_total,
        "sources_with_feed": sources_with_feed,
        "sources_checked": len(to_check),
        "items_found": 0,
        "inserted": 0,
        "skipped_duplicate": 0,
        "errors": 0,
        "dry_run": dry_run,
    }

    # First pass: fetch and parse all feeds
    # Each entry: (source_dict, parsed_items, status_str, error_str)
    source_results: list[tuple[dict, list[dict], str, str]] = []

    for source in to_check:
        feed_url = str(source.get("feed_url", "") or "").strip()
        try:
            status_code, body = _get_feed_content(
                feed_url, offline_fixture=offline_fixture
            )
        except Exception as exc:
            source_results.append((source, [], "error", str(exc)))
            summary["errors"] = int(summary["errors"]) + 1
            continue

        if status_code == 0 or not body:
            source_results.append((source, [], f"http_{status_code}", "empty or failed response"))
            summary["errors"] = int(summary["errors"]) + 1
            continue

        try:
            items = parse_feed_xml(body)
        except ET.ParseError as exc:
            source_results.append((source, [], "parse_error", str(exc)))
            summary["errors"] = int(summary["errors"]) + 1
            continue

        summary["items_found"] = int(summary["items_found"]) + len(items)
        source_results.append((source, items, str(status_code), ""))

    if dry_run:
        summary["inserted"] = summary["items_found"]
        report_rows = [
            {
                "source_id": str(s.get("id", "")),
                "source_name": str(s.get("name", "")),
                "feed_url": str(s.get("feed_url", "") or ""),
                "status": status,
                "items_found": len(items),
                "inserted": len(items),
                "skipped_duplicate": 0,
                "error": error,
            }
            for s, items, status, error in source_results
        ]
        _write_report(report_rows, report_path)
        return summary

    # Live mode: open DB and write
    conn = init_db(db_path)
    now = _now()
    report_rows = []

    try:
        for source, items, status, error in source_results:
            sid = str(source.get("id", "")).strip()
            sname = str(source.get("name", "")).strip()
            stype = str(source.get("source_type", "")).strip()
            feed_url = str(source.get("feed_url", "") or "").strip()
            row_inserted = 0
            row_skipped = 0

            for item in items:
                url = item.get("url")
                if not url:
                    continue

                url_hash = _sha256(url)
                title_hash = _sha256(item["title"])

                cur = conn.execute(
                    _INSERT_ITEM,
                    (
                        item["title"],
                        url,
                        url,
                        url_hash,
                        title_hash,
                        sid,
                        sname,
                        stype,
                        item.get("published_at"),
                        now,
                        now,
                        now,
                        now,
                    ),
                )

                if cur.rowcount > 0:
                    item_id = cur.lastrowid
                    row_inserted += 1
                    summary["inserted"] = int(summary["inserted"]) + 1
                else:
                    item_id = None
                    row_skipped += 1
                    summary["skipped_duplicate"] = int(summary["skipped_duplicate"]) + 1

                conn.execute(_UPSERT_SEEN_URL, (url_hash, url, now, now, sid, item_id))

            conn.commit()

            report_rows.append({
                "source_id": sid,
                "source_name": sname,
                "feed_url": feed_url,
                "status": status,
                "items_found": len(items),
                "inserted": row_inserted,
                "skipped_duplicate": row_skipped,
                "error": error,
            })

    finally:
        conn.close()

    _write_report(report_rows, report_path)
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch RSS/Atom feeds and store new items in SQLite."
    )
    parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of sources to check")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse feeds but do not write to DB")
    parser.add_argument("--offline-fixture", type=Path, default=None,
                        help="Use this local XML file as feed content instead of HTTP")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}", file=sys.stderr)
        return 1

    if args.offline_fixture and not args.offline_fixture.exists():
        print(f"ERROR: fixture not found: {args.offline_fixture}", file=sys.stderr)
        return 1

    try:
        sources = load_sources_yaml(args.sources)
    except Exception as exc:
        print(f"ERROR loading sources: {exc}", file=sys.stderr)
        return 1

    summary = fetch_and_store(
        sources,
        db_path=args.db,
        dry_run=args.dry_run,
        limit=args.limit,
        offline_fixture=args.offline_fixture,
        report_path=args.report,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

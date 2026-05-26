#!/usr/bin/env python3
"""Daily draft pipeline: sync sources → fetch → score → build issue → build site.

Usage:
    python3 scripts/build_daily_draft.py --date 2026-05-26
    python3 scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10
    python3 scripts/build_daily_draft.py --date 2026-05-26 --dry-run
    python3 scripts/build_daily_draft.py --date 2026-05-26 --base-path /coma-artist-radar
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.sync_sources_to_db import sync_sources
from scripts.fetch_sources import fetch_and_store, load_sources_yaml
from scripts.import_human_submissions import parse_inbox, import_submissions
from scripts.score_items import score_items
from scripts.build_issue import build_issue, normalize_base_path
from scripts.build_tag_pages import build_tag_pages
from scripts.build_site import build_site

DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"
DEFAULT_SOURCES = _REPO_ROOT / "data" / "sources_music.yaml"
DEFAULT_INBOX = _REPO_ROOT / "inbox" / "manual.md"
DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_BASE_URL = "https://deisign.github.io/coma-artist-radar"
DEFAULT_BASE_PATH = "/coma-artist-radar"
DEFAULT_MIN_SCORE = 30
DEFAULT_ISSUE_LIMIT = 10


def run_pipeline(
    date: str,
    fetch_limit: int | None = None,
    min_score: int = DEFAULT_MIN_SCORE,
    issue_limit: int = DEFAULT_ISSUE_LIMIT,
    base_url: str = DEFAULT_BASE_URL,
    base_path: str = DEFAULT_BASE_PATH,
    dry_run: bool = False,
    db_path: Path = DEFAULT_DB,
    sources_path: Path = DEFAULT_SOURCES,
    inbox_path: Path = DEFAULT_INBOX,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dist_dir: Path = DEFAULT_DIST_DIR,
) -> dict:
    """Run the full daily draft pipeline. Returns a summary dict."""
    base_path = normalize_base_path(base_path)

    # Step 1: Sync sources metadata to DB (creates DB if absent)
    sync_sources(sources_path=sources_path, db_path=db_path)

    # Step 2: Import human submissions from inbox if present
    if inbox_path.exists():
        raw = parse_inbox(inbox_path)
        import_submissions(raw, db_path=db_path, dry_run=dry_run)

    # Step 3: Fetch RSS/Atom feeds and store new items
    sources = load_sources_yaml(sources_path)
    fetch_summary = fetch_and_store(
        sources=sources,
        db_path=db_path,
        dry_run=dry_run,
        limit=fetch_limit,
    )

    # Step 4: Score all unscored items
    score_summary = score_items(
        db_path=db_path,
        dry_run=dry_run,
        min_score=min_score,
    )

    # Step 5: Build issue HTML pages and JSON content drafts
    if not dry_run:
        issue_summary = build_issue(
            db_path=db_path,
            issue_date=date,
            limit=issue_limit,
            min_score=min_score,
            draft=True,
            content_dir=content_dir,
            dist_dir=dist_dir,
            base_path=base_path,
        )
    else:
        issue_summary = {
            "issue_date": date,
            "languages": ["en", "uk"],
            "selected_items": 0,
            "output_files": [],
            "draft": True,
        }

    # Step 6: Build per-tag pages
    tag_summary = build_tag_pages(
        content_dir=content_dir,
        dist_dir=dist_dir,
        dry_run=dry_run,
        base_path=base_path,
    )

    # Step 7: Build site shell (index, archive, sitemap, robots, feed)
    site_summary = build_site(
        content_dir=content_dir,
        dist_dir=dist_dir,
        base_url=base_url,
        base_path=base_path,
        dry_run=dry_run,
    )

    base = base_url.rstrip("/")
    output_urls = [
        f"{base}/en/issues/{date}.html",
        f"{base}/uk/issues/{date}.html",
        f"{base}/en/index.html",
        f"{base}/uk/index.html",
    ]

    return {
        "date": date,
        "fetch_summary": fetch_summary,
        "score_summary": score_summary,
        "issue_summary": issue_summary,
        "site_summary": site_summary,
        "output_urls": output_urls,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full daily draft pipeline: fetch → score → build issue → build site."
    )
    parser.add_argument(
        "--date", dest="date", default=None,
        help="Issue date YYYY-MM-DD (default: today UTC)",
    )
    parser.add_argument(
        "--fetch-limit", type=int, default=None, dest="fetch_limit",
        help="Max number of sources to fetch (default: all active sources)",
    )
    parser.add_argument(
        "--min-score", type=int, default=DEFAULT_MIN_SCORE, dest="min_score",
        help=f"Minimum score to include an item in the issue (default: {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument(
        "--issue-limit", type=int, default=DEFAULT_ISSUE_LIMIT, dest="issue_limit",
        help=f"Max items in the issue (default: {DEFAULT_ISSUE_LIMIT})",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, dest="base_url",
        help="Canonical base URL for sitemap and feed",
    )
    parser.add_argument(
        "--base-path", default=DEFAULT_BASE_PATH, dest="base_path",
        help="Base path prefix for internal links, e.g. /coma-artist-radar",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Fetch and score but do not write HTML files or modify DB",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    date = args.date or datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    summary = run_pipeline(
        date=date,
        fetch_limit=args.fetch_limit,
        min_score=args.min_score,
        issue_limit=args.issue_limit,
        base_url=args.base_url,
        base_path=args.base_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

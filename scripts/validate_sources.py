#!/usr/bin/env python3
"""Validate data/sources_music.yaml — structural check and optional HTTP probing.

Usage:
    python3 scripts/validate_sources.py --offline    # structural check only, no network
    python3 scripts/validate_sources.py              # full check with HTTP probing
"""

from __future__ import annotations

import argparse
import csv
import html.parser
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCES = _REPO_ROOT / "data" / "sources_music.yaml"
DEFAULT_REPORT = _REPO_ROOT / "reports" / "sources_report.csv"

VALID_SOURCE_TYPES = {
    "magazine", "blog", "label", "bandcamp_editorial", "festival",
    "archive", "youtube_channel", "podcast", "newsletter", "radio",
    "official_artist_site",
}
VALID_PRIORITIES = {"high", "medium", "low"}
VALID_PAYWALL = {"false", "partial", "true", "unknown"}
REQUIRED_FIELDS = {"id", "name", "site_url", "source_type", "priority", "active"}

REPORT_FIELDS = [
    "id", "name", "site_url", "feed_url", "source_type", "priority",
    "active", "structural_ok", "site_status", "feed_status",
    "feed_found", "discovered_feed_url", "error",
]

_HTTP_TIMEOUT = 12
_HTTP_UA = "coma-radar/1.0 (+https://radar.coma.fm)"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_sources(path: Path = DEFAULT_SOURCES) -> list[dict]:
    """Return the list of source dicts from sources_music.yaml."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("sources", [])


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def validate_source_structure(source: dict) -> tuple[bool, str]:
    """Return (ok, error_message). Error is empty string when ok."""
    missing = REQUIRED_FIELDS - set(source.keys())
    if missing:
        return False, f"Missing fields: {', '.join(sorted(missing))}"

    source_type = str(source.get("source_type", "")).strip().lower()
    if source_type not in VALID_SOURCE_TYPES:
        return False, (
            f"Invalid source_type {source_type!r}. "
            f"Must be one of: {', '.join(sorted(VALID_SOURCE_TYPES))}"
        )

    priority = str(source.get("priority", "")).strip().lower()
    if priority not in VALID_PRIORITIES:
        return False, (
            f"Invalid priority {priority!r}. "
            f"Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
        )

    paywall = str(source.get("paywall", "false")).strip().lower()
    if paywall not in VALID_PAYWALL:
        return False, (
            f"Invalid paywall {paywall!r}. "
            f"Must be one of: {', '.join(sorted(VALID_PAYWALL))}"
        )

    site_url = str(source.get("site_url", "") or "").strip()
    if site_url and not (site_url.startswith("http://") or site_url.startswith("https://")):
        return False, f"Invalid site_url: {site_url!r}"

    feed_url = str(source.get("feed_url", "") or "").strip()
    if feed_url and not (feed_url.startswith("http://") or feed_url.startswith("https://")):
        return False, f"Invalid feed_url: {feed_url!r}"

    return True, ""


# ---------------------------------------------------------------------------
# HTTP probe (isolated for monkeypatching in tests)
# ---------------------------------------------------------------------------

def _http_probe(url: str, timeout: int = _HTTP_TIMEOUT) -> tuple[int, bytes]:
    """Return (HTTP status, body). Returns (0, b'') on any network error."""
    try:
        req = Request(url, headers={"User-Agent": _HTTP_UA})
        with urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read(65536)
    except Exception:
        return 0, b""


# ---------------------------------------------------------------------------
# RSS/Atom autodiscovery
# ---------------------------------------------------------------------------

class _FeedLinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.feeds: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "link":
            return
        attr = {k.lower(): (v or "") for k, v in attrs}
        rel = attr.get("rel", "").lower()
        mime = attr.get("type", "").lower()
        href = attr.get("href", "").strip()
        if rel == "alternate" and mime in (
            "application/rss+xml", "application/atom+xml"
        ) and href:
            self.feeds.append(href)


def discover_feed_from_html(html_content: bytes, site_url: str) -> str | None:
    """Find the first RSS or Atom feed link declared in the HTML <head>.

    Returns an absolute URL or None.
    """
    try:
        parser = _FeedLinkParser()
        parser.feed(html_content.decode("utf-8", errors="replace"))
    except Exception:
        return None

    if not parser.feeds:
        return None

    href = parser.feeds[0]
    if href.startswith("http://") or href.startswith("https://"):
        return href

    parsed = urlparse(site_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if href.startswith("/"):
        return base + href
    return base + "/" + href


# ---------------------------------------------------------------------------
# Per-source check
# ---------------------------------------------------------------------------

def check_source(source: dict, offline: bool = False) -> dict:
    """Validate one source and return a report row dict."""
    structural_ok, error = validate_source_structure(source)

    row: dict[str, str] = {
        "id": str(source.get("id", "")),
        "name": str(source.get("name", "")),
        "site_url": str(source.get("site_url", "") or ""),
        "feed_url": str(source.get("feed_url", "") or ""),
        "source_type": str(source.get("source_type", "")),
        "priority": str(source.get("priority", "")),
        "active": str(source.get("active", "")),
        "structural_ok": "true" if structural_ok else "false",
        "site_status": "",
        "feed_status": "",
        "feed_found": "",
        "discovered_feed_url": "",
        "error": error,
    }

    if offline or not structural_ok:
        return row

    # HTTP check for site_url
    site_url = str(source.get("site_url", "") or "").strip()
    site_content = b""
    if site_url:
        status, site_content = _http_probe(site_url)
        row["site_status"] = str(status) if status else "error"

    # Feed check: configured or autodiscovered
    feed_url = str(source.get("feed_url", "") or "").strip()
    if feed_url:
        feed_status, _ = _http_probe(feed_url)
        row["feed_status"] = str(feed_status) if feed_status else "error"
        row["feed_found"] = "true" if feed_status else "false"
    elif site_content:
        discovered = discover_feed_from_html(site_content, site_url)
        if discovered:
            row["discovered_feed_url"] = discovered
            row["feed_found"] = "discovered"
        else:
            row["feed_found"] = "false"

    return row


# ---------------------------------------------------------------------------
# Batch validation + report
# ---------------------------------------------------------------------------

def validate_all(sources: list[dict], offline: bool = False) -> list[dict]:
    """Check all sources and return a list of report row dicts."""
    return [check_source(s, offline=offline) for s in sources]


def write_report(rows: list[dict], path: Path = DEFAULT_REPORT) -> None:
    """Write report rows to a CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate sources_music.yaml and write sources_report.csv."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=DEFAULT_SOURCES,
        help="Path to sources_music.yaml",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Output CSV report path",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Structural validation only — no HTTP requests",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.sources.exists():
        print(f"ERROR: sources file not found: {args.sources}", file=sys.stderr)
        return 1

    try:
        sources = load_sources(args.sources)
    except Exception as exc:
        print(f"ERROR loading sources: {exc}", file=sys.stderr)
        return 1

    mode_label = "offline (structural only)" if args.offline else "online"
    print(f"Validating {len(sources)} sources [{mode_label}] …")

    rows = validate_all(sources, offline=args.offline)
    write_report(rows, args.report)

    total = len(rows)
    ok = sum(1 for r in rows if r["structural_ok"] == "true")
    errors = total - ok

    print(f"  Structural:  {ok} ok, {errors} errors")
    print(f"  Report:      {args.report}")

    if not args.offline:
        reachable = sum(
            1 for r in rows
            if r["site_status"].startswith("2") or r["site_status"].startswith("3")
        )
        feeds = sum(
            1 for r in rows
            if r["feed_found"] in ("true", "discovered")
        )
        print(f"  Reachable:   {reachable}/{total} sites")
        print(f"  Feeds found: {feeds}/{total}")

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

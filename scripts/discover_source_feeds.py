#!/usr/bin/env python3
"""Stage27E: Feed discovery for longtail source candidates.

Reads a CSV of candidate domains produced by Stage27D longtail analysis,
checks each domain for RSS/Atom feeds, validates them, deduplicates against
the existing source registry, and writes a review CSV.

Usage:
    python scripts/discover_source_feeds.py --dry-run --limit 10
    python scripts/discover_source_feeds.py --limit 20 --sleep 1 --resume
    python scripts/discover_source_feeds.py reports/stage27e_feed_check_candidates.csv \\
        --out reports/stage27e_feed_discovery.csv

sources_music.yaml is NOT modified by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    import yaml as _yaml
    _YAML_OK = True
except ImportError:
    _YAML_OK = False

# ── paths ─────────────────────────────────────────────────────────────────────

DEFAULT_INPUT = _REPO_ROOT / "reports" / "stage27e_feed_check_candidates.csv"
DEFAULT_OUTPUT = _REPO_ROOT / "reports" / "stage27e_feed_discovery.csv"
SOURCES_YAML = _REPO_ROOT / "data" / "sources_music.yaml"

# ── constants ──────────────────────────────────────────────────────────────────

COMMON_FEED_PATHS = [
    "/feed/",
    "/rss/",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
    "/blog/feed/",
    "/news/feed/",
    "/feed",
]

FEED_MARKERS = (b"<rss", b"<feed", b"<rdf:RDF")

NICHE_KEYWORDS = frozenset({
    "surf", "psychobilly", "rockabilly", "blues", "jazz", "americana",
    "soul", "garage", "vintage", "roots", "exotica", "country", "western",
    "rhythm", "swamp", "punk", "zine", "fanzine",
})

OUTPUT_FIELDS = [
    "domain",
    "bucket",
    "feed_check_action",
    "source_type_guess",
    "longtail_score",
    "unique_artists",
    "hits_total",
    "sample_artists",
    "site_url",
    "site_status",
    "detected_feed_url",
    "feed_status",
    "feed_title",
    "feed_type",
    "already_in_sources",
    "existing_source_id",
    "existing_source_name",
    "suggested_source_id",
    "suggested_name",
    "suggested_source_type",
    "suggested_priority",
    "suggested_import_action",
    "notes",
]

USER_AGENT = "Mozilla/5.0 (compatible; ComaFmRadarBot/1.0; +https://coma.fm/bot)"

# ── slugify / ID generation ───────────────────────────────────────────────────


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def normalize_domain(url_or_domain: str) -> str:
    """Extract and normalize a bare domain from a URL or domain string."""
    s = url_or_domain.strip()
    if not s:
        return ""
    if not s.startswith(("http://", "https://")):
        s = "https://" + s
    try:
        host = urlparse(s).hostname or ""
    except Exception:
        return ""
    host = host.lower()
    host = re.sub(r"^www\.", "", host)
    host = re.sub(r"^m\.", "", host)
    return host


def domain_to_source_id(domain: str) -> str:
    """Generate a suggested source_id slug from a domain."""
    clean = domain
    for suffix in (
        ".blogspot.com",
        ".bandcamp.com",
        ".substack.com",
        ".wordpress.com",
    ):
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]
            break
    clean = re.sub(r"\.(com|org|net|co\.uk|co|fm|io|info|uk)$", "", clean)
    return slugify(clean)


# ── platform detection ────────────────────────────────────────────────────────


def detect_platform(domain: str) -> str | None:
    if domain.endswith(".blogspot.com"):
        return "blogspot"
    if domain.endswith(".substack.com"):
        return "substack"
    if domain.endswith(".bandcamp.com"):
        return "bandcamp"
    if domain.endswith(".wordpress.com"):
        return "wordpress"
    return None


def platform_feed_paths(domain: str) -> list[str]:
    """Return platform-specific feed paths to try before common paths."""
    platform = detect_platform(domain)
    if platform == "blogspot":
        return ["/feeds/posts/default?alt=rss", "/feeds/posts/default"]
    if platform == "substack":
        return ["/feed"]
    if platform == "wordpress":
        return ["/feed/", "/feed"]
    return []


# ── HTML feed link extraction ─────────────────────────────────────────────────

_LINK_TAG_RE = re.compile(r"<link\b[^>]+>", re.IGNORECASE | re.DOTALL)
_ATTR_RE = re.compile(
    r"(\w[\w-]*)\s*=\s*(?:\"([^\"]*?)\"|'([^']*?)'|([^\s>]+))",
    re.IGNORECASE,
)
_FEED_MIME_TYPES = frozenset({
    "application/rss+xml",
    "application/atom+xml",
    "application/rss",
    "application/xml",
    "text/xml",
})


def parse_html_feed_links(html: str, base_url: str) -> list[str]:
    """Extract feed URLs from <link rel='alternate'> tags in HTML."""
    feeds: list[str] = []
    for tag_match in _LINK_TAG_RE.finditer(html):
        tag = tag_match.group(0)
        attrs: dict[str, str] = {}
        for m in _ATTR_RE.finditer(tag):
            key = m.group(1).lower()
            val = m.group(2) or m.group(3) or m.group(4) or ""
            attrs[key] = val
        rel = attrs.get("rel", "").lower()
        typ = attrs.get("type", "").lower()
        href = attrs.get("href", "")
        if "alternate" in rel and typ in _FEED_MIME_TYPES and href:
            abs_url = urljoin(base_url, href)
            if abs_url not in feeds:
                feeds.append(abs_url)
    return feeds


# ── feed validation ───────────────────────────────────────────────────────────


def is_valid_feed(content: bytes) -> bool:
    snip = content[:2048]
    return any(marker in snip for marker in FEED_MARKERS)


def detect_feed_type(content: bytes) -> str:
    snip = content[:512]
    if b"<rss" in snip:
        return "rss"
    if b"<feed" in snip:
        return "atom"
    if b"<rdf:RDF" in snip:
        return "rdf"
    return ""


def extract_feed_title(content: bytes) -> str:
    """Extract feed title via regex (tolerant of namespace/encoding issues)."""
    for pattern in (
        rb"<title>([^<]{1,200})</title>",
        rb"<title\b[^>]*>([^<]{1,200})</title>",
    ):
        m = re.search(pattern, content, re.IGNORECASE)
        if m:
            raw = m.group(1).decode("utf-8", errors="replace").strip()
            raw = re.sub(r"<[^>]+>", "", raw)
            raw = re.sub(r"&amp;", "&", raw)
            raw = re.sub(r"&lt;", "<", raw)
            raw = re.sub(r"&gt;", ">", raw)
            raw = re.sub(r"&#?\w+;", "", raw)
            return raw[:200].strip()
    return ""


# ── source registry deduplication ─────────────────────────────────────────────


def load_yaml_sources(path: Path) -> list[dict]:
    if not _YAML_OK:
        raise RuntimeError("PyYAML is not installed; cannot load sources_music.yaml")
    with path.open("r", encoding="utf-8") as f:
        data = _yaml.safe_load(f)
    return data.get("sources", [])


def build_source_index(sources: list[dict]) -> dict:
    """Build lookup index keyed by domain and feed_url."""
    index: dict[str, dict] = {}
    for s in sources:
        site_url = s.get("site_url") or ""
        if site_url:
            d = normalize_domain(site_url)
            if d:
                index[d] = s
        feed_url = s.get("feed_url") or ""
        if feed_url:
            index[feed_url.rstrip("/")] = s
    return index


def check_dedup(
    domain: str,
    feed_url: str,
    source_index: dict,
) -> tuple[bool, str, str]:
    """Return (already_in_sources, existing_id, existing_name)."""
    found = source_index.get(domain)
    if not found and feed_url:
        found = source_index.get(feed_url.rstrip("/"))
    if found:
        return True, found.get("id", ""), found.get("name", "")
    return False, "", ""


# ── priority / action suggestion ──────────────────────────────────────────────


def _domain_has_niche_keyword(domain: str) -> bool:
    parts = set(re.split(r"[.\-_]", domain.lower()))
    return bool(NICHE_KEYWORDS & parts)


def suggest_priority(
    domain: str,
    bucket: str,
    source_type_guess: str,
    has_valid_feed: bool,
    sample_artists: str = "",
) -> str:
    if not has_valid_feed:
        return "low"
    if detect_platform(domain) == "bandcamp":
        return "low"
    if bucket == "archive":
        return "manual_review"
    if bucket in ("niche_blog_fanzine", "niche_site") and _domain_has_niche_keyword(domain):
        return "high"
    if bucket in ("niche_blog_fanzine", "niche_site"):
        return "medium"
    if bucket == "label_or_record_shop":
        return "medium"
    if bucket == "label_bandcamp":
        return "low"
    return "medium"


def suggest_import_action(
    has_valid_feed: bool,
    already_in_sources: bool,
    feed_status: int | str,
    site_status: int | str,
    platform: str | None,
    bucket: str,
) -> str:
    if already_in_sources:
        return "ALREADY_EXISTS"
    if not has_valid_feed:
        if platform == "bandcamp":
            return "NO_FEED_FOUND"
        site_ok = str(site_status)[:1] in ("2", "3")
        return "NO_FEED_FOUND" if site_ok else "MANUAL_REVIEW"
    if platform == "bandcamp":
        return "REVIEW_FEED"
    return "IMPORT_READY"


def suggest_source_type(bucket: str, source_type_guess: str) -> str:
    explicit = {
        "label": "label",
        "magazine": "magazine",
        "blog": "blog",
        "archive": "archive",
        "podcast": "podcast",
        "radio": "radio",
    }
    if source_type_guess.lower() in explicit:
        return explicit[source_type_guess.lower()]
    mapping = {
        "niche_blog_fanzine": "blog",
        "niche_site": "blog",
        "label_or_record_shop": "label",
        "label_bandcamp": "label",
        "archive": "archive",
    }
    return mapping.get(bucket, "blog")


# ── HTTP fetcher abstraction ───────────────────────────────────────────────────


class Fetcher(ABC):
    @abstractmethod
    def fetch(self, url: str, timeout: float = 10) -> tuple[int, bytes, str, str]:
        """Return (status_code, content, final_url, error_msg)."""


class RealFetcher(Fetcher):
    def fetch(self, url: str, timeout: float = 10) -> tuple[int, bytes, str, str]:
        try:
            req = Request(url, headers={"User-Agent": USER_AGENT})
            with urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.read(), resp.url, ""
        except URLError as exc:
            return 0, b"", url, str(exc.reason)
        except Exception as exc:
            return 0, b"", url, str(exc)


class FakeFetcher(Fetcher):
    """Deterministic fake fetcher for tests — no real network calls."""

    def __init__(
        self, responses: dict[str, tuple[int, bytes, str]] | None = None
    ) -> None:
        self._responses: dict[str, tuple[int, bytes, str]] = responses or {}

    def add(
        self, url: str, status: int, content: bytes, final_url: str = ""
    ) -> None:
        self._responses[url] = (status, content, final_url or url)

    def fetch(self, url: str, timeout: float = 10) -> tuple[int, bytes, str, str]:
        if url in self._responses:
            status, content, final_url = self._responses[url]
            return status, content, final_url, ""
        return 0, b"", url, "no response configured"


# ── core discovery ─────────────────────────────────────────────────────────────


def _try_feed_url(
    fetcher: Fetcher, url: str, timeout: float
) -> tuple[int, str, bool, str, str]:
    """Fetch url; return (status, final_url, is_valid, title, feed_type)."""
    status, content, final_url, err = fetcher.fetch(url, timeout)
    if err or not content:
        return status, final_url, False, "", ""
    valid = is_valid_feed(content)
    title = extract_feed_title(content) if valid else ""
    ftype = detect_feed_type(content) if valid else ""
    return status, final_url, valid, title, ftype


def find_feed_for_domain(
    domain: str,
    fetcher: Fetcher,
    timeout: float = 10,
) -> dict:
    """
    Try to find a valid RSS/Atom feed for the domain.

    Returns a dict with keys: site_url, site_status, detected_feed_url,
    feed_status, feed_title, feed_type, notes.
    """
    result: dict = {
        "site_url": "",
        "site_status": "",
        "detected_feed_url": "",
        "feed_status": "",
        "feed_title": "",
        "feed_type": "",
        "notes": "",
    }
    notes_parts: list[str] = []
    platform = detect_platform(domain)

    # Step 1: load homepage (https preferred, http fallback)
    homepage_content = b""
    homepage_url = ""
    for scheme in ("https", "http"):
        url = f"{scheme}://{domain}/"
        status, content, final_url, err = fetcher.fetch(url, timeout)
        if status and status < 400:
            result["site_url"] = final_url
            result["site_status"] = str(status)
            homepage_content = content
            homepage_url = final_url
            break
        if err:
            notes_parts.append(f"{scheme}: {err[:80]}")

    if not result["site_url"]:
        result["site_url"] = f"https://{domain}/"
        result["site_status"] = "0"

    if platform == "bandcamp":
        notes_parts.append("bandcamp: no RSS feed expected")

    # Step 2: parse HTML <link rel=alternate> tags
    feed_candidates: list[str] = []
    if homepage_content:
        try:
            html = homepage_content.decode("utf-8", errors="replace")
        except Exception:
            html = ""
        if html:
            base = result["site_url"] or f"https://{domain}/"
            feed_candidates.extend(parse_html_feed_links(html, base))

    # Step 3: build ordered path list (platform-specific first)
    paths = platform_feed_paths(domain) + COMMON_FEED_PATHS
    seen: set[str] = set()
    base_scheme = "http" if result["site_url"].startswith("http://") else "https"
    for path in paths:
        candidate = f"{base_scheme}://{domain}{path}"
        if candidate not in seen and candidate not in feed_candidates:
            seen.add(candidate)
            feed_candidates.append(candidate)

    # Step 4: try each candidate until a valid feed is found
    for furl in feed_candidates:
        fstatus, ffinal, is_feed, ftitle, ftype = _try_feed_url(
            fetcher, furl, timeout
        )
        if is_feed:
            result["detected_feed_url"] = ffinal or furl
            result["feed_status"] = str(fstatus)
            result["feed_title"] = ftitle
            result["feed_type"] = ftype
            break

    if not result["detected_feed_url"]:
        result["feed_status"] = "no_feed" if platform == "bandcamp" else "not_found"

    result["notes"] = "; ".join(notes_parts)
    return result


# ── resume / output helpers ───────────────────────────────────────────────────


def load_existing_domains(path: Path) -> set[str]:
    """Return set of domains already present in output CSV."""
    if not path.exists():
        return set()
    done: set[str] = set()
    try:
        with path.open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                d = row.get("domain", "").strip()
                if d:
                    done.add(d)
    except Exception:
        pass
    return done


def write_output_csv(rows: list[dict], path: Path, append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    write_header = not append or not path.exists()
    with path.open(mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ── row processing ─────────────────────────────────────────────────────────────


def process_row(
    row: dict,
    fetcher: Fetcher,
    source_index: dict,
    timeout: float = 10,
    dry_run: bool = False,
) -> dict:
    """Process one input candidate row; return an output row dict."""
    domain = row.get("domain", "").strip()
    bucket = row.get("bucket", "").strip()
    action = row.get("feed_check_action", "").strip()
    source_type_guess = row.get("source_type_guess", "").strip()

    out: dict = {f: "" for f in OUTPUT_FIELDS}
    out.update(
        {
            "domain": domain,
            "bucket": bucket,
            "feed_check_action": action,
            "source_type_guess": source_type_guess,
            "longtail_score": row.get("longtail_score", ""),
            "unique_artists": row.get("unique_artists", ""),
            "hits_total": row.get("hits_total", ""),
            "sample_artists": row.get("sample_artists", ""),
        }
    )

    if not domain:
        out["notes"] = "missing domain"
        out["suggested_import_action"] = "ERROR"
        return out

    if action not in ("check_feed", "manual_review"):
        out["notes"] = f"skipped (action={action!r})"
        out["suggested_import_action"] = "MANUAL_REVIEW"
        return out

    # Suggested metadata (doesn't require fetching)
    out["suggested_source_id"] = domain_to_source_id(domain)
    out["suggested_source_type"] = suggest_source_type(bucket, source_type_guess)

    # Dedup check before fetching
    already, ex_id, ex_name = check_dedup(domain, "", source_index)
    out["already_in_sources"] = "yes" if already else "no"
    out["existing_source_id"] = ex_id
    out["existing_source_name"] = ex_name

    if dry_run:
        out["site_url"] = f"https://{domain}/"
        out["notes"] = "dry-run; no fetch performed"
        out["suggested_priority"] = "manual_review"
        out["suggested_import_action"] = "ALREADY_EXISTS" if already else "MANUAL_REVIEW"
        return out

    # Discover feed
    discovery = find_feed_for_domain(domain, fetcher, timeout)
    out.update(discovery)

    has_valid_feed = bool(out["detected_feed_url"])
    platform = detect_platform(domain)

    # Re-check dedup against discovered feed URL
    if has_valid_feed and not already:
        already2, ex_id2, ex_name2 = check_dedup(
            domain, out["detected_feed_url"], source_index
        )
        if already2:
            already = True
            out["already_in_sources"] = "yes"
            out["existing_source_id"] = ex_id2
            out["existing_source_name"] = ex_name2

    # Suggested name: prefer feed title, fall back to readable domain label
    if out["feed_title"]:
        out["suggested_name"] = out["feed_title"]
    else:
        out["suggested_name"] = domain_to_source_id(domain).replace("-", " ").title()

    sample_artists = row.get("sample_artists", "")
    out["suggested_priority"] = suggest_priority(
        domain, bucket, source_type_guess, has_valid_feed, sample_artists
    )
    out["suggested_import_action"] = suggest_import_action(
        has_valid_feed=has_valid_feed,
        already_in_sources=already,
        feed_status=out["feed_status"],
        site_status=out["site_status"],
        platform=platform,
        bucket=bucket,
    )

    return out


# ── CLI ────────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage27E: Discover RSS/Atom feeds for longtail source candidates."
    )
    p.add_argument(
        "input",
        nargs="?",
        default=str(DEFAULT_INPUT),
        help=f"Input candidates CSV (default: {DEFAULT_INPUT.name})",
    )
    p.add_argument(
        "--out",
        default=None,
        help=(
            f"Output CSV (default when writing: {DEFAULT_OUTPUT.name}). "
            "In dry-run mode without --out, no file is written."
        ),
    )
    p.add_argument("--limit", type=int, default=None, help="Max rows to process")
    p.add_argument("--offset", type=int, default=0, help="Skip first N input rows")
    p.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Seconds to sleep between domains (default: 1.0)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout per request in seconds (default: 10)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Skip domains already in output CSV and append new rows",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Skip all network requests. Without --out, prints a summary only "
            "and does NOT write any CSV (safe to run before a real run)."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = Path(args.input)
    # Distinguish explicit --out from the default so dry-run can avoid writing
    # to the normal report path and poisoning --resume.
    out_explicit = args.out is not None
    output_path = Path(args.out) if out_explicit else DEFAULT_OUTPUT

    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}", file=sys.stderr)
        return 1

    # Load source registry for dedup
    source_index: dict = {}
    if SOURCES_YAML.exists():
        try:
            sources = load_yaml_sources(SOURCES_YAML)
            source_index = build_source_index(sources)
        except Exception as exc:
            print(f"[warn] Could not load sources YAML: {exc}", file=sys.stderr)

    # Resume: load already-processed domains
    done_domains: set[str] = set()
    if args.resume:
        done_domains = load_existing_domains(output_path)
        if done_domains:
            print(f"[resume] {len(done_domains)} domains already in output, skipping")

    # Read and slice input
    with input_path.open(newline="", encoding="utf-8") as f:
        all_rows = list(csv.DictReader(f))
    rows = all_rows[args.offset :]
    if args.limit is not None:
        rows = rows[: args.limit]

    fetcher: Fetcher = RealFetcher()
    append_mode = args.resume and output_path.exists()

    stats: dict[str, int | str | bool] = {
        "total_input": len(rows),
        "skipped_resume": 0,
        "processed": 0,
        "feed_found": 0,
        "no_feed": 0,
        "already_exists": 0,
        "import_ready": 0,
        "errors": 0,
    }

    output_rows: list[dict] = []

    for i, row in enumerate(rows):
        domain = row.get("domain", "").strip()

        if args.resume and domain in done_domains:
            stats["skipped_resume"] = int(stats["skipped_resume"]) + 1  # type: ignore[arg-type]
            continue

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"[{ts}] ({i+1}/{len(rows)}) {domain}", end=" ... ", flush=True)

        try:
            out_row = process_row(
                row,
                fetcher=fetcher,
                source_index=source_index,
                timeout=args.timeout,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            print(f"ERROR: {exc}", flush=True)
            out_row = {f: "" for f in OUTPUT_FIELDS}
            out_row.update(
                {
                    "domain": domain,
                    "bucket": row.get("bucket", ""),
                    "feed_check_action": row.get("feed_check_action", ""),
                    "source_type_guess": row.get("source_type_guess", ""),
                    "longtail_score": row.get("longtail_score", ""),
                    "unique_artists": row.get("unique_artists", ""),
                    "hits_total": row.get("hits_total", ""),
                    "sample_artists": row.get("sample_artists", ""),
                    "notes": f"unhandled exception: {exc}",
                    "suggested_import_action": "ERROR",
                }
            )
            stats["errors"] = int(stats["errors"]) + 1  # type: ignore[arg-type]
            output_rows.append(out_row)
            if not args.dry_run and args.sleep > 0 and i < len(rows) - 1:
                time.sleep(args.sleep)
            continue

        ia = out_row.get("suggested_import_action", "")
        feed = out_row.get("detected_feed_url", "")
        print(f"{ia} | feed={feed or '—'}", flush=True)

        stats["processed"] = int(stats["processed"]) + 1  # type: ignore[arg-type]
        if ia == "IMPORT_READY":
            stats["import_ready"] = int(stats["import_ready"]) + 1  # type: ignore[arg-type]
        if ia == "ALREADY_EXISTS":
            stats["already_exists"] = int(stats["already_exists"]) + 1  # type: ignore[arg-type]
        if ia == "ERROR":
            stats["errors"] = int(stats["errors"]) + 1  # type: ignore[arg-type]
        if feed:
            stats["feed_found"] = int(stats["feed_found"]) + 1  # type: ignore[arg-type]
        else:
            stats["no_feed"] = int(stats["no_feed"]) + 1  # type: ignore[arg-type]

        output_rows.append(out_row)

        if not args.dry_run and args.sleep > 0 and i < len(rows) - 1:
            time.sleep(args.sleep)

    if args.dry_run and not out_explicit:
        print(f"\n[dry-run] {len(output_rows)} rows — not written to disk")
        print("[dry-run] Use --out <path> to save a preview CSV without touching the real report")
    else:
        write_output_csv(output_rows, output_path, append=append_mode)
        print(f"\n[done] Wrote {len(output_rows)} rows → {output_path}")

    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "output": str(output_path),
        "dry_run": args.dry_run,
        **{k: v for k, v in stats.items()},
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

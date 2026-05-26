#!/usr/bin/env python3
"""Build static site for GitHub Pages: index, archive, sitemap, robots, feed.

Usage:
    python3 scripts/build_site.py --dry-run
    python3 scripts/build_site.py
    python3 scripts/build_site.py --base-url https://radar.coma.fm
    python3 scripts/build_site.py --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar
    python3 scripts/build_site.py --content-dir content/issues --dist-dir dist
"""
from __future__ import annotations

import argparse
import calendar
import json
import sys
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_TEMPLATES_DIR = _REPO_ROOT / "templates"
DEFAULT_BASE_URL = "https://radar.coma.fm"
_FEED_ITEMS_MAX = 20
_INDEX_ISSUES_MAX = 10

_LOCALE: dict[str, dict[str, str]] = {
    "en": {
        "title": "coma.fm Radar",
        "description": "A weekly digest of music from the coma.fm field.",
        "latest_issues_heading": "Latest Issues",
        "archive_label": "View full archive →",
        "tags_label": "Browse tags →",
        "no_issues": "No issues yet.",
        "archive_title": "Archive — coma.fm Radar",
        "archive_heading": "Issue Archive",
        "back_label": "← Home",
        "no_archive_issues": "No issues yet.",
        "items_label": "items",
        "status_draft": "draft",
        "status_published": "published",
    },
    "uk": {
        "title": "coma.fm Радар",
        "description": "Щотижневий дайджест музики з поля coma.fm.",
        "latest_issues_heading": "Останні випуски",
        "archive_label": "Повний архів →",
        "tags_label": "Огляд тегів →",
        "no_issues": "Ще немає випусків.",
        "archive_title": "Архів — coma.fm Радар",
        "archive_heading": "Архів випусків",
        "back_label": "← Головна",
        "no_archive_issues": "Ще немає випусків.",
        "items_label": "матеріалів",
        "status_draft": "чернетка",
        "status_published": "опубліковано",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_base_path(path: str) -> str:
    """Normalize base_path: '' or '/' -> '', 'foo' -> '/foo', '/foo/' -> '/foo'."""
    path = path.strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


def _render(template_path: Path, ctx: dict) -> str:
    from scripts.build_issue import _J2Renderer
    src = template_path.read_text(encoding="utf-8")
    return _J2Renderer().render(src, ctx)


def _rfc822_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to RFC 822 date string for RSS."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        ts = calendar.timegm(dt.timetuple())
        return formatdate(ts, usegmt=True)
    except (ValueError, OverflowError):
        return date_str


def _write(path: Path, content: str, dry_run: bool) -> bool:
    """Write file unless dry_run; return True if written."""
    if dry_run:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_content_issues(content_dir: Path) -> dict[str, list[dict]]:
    """Return {lang: [issue_dict, ...]} sorted newest first."""
    result: dict[str, list[dict]] = {"en": [], "uk": []}
    for p in sorted(content_dir.glob("*.json")):
        stem = p.stem  # e.g. "2026-05-25.en"
        parts = stem.rsplit(".", 1)
        if len(parts) != 2 or parts[1] not in ("en", "uk"):
            continue
        lang = parts[1]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        result[lang].append(data)
    for lang in result:
        result[lang].sort(key=lambda x: x.get("issue_date", ""), reverse=True)
    return result


def _issue_rows(issues: list[dict], lang: str, base_path: str = "") -> list[dict]:
    return [
        {
            "date": iss.get("issue_date", ""),
            "title": f"coma.fm Radar — {iss.get('issue_date', '')}",
            "item_count": iss.get("total_items", 0),
            "status": "draft" if iss.get("draft") else "published",
            "href": f"{base_path}/{lang}/issues/{iss.get('issue_date', '')}.html",
            "draft": bool(iss.get("draft", False)),
        }
        for iss in issues
    ]


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _build_root_index(
    dist_dir: Path,
    base_path: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    en_href = f"{base_path}/en/index.html"
    uk_href = f"{base_path}/uk/index.html"
    content = (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n"
        "  <title>coma.fm Radar</title>\n"
        "  <style>\n"
        "    body{font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Georgia,serif;"
        "background:#161616;color:#e0ddd8;display:flex;align-items:center;"
        "justify-content:center;min-height:100vh;margin:0;}\n"
        "    .chooser{text-align:center;}\n"
        "    h1{font-size:2rem;letter-spacing:-0.02em;margin-bottom:1rem;}\n"
        "    p{color:#888;font-size:0.9rem;font-style:italic;margin-bottom:2rem;}\n"
        "    .langs{display:flex;gap:1.5rem;justify-content:center;}\n"
        "    .langs a{color:#c8a46e;text-decoration:none;font-size:1.1rem;"
        "letter-spacing:0.1em;text-transform:uppercase;border:1px solid #2a2a2a;"
        "padding:0.5rem 1.5rem;border-radius:4px;}\n"
        "    .langs a:hover{border-color:#c8a46e;}\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "<div class=\"chooser\">\n"
        "  <h1>coma.fm Radar</h1>\n"
        "  <p>A weekly digest of music from the coma.fm field.</p>\n"
        "  <div class=\"langs\">\n"
        f"    <a href=\"{en_href}\">EN</a>\n"
        f"    <a href=\"{uk_href}\">UK</a>\n"
        "  </div>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )
    out_path = dist_dir / "index.html"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


def _build_lang_index(
    issues: list[dict],
    lang: str,
    dist_dir: Path,
    templates_dir: Path,
    base_path: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    locale = _LOCALE[lang]
    other = "uk" if lang == "en" else "en"
    ctx = {
        "lang": lang,
        "title": locale["title"],
        "description": locale["description"],
        "latest_issues_heading": locale["latest_issues_heading"],
        "nav_en_href": f"{base_path}/en/index.html",
        "nav_uk_href": f"{base_path}/uk/index.html",
        "archive_href": f"{base_path}/{lang}/archive.html",
        "archive_label": locale["archive_label"],
        "tags_href": f"{base_path}/{lang}/tags/index.html",
        "tags_label": locale["tags_label"],
        "no_issues_msg": locale["no_issues"],
        "other_lang": other.upper(),
        "other_lang_href": f"{base_path}/{other}/index.html",
        "issues": _issue_rows(issues[:_INDEX_ISSUES_MAX], lang, base_path),
    }
    content = _render(templates_dir / "index.html.j2", ctx)
    out_path = dist_dir / lang / "index.html"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


def _build_archive(
    issues: list[dict],
    lang: str,
    dist_dir: Path,
    templates_dir: Path,
    base_path: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    locale = _LOCALE[lang]
    other = "uk" if lang == "en" else "en"
    ctx = {
        "lang": lang,
        "title": locale["archive_title"],
        "heading": locale["archive_heading"],
        "nav_en_href": f"{base_path}/en/archive.html",
        "nav_uk_href": f"{base_path}/uk/archive.html",
        "back_href": f"{base_path}/{lang}/index.html",
        "back_label": locale["back_label"],
        "no_issues_msg": locale["no_archive_issues"],
        "other_lang": other.upper(),
        "other_lang_href": f"{base_path}/{other}/archive.html",
        "items_label": locale["items_label"],
        "status_draft": locale["status_draft"],
        "status_published": locale["status_published"],
        "issues": _issue_rows(issues, lang, base_path),
    }
    content = _render(templates_dir / "archive.html.j2", ctx)
    out_path = dist_dir / lang / "archive.html"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


def _build_robots(
    dist_dir: Path,
    templates_dir: Path,
    base_url: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    ctx = {"sitemap_url": f"{base_url}/sitemap.xml"}
    content = _render(templates_dir / "robots.txt.j2", ctx)
    out_path = dist_dir / "robots.txt"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


def _collect_sitemap_pages(
    issues_by_lang: dict[str, list[dict]],
    dist_dir: Path,
    base_url: str,
    today: str,
) -> list[dict]:
    pages: list[dict] = [
        {"loc": f"{base_url}/", "lastmod": today, "changefreq": "daily", "priority": "1.0"},
        {"loc": f"{base_url}/en/index.html", "lastmod": today, "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base_url}/uk/index.html", "lastmod": today, "changefreq": "daily", "priority": "0.9"},
        {"loc": f"{base_url}/en/archive.html", "lastmod": today, "changefreq": "weekly", "priority": "0.7"},
        {"loc": f"{base_url}/uk/archive.html", "lastmod": today, "changefreq": "weekly", "priority": "0.7"},
    ]
    for lang in ("en", "uk"):
        for iss in issues_by_lang.get(lang, []):
            date = iss.get("issue_date", "")
            if not date:
                continue
            pages.append({
                "loc": f"{base_url}/{lang}/issues/{date}.html",
                "lastmod": date,
                "changefreq": "monthly",
                "priority": "0.8",
            })
    for lang in ("en", "uk"):
        tags_dir = dist_dir / lang / "tags"
        if tags_dir.exists():
            for html_file in sorted(tags_dir.glob("*.html")):
                pages.append({
                    "loc": f"{base_url}/{lang}/tags/{html_file.stem}.html",
                    "lastmod": today,
                    "changefreq": "weekly",
                    "priority": "0.5",
                })
    return pages


def _build_sitemap(
    issues_by_lang: dict[str, list[dict]],
    dist_dir: Path,
    templates_dir: Path,
    base_url: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    pages = _collect_sitemap_pages(issues_by_lang, dist_dir, base_url, today)
    ctx = {"base_url": base_url, "pages": pages}
    content = _render(templates_dir / "sitemap.xml.j2", ctx)
    out_path = dist_dir / "sitemap.xml"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


def _build_feed(
    issues_by_lang: dict[str, list[dict]],
    dist_dir: Path,
    templates_dir: Path,
    base_url: str,
    dry_run: bool,
) -> tuple[int, list[str]]:
    en_issues = issues_by_lang.get("en", [])
    feed_items = [
        {
            "title": f"coma.fm Radar — {iss.get('issue_date', '')}",
            "link": f"{base_url}/en/issues/{iss.get('issue_date', '')}.html",
            "description": f"{iss.get('total_items', 0)} items",
            "pub_date": _rfc822_date(iss.get("issue_date", "")),
            "guid": f"{base_url}/en/issues/{iss.get('issue_date', '')}.html",
        }
        for iss in en_issues[:_FEED_ITEMS_MAX]
    ]
    ctx = {
        "feed_title": "coma.fm Radar",
        "feed_link": base_url,
        "feed_description": "A weekly digest of music from the coma.fm field.",
        "feed_url": f"{base_url}/feed.xml",
        "build_date": formatdate(datetime.now(tz=timezone.utc).timestamp(), usegmt=True),
        "items": feed_items,
    }
    content = _render(templates_dir / "feed.xml.j2", ctx)
    out_path = dist_dir / "feed.xml"
    written = 1 if _write(out_path, content, dry_run) else 0
    return written, [_rel(out_path)] if written else []


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_site(
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dist_dir: Path = DEFAULT_DIST_DIR,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    base_url: str = DEFAULT_BASE_URL,
    base_path: str = "",
    dry_run: bool = False,
) -> dict:
    """Build full static site. Returns summary dict."""
    base_path = normalize_base_path(base_path)
    issues_by_lang = load_content_issues(content_dir)

    all_dates: set[str] = set()
    for lang_issues in issues_by_lang.values():
        for iss in lang_issues:
            d = iss.get("issue_date", "")
            if d:
                all_dates.add(d)

    pages_written = 0
    output_files: list[str] = []

    w, fs = _build_root_index(dist_dir, base_path, dry_run)
    pages_written += w
    output_files.extend(fs)

    for lang in ("en", "uk"):
        issues = issues_by_lang.get(lang, [])

        w, fs = _build_lang_index(issues, lang, dist_dir, templates_dir, base_path, dry_run)
        pages_written += w
        output_files.extend(fs)

        w, fs = _build_archive(issues, lang, dist_dir, templates_dir, base_path, dry_run)
        pages_written += w
        output_files.extend(fs)

    w, fs = _build_robots(dist_dir, templates_dir, base_url, dry_run)
    pages_written += w
    output_files.extend(fs)

    w, fs = _build_sitemap(issues_by_lang, dist_dir, templates_dir, base_url, dry_run)
    pages_written += w
    output_files.extend(fs)

    w, fs = _build_feed(issues_by_lang, dist_dir, templates_dir, base_url, dry_run)
    pages_written += w
    output_files.extend(fs)

    return {
        "issues_total": len(all_dates),
        "pages_written": pages_written,
        "output_files": output_files,
        "base_url": base_url,
        "base_path": base_path,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static site for GitHub Pages."
    )
    parser.add_argument(
        "--content-dir", type=Path, default=DEFAULT_CONTENT_DIR, dest="content_dir",
    )
    parser.add_argument(
        "--dist-dir", type=Path, default=DEFAULT_DIST_DIR, dest="dist_dir",
    )
    parser.add_argument(
        "--templates-dir", type=Path, default=DEFAULT_TEMPLATES_DIR, dest="templates_dir",
    )
    parser.add_argument(
        "--base-url", default=DEFAULT_BASE_URL, dest="base_url",
        help="Base URL for the site (default: https://radar.coma.fm)",
    )
    parser.add_argument(
        "--base-path", default="", dest="base_path",
        help="Base path prefix for internal links, e.g. /coma-artist-radar",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Parse and render without writing files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_site(
        content_dir=args.content_dir,
        dist_dir=args.dist_dir,
        templates_dir=args.templates_dir,
        base_url=args.base_url,
        base_path=args.base_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

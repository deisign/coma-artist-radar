#!/usr/bin/env python3
"""Build static bilingual tag pages from content/issues JSON drafts.

Usage:
    python3 scripts/build_tag_pages.py
    python3 scripts/build_tag_pages.py --lang uk
    python3 scripts/build_tag_pages.py --dry-run
    python3 scripts/build_tag_pages.py --base-path /coma-artist-radar
    python3 scripts/build_tag_pages.py --content-dir content/issues --dist-dir dist
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_REPORT = _REPO_ROOT / "reports" / "tag_pages_report.csv"
DEFAULT_TAG_TEMPLATE = _REPO_ROOT / "templates" / "tag_page.html.j2"
DEFAULT_INDEX_TEMPLATE = _REPO_ROOT / "templates" / "tags_index.html.j2"


def normalize_base_path(path: str) -> str:
    """Normalize base_path: '' or '/' -> '', 'foo' -> '/foo', '/foo/' -> '/foo'."""
    path = path.strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")

_LOCALE: dict[str, dict] = {
    "en": {
        "site_heading": "coma.fm Radar",
        "tag_index_heading": "Tag Index",
        "back_to_index": "← All tags",
        "no_items": "No items for this tag.",
        "items_heading": "Items",
        "related_heading": "Related tags",
        "type_labels": {
            "genre": "Genres",
            "subgenre": "Subgenres",
            "aesthetic": "Aesthetic",
            "content_type": "Content Types",
            "editorial": "Editorial",
            "negative": "Negative",
        },
    },
    "uk": {
        "site_heading": "coma.fm Радар",
        "tag_index_heading": "Карта тегів",
        "back_to_index": "← Всі теги",
        "no_items": "Немає матеріалів для цього тегу.",
        "items_heading": "Матеріали",
        "related_heading": "Схожі теги",
        "type_labels": {
            "genre": "Жанри",
            "subgenre": "Піджанри",
            "aesthetic": "Естетика",
            "content_type": "Типи контенту",
            "editorial": "Редакційні",
            "negative": "Негативні",
        },
    },
}

_TYPE_ORDER = ["genre", "subgenre", "aesthetic", "content_type", "editorial", "negative"]

_REPORT_FIELDS = [
    "tag_id", "slug", "label", "type", "lang",
    "item_count", "page_path", "status", "error",
]


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tags(tags_path: Path = DEFAULT_TAGS) -> list[dict]:
    """Load all tags from tags.yaml."""
    import yaml
    with tags_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("tags", [])


def load_issue_jsons(content_dir: Path, lang: str) -> list[dict]:
    """Load all YYYY-MM-DD.{lang}.json files from content_dir."""
    issues = []
    for p in sorted(content_dir.glob(f"*.{lang}.json")):
        try:
            with p.open("r", encoding="utf-8") as fh:
                issues.append(json.load(fh))
        except (json.JSONDecodeError, OSError):
            pass
    return issues


def build_tag_index(issues: list[dict]) -> dict[str, list[dict]]:
    """Return {tag_id: [{issue_date, item}, ...]} from issue dicts.

    Items are deduplicated by id; the most recent issue wins.
    """
    index: dict[str, list[dict]] = {}
    seen_ids: set = set()
    for issue in sorted(issues, key=lambda i: i.get("issue_date", ""), reverse=True):
        issue_date = issue.get("issue_date", "")
        for item in issue.get("items", []):
            item_id = item.get("id")
            if item_id is not None and item_id in seen_ids:
                continue
            if item_id is not None:
                seen_ids.add(item_id)
            tags_str = str(item.get("matched_tags") or "")
            for tid in [t.strip() for t in tags_str.split(",") if t.strip()]:
                index.setdefault(tid, [])
                index[tid].append({"issue_date": issue_date, "item": item})
    return index


# ---------------------------------------------------------------------------
# Rendering helpers
# ---------------------------------------------------------------------------

def _render(template_src: str, ctx: dict) -> str:
    from scripts.build_issue import _J2Renderer
    return _J2Renderer().render(template_src, ctx)


def _out_path(path: Path) -> str:
    try:
        return str(path.relative_to(_REPO_ROOT))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------------------
# Page builders
# ---------------------------------------------------------------------------

def _build_tag_page(
    tag: dict,
    tag_map: dict,
    tag_index: dict,
    lng: str,
    locale: dict,
    template_src: str,
    dist_dir: Path,
    dry_run: bool,
    base_path: str = "",
) -> tuple[int, dict]:
    """Build one tag page. Returns (pages_written, report_row)."""
    tid = tag["id"]
    slug = tag.get("slug", tid)
    entries = tag_index.get(tid, [])

    description = tag.get(f"description_{lng}") or tag.get("description_en", "")

    related = []
    for rtid in (tag.get("related_tags") or []):
        if rtid in tag_map:
            rt = tag_map[rtid]
            rslug = rt.get("slug", rtid)
            related.append({
                "id": rtid,
                "slug": rslug,
                "label": rt["label"],
                "href": f"{base_path}/{lng}/tags/{rslug}.html",
            })

    items_ctx = [
        {
            "title": e["item"].get("title", ""),
            "url": e["item"].get("url", ""),
            "source_name": e["item"].get("source_name", ""),
            "score": e["item"].get("score", 0),
            "matched_artists": e["item"].get("matched_artists", ""),
            "published_at": e["item"].get("published_at", ""),
            "issue_date": e["issue_date"],
            "issue_href": f"{base_path}/{lng}/issues/{e['issue_date']}.html",
        }
        for e in sorted(entries, key=lambda x: x["issue_date"], reverse=True)
    ]

    ctx = {
        "lang": lng,
        "site_heading": locale["site_heading"],
        "heading": tag["label"],
        "tag_label": tag["label"],
        "tag_type": tag.get("type", ""),
        "tag_description": description,
        "related_tags": related,
        "items": items_ctx,
        "no_items_message": locale["no_items"],
        "back_to_index": locale["back_to_index"],
        "back_href": f"{base_path}/{lng}/tags/index.html",
        "nav_en_href": f"{base_path}/en/tags/index.html",
        "nav_uk_href": f"{base_path}/uk/tags/index.html",
        "items_heading": locale["items_heading"],
        "related_heading": locale["related_heading"],
    }

    page_path = f"dist/{lng}/tags/{slug}.html"
    status = "dry_run" if dry_run else "ok"
    error = ""
    written = 0

    if not dry_run:
        try:
            html = _render(template_src, ctx)
            out_dir = dist_dir / lng / "tags"
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / f"{slug}.html"
            out_path.write_text(html, encoding="utf-8")
            written = 1
        except Exception as exc:
            status = "error"
            error = str(exc)

    row = {
        "tag_id": tid,
        "slug": slug,
        "label": tag["label"],
        "type": tag.get("type", ""),
        "lang": lng,
        "item_count": len(items_ctx),
        "page_path": page_path,
        "status": status,
        "error": error,
    }
    return written, row


def _build_index_page(
    tags: list[dict],
    tag_index: dict,
    lng: str,
    locale: dict,
    template_src: str,
    dist_dir: Path,
    dry_run: bool,
    base_path: str = "",
) -> tuple[int, dict]:
    """Build the tag index page. Returns (pages_written, report_row)."""
    groups = []
    for ttype in _TYPE_ORDER:
        type_tags = [t for t in tags if t.get("type") == ttype]
        if not type_tags:
            continue
        group_tags = []
        for t in type_tags:
            ttid = t["id"]
            tslug = t.get("slug", ttid)
            group_tags.append({
                "id": ttid,
                "slug": tslug,
                "label": t["label"],
                "description": t.get(f"description_{lng}") or t.get("description_en", ""),
                "count": len(tag_index.get(ttid, [])),
                "href": f"{base_path}/{lng}/tags/{tslug}.html",
            })
        groups.append({
            "type_id": ttype,
            "type_label": locale["type_labels"].get(ttype, ttype),
            "tags": group_tags,
        })

    ctx = {
        "lang": lng,
        "site_heading": locale["site_heading"],
        "heading": locale["tag_index_heading"],
        "nav_en_href": f"{base_path}/en/tags/index.html",
        "nav_uk_href": f"{base_path}/uk/tags/index.html",
        "groups": groups,
    }

    status = "dry_run" if dry_run else "ok"
    error = ""
    written = 0

    if not dry_run:
        try:
            html = _render(template_src, ctx)
            idx_dir = dist_dir / lng / "tags"
            idx_dir.mkdir(parents=True, exist_ok=True)
            idx_path = idx_dir / "index.html"
            idx_path.write_text(html, encoding="utf-8")
            written = 1
        except Exception as exc:
            status = "error"
            error = str(exc)

    row = {
        "tag_id": "INDEX",
        "slug": "index",
        "label": locale["tag_index_heading"],
        "type": "",
        "lang": lng,
        "item_count": sum(len(v) for v in tag_index.values()),
        "page_path": f"dist/{lng}/tags/index.html",
        "status": status,
        "error": error,
    }
    return written, row


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_tag_pages(
    tags_path: Path = DEFAULT_TAGS,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dist_dir: Path = DEFAULT_DIST_DIR,
    lang: str | None = None,
    dry_run: bool = False,
    report_path: Path = DEFAULT_REPORT,
    tag_template_path: Path = DEFAULT_TAG_TEMPLATE,
    index_template_path: Path = DEFAULT_INDEX_TEMPLATE,
    base_path: str = "",
) -> dict:
    """Build tag pages for all requested languages. Returns summary dict."""
    base_path = normalize_base_path(base_path)
    tags = load_tags(tags_path)
    tag_map = {t["id"]: t for t in tags}
    languages = [lang] if lang else ["en", "uk"]

    tag_template_src = tag_template_path.read_text(encoding="utf-8")
    index_template_src = index_template_path.read_text(encoding="utf-8")

    unknown_tags: set[str] = set()
    output_files: list[str] = []
    report_rows: list[dict] = []
    pages_written = 0
    tags_with_items_sets: list[set] = []

    for lng in languages:
        locale = _LOCALE.get(lng, _LOCALE["en"])
        issues = load_issue_jsons(content_dir, lng)
        tag_index = build_tag_index(issues)

        for tid in tag_index:
            if tid not in tag_map:
                unknown_tags.add(tid)

        tags_with_items_sets.append({tid for tid in tag_index if tid in tag_map})

        for tag in tags:
            written, row = _build_tag_page(
                tag, tag_map, tag_index, lng, locale,
                tag_template_src, dist_dir, dry_run,
                base_path=base_path,
            )
            pages_written += written
            report_rows.append(row)
            if written:
                out_path = dist_dir / lng / "tags" / f"{tag.get('slug', tag['id'])}.html"
                output_files.append(_out_path(out_path))

        for tid in tag_index:
            if tid not in tag_map:
                report_rows.append({
                    "tag_id": tid,
                    "slug": tid,
                    "label": tid,
                    "type": "",
                    "lang": lng,
                    "item_count": len(tag_index[tid]),
                    "page_path": "",
                    "status": "unknown_tag",
                    "error": f"'{tid}' not in tags.yaml",
                })

        written, idx_row = _build_index_page(
            tags, tag_index, lng, locale,
            index_template_src, dist_dir, dry_run,
            base_path=base_path,
        )
        pages_written += written
        report_rows.append(idx_row)
        if written:
            idx_path = dist_dir / lng / "tags" / "index.html"
            output_files.append(_out_path(idx_path))

    if not dry_run:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_REPORT_FIELDS)
            writer.writeheader()
            writer.writerows(report_rows)

    tags_with_items = len(set().union(*tags_with_items_sets) if tags_with_items_sets else set())

    return {
        "languages": languages,
        "tags_total": len(tags),
        "tags_with_items": tags_with_items,
        "pages_written": pages_written,
        "unknown_tags": sorted(unknown_tags),
        "output_files": output_files,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build static bilingual tag pages from issue JSON drafts."
    )
    parser.add_argument("--lang", choices=["en", "uk"], default=None,
                        help="Language to build (default: both en and uk)")
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR,
                        dest="content_dir")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR,
                        dest="dist_dir")
    parser.add_argument("--tags", type=Path, default=DEFAULT_TAGS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and render without writing files")
    parser.add_argument("--base-path", default="", dest="base_path",
                        help="Base path prefix for internal links, e.g. /coma-artist-radar")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_tag_pages(
        tags_path=args.tags,
        content_dir=args.content_dir,
        dist_dir=args.dist_dir,
        lang=args.lang,
        dry_run=args.dry_run,
        report_path=args.report,
        base_path=args.base_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

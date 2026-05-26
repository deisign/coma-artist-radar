#!/usr/bin/env python3
"""Build a static bilingual HTML issue from scored items in coma_radar.sqlite.

Usage:
    python3 scripts/build_issue.py --date 2026-05-25 --draft --limit 10
    python3 scripts/build_issue.py --date 2026-05-25 --lang uk --draft --limit 10
    python3 scripts/build_issue.py --date 2026-05-25
"""
from __future__ import annotations

import argparse
import html
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
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_TEMPLATE = _REPO_ROOT / "templates" / "issue.html.j2"
DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_MIN_SCORE = 30
DEFAULT_LIMIT = 50

def normalize_base_path(path: str) -> str:
    """Normalize base_path: '' or '/' -> '', 'foo' -> '/foo', '/foo/' -> '/foo'."""
    path = path.strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


_LOCALE: dict[str, dict[str, str]] = {
    "en": {
        "heading": "coma.fm Radar",
        "intro": "A weekly digest of music from the coma.fm field.",
        "draft_notice": "Draft — not published",
        "no_items": "No items for this issue.",
    },
    "uk": {
        "heading": "coma.fm Радар",
        "intro": "Щотижневий дайджест музики з поля coma.fm.",
        "draft_notice": "Чернетка — не опубліковано",
        "no_items": "Для цього випуску немає матеріалів.",
    },
}


# ---------------------------------------------------------------------------
# Minimal Jinja2-subset renderer
# ---------------------------------------------------------------------------

class _J2Renderer:
    """Renders a Jinja2-like template using only Python stdlib.

    Supported: {{ expr }}, {% for x in y %}...{% endfor %},
               {% if cond %}...{% else %}...{% endif %}, {# comment #},
               == and != comparisons in if-conditions, dot-notation lookups.
    """

    _TOK = re.compile(
        r"(\{%-?\s*.*?\s*-?%\}|\{\{-?\s*.*?\s*-?\}\}|\{#.*?#\})",
        re.DOTALL,
    )

    def render(self, src: str, ctx: dict) -> str:
        return "".join(self._seq(self._TOK.split(src), 0, ctx)[0])

    def _val(self, expr: str, ctx: dict):
        expr = expr.strip()
        if "|" in expr:
            expr = expr.split("|")[0].strip()
        parts = expr.split(".")
        v = ctx.get(parts[0])
        for p in parts[1:]:
            v = v.get(p) if isinstance(v, dict) else None
        return v

    def _cond(self, expr: str, ctx: dict) -> bool:
        for op in (" == ", " != "):
            if op in expr:
                lhs, rhs = expr.split(op, 1)
                lv = self._val(lhs, ctx)
                rv = rhs.strip().strip('"').strip("'")
                return (str(lv) == rv) if " == " in op else (str(lv) != rv)
        return bool(self._val(expr, ctx))

    def _out(self, val) -> str:
        if val is None:
            return ""
        if isinstance(val, str):
            return html.escape(val)
        return str(val)

    def _seq(self, toks: list, pos: int, ctx: dict) -> tuple[list, int]:
        result: list[str] = []
        n = len(toks)
        while pos < n:
            t = toks[pos]
            if not t:
                pos += 1
                continue
            if t.startswith("{#"):
                pos += 1
                continue
            if t.startswith("{{"):
                m = re.match(r"\{\{-?\s*(.*?)\s*-?\}\}", t, re.DOTALL)
                result.append(self._out(self._val(m.group(1), ctx)) if m else "")
                pos += 1
                continue
            if t.startswith("{%"):
                m = re.match(r"\{%-?\s*(.*?)\s*-?%\}", t, re.DOTALL)
                tag = m.group(1).strip() if m else ""
                pos += 1
                if re.match(r"for\s", tag):
                    fm = re.match(r"for\s+(\w+)\s+in\s+([\w.]+)", tag)
                    if fm:
                        body, pos = self._until(toks, pos, "for", "endfor")
                        coll = self._val(fm.group(2), ctx)
                        if isinstance(coll, (list, tuple)):
                            for item in coll:
                                r2, _ = self._seq(body, 0, {**ctx, fm.group(1): item})
                                result.extend(r2)
                elif re.match(r"if\s", tag):
                    if_b, else_b, pos = self._if_blocks(toks, pos)
                    chosen = if_b if self._cond(tag[3:], ctx) else else_b
                    r2, _ = self._seq(chosen, 0, ctx)
                    result.extend(r2)
                continue
            result.append(t)
            pos += 1
        return result, pos

    def _until(self, toks: list, pos: int, open_kw: str, close_kw: str) -> tuple[list, int]:
        body: list[str] = []
        depth = 1
        op = re.compile(r"\{%-?\s*" + re.escape(open_kw) + r"\s")
        cl = re.compile(r"\{%-?\s*" + re.escape(close_kw) + r"\s*-?%\}")
        while pos < len(toks) and depth:
            t = toks[pos]
            if op.search(t):
                depth += 1
            elif cl.search(t):
                depth -= 1
                if not depth:
                    pos += 1
                    break
            if depth:
                body.append(t)
            pos += 1
        return body, pos

    def _if_blocks(self, toks: list, pos: int) -> tuple[list, list, int]:
        if_b: list[str] = []
        else_b: list[str] = []
        in_else = False
        depth = 1
        if_re = re.compile(r"\{%-?\s*if\s")
        end_re = re.compile(r"\{%-?\s*endif\s*-?%\}")
        else_re = re.compile(r"\{%-?\s*else\s*-?%\}")
        while pos < len(toks) and depth:
            t = toks[pos]
            if if_re.search(t):
                depth += 1
            elif end_re.search(t):
                depth -= 1
                if not depth:
                    pos += 1
                    break
            elif else_re.search(t) and depth == 1:
                in_else = True
                pos += 1
                continue
            if depth:
                (else_b if in_else else if_b).append(t)
            pos += 1
        return if_b, else_b, pos


# ---------------------------------------------------------------------------
# Tag map
# ---------------------------------------------------------------------------

def load_tag_map(tags_path: Path = DEFAULT_TAGS) -> dict[str, dict]:
    """Return {tag_id: {slug, label}} from tags.yaml."""
    import yaml
    with tags_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {
        tag["id"]: {"slug": tag.get("slug", tag["id"]), "label": tag.get("label", tag["id"])}
        for tag in data.get("tags", [])
    }


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def load_items(
    db_path: Path,
    min_score: int = DEFAULT_MIN_SCORE,
    limit: int = DEFAULT_LIMIT,
) -> list[dict]:
    """Load top-scored items from the database."""
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT id, title, url, source_name, source_type, published_at, "
        "score, matched_artists, matched_tags, matched_genres "
        "FROM items "
        "WHERE score >= ? "
        "ORDER BY score DESC "
        "LIMIT ?",
        (min_score, limit),
    ).fetchall()
    conn.close()
    cols = [
        "id", "title", "url", "source_name", "source_type",
        "published_at", "score", "matched_artists", "matched_tags", "matched_genres",
    ]
    return [dict(zip(cols, row)) for row in rows]


# ---------------------------------------------------------------------------
# Item enrichment
# ---------------------------------------------------------------------------

def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10] if len(date_str) >= 10 else date_str


def enrich_items(items: list[dict], tag_map: dict) -> list[dict]:
    """Add a structured 'tags' list to each item and format dates."""
    enriched = []
    for item in items:
        tags_str = str(item.get("matched_tags") or "")
        tag_ids = [t.strip() for t in tags_str.split(",") if t.strip()]
        tags = [
            {"id": tid, "slug": tag_map[tid]["slug"], "label": tag_map[tid]["label"]}
            for tid in tag_ids
            if tid in tag_map
        ]
        enriched.append({
            **item,
            "published_at": _format_date(str(item.get("published_at") or "")),
            "matched_artists": str(item.get("matched_artists") or ""),
            "tags": tags,
        })
    return enriched


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_html(
    items: list[dict],
    issue_date: str,
    lang: str,
    draft: bool,
    template_path: Path = DEFAULT_TEMPLATE,
    base_path: str = "",
) -> str:
    base_path = normalize_base_path(base_path)
    locale = _LOCALE.get(lang, _LOCALE["en"])
    ctx = {
        "lang": lang,
        "title": f"coma.fm Radar — {issue_date} — {lang.upper()}",
        "description": locale["intro"],
        "issue_date": issue_date,
        "heading": locale["heading"],
        "intro": locale["intro"],
        "no_items_message": locale["no_items"],
        "draft": draft,
        "draft_notice": locale["draft_notice"],
        "items": items,
        "nav_en_href": f"{base_path}/en/issues/{issue_date}.html",
        "nav_uk_href": f"{base_path}/uk/issues/{issue_date}.html",
        "tag_href_prefix": f"{base_path}/{lang}/tags",
        "asset_path": f"{base_path}/assets",
    }
    template_src = template_path.read_text(encoding="utf-8")
    return _J2Renderer().render(template_src, ctx)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_issue(
    db_path: Path = DEFAULT_DB,
    issue_date: str | None = None,
    lang: str | None = None,
    limit: int = DEFAULT_LIMIT,
    min_score: int = DEFAULT_MIN_SCORE,
    draft: bool = False,
    template_path: Path = DEFAULT_TEMPLATE,
    tags_path: Path = DEFAULT_TAGS,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dist_dir: Path = DEFAULT_DIST_DIR,
    base_path: str = "",
) -> dict:
    """Build HTML issue(s) and JSON drafts. Returns summary dict."""
    if issue_date is None:
        issue_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    languages = [lang] if lang else ["en", "uk"]
    tag_map = load_tag_map(tags_path)
    raw_items = load_items(db_path, min_score=min_score, limit=limit)
    items = enrich_items(raw_items, tag_map)

    output_files: list[str] = []
    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for lng in languages:
        # --- HTML ---
        html_dir = dist_dir / lng / "issues"
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{issue_date}.html"
        html_content = render_html(items, issue_date, lng, draft, template_path, base_path)
        html_path.write_text(html_content, encoding="utf-8")
        try:
            output_files.append(str(html_path.relative_to(_REPO_ROOT)))
        except ValueError:
            output_files.append(str(html_path))

        # --- JSON ---
        content_dir.mkdir(parents=True, exist_ok=True)
        json_path = content_dir / f"{issue_date}.{lng}.json"
        issue_data = {
            "issue_date": issue_date,
            "lang": lng,
            "draft": draft,
            "generated_at": now_iso,
            "min_score": min_score,
            "total_items": len(items),
            "items": [
                {
                    "id": it["id"],
                    "title": it["title"],
                    "url": it["url"],
                    "source_name": it["source_name"],
                    "published_at": it["published_at"],
                    "score": it["score"],
                    "matched_artists": it["matched_artists"],
                    "matched_tags": it.get("matched_tags", ""),
                    "matched_genres": it.get("matched_genres", ""),
                }
                for it in items
            ],
        }
        json_path.write_text(
            json.dumps(issue_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            output_files.append(str(json_path.relative_to(_REPO_ROOT)))
        except ValueError:
            output_files.append(str(json_path))

    return {
        "issue_date": issue_date,
        "languages": languages,
        "selected_items": len(items),
        "output_files": output_files,
        "draft": draft,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static bilingual issue HTML from scored items."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--date", dest="issue_date", default=None,
        help="Issue date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--lang", choices=["en", "uk"], default=None,
        help="Language to build (default: both en and uk)",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--draft", action="store_true",
                        help="Mark output as draft")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--base-path", default="", dest="base_path",
                        help="Base path prefix for internal links, e.g. /coma-artist-radar")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 1

    summary = build_issue(
        db_path=args.db,
        issue_date=args.issue_date,
        lang=args.lang,
        limit=args.limit,
        min_score=args.min_score,
        draft=args.draft,
        template_path=args.template,
        base_path=args.base_path,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

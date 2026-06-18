#!/usr/bin/env python3
"""Build a Telegram dry-run announcement post from a built issue JSON.

Usage:
    python scripts/build_telegram_draft.py --date 2026-05-26 --lang uk
    python scripts/build_telegram_draft.py --date 2026-05-26 --lang en --json
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_BASE_URL = "https://radar.coma.fm"
DEFAULT_BASE_PATH = ""
DEFAULT_MAX_CHARS = 3500
DEFAULT_LIMIT_ITEMS = 10

CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DIST_DIR = _REPO_ROOT / "dist"
REPORTS_DIR = _REPO_ROOT / "reports" / "telegram"
TEMPLATES_DIR = _REPO_ROOT / "templates"

_EDITORIAL_TAGS = frozenset({
    "review", "reissue", "interview", "essay", "podcast",
    "scene-report", "label-profile", "archive-release",
    "live-recording", "new-release", "editor-note", "evergreen",
    "good-for-telegram", "high-priority", "must-use", "needs-check",
    "duplicate-risk", "bad-radio-signal", "celebrity-gossip",
    "seo-listicle", "press-release-only", "ai-generated-spam",
    "time-sensitive",
})


def _music_tags(tags_str: str, max_tags: int = 3) -> str:
    if not tags_str:
        return ""
    parts = [t.strip().replace("_", "-") for t in tags_str.split(",")]
    music: list[str] = []
    seen: set[str] = set()
    for tag in parts:
        if not tag or tag in _EDITORIAL_TAGS or tag in seen:
            continue
        seen.add(tag)
        music.append(tag)
    return ", ".join(music[:max_tags])


def _short_title(title: str, max_len: int = 96) -> str:
    t = title.strip()
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


_SIGNAL_EMOJI = {
    "review": "🎧",
    "release": "💿",
    "video": "🎬",
    "interview": "🎙️",
    "podcast": "🎙️",
    "signal": "🛰️",
}


def _html(value: str) -> str:
    return html.escape(value or "", quote=False)


def _tag_markup(tags_str: str) -> str:
    if not tags_str:
        return ""
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]
    return " ".join(f"<code>{_html(tag)}</code>" for tag in tags)


def _render_post(date: str, lang: str, issue_url: str, items: list[dict]) -> str:
    """Render the Telegram post as Telegram HTML."""
    if lang == "uk":
        section_label = "Сьогодні в дайджесті:"
        footer_label = "Повний випуск:"
    else:
        section_label = "In today's digest:"
        footer_label = "Full issue:"

    item_blocks = []
    for item in items:
        emoji = _SIGNAL_EMOJI.get(item.get("signal_type") or "", "🛰️")
        title = _html(item["title_short"])
        source = _html(item.get("source_name") or "")
        tags = _tag_markup(item.get("tags_str") or "")

        block_lines = [f"{emoji} <b>{title}</b>"]
        meta_parts = [part for part in (source, tags) if part]
        if meta_parts:
            block_lines.append(" · ".join(meta_parts))
        item_blocks.append("\n".join(block_lines))

    parts = [
        "📡 <b>coma.fm Radar</b>",
        date,
        "",
        f"<b>{section_label}</b>",
        "",
        "\n\n".join(item_blocks),
        "",
        f"<b>{footer_label}</b>",
        _html(issue_url),
    ]
    return "\n".join(parts)


def build_telegram_draft(
    date: str,
    lang: str = "uk",
    base_url: str = DEFAULT_BASE_URL,
    base_path: str = DEFAULT_BASE_PATH,
    max_chars: int = DEFAULT_MAX_CHARS,
    limit_items: int = DEFAULT_LIMIT_ITEMS,
    dry_run: bool = True,
    content_dir: Path = CONTENT_DIR,
    dist_dir: Path = DIST_DIR,
    reports_dir: Path = REPORTS_DIR,
    templates_dir: Path = TEMPLATES_DIR,
) -> dict:
    """Build a Telegram dry-run post. Returns a summary dict."""
    warnings_list: list[str] = []
    base_path = base_path.rstrip("/")
    if not base_path.startswith("/"):
        base_path = "/" + base_path

    issue_path = content_dir / f"{date}.{lang}.json"
    if not issue_path.exists():
        raise FileNotFoundError(f"Issue JSON not found: {issue_path}")

    issue = json.loads(issue_path.read_text(encoding="utf-8"))
    all_items = issue.get("items", [])

    base = base_url.rstrip("/")
    issue_url = f"{base}/{lang}/issues/{date}.html"

    cover_local = dist_dir / "assets" / "covers" / "issues" / date / f"cover-{lang}.svg"
    if cover_local.exists():
        cover_url: str | None = (
            f"{base}/assets/covers/issues/{date}/cover-{lang}.svg"
        )
    else:
        cover_url = None
        warnings_list.append(f"Cover not found: {cover_local}")

    if len(all_items) < 3:
        warnings_list.append(
            f"Issue has only {len(all_items)} item(s); expected at least 3 for a full Telegram post."
        )

    selected = all_items[:limit_items]

    def make_item(raw: dict) -> dict:
        tag_source = ",".join(
            part for part in (
                raw.get("matched_tags", ""),
                raw.get("matched_genres", ""),
            )
            if part
        )
        return {
            "title_short": _short_title(raw.get("title", ""), max_len=96),
            "tags_str": _music_tags(tag_source),
            "signal_type": raw.get("signal_type", ""),
            "source_name": raw.get("source_name", ""),
        }

    template_items = [make_item(r) for r in selected]
    text = _render_post(date, lang, issue_url, template_items)

    while len(text) > max_chars and len(template_items) > 1:
        template_items = template_items[:-1]
        text = _render_post(date, lang, issue_url, template_items)

    if len(text) > max_chars and template_items:
        for field in ("tags_str", "source_name"):
            if len(text) <= max_chars:
                break
            template_items[-1] = {**template_items[-1], field: ""}
            text = _render_post(date, lang, issue_url, template_items)

        while len(text) > max_chars and len(template_items[-1]["title_short"]) > 1:
            last = template_items[-1]
            overflow = len(text) - max_chars
            cut = max(1, len(last["title_short"]) - overflow - 1)
            if cut >= len(last["title_short"]):
                cut = len(last["title_short"]) - 1
            template_items[-1] = {**last, "title_short": last["title_short"][:cut].rstrip() + "…"}
            text = _render_post(date, lang, issue_url, template_items)

    reports_dir.mkdir(parents=True, exist_ok=True)
    output_path = reports_dir / f"{date}.{lang}.txt"
    output_path.write_text(text, encoding="utf-8")

    return {
        "issue_date": date,
        "lang": lang,
        "output_file": str(output_path),
        "issue_url": issue_url,
        "cover_url": cover_url,
        "chars": len(text),
        "max_chars": max_chars,
        "item_count": len(template_items),
        "warnings": warnings_list,
        "dry_run": dry_run,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Build a Telegram dry-run announcement post from an issue JSON."
    )
    p.add_argument("--date", required=True, help="Issue date YYYY-MM-DD")
    p.add_argument("--lang", default="uk", choices=["uk", "en"])
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, dest="base_url")
    p.add_argument("--base-path", default=DEFAULT_BASE_PATH, dest="base_path")
    p.add_argument(
        "--max-chars", type=int, default=DEFAULT_MAX_CHARS, dest="max_chars"
    )
    p.add_argument(
        "--limit-items", type=int, default=DEFAULT_LIMIT_ITEMS, dest="limit_items"
    )
    p.add_argument("--dry-run", action="store_true", default=True, dest="dry_run")
    p.add_argument(
        "--json", action="store_true", default=False, dest="as_json",
        help="Print JSON summary",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_telegram_draft(
        date=args.date,
        lang=args.lang,
        base_url=args.base_url,
        base_path=args.base_path,
        max_chars=args.max_chars,
        limit_items=args.limit_items,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

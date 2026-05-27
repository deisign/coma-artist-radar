#!/usr/bin/env python3
"""Generate SVG cover images for coma.fm Radar issues.

Covers are placed at:
  dist/assets/covers/issues/YYYY-MM-DD/cover-en.svg
  dist/assets/covers/issues/YYYY-MM-DD/cover-uk.svg

Usage:
    python3 scripts/generate_issue_cover.py --date 2026-05-26 --lang all
    python3 scripts/generate_issue_cover.py --date 2026-05-26 --lang en --main-tag surf
    python3 scripts/generate_issue_cover.py --date 2026-05-26 --dry-run --json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_TEMPLATES_DIR = _REPO_ROOT / "templates"
DEFAULT_THEMES = _REPO_ROOT / "data" / "visual_themes.yaml"
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"

_COVER_TEMPLATE = "cover.svg.j2"

# Priority order for main-tag type selection
_TYPE_PRIORITY = ("aesthetic", "genre", "subgenre", "content_type", "editorial")

# Deterministic visual cover modes — selected from tx_code hash
_COVER_MODES = ["concentric", "frequency_bars", "modular_skyline", "tuner_scale", "horizon_signal"]
_NODE = "COMA-RADAR"


# ---------------------------------------------------------------------------
# Cover mode — deterministic visual system
# ---------------------------------------------------------------------------

def cover_mode_from_tx_code(tx_code: str) -> str:
    """Deterministically select a cover mode from the tx_code hash."""
    raw = hashlib.sha256(tx_code.encode("utf-8")).digest()
    return _COVER_MODES[raw[0] % len(_COVER_MODES)]


def _build_cover_mode_ctx(tx_code: str) -> dict:
    """Build mode-specific SVG context values from tx_code hash."""
    mode = cover_mode_from_tx_code(tx_code)
    b = hashlib.sha256(tx_code.encode("utf-8")).digest()
    ctx: dict = {"cover_mode": mode}

    if mode == "concentric":
        cx = 300 + (b[1] % 300)
        cy = 440 + (b[2] % 100)
        specs = [
            (290, "0.26", "1.5"),
            (240, "0.22", "1"),
            (185, "0.19", "1.5"),
            (136, "0.17", "1"),
            (90,  "0.15", "1.5"),
            (48,  "0.13", "1"),
        ]
        ctx["cover_cx"] = cx
        ctx["cover_cy"] = cy
        ctx["cover_arc_r"] = 18
        ctx["cover_arcs"] = [
            {"r": r, "opacity": op, "sw": sw} for r, op, sw in specs
        ]

    elif mode == "frequency_bars":
        n, bar_w, gap = 14, 22, 10
        start_x = 90 + (b[1] % 50)
        bars = []
        for i in range(n):
            h = 55 + (b[(i + 3) % 32] % 295)
            bars.append({
                "x": start_x + i * (bar_w + gap),
                "y": 675 - h,
                "h": h,
                "w": bar_w,
            })
        ctx["cover_bars"] = bars

    elif mode == "modular_skyline":
        n, start_x, col_w = 9, 75, 83
        modules = []
        for i in range(n):
            h = 80 + (b[(i + 5) % 32] % 340)
            gap_v = 5 + (b[(i + 11) % 32] % 5)
            w = col_w - gap_v * 2
            modules.append({
                "x": start_x + i * col_w + gap_v,
                "y": 675 - h,
                "h": h,
                "w": w,
            })
        ctx["cover_modules"] = modules

    elif mode == "tuner_scale":
        needle_x = 120 + (b[1] % 620)
        scale_x0, freq_range = 80, 20
        tick_space = 740 / freq_range
        ticks = []
        for i in range(freq_range + 1):
            x = scale_x0 + int(i * tick_space)
            freq = 88 + i
            major = (freq % 4 == 0)
            ticks.append({
                "x": x,
                "freq": str(freq) if major else "",
                "y1": 542,
                "y2": 542 + (22 if major else 12),
                "text_y": 530,
                "sw": "1.5" if major else "0.75",
            })
        ctx["cover_needle_x"] = needle_x
        ctx["cover_ticks"] = ticks

    elif mode == "horizon_signal":
        rows = []
        y = 280
        for i in range(32):
            stride = 9 + (b[(i + 7) % 32] % 18)
            y += stride
            if y > 700:
                break
            x0 = 60 + (b[(i + 2) % 32] % 50)
            x1 = 840 - (b[(i + 4) % 32] % 70)
            opc = min(0.12 + (i % 7) * 0.04, 0.42)
            sw = "1.5" if i % 5 == 0 else ("0.75" if i % 3 == 0 else "1")
            rows.append({
                "y": y, "x0": x0, "x1": x1,
                "opacity": f"{opc:.2f}", "sw": sw,
            })
        ctx["cover_horizon_rows"] = rows

    return ctx


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_themes(themes_path: Path = DEFAULT_THEMES) -> dict[str, dict]:
    """Return {theme_id: theme_dict} from visual_themes.yaml."""
    import yaml
    with themes_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {t["id"]: t for t in data.get("themes", [])}


def load_tags_typed(tags_path: Path = DEFAULT_TAGS) -> dict[str, str]:
    """Return {tag_id: tag_type} from tags.yaml."""
    import yaml
    with tags_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {
        str(t.get("id", "") or "").strip(): str(t.get("type", "") or "").strip()
        for t in data.get("tags", [])
        if t.get("id")
    }


# ---------------------------------------------------------------------------
# Main-tag detection
# ---------------------------------------------------------------------------

def detect_main_tag_from_items(
    items: list[dict],
    tags_typed: dict[str, str],
) -> str | None:
    """Return the dominant tag by aesthetic > genre > subgenre priority."""
    counts: Counter = Counter()
    for item in items:
        tags_str = str(item.get("matched_tags") or "")
        for tid in [t.strip() for t in tags_str.split(",") if t.strip()]:
            counts[tid] += 1

    if not counts:
        return None

    for ttype in _TYPE_PRIORITY:
        candidates = [tid for tid, _ in counts.most_common() if tags_typed.get(tid) == ttype]
        if candidates:
            return candidates[0]

    # Fallback: most frequent tag regardless of type
    return counts.most_common(1)[0][0]


def _load_items_from_json(content_dir: Path, issue_date: str, lang: str) -> list[dict]:
    """Load items from content/issues/YYYY-MM-DD.{lang}.json if it exists."""
    p = content_dir / f"{issue_date}.{lang}.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("items", [])
    except (json.JSONDecodeError, OSError):
        return []


# ---------------------------------------------------------------------------
# Theme selection
# ---------------------------------------------------------------------------

def get_theme(main_tag: str | None, themes: dict[str, dict]) -> dict:
    """Return theme dict for main_tag, falling back to 'default'."""
    if main_tag and main_tag in themes:
        return themes[main_tag]
    return themes.get("default", next(iter(themes.values())))


# ---------------------------------------------------------------------------
# SVG rendering
# ---------------------------------------------------------------------------

def _render_svg(template_src: str, ctx: dict) -> str:
    from scripts.build_issue import _J2Renderer
    return _J2Renderer().render(template_src, ctx)


def _build_svg_ctx(
    theme: dict,
    title: str,
    subtitle: str,
    issue_date: str,
    main_tag_label: str,
    item_count: int,
    lang: str,
) -> dict:
    """Build the template context for cover.svg.j2."""
    tag_pill_width = max(140, len(main_tag_label) * 12 + 48)
    date_compact = issue_date.replace("-", "")
    tx_code = f"TX-{date_compact}-{lang.upper()}"
    cover_ctx = _build_cover_mode_ctx(tx_code)
    return {
        "bg": theme["background"],
        "surface": theme["surface"],
        "text_color": theme["text"],
        "muted": theme["muted"],
        "accent": theme["accent"],
        "accent_2": theme["accent_2"],
        "motif": theme["motif"],
        "title": title,
        "subtitle": subtitle,
        "issue_date": issue_date,
        "main_tag_label": main_tag_label,
        "item_count": item_count,
        "lang_label": lang.upper(),
        "tag_pill_width": tag_pill_width,
        "tx_code": tx_code,
        "band": "88–108 FM",
        "node": _NODE,
        **cover_ctx,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_issue_cover(
    issue_date: str,
    lang: str,
    main_tag: str | None = None,
    title: str = "coma.fm Radar",
    subtitle: str = "",
    item_count: int = 0,
    dist_dir: Path = DEFAULT_DIST_DIR,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    themes_path: Path = DEFAULT_THEMES,
    tags_path: Path = DEFAULT_TAGS,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dry_run: bool = False,
) -> dict:
    """Generate a single-language SVG cover. Returns summary dict."""
    themes = load_themes(themes_path)
    tags_typed = load_tags_typed(tags_path)

    # Determine main_tag if not provided
    resolved_tag = main_tag
    if resolved_tag is None:
        items = _load_items_from_json(content_dir, issue_date, lang)
        resolved_tag = detect_main_tag_from_items(items, tags_typed)

    theme = get_theme(resolved_tag, themes)
    main_tag_label = theme["label"]

    template_path = templates_dir / _COVER_TEMPLATE
    template_src = template_path.read_text(encoding="utf-8")

    ctx = _build_svg_ctx(
        theme=theme,
        title=title,
        subtitle=subtitle,
        issue_date=issue_date,
        main_tag_label=main_tag_label,
        item_count=item_count,
        lang=lang,
    )
    svg = _render_svg(template_src, ctx)

    out_path = dist_dir / "assets" / "covers" / "issues" / issue_date / f"cover-{lang}.svg"

    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(svg, encoding="utf-8")

    return {
        "issue_date": issue_date,
        "lang": lang,
        "main_tag": resolved_tag,
        "theme_id": theme["id"],
        "output_file": str(out_path),
        "dry_run": dry_run,
    }


def generate_issue_covers(
    issue_date: str,
    languages: list[str],
    main_tag: str | None = None,
    title: str = "coma.fm Radar",
    subtitle: str = "",
    item_count: int = 0,
    dist_dir: Path = DEFAULT_DIST_DIR,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    themes_path: Path = DEFAULT_THEMES,
    tags_path: Path = DEFAULT_TAGS,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dry_run: bool = False,
) -> dict:
    """Generate covers for all requested languages. Returns summary dict."""
    output_files: list[str] = []
    theme_id = None
    resolved_tag = main_tag

    for lang in languages:
        result = generate_issue_cover(
            issue_date=issue_date,
            lang=lang,
            main_tag=resolved_tag,
            title=title,
            subtitle=subtitle,
            item_count=item_count,
            dist_dir=dist_dir,
            templates_dir=templates_dir,
            themes_path=themes_path,
            tags_path=tags_path,
            content_dir=content_dir,
            dry_run=dry_run,
        )
        if not dry_run:
            output_files.append(result["output_file"])
        # Use detected tag from first language for consistency
        if resolved_tag is None:
            resolved_tag = result["main_tag"]
        theme_id = result["theme_id"]

    return {
        "issue_date": issue_date,
        "languages": languages,
        "main_tag": resolved_tag,
        "theme_id": theme_id,
        "output_files": output_files,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate SVG cover images for coma.fm Radar issues."
    )
    parser.add_argument("--date", required=True, help="Issue date YYYY-MM-DD")
    parser.add_argument(
        "--lang", default="all", choices=["en", "uk", "all"],
        help="Language(s) to generate (default: all)",
    )
    parser.add_argument("--main-tag", default=None, dest="main_tag",
                        help="Force a specific main tag ID")
    parser.add_argument("--title", default="coma.fm Radar",
                        help="Cover title (default: coma.fm Radar)")
    parser.add_argument("--subtitle", default="", help="Optional subtitle")
    parser.add_argument("--content-dir", type=Path, default=DEFAULT_CONTENT_DIR,
                        dest="content_dir")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR,
                        dest="dist_dir")
    parser.add_argument("--templates-dir", type=Path, default=DEFAULT_TEMPLATES_DIR,
                        dest="templates_dir")
    parser.add_argument("--themes", type=Path, default=DEFAULT_THEMES,
                        help="Path to visual_themes.yaml")
    parser.add_argument("--tags", type=Path, default=DEFAULT_TAGS,
                        help="Path to tags.yaml")
    parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                        help="Render without writing files")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="Print summary as JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    languages = ["en", "uk"] if args.lang == "all" else [args.lang]

    summary = generate_issue_covers(
        issue_date=args.date,
        languages=languages,
        main_tag=args.main_tag,
        title=args.title,
        subtitle=args.subtitle,
        dist_dir=args.dist_dir,
        templates_dir=args.templates_dir,
        themes_path=args.themes,
        tags_path=args.tags,
        content_dir=args.content_dir,
        dry_run=args.dry_run,
    )

    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Issue date  : {summary['issue_date']}")
        print(f"Languages   : {', '.join(summary['languages'])}")
        print(f"Main tag    : {summary['main_tag']}")
        print(f"Theme       : {summary['theme_id']}")
        print(f"Covers      : {len(summary['output_files'])}")
        for f in summary["output_files"]:
            print(f"  {f}")
        if summary["dry_run"]:
            print("(dry-run — no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Render style.css.j2 and write dist/assets/style.css.

Usage:
    python3 scripts/build_css.py
    python3 scripts/build_css.py --dry-run
    python3 scripts/build_css.py --dist-dir /tmp/dist
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_TEMPLATES_DIR = _REPO_ROOT / "templates"


def build_css(
    dist_dir: Path = DEFAULT_DIST_DIR,
    templates_dir: Path = DEFAULT_TEMPLATES_DIR,
    dry_run: bool = False,
) -> dict:
    """Render style.css.j2 and write to dist/assets/style.css. Returns summary dict."""
    from scripts.build_issue import _J2Renderer

    template_path = templates_dir / "style.css.j2"
    src = template_path.read_text(encoding="utf-8")
    css = _J2Renderer().render(src, {})

    out_path = dist_dir / "assets" / "style.css"

    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(css, encoding="utf-8")

    return {
        "output_file": str(out_path),
        "bytes": len(css.encode("utf-8")),
        "dry_run": dry_run,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render style.css.j2 and write to dist/assets/style.css."
    )
    parser.add_argument(
        "--dist-dir", type=Path, default=DEFAULT_DIST_DIR, dest="dist_dir",
    )
    parser.add_argument(
        "--templates-dir", type=Path, default=DEFAULT_TEMPLATES_DIR, dest="templates_dir",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Parse and render without writing files",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = build_css(
        dist_dir=args.dist_dir,
        templates_dir=args.templates_dir,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

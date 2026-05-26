#!/usr/bin/env python3
"""Telegram announcement wrapper — dry-run only, no real sending.

Usage:
    python scripts/send_telegram.py --date 2026-05-26 --lang uk --dry-run
    python scripts/send_telegram.py --date 2026-05-26 --send  # exits with error
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_telegram_draft import (
    DEFAULT_BASE_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_LIMIT_ITEMS,
    DEFAULT_MAX_CHARS,
    CONTENT_DIR,
    DIST_DIR,
    REPORTS_DIR,
    TEMPLATES_DIR,
    build_telegram_draft,
)

_SEND_NOT_IMPLEMENTED = (
    "Real Telegram sending is not implemented yet. Use --dry-run."
)


def run_send(
    date: str,
    lang: str = "uk",
    base_url: str = DEFAULT_BASE_URL,
    base_path: str = DEFAULT_BASE_PATH,
    dry_run: bool = True,
    send: bool = False,
    content_dir: Path = CONTENT_DIR,
    dist_dir: Path = DIST_DIR,
    reports_dir: Path = REPORTS_DIR,
    templates_dir: Path = TEMPLATES_DIR,
) -> dict:
    """Run dry-run or raise if --send requested."""
    if send:
        raise RuntimeError(_SEND_NOT_IMPLEMENTED)
    return build_telegram_draft(
        date=date,
        lang=lang,
        base_url=base_url,
        base_path=base_path,
        dry_run=dry_run,
        content_dir=content_dir,
        dist_dir=dist_dir,
        reports_dir=reports_dir,
        templates_dir=templates_dir,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Telegram announcement wrapper — dry-run only."
    )
    p.add_argument("--date", required=True, help="Issue date YYYY-MM-DD")
    p.add_argument("--lang", default="uk", choices=["uk", "en"])
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, dest="base_url")
    p.add_argument("--base-path", default=DEFAULT_BASE_PATH, dest="base_path")
    p.add_argument("--dry-run", action="store_true", default=True, dest="dry_run")
    p.add_argument(
        "--send", action="store_true", default=False,
        help="Attempt real send — exits with error (not implemented).",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.send:
        print(_SEND_NOT_IMPLEMENTED, file=sys.stderr)
        return 1
    summary = run_send(
        date=args.date,
        lang=args.lang,
        base_url=args.base_url,
        base_path=args.base_path,
        dry_run=args.dry_run,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

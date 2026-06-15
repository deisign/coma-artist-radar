#!/usr/bin/env python3
"""Telegram announcement wrapper.

Usage:
    python scripts/send_telegram.py --date 2026-05-26 --lang uk --dry-run
    python scripts/send_telegram.py --date 2026-05-26 --lang uk --send
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.build_telegram_draft import (
    DEFAULT_BASE_PATH,
    DEFAULT_BASE_URL,
    CONTENT_DIR,
    DIST_DIR,
    REPORTS_DIR,
    TEMPLATES_DIR,
    build_telegram_draft,
)

DEFAULT_TELEGRAM_POSTS_PATH = _REPO_ROOT / "data" / "telegram_posts.json"


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_telegram_posts(path: Path = DEFAULT_TELEGRAM_POSTS_PATH) -> dict:
    if not path.exists():
        return {"posts": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data.setdefault("posts", [])
        return data
    return {"posts": []}


def already_posted(date: str, lang: str, path: Path = DEFAULT_TELEGRAM_POSTS_PATH) -> bool:
    data = load_telegram_posts(path)
    return any(
        post.get("issue_date") == date and post.get("lang") == lang
        for post in data.get("posts", [])
    )


def record_telegram_post(
    *,
    path: Path,
    summary: dict,
    response: dict,
    chat_id: str,
    posted_at: str | None = None,
) -> None:
    posted_at = posted_at or _now_iso()
    data = load_telegram_posts(path)
    posts = [
        post for post in data.get("posts", [])
        if not (
            post.get("issue_date") == summary.get("issue_date")
            and post.get("lang") == summary.get("lang")
        )
    ]

    result = response.get("result") if isinstance(response, dict) else {}
    if not isinstance(result, dict):
        result = {}

    posts.append({
        "issue_date": summary.get("issue_date"),
        "lang": summary.get("lang"),
        "issue_url": summary.get("issue_url"),
        "posted_at": posted_at,
        "chat_id": chat_id,
        "message_id": result.get("message_id"),
        "chars": summary.get("chars"),
        "item_count": summary.get("item_count"),
    })

    posts.sort(key=lambda p: (str(p.get("issue_date")), str(p.get("lang"))))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"generated_at": posted_at, "posts": posts}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def send_telegram_message(*, bot_token: str, chat_id: str, text: str) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": "false",
    }).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    if not data.get("ok"):
        raise RuntimeError(f"Telegram send failed: {body}")
    return data


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
    posts_path: Path = DEFAULT_TELEGRAM_POSTS_PATH,
    bot_token: str | None = None,
    chat_id: str | None = None,
    allow_repeat: bool = False,
) -> dict:
    """Build a draft, optionally send it, and record sent posts in a ledger."""
    if send:
        if already_posted(date, lang, posts_path) and not allow_repeat:
            return {
                "issue_date": date,
                "lang": lang,
                "posted": False,
                "skipped": True,
                "reason": f"Telegram post already recorded for {date}.{lang}",
            }

        bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        if not bot_token or not chat_id:
            raise RuntimeError("Telegram send requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")

    summary = build_telegram_draft(
        date=date,
        lang=lang,
        base_url=base_url,
        base_path=base_path,
        dry_run=dry_run and not send,
        content_dir=content_dir,
        dist_dir=dist_dir,
        reports_dir=reports_dir,
        templates_dir=templates_dir,
    )

    if not send:
        return {**summary, "posted": False}

    text = Path(summary["output_file"]).read_text(encoding="utf-8")
    response = send_telegram_message(bot_token=bot_token, chat_id=chat_id, text=text)
    record_telegram_post(
        path=posts_path,
        summary=summary,
        response=response,
        chat_id=chat_id,
    )
    return {
        **summary,
        "posted": True,
        "telegram_response_ok": response.get("ok") is True,
        "message_id": (response.get("result") or {}).get("message_id"),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Telegram announcement wrapper.")
    p.add_argument("--date", required=True, help="Issue date YYYY-MM-DD")
    p.add_argument("--lang", default="uk", choices=["uk", "en"])
    p.add_argument("--base-url", default=DEFAULT_BASE_URL, dest="base_url")
    p.add_argument("--base-path", default=DEFAULT_BASE_PATH, dest="base_path")
    p.add_argument("--dry-run", action="store_true", default=True, dest="dry_run")
    p.add_argument("--send", action="store_true", default=False)
    p.add_argument("--bot-token", default=None, dest="bot_token")
    p.add_argument("--chat-id", default=None, dest="chat_id")
    p.add_argument("--posts-path", default=str(DEFAULT_TELEGRAM_POSTS_PATH), dest="posts_path")
    p.add_argument("--allow-repeat", action="store_true", default=False, dest="allow_repeat")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = run_send(
            date=args.date,
            lang=args.lang,
            base_url=args.base_url,
            base_path=args.base_path,
            dry_run=args.dry_run,
            send=args.send,
            bot_token=args.bot_token,
            chat_id=args.chat_id,
            posts_path=Path(args.posts_path),
            allow_repeat=args.allow_repeat,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

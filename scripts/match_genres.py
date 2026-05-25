#!/usr/bin/env python3
"""Match text against genre_radar.yaml to identify coma.fm genres.

Usage:
    python3 scripts/match_genres.py --text "horrorbilly psychobilly"
    python3 scripts/match_genres.py --demo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GENRE_RADAR = _REPO_ROOT / "data" / "genre_radar.yaml"

SCORE_CORE = 30
SCORE_ADJACENT = 10
SCORE_NEGATIVE = -40

DEMO_TEXTS = [
    "New psychobilly album from The Meteors — horrorbilly meets punkabilly vibes",
    "Instrumental surf guitar compilation, reverb-heavy twang from the vault",
    "Honky tonk deep cut — gothic country and outlaw americana",
    "Dark jazz and jazz noir — new album from the Paris underground scene",
    "Surf forecast for the weekend: 6-8 foot waves, surfboard rentals available",
    "Top 10 best pop hits this summer — mainstream chart roundup",
]


def load_genre_radar(path: Path = DEFAULT_GENRE_RADAR) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _phrase_re(phrase: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(phrase.lower()) + r"\b")


def match_text(text: str, genre_data: dict) -> dict:
    """Match text against genre_radar data and return scored results."""
    text_lower = text.lower()

    matched_core: dict[str, list[str]] = {}
    matched_adjacent: dict[str, list[str]] = {}
    negative_matches: dict[str, list[str]] = {}
    genre_score: dict[str, int] = {}
    matched_genres: list[str] = []

    for genre, cfg in genre_data.items():
        core = [
            tag for tag in cfg.get("core_tags", [])
            if _phrase_re(tag).search(text_lower)
        ]
        adjacent = [
            tag for tag in cfg.get("adjacent_tags", [])
            if _phrase_re(tag).search(text_lower)
        ]
        negative = [
            tag for tag in cfg.get("negative_tags", [])
            if _phrase_re(tag).search(text_lower)
        ]

        raw = (
            len(core) * SCORE_CORE
            + len(adjacent) * SCORE_ADJACENT
            + len(negative) * SCORE_NEGATIVE
        )
        score = max(0, min(100, raw))

        matched_core[genre] = core
        matched_adjacent[genre] = adjacent
        negative_matches[genre] = negative
        genre_score[genre] = score

        if score > 0:
            matched_genres.append(genre)

    matched_genres.sort(key=lambda g: genre_score[g], reverse=True)

    return {
        "matched_genres": matched_genres,
        "matched_core_tags": {g: matched_core[g] for g in matched_genres},
        "matched_adjacent_tags": {g: matched_adjacent[g] for g in matched_genres},
        "negative_matches": {g: v for g, v in negative_matches.items() if v},
        "genre_score": genre_score,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Match text against coma.fm genre radar.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="Text to analyse")
    group.add_argument("--demo", action="store_true", help="Run demo examples")
    parser.add_argument(
        "--genre-radar",
        type=Path,
        default=DEFAULT_GENRE_RADAR,
        help="Path to genre_radar.yaml",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        genre_data = load_genre_radar(args.genre_radar)
    except Exception as exc:
        print(f"ERROR loading genre_radar.yaml: {exc}", file=sys.stderr)
        return 1

    if args.demo:
        results = []
        for text in DEMO_TEXTS:
            result = match_text(text, genre_data)
            results.append({"text": text, **result})
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        result = match_text(args.text, genre_data)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

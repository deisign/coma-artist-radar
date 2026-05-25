#!/usr/bin/env python3
"""Tag a content item using tags.yaml and tag_rules.yaml.

Usage:
    python3 scripts/tag_item.py --title "surf guitar" --excerpt "twang from the vault"
    python3 scripts/tag_item.py --demo
    python3 scripts/tag_item.py --title "horrorbilly night" --manual-tags "psychobilly,new_release"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_RULES = _REPO_ROOT / "data" / "tag_rules.yaml"
DEFAULT_UNKNOWN_REPORT = _REPO_ROOT / "reports" / "unknown_tags.csv"

_TAG_TYPES = ("genre", "subgenre", "aesthetic", "content_type", "editorial", "negative")

DEMO_ITEMS = [
    {
        "title": "New instrumental surf guitar EP from the vault",
        "excerpt": "Reverb-heavy twang, surf instrumental sounds.",
    },
    {
        "title": "Horrorbilly night at the cemetery",
        "excerpt": "Psychobilly and punkabilly all night long.",
    },
    {
        "title": "Honky tonk deep in gothic country",
        "excerpt": "Dark americana, outlaw style, murder ballad territory.",
    },
    {
        "title": "Surf forecast: waves this weekend",
        "excerpt": "Best surfboard rentals and surf report for beginners.",
    },
    {
        "title": "Top 10 best guitar albums of all time",
        "excerpt": "Ranked list of classic guitar records everyone should own.",
    },
]


def load_tags(path: Path = DEFAULT_TAGS) -> dict:
    """Return {tag_id: tag_object} from tags.yaml."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {tag["id"]: tag for tag in data.get("tags", [])}


def load_tag_rules(path: Path = DEFAULT_RULES) -> list:
    """Return list of rule dicts from tag_rules.yaml."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("rules", [])


def _phrase_re(phrase: str) -> re.Pattern:
    return re.compile(r"\b" + re.escape(phrase.lower()) + r"\b")


def _rule_fires(text_lower: str, rule: dict) -> bool:
    """True if any include matches and no exclude matches."""
    if not any(_phrase_re(p).search(text_lower) for p in rule.get("include", [])):
        return False
    return not any(_phrase_re(p).search(text_lower) for p in rule.get("exclude", []))


def _propagate_parents(matched: dict, tag_registry: dict) -> None:
    """Add parent genre/subgenre for each matched tag (in-place)."""
    to_add: dict[str, dict] = {}
    for tag_id, data in list(matched.items()):
        tag_obj = tag_registry.get(tag_id)
        if not tag_obj:
            continue
        parent = tag_obj.get("parent")
        if not parent or parent in matched or parent in to_add:
            continue
        if parent not in tag_registry:
            continue
        to_add[parent] = {
            "confidence": round(data["confidence"] * 0.9, 3),
            "source": "parent_inference",
            "score": max(0, int(data.get("score", 0) * 0.8)),
        }
    matched.update(to_add)


def _record_unknown_tags(unknowns: list[str], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(["tag_id"])
        for tag_id in unknowns:
            writer.writerow([tag_id])


def match_tags(
    text: str,
    rules: list,
    tag_registry: dict,
    manual_tags: list[str] | None = None,
    report_unknown_path: Path = DEFAULT_UNKNOWN_REPORT,
) -> dict:
    """Core matching logic. Returns structured result dict."""
    text_lower = text.lower()
    matched: dict[str, dict] = {}

    for rule in rules:
        tag_id = rule.get("tag")
        if not tag_id or not _rule_fires(text_lower, rule):
            continue
        new_conf = float(rule.get("confidence", 0.5))
        existing = matched.get(tag_id)
        if existing is None or new_conf > existing["confidence"]:
            matched[tag_id] = {
                "confidence": new_conf,
                "source": "keyword_match",
                "score": int(rule.get("score", 0)),
            }

    _propagate_parents(matched, tag_registry)

    unknown: list[str] = []
    for raw in (manual_tags or []):
        tag_id = raw.strip()
        if not tag_id:
            continue
        if tag_id not in tag_registry:
            unknown.append(tag_id)
        matched[tag_id] = {"confidence": 1.0, "source": "manual", "score": 30}

    if unknown:
        _record_unknown_tags(unknown, report_unknown_path)

    tags_by_type: dict[str, list[str]] = {t: [] for t in _TAG_TYPES}
    for tag_id in matched:
        tag_obj = tag_registry.get(tag_id)
        tag_type = tag_obj["type"] if tag_obj else "editorial"
        if tag_type in tags_by_type:
            tags_by_type[tag_type].append(tag_id)

    raw_score = sum(d["score"] for d in matched.values())
    score = max(0, min(100, raw_score))

    return {
        "tags": tags_by_type,
        "tag_confidence": {tid: d["confidence"] for tid, d in matched.items()},
        "tag_sources": {tid: d["source"] for tid, d in matched.items()},
        "negative_tags": tags_by_type["negative"],
        "score": score,
    }


def tag_item(
    title: str = "",
    excerpt: str = "",
    source_text: str = "",
    manual_tags: list[str] | None = None,
    tags_path: Path = DEFAULT_TAGS,
    rules_path: Path = DEFAULT_RULES,
    report_unknown_path: Path = DEFAULT_UNKNOWN_REPORT,
) -> dict:
    """Load data, combine text, run tag matching."""
    tag_registry = load_tags(tags_path)
    rules = load_tag_rules(rules_path)
    text = " ".join(filter(None, [title, excerpt, source_text]))
    return match_tags(text, rules, tag_registry, manual_tags, report_unknown_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tag a content item for coma.fm Radar.")
    parser.add_argument("--title", default="", help="Item title")
    parser.add_argument("--excerpt", default="", help="Item excerpt or description")
    parser.add_argument("--source-text", default="", help="Full source text")
    parser.add_argument(
        "--manual-tags",
        default="",
        help='Comma-separated manual tags, e.g. "surf,new_release"',
    )
    parser.add_argument("--demo", action="store_true", help="Run demo examples")
    parser.add_argument("--tags", type=Path, default=DEFAULT_TAGS, help="Path to tags.yaml")
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES, help="Path to tag_rules.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manual = [t.strip() for t in args.manual_tags.split(",") if t.strip()] or None

    try:
        tag_registry = load_tags(args.tags)
        rules = load_tag_rules(args.rules)
    except Exception as exc:
        print(f"ERROR loading tag data: {exc}", file=sys.stderr)
        return 1

    if args.demo:
        results = []
        for item in DEMO_ITEMS:
            text = " ".join(filter(None, [item.get("title", ""), item.get("excerpt", "")]))
            result = match_tags(text, rules, tag_registry)
            results.append({"title": item["title"], **result})
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        text = " ".join(filter(None, [args.title, args.excerpt, args.source_text]))
        result = match_tags(text, rules, tag_registry, manual)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

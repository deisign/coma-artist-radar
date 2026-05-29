#!/usr/bin/env python3
"""Audit Feedly OPML sources for coma.fm Radar source expansion.

This script does not modify data/sources_music.yaml. It reads OPML, walks folders
recursively, writes a CSV candidate audit, and prints a compact JSON summary.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

REPORT_FIELDS = [
    "source_id",
    "title",
    "category_path",
    "xml_url",
    "html_url",
    "source_type",
    "priority",
    "relevance_score",
    "duplicate_url",
    "suggested_action",
]


def slugify(value: str) -> str:
    """Return a deterministic source id candidate."""
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:80] or "source"


def _outline_label(node: ET.Element) -> str:
    return (node.attrib.get("title") or node.attrib.get("text") or "").strip()


def iter_opml_feeds(opml_path: Path) -> list[dict]:
    """Return feed entries from OPML, preserving recursive folder path."""
    root = ET.parse(opml_path).getroot()
    body = root.find("body")
    if body is None:
        return []

    feeds: list[dict] = []

    def walk(node: ET.Element, path: list[str]) -> None:
        label = _outline_label(node)
        xml_url = (node.attrib.get("xmlUrl") or "").strip()
        html_url = (node.attrib.get("htmlUrl") or "").strip()

        if xml_url:
            title = label or xml_url
            feeds.append({
                "title": title,
                "category_path": " / ".join(path) if path else "root",
                "xml_url": xml_url,
                "html_url": html_url,
            })

        next_path = path
        if not xml_url and label:
            next_path = [*path, label]

        for child in list(node):
            walk(child, next_path)

    for child in list(body):
        walk(child, [])

    return feeds


def guess_source_type(category_path: str, title: str, url: str) -> str:
    hay = f"{category_path} {title} {url}".lower()
    if any(k in hay for k in ("radio", "wfmu", "kcrw")):
        return "radio"
    if any(k in hay for k in ("records", "recordings", "label", "sundazed", "numero", "fat possum", "light in the attic", "crypt", "norton")):
        return "label"
    if any(k in hay for k in ("festival", "weekend", "rumble")):
        return "festival"
    if "podcast" in hay:
        return "podcast"
    if any(k in hay for k in ("magazine", "pitchfork", "uncut", "wire", "nme", "louder", "offbeat", "rue morgue", "guardian music")):
        return "magazine"
    return "blog"


def relevance_score(category_path: str, title: str, url: str) -> int:
    hay = f"{category_path} {title} {url}".lower()
    keywords = [
        "music", "song", "album", "band", "records", "recordings", "vinyl", "reissue",
        "rockabilly", "psychobilly", "surf", "garage", "punk", "americana", "country",
        "roots", "folk", "blues", "jazz", "soul", "r&b", "exotica", "lounge", "noir",
        "bandcamp", "pitchfork", "uncut", "nme", "louder", "wfmu", "offbeat",
        "raven sings the blues", "perfect sound forever", "saving country music",
        "no depression", "aquarium drunkard", "dereksmusicblog",
    ]
    score = sum(1 for keyword in keywords if keyword in hay)

    core_paths = ("music mags", "rockabilly", "psychobilly", "surf")
    if any(path in hay for path in core_paths):
        score += 4

    non_music_paths = ("design", "photography", "illustration", "art colleges")
    if any(path in hay for path in non_music_paths):
        score -= 2

    return max(0, score)


def guess_priority(category_path: str, title: str, url: str, relevance: int) -> str:
    hay = f"{category_path} {title} {url}".lower()
    high = (
        "rockabilly", "psychobilly", "surf", "americana", "no depression",
        "saving country music", "raven sings the blues", "perfect sound forever",
        "bandcamp", "offbeat", "wfmu", "aquarium drunkard",
    )
    medium = (
        "country", "roots", "folk", "blues", "jazz", "pitchfork", "nme",
        "louder", "uncut", "open culture", "flavorwire", "ultimate classic rock",
    )
    if relevance >= 5 or any(k in hay for k in high):
        return "high"
    if relevance >= 3 or any(k in hay for k in medium):
        return "medium"
    return "low"


def suggested_action(category_path: str, title: str, url: str, relevance: int, duplicate: bool) -> str:
    if duplicate:
        return "DUPLICATE"

    hay = f"{category_path} {title} {url}".lower()
    if any(k in hay for k in ("design", "photography", "illustration", "art colleges")) and relevance < 3:
        return "SKIP_NON_MUSIC"

    if relevance >= 5:
        return "IMPORT_CORE"
    if relevance >= 3:
        return "IMPORT_PERIPHERAL"
    if relevance >= 1:
        return "REVIEW"
    return "SKIP_NON_MUSIC"


def audit_opml(opml_path: Path, output_path: Path) -> dict:
    feeds = iter_opml_feeds(opml_path)
    seen_urls: set[str] = set()
    rows: list[dict] = []

    for feed in feeds:
        xml_url = feed["xml_url"]
        html_url = feed["html_url"]
        title = feed["title"]
        category_path = feed["category_path"]
        duplicate = xml_url.strip().lower() in seen_urls
        seen_urls.add(xml_url.strip().lower())

        rel = relevance_score(category_path, title, html_url or xml_url)
        rows.append({
            "source_id": slugify(title),
            "title": title,
            "category_path": category_path,
            "xml_url": xml_url,
            "html_url": html_url,
            "source_type": guess_source_type(category_path, title, html_url or xml_url),
            "priority": guess_priority(category_path, title, html_url or xml_url, rel),
            "relevance_score": rel,
            "duplicate_url": "true" if duplicate else "false",
            "suggested_action": suggested_action(category_path, title, html_url or xml_url, rel, duplicate),
        })

    rows.sort(
        key=lambda row: (
            row["suggested_action"] not in ("IMPORT_CORE", "IMPORT_PERIPHERAL"),
            -int(row["relevance_score"]),
            row["category_path"].lower(),
            row["title"].lower(),
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "opml": str(opml_path),
        "output": str(output_path),
        "outline_feeds": len(feeds),
        "unique_feed_urls": len({feed["xml_url"].strip().lower() for feed in feeds}),
        "duplicate_feed_urls": len(feeds) - len({feed["xml_url"].strip().lower() for feed in feeds}),
        "categories": dict(Counter(row["category_path"] for row in rows).most_common()),
        "actions": dict(Counter(row["suggested_action"] for row in rows).most_common()),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Feedly OPML source candidates.")
    parser.add_argument("opml", type=Path, help="Path to Feedly OPML file")
    parser.add_argument("--out", type=Path, default=Path("reports/feedly_opml_audit.csv"))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.opml.exists():
        print(f"ERROR: OPML not found: {args.opml}", file=sys.stderr)
        return 1

    summary = audit_opml(args.opml, args.out)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

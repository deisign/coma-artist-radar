#!/usr/bin/env python3
"""Quality gate for issue content before publication.

Reads content/issues/*.json, validates structure and content rules,
writes a CSV report, and exits with appropriate codes.

Usage:
    python3 scripts/validate_issue_content.py
    python3 scripts/validate_issue_content.py --date 2026-05-26
    python3 scripts/validate_issue_content.py --date 2026-05-26 --lang en
    python3 scripts/validate_issue_content.py --date 2026-05-26 --json
    python3 scripts/validate_issue_content.py --date 2026-05-26 --fail-on-warnings
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

DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_REPORT = _REPO_ROOT / "reports" / "issue_quality_report.csv"

_REPORT_FIELDS = [
    "issue_file", "lang", "issue_date",
    "item_title", "url", "score",
    "status", "severity", "problem",
]

_MAX_EXCERPT_LEN = 700
_FULL_TEXT_LEN = 1500
_FULL_TEXT_NEWLINES = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_tags_str(tags_str: str) -> list[str]:
    return [t.strip() for t in str(tags_str or "").split(",") if t.strip()]


def _load_tag_info(tags_path: Path) -> tuple[set[str], set[str]]:
    """Return (all_tag_ids, negative_tag_ids) from tags.yaml."""
    import yaml
    with tags_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    all_ids: set[str] = set()
    negative_ids: set[str] = set()
    for tag in data.get("tags", []):
        tid = str(tag.get("id", "") or "").strip()
        if tid:
            all_ids.add(tid)
            if tag.get("type") == "negative":
                negative_ids.add(tid)
    return all_ids, negative_ids


def _row(
    issue_file: str,
    lang: str,
    issue_date: str,
    item_title: str,
    url: str,
    score,
    severity: str,
    problem: str,
) -> dict:
    return {
        "issue_file": issue_file,
        "lang": lang,
        "issue_date": issue_date,
        "item_title": item_title,
        "url": url,
        "score": score if score is not None else "",
        "status": severity,
        "severity": severity,
        "problem": problem,
    }


# ---------------------------------------------------------------------------
# Per-issue validation
# ---------------------------------------------------------------------------

def validate_issue(
    issue_data: dict,
    issue_path: Path,
    all_tag_ids: set[str],
    negative_tag_ids: set[str],
    min_items: int,
    min_score: int,
) -> list[dict]:
    """Validate a single issue dict. Returns a list of finding rows (empty = clean)."""
    rows: list[dict] = []
    file_str = issue_path.name
    lang = str(issue_data.get("lang") or "")
    issue_date = str(issue_data.get("issue_date") or "")
    draft = bool(issue_data.get("draft", False))
    items = issue_data.get("items")

    def _e(item_title: str, url: str, score, problem: str) -> dict:
        return _row(file_str, lang, issue_date, item_title, url, score, "error", problem)

    def _w(item_title: str, url: str, score, problem: str) -> dict:
        return _row(file_str, lang, issue_date, item_title, url, score, "warning", problem)

    # --- Issue-level structural checks ---
    if not issue_data.get("issue_date"):
        rows.append(_e("", "", None, "missing issue_date"))
    if not issue_data.get("lang"):
        rows.append(_e("", "", None, "missing lang"))
    if "title" not in issue_data:
        rows.append(_w("", "", None, "missing issue title"))
    if not isinstance(items, list):
        rows.append(_e("", "", None, "items field missing or not a list"))
        return rows

    if not draft and len(items) < min_items:
        rows.append(_e(
            "", "", None,
            f"too few items: {len(items)} < {min_items} (not a draft)",
        ))

    # --- Duplicate URL check ---
    seen_urls: set[str] = set()
    for item in items:
        url = str(item.get("url") or "").strip()
        if url:
            if url in seen_urls:
                rows.append(_e(
                    str(item.get("title") or ""),
                    url,
                    item.get("score"),
                    "duplicate URL within issue",
                ))
            else:
                seen_urls.add(url)

    # --- Item-level checks ---
    for item in items:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        score = item.get("score")
        source_name = str(item.get("source_name") or "").strip()
        matched_tags = str(item.get("matched_tags") or "")
        matched_genres = str(item.get("matched_genres") or "")

        if not title:
            rows.append(_e("", url, score, "item missing title"))

        if not url:
            rows.append(_e(title, "", score, "item missing URL"))
        elif not (url.startswith("http://") or url.startswith("https://")):
            rows.append(_e(title, url, score, "item URL must start with http:// or https://"))

        if not source_name:
            rows.append(_w(title, url, score, "item missing source_name"))

        if score is not None:
            try:
                if float(score) < min_score:
                    rows.append(_e(title, url, score, f"score {score} below min_score {min_score}"))
            except (TypeError, ValueError):
                rows.append(_e(title, url, score, f"score is not a number: {score!r}"))

        tag_ids = _parse_tags_str(matched_tags)

        for tid in tag_ids:
            if tid in negative_tag_ids:
                rows.append(_e(title, url, score, f"negative tag present: {tid}"))

        for tid in tag_ids:
            if tid not in all_tag_ids:
                rows.append(_w(title, url, score, f"unknown tag not in tags.yaml: {tid}"))

        if url and not matched_tags.strip() and not matched_genres.strip():
            rows.append(_w(title, url, score, "no matched_tags or matched_genres"))

        for field in ("excerpt", "summary"):
            text = str(item.get(field) or "")
            if not text:
                continue
            if len(text) > _MAX_EXCERPT_LEN:
                rows.append(_w(
                    title, url, score,
                    f"{field} too long: {len(text)} chars (max {_MAX_EXCERPT_LEN})",
                ))
            if len(text) > _FULL_TEXT_LEN and text.count("\n") > _FULL_TEXT_NEWLINES:
                rows.append(_w(title, url, score, f"{field} looks like full article text"))

    return rows


# ---------------------------------------------------------------------------
# Cross-language validation
# ---------------------------------------------------------------------------

def _cross_lang_rows(
    date_str: str,
    en_data: dict,
    uk_data: dict,
) -> list[dict]:
    rows: list[dict] = []
    file_str = f"{date_str}.*.json"

    en_items = en_data.get("items") or []
    uk_items = uk_data.get("items") or []
    en_urls = [str(it.get("url") or "") for it in en_items]
    uk_urls = [str(it.get("url") or "") for it in uk_items]

    if len(en_urls) != len(uk_urls):
        rows.append(_row(
            file_str, "en/uk", date_str, "", "", None, "error",
            f"EN/UK item count mismatch: en={len(en_urls)}, uk={len(uk_urls)}",
        ))

    en_set = set(en_urls)
    uk_set = set(uk_urls)
    only_en = en_set - uk_set
    only_uk = uk_set - en_set
    if only_en or only_uk:
        rows.append(_row(
            file_str, "en/uk", date_str, "", "", None, "error",
            f"EN/UK URL mismatch: {len(only_en)} URL(s) only in EN, {len(only_uk)} only in UK",
        ))

    return rows


# ---------------------------------------------------------------------------
# Main validation pipeline
# ---------------------------------------------------------------------------

def validate_content(
    content_dir: Path = DEFAULT_CONTENT_DIR,
    tags_path: Path = DEFAULT_TAGS,
    date: str | None = None,
    lang: str | None = None,
    min_items: int = 3,
    min_score: int = 30,
    report_path: Path = DEFAULT_REPORT,
) -> dict:
    """Validate all issue JSONs in content_dir. Returns summary dict."""
    all_tag_ids, negative_tag_ids = _load_tag_info(tags_path)

    # Discover and filter files
    candidates: list[Path] = []
    for p in sorted(content_dir.glob("*.json")):
        stem_parts = p.stem.split(".")
        if len(stem_parts) != 2:
            continue
        file_date, file_lang = stem_parts
        if date and file_date != date:
            continue
        if lang and file_lang != lang:
            continue
        candidates.append(p)

    all_rows: list[dict] = []
    errors = 0
    warnings = 0
    loaded: list[tuple[Path, dict]] = []
    issues_by_date: dict[str, dict[str, dict]] = {}

    for p in candidates:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            r = _row(p.name, "", "", "", "", None, "error", f"cannot parse JSON: {exc}")
            all_rows.append(r)
            errors += 1
            continue

        loaded.append((p, data))
        file_date = data.get("issue_date") or p.stem.split(".")[0]
        file_lang = data.get("lang") or (p.stem.split(".")[1] if "." in p.stem else "")
        issues_by_date.setdefault(file_date, {})[file_lang] = data

    for p, data in loaded:
        findings = validate_issue(data, p, all_tag_ids, negative_tag_ids, min_items, min_score)
        if not findings:
            all_rows.append(_row(
                p.name, data.get("lang", ""), data.get("issue_date", ""),
                "", "", None, "ok", "",
            ))
        else:
            all_rows.extend(findings)
            for r in findings:
                if r["severity"] == "error":
                    errors += 1
                elif r["severity"] == "warning":
                    warnings += 1

    # Cross-language checks (only when not restricted to a single lang)
    if not lang:
        for date_str, lang_map in issues_by_date.items():
            if "en" in lang_map and "uk" in lang_map:
                cross = _cross_lang_rows(date_str, lang_map["en"], lang_map["uk"])
                all_rows.extend(cross)
                for r in cross:
                    if r["severity"] == "error":
                        errors += 1
                    elif r["severity"] == "warning":
                        warnings += 1

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    return {
        "issues_checked": len(loaded),
        "errors": errors,
        "warnings": warnings,
        "ok": errors == 0,
        "report_path": str(report_path),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate issue content JSON files before publication."
    )
    parser.add_argument(
        "--date", default=None,
        help="Validate only issues for this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--lang", choices=["en", "uk"], default=None,
        help="Validate only this language",
    )
    parser.add_argument(
        "--min-items", type=int, default=3, dest="min_items",
        help="Minimum items required in a non-draft issue (default: 3)",
    )
    parser.add_argument(
        "--min-score", type=int, default=30, dest="min_score",
        help="Minimum item score (default: 30)",
    )
    parser.add_argument(
        "--fail-on-warnings", action="store_true", dest="fail_on_warnings",
        help="Exit 1 if there are any warnings",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Print summary as JSON",
    )
    parser.add_argument(
        "--content-dir", type=Path, default=DEFAULT_CONTENT_DIR, dest="content_dir",
        help="Directory containing issue JSON files",
    )
    parser.add_argument(
        "--tags", type=Path, default=DEFAULT_TAGS,
        help="Path to tags.yaml",
    )
    parser.add_argument(
        "--report", type=Path, default=DEFAULT_REPORT,
        help="Path for the CSV quality report",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = validate_content(
        content_dir=args.content_dir,
        tags_path=args.tags,
        date=args.date,
        lang=args.lang,
        min_items=args.min_items,
        min_score=args.min_score,
        report_path=args.report,
    )

    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        status = "OK" if summary["ok"] else "FAILED"
        print(f"Issues checked : {summary['issues_checked']}")
        print(f"Errors         : {summary['errors']}")
        print(f"Warnings       : {summary['warnings']}")
        print(f"Report         : {summary['report_path']}")
        print(f"Status         : {status}")

    if summary["errors"] > 0:
        return 1
    if args.fail_on_warnings and summary["warnings"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

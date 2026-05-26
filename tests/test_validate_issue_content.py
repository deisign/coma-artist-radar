import csv
import json
from pathlib import Path

import pytest

from scripts.validate_issue_content import (
    validate_content,
    validate_issue,
    _load_tag_info,
    main,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_VALID_ITEM = {
    "id": 1,
    "title": "A Fine Article",
    "url": "https://example.com/article-1",
    "source_name": "Test Source",
    "published_at": "2026-01-15",
    "score": 50,
    "matched_artists": "Test Artist",
    "matched_tags": "country",
    "matched_genres": "",
}

_VALID_ISSUE_EN = {
    "issue_date": "2026-01-15",
    "lang": "en",
    "title": "Test Issue EN",
    "draft": False,
    "generated_at": "2026-01-15T00:00:00Z",
    "min_score": 30,
    "total_items": 3,
    "items": [
        {**_VALID_ITEM, "id": 1, "url": "https://example.com/article-1"},
        {**_VALID_ITEM, "id": 2, "url": "https://example.com/article-2", "title": "Second Article"},
        {**_VALID_ITEM, "id": 3, "url": "https://example.com/article-3", "title": "Third Article"},
    ],
}

_VALID_ISSUE_UK = {
    **_VALID_ISSUE_EN,
    "lang": "uk",
    "title": "Test Issue UK",
}


def _write_issue(content_dir: Path, date: str, lang: str, data: dict) -> Path:
    content_dir.mkdir(parents=True, exist_ok=True)
    p = content_dir / f"{date}.{lang}.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def _run(
    content_dir: Path,
    tmp_path: Path,
    date: str | None = None,
    lang: str | None = None,
    min_items: int = 3,
    min_score: int = 30,
) -> dict:
    report_path = tmp_path / "report.csv"
    return validate_content(
        content_dir=content_dir,
        tags_path=_TAGS_PATH,
        date=date,
        lang=lang,
        min_items=min_items,
        min_score=min_score,
        report_path=report_path,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_issue_passes(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] == 0
    assert summary["warnings"] == 0
    assert summary["ok"] is True
    assert summary["issues_checked"] == 2


def test_no_issues_returns_ok(tmp_path):
    cdir = tmp_path / "empty"
    cdir.mkdir()
    summary = _run(cdir, tmp_path)
    assert summary["errors"] == 0
    assert summary["ok"] is True
    assert summary["issues_checked"] == 0


def test_date_filter_limits_checked(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-22", "en", {**_VALID_ISSUE_EN, "issue_date": "2026-01-22"})
    summary = _run(cdir, tmp_path, date="2026-01-15")
    assert summary["issues_checked"] == 1


def test_lang_filter_limits_checked(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    summary = _run(cdir, tmp_path, lang="en")
    assert summary["issues_checked"] == 1


# ---------------------------------------------------------------------------
# Item score check
# ---------------------------------------------------------------------------

def test_item_below_min_score_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    low_score_item = {**_VALID_ITEM, "score": 10}
    issue = {**_VALID_ISSUE_EN, "items": [low_score_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path, min_score=30)
    assert summary["errors"] > 0


def test_item_at_min_score_passes(tmp_path):
    cdir = tmp_path / "issues"
    item = {**_VALID_ITEM, "score": 30}
    issue = {
        **_VALID_ISSUE_EN,
        "items": [
            {**item, "url": "https://example.com/1"},
            {**item, "url": "https://example.com/2", "title": "B"},
            {**item, "url": "https://example.com/3", "title": "C"},
        ],
    }
    _write_issue(cdir, "2026-01-15", "en", issue)
    _write_issue(cdir, "2026-01-15", "uk", {**issue, "lang": "uk", "title": "UK"})
    summary = _run(cdir, tmp_path, min_score=30)
    assert summary["errors"] == 0


# ---------------------------------------------------------------------------
# Negative tag check
# ---------------------------------------------------------------------------

def test_negative_tag_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    neg_item = {**_VALID_ITEM, "matched_tags": "country, seo_listicle"}
    issue = {**_VALID_ISSUE_EN, "items": [neg_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] > 0


def test_negative_tag_problem_text(tmp_path):
    cdir = tmp_path / "issues"
    neg_item = {**_VALID_ITEM, "matched_tags": "country, seo_listicle"}
    issue = {**_VALID_ISSUE_EN, "items": [neg_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    rows = list(csv.DictReader(report_path.read_text(encoding="utf-8").splitlines()))
    error_rows = [r for r in rows if r["severity"] == "error"]
    assert any("seo_listicle" in r["problem"] for r in error_rows)


# ---------------------------------------------------------------------------
# Unknown tag check
# ---------------------------------------------------------------------------

def test_unknown_tag_gives_warning(tmp_path):
    cdir = tmp_path / "issues"
    unk_item = {**_VALID_ITEM, "matched_tags": "country, totally_unknown_xyz"}
    issue = {**_VALID_ISSUE_EN, "items": [unk_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path, min_items=1)
    assert summary["warnings"] > 0
    assert summary["errors"] == 0


# ---------------------------------------------------------------------------
# Duplicate URL check
# ---------------------------------------------------------------------------

def test_duplicate_url_within_issue_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    dup = {**_VALID_ITEM, "url": "https://example.com/same"}
    issue = {**_VALID_ISSUE_EN, "items": [
        {**dup, "title": "Article A"},
        {**dup, "title": "Article B"},
    ]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] > 0


def test_duplicate_url_problem_text(tmp_path):
    cdir = tmp_path / "issues"
    dup = {**_VALID_ITEM, "url": "https://example.com/same"}
    issue = {**_VALID_ISSUE_EN, "items": [
        {**dup, "title": "Article A"},
        {**dup, "title": "Article B"},
    ]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    rows = list(csv.DictReader(report_path.read_text(encoding="utf-8").splitlines()))
    assert any("duplicate" in r["problem"].lower() for r in rows)


# ---------------------------------------------------------------------------
# Excerpt / summary length check
# ---------------------------------------------------------------------------

def test_excerpt_too_long_gives_warning(tmp_path):
    cdir = tmp_path / "issues"
    long_item = {**_VALID_ITEM, "excerpt": "x" * 800}
    issue = {**_VALID_ISSUE_EN, "items": [long_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["warnings"] > 0


def test_excerpt_under_limit_no_warning(tmp_path):
    cdir = tmp_path / "issues"
    ok_item = {**_VALID_ITEM, "excerpt": "x" * 300}
    issue = {
        **_VALID_ISSUE_EN,
        "items": [
            {**ok_item, "url": "https://example.com/1"},
            {**ok_item, "url": "https://example.com/2", "title": "B"},
            {**ok_item, "url": "https://example.com/3", "title": "C"},
        ],
    }
    _write_issue(cdir, "2026-01-15", "en", issue)
    _write_issue(cdir, "2026-01-15", "uk", {**issue, "lang": "uk", "title": "UK"})
    summary = _run(cdir, tmp_path)
    excerpt_warnings = [
        r for r in _read_rows(tmp_path / "report.csv")
        if "excerpt" in r.get("problem", "").lower()
    ]
    assert len(excerpt_warnings) == 0


# ---------------------------------------------------------------------------
# --fail-on-warnings
# ---------------------------------------------------------------------------

def test_fail_on_warnings_returns_1(tmp_path):
    cdir = tmp_path / "issues"
    unk_item = {**_VALID_ITEM, "matched_tags": "country, not_in_tags_yaml_xyz"}
    issue = {**_VALID_ISSUE_EN, "items": [unk_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    result = main([
        "--content-dir", str(cdir),
        "--tags", str(_TAGS_PATH),
        "--report", str(report_path),
        "--fail-on-warnings",
    ])
    assert result == 1


def test_no_fail_on_warnings_without_flag(tmp_path):
    cdir = tmp_path / "issues"
    unk_item = {**_VALID_ITEM, "matched_tags": "country, not_in_tags_yaml_xyz"}
    issue = {**_VALID_ISSUE_EN, "items": [unk_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    result = main([
        "--content-dir", str(cdir),
        "--tags", str(_TAGS_PATH),
        "--report", str(report_path),
        "--min-items", "1",
    ])
    assert result == 0


def test_errors_always_return_1(tmp_path):
    cdir = tmp_path / "issues"
    low_item = {**_VALID_ITEM, "score": 5}
    issue = {**_VALID_ISSUE_EN, "items": [low_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    result = main([
        "--content-dir", str(cdir),
        "--tags", str(_TAGS_PATH),
        "--report", str(report_path),
    ])
    assert result == 1


# ---------------------------------------------------------------------------
# EN/UK mismatch
# ---------------------------------------------------------------------------

def test_en_uk_url_mismatch_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    en_issue = {
        **_VALID_ISSUE_EN,
        "items": [
            {**_VALID_ITEM, "url": "https://example.com/1"},
            {**_VALID_ITEM, "url": "https://example.com/2", "title": "B"},
        ],
    }
    uk_issue = {
        **_VALID_ISSUE_UK,
        "items": [
            {**_VALID_ITEM, "url": "https://example.com/1"},
            {**_VALID_ITEM, "url": "https://example.com/DIFFERENT", "title": "B"},
        ],
    }
    _write_issue(cdir, "2026-01-15", "en", en_issue)
    _write_issue(cdir, "2026-01-15", "uk", uk_issue)
    summary = _run(cdir, tmp_path, min_items=2)
    assert summary["errors"] > 0


def test_en_uk_count_mismatch_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    en_issue = {
        **_VALID_ISSUE_EN,
        "items": [
            {**_VALID_ITEM, "url": "https://example.com/1"},
            {**_VALID_ITEM, "url": "https://example.com/2", "title": "B"},
            {**_VALID_ITEM, "url": "https://example.com/3", "title": "C"},
        ],
    }
    uk_issue = {
        **_VALID_ISSUE_UK,
        "items": [
            {**_VALID_ITEM, "url": "https://example.com/1"},
        ],
    }
    _write_issue(cdir, "2026-01-15", "en", en_issue)
    _write_issue(cdir, "2026-01-15", "uk", uk_issue)
    summary = _run(cdir, tmp_path, min_items=1)
    assert summary["errors"] > 0


def test_lang_filter_skips_cross_lang_check(tmp_path):
    cdir = tmp_path / "issues"
    en_issue = {
        **_VALID_ISSUE_EN,
        "items": [{**_VALID_ITEM, "url": "https://example.com/1"},
                  {**_VALID_ITEM, "url": "https://example.com/2", "title": "B"},
                  {**_VALID_ITEM, "url": "https://example.com/3", "title": "C"}],
    }
    uk_issue = {
        **_VALID_ISSUE_UK,
        "items": [{**_VALID_ITEM, "url": "https://example.com/DIFFERENT"}],
    }
    _write_issue(cdir, "2026-01-15", "en", en_issue)
    _write_issue(cdir, "2026-01-15", "uk", uk_issue)
    summary = _run(cdir, tmp_path, lang="en")
    assert summary["errors"] == 0


# ---------------------------------------------------------------------------
# Draft vs non-draft
# ---------------------------------------------------------------------------

def test_draft_issue_skips_min_items_check(tmp_path):
    cdir = tmp_path / "issues"
    draft_issue = {
        **_VALID_ISSUE_EN,
        "draft": True,
        "items": [{**_VALID_ITEM}],  # only 1 item, below default min_items=3
    }
    _write_issue(cdir, "2026-01-15", "en", draft_issue)
    _write_issue(cdir, "2026-01-15", "uk", {**draft_issue, "lang": "uk", "title": "UK"})
    summary = _run(cdir, tmp_path, min_items=3)
    assert summary["errors"] == 0


def test_non_draft_below_min_items_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    issue = {
        **_VALID_ISSUE_EN,
        "draft": False,
        "items": [{**_VALID_ITEM}],
    }
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path, min_items=3)
    assert summary["errors"] > 0


# ---------------------------------------------------------------------------
# Report CSV
# ---------------------------------------------------------------------------

def _read_rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))


def test_report_csv_created(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    assert report_path.exists()


def test_report_csv_has_header(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    first_line = report_path.read_text(encoding="utf-8").splitlines()[0]
    assert "issue_file" in first_line
    assert "severity" in first_line
    assert "problem" in first_line


def test_report_rows_contain_filename(tmp_path):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    rows = _read_rows(report_path)
    assert any("2026-01-15" in r["issue_file"] for r in rows)


def test_error_row_appears_in_report(tmp_path):
    cdir = tmp_path / "issues"
    low_item = {**_VALID_ITEM, "score": 5}
    issue = {**_VALID_ISSUE_EN, "items": [low_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    report_path = tmp_path / "report.csv"
    validate_content(
        content_dir=cdir, tags_path=_TAGS_PATH,
        report_path=report_path,
    )
    rows = _read_rows(report_path)
    assert any(r["severity"] == "error" for r in rows)


# ---------------------------------------------------------------------------
# --json output
# ---------------------------------------------------------------------------

def test_json_output_prints_valid_json(tmp_path, capsys):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    report_path = tmp_path / "report.csv"
    main([
        "--content-dir", str(cdir),
        "--tags", str(_TAGS_PATH),
        "--report", str(report_path),
        "--json",
    ])
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "errors" in data
    assert "warnings" in data
    assert "ok" in data
    assert "issues_checked" in data


def test_json_output_returns_0_for_valid(tmp_path, capsys):
    cdir = tmp_path / "issues"
    _write_issue(cdir, "2026-01-15", "en", _VALID_ISSUE_EN)
    _write_issue(cdir, "2026-01-15", "uk", _VALID_ISSUE_UK)
    report_path = tmp_path / "report.csv"
    result = main([
        "--content-dir", str(cdir),
        "--tags", str(_TAGS_PATH),
        "--report", str(report_path),
        "--json",
    ])
    assert result == 0


# ---------------------------------------------------------------------------
# Missing required fields
# ---------------------------------------------------------------------------

def test_missing_url_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    no_url_item = {**_VALID_ITEM, "url": ""}
    issue = {**_VALID_ISSUE_EN, "items": [no_url_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] > 0


def test_invalid_url_scheme_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    bad_url_item = {**_VALID_ITEM, "url": "ftp://example.com/article"}
    issue = {**_VALID_ISSUE_EN, "items": [bad_url_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] > 0


def test_missing_item_title_gives_error(tmp_path):
    cdir = tmp_path / "issues"
    no_title_item = {**_VALID_ITEM, "title": ""}
    issue = {**_VALID_ISSUE_EN, "items": [no_title_item]}
    _write_issue(cdir, "2026-01-15", "en", issue)
    summary = _run(cdir, tmp_path)
    assert summary["errors"] > 0


def test_missing_source_name_gives_warning(tmp_path):
    cdir = tmp_path / "issues"
    no_src_item = {**_VALID_ITEM, "source_name": ""}
    issue = {
        **_VALID_ISSUE_EN,
        "items": [
            {**no_src_item, "url": "https://example.com/1"},
            {**_VALID_ITEM, "url": "https://example.com/2", "title": "B"},
            {**_VALID_ITEM, "url": "https://example.com/3", "title": "C"},
        ],
    }
    _write_issue(cdir, "2026-01-15", "en", issue)
    _write_issue(cdir, "2026-01-15", "uk", {**issue, "lang": "uk", "title": "UK"})
    summary = _run(cdir, tmp_path)
    assert summary["warnings"] > 0
    assert summary["errors"] == 0

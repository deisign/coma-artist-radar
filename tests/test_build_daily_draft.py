from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.build_daily_draft import (
    DEFAULT_BASE_PATH,
    DEFAULT_BASE_URL,
    DEFAULT_ISSUE_LIMIT,
    DEFAULT_MIN_SCORE,
    run_pipeline,
)

# ---------------------------------------------------------------------------
# Canonical mock return values
# ---------------------------------------------------------------------------

_SYNC_SUMMARY = {"total_in_yaml": 2, "inserted": 0, "updated": 2, "active": 2, "inactive": 0}
_FETCH_SUMMARY = {
    "sources_total": 2, "sources_with_feed": 2, "sources_checked": 2,
    "items_found": 5, "inserted": 5, "skipped_duplicate": 0, "errors": 0, "dry_run": False,
}
_SCORE_SUMMARY = {
    "items_total": 5, "items_checked": 5, "updated": 5, "skipped": 0,
    "errors": 0, "dry_run": False, "top_candidates": [],
}
_ISSUE_SUMMARY = {
    "issue_date": "2026-01-01", "languages": ["en", "uk"],
    "selected_items": 3, "output_files": [], "draft": True,
}
_TAG_SUMMARY = {
    "languages": ["en", "uk"], "tags_total": 5, "tags_with_items": 2,
    "pages_written": 10, "unknown_tags": [], "output_files": [],
}
_SITE_SUMMARY = {
    "issues_total": 1, "pages_written": 8, "output_files": [],
    "base_url": DEFAULT_BASE_URL, "base_path": DEFAULT_BASE_PATH, "dry_run": False,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_all(monkeypatch) -> dict:
    """Replace all external pipeline callables with MagicMocks."""
    mocks: dict[str, MagicMock] = {}
    for name, rv in [
        ("sync_sources", _SYNC_SUMMARY),
        ("load_sources_yaml", []),
        ("fetch_and_store", _FETCH_SUMMARY),
        ("score_items", _SCORE_SUMMARY),
        ("build_issue", _ISSUE_SUMMARY),
        ("build_tag_pages", _TAG_SUMMARY),
        ("build_site", _SITE_SUMMARY),
    ]:
        m = MagicMock(return_value=rv)
        monkeypatch.setattr(f"scripts.build_daily_draft.{name}", m)
        mocks[name] = m
    return mocks


def _base_kwargs(tmp_path: Path, date: str = "2026-01-01") -> dict:
    return {
        "date": date,
        "db_path": tmp_path / "test.sqlite",
        "sources_path": tmp_path / "sources.yaml",
        "inbox_path": tmp_path / "manual.md",   # does not exist → inbox step skipped
        "content_dir": tmp_path / "content" / "issues",
        "dist_dir": tmp_path / "dist",
    }


# ---------------------------------------------------------------------------
# Steps and call order
# ---------------------------------------------------------------------------

def test_steps_called_in_order(monkeypatch, tmp_path):
    call_order: list[str] = []

    for name, rv in [
        ("sync_sources", _SYNC_SUMMARY),
        ("load_sources_yaml", []),
        ("fetch_and_store", _FETCH_SUMMARY),
        ("score_items", _SCORE_SUMMARY),
        ("build_issue", _ISSUE_SUMMARY),
        ("build_tag_pages", _TAG_SUMMARY),
        ("build_site", _SITE_SUMMARY),
    ]:
        def make_fn(n: str, r):
            def fn(*a, **kw):
                call_order.append(n)
                return r
            return fn
        monkeypatch.setattr(f"scripts.build_daily_draft.{name}", make_fn(name, rv))

    run_pipeline(**_base_kwargs(tmp_path))

    assert call_order == [
        "sync_sources",
        "load_sources_yaml",
        "fetch_and_store",
        "score_items",
        "build_issue",
        "build_tag_pages",
        "build_site",
    ]


def test_sync_sources_called_once(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["sync_sources"].assert_called_once()


def test_fetch_and_store_called_once(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["fetch_and_store"].assert_called_once()


def test_score_items_called_once(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["score_items"].assert_called_once()


def test_build_issue_called_once_in_normal_mode(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["build_issue"].assert_called_once()


def test_build_tag_pages_called_once(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["build_tag_pages"].assert_called_once()


def test_build_site_called_once(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    mocks["build_site"].assert_called_once()


# ---------------------------------------------------------------------------
# dry-run behaviour
# ---------------------------------------------------------------------------

def test_dry_run_skips_build_issue(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    mocks["build_issue"].assert_not_called()


def test_dry_run_build_site_receives_dry_run_true(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    _, kwargs = mocks["build_site"].call_args
    assert kwargs.get("dry_run") is True


def test_dry_run_build_tag_pages_receives_dry_run_true(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    _, kwargs = mocks["build_tag_pages"].call_args
    assert kwargs.get("dry_run") is True


def test_dry_run_fetch_receives_dry_run_true(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    _, kwargs = mocks["fetch_and_store"].call_args
    assert kwargs.get("dry_run") is True


def test_dry_run_no_dist_dir_created(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    assert not (tmp_path / "dist").exists()


def test_dry_run_issue_summary_has_zero_items(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    assert summary["issue_summary"]["selected_items"] == 0


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_output_urls(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path))
    assert "output_urls" in summary
    assert len(summary["output_urls"]) > 0


def test_summary_has_required_keys(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path))
    for key in ("date", "fetch_summary", "score_summary", "issue_summary",
                "site_summary", "output_urls", "dry_run"):
        assert key in summary, f"Missing key: {key}"


def test_summary_date_matches(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path, date="2026-05-26"))
    assert summary["date"] == "2026-05-26"


def test_summary_dry_run_flag(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path), dry_run=True)
    assert summary["dry_run"] is True


def test_output_urls_contain_issue_date(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path, date="2026-05-26"))
    assert any("2026-05-26" in u for u in summary["output_urls"])


def test_output_urls_contain_both_langs(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path))
    urls = summary["output_urls"]
    assert any("/en/" in u for u in urls)
    assert any("/uk/" in u for u in urls)


def test_output_urls_are_absolute(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    summary = run_pipeline(**_base_kwargs(tmp_path), base_url="https://example.com")
    assert all(u.startswith("https://") for u in summary["output_urls"])


# ---------------------------------------------------------------------------
# base_path forwarding
# ---------------------------------------------------------------------------

def test_base_path_forwarded_to_build_issue(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), base_path="/my-radar")
    _, kwargs = mocks["build_issue"].call_args
    assert kwargs.get("base_path") == "/my-radar"


def test_base_path_forwarded_to_build_tag_pages(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), base_path="/my-radar")
    _, kwargs = mocks["build_tag_pages"].call_args
    assert kwargs.get("base_path") == "/my-radar"


def test_base_path_forwarded_to_build_site(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), base_path="/my-radar")
    _, kwargs = mocks["build_site"].call_args
    assert kwargs.get("base_path") == "/my-radar"


def test_base_path_normalization_applied(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), base_path="my-radar/")
    _, kwargs = mocks["build_site"].call_args
    assert kwargs.get("base_path") == "/my-radar"


# ---------------------------------------------------------------------------
# fetch-limit forwarding
# ---------------------------------------------------------------------------

def test_fetch_limit_forwarded_to_fetch_and_store(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), fetch_limit=3)
    _, kwargs = mocks["fetch_and_store"].call_args
    assert kwargs.get("limit") == 3


def test_fetch_limit_none_by_default(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    _, kwargs = mocks["fetch_and_store"].call_args
    assert kwargs.get("limit") is None


# ---------------------------------------------------------------------------
# min-score and issue-limit forwarding
# ---------------------------------------------------------------------------

def test_min_score_forwarded_to_build_issue(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), min_score=50)
    _, kwargs = mocks["build_issue"].call_args
    assert kwargs.get("min_score") == 50


def test_issue_limit_forwarded_to_build_issue(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), issue_limit=5)
    _, kwargs = mocks["build_issue"].call_args
    assert kwargs.get("limit") == 5


def test_min_score_forwarded_to_score_items(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path), min_score=40)
    _, kwargs = mocks["score_items"].call_args
    assert kwargs.get("min_score") == 40


def test_default_min_score_is_30(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    _, kwargs = mocks["build_issue"].call_args
    assert kwargs.get("min_score") == DEFAULT_MIN_SCORE


def test_default_issue_limit_is_10(monkeypatch, tmp_path):
    mocks = _patch_all(monkeypatch)
    run_pipeline(**_base_kwargs(tmp_path))
    _, kwargs = mocks["build_issue"].call_args
    assert kwargs.get("limit") == DEFAULT_ISSUE_LIMIT


# ---------------------------------------------------------------------------
# inbox skipped when file absent
# ---------------------------------------------------------------------------

def test_no_inbox_import_submissions_not_called(monkeypatch, tmp_path):
    _patch_all(monkeypatch)
    import_mock = MagicMock()
    monkeypatch.setattr("scripts.build_daily_draft.import_submissions", import_mock)
    run_pipeline(**_base_kwargs(tmp_path))
    import_mock.assert_not_called()

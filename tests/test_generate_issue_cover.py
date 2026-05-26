from pathlib import Path

import pytest

from scripts.generate_issue_cover import (
    detect_main_tag_from_items,
    generate_issue_cover,
    generate_issue_covers,
    get_theme,
    load_themes,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_THEMES_PATH = _REPO_ROOT / "data" / "visual_themes.yaml"
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CONTENT_DIR = _REPO_ROOT / "content" / "issues"


def _cover_path(tmp_path: Path, date: str, lang: str) -> Path:
    return tmp_path / "dist" / "assets" / "covers" / "issues" / date / f"cover-{lang}.svg"


def _make_cover(tmp_path: Path, date: str = "2026-01-01", lang: str = "en",
                main_tag: str = "default", **kwargs) -> dict:
    return generate_issue_cover(
        issue_date=date,
        lang=lang,
        main_tag=main_tag,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------

def test_generate_cover_creates_en_svg(tmp_path):
    _make_cover(tmp_path, lang="en")
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()


def test_generate_cover_creates_uk_svg(tmp_path):
    _make_cover(tmp_path, lang="uk")
    assert _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_covers_both_langs(tmp_path):
    generate_issue_covers(
        issue_date="2026-01-01",
        languages=["en", "uk"],
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
    )
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()
    assert _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_covers_only_en(tmp_path):
    generate_issue_covers(
        issue_date="2026-01-01",
        languages=["en"],
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
    )
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()
    assert not _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_cover_dry_run_no_file(tmp_path):
    _make_cover(tmp_path, dry_run=True)
    assert not _cover_path(tmp_path, "2026-01-01", "en").exists()


# ---------------------------------------------------------------------------
# Theme selection
# ---------------------------------------------------------------------------

def test_surf_tag_selects_surf_theme(tmp_path):
    result = _make_cover(tmp_path, main_tag="surf")
    assert result["theme_id"] == "surf"


def test_unknown_tag_falls_back_to_default(tmp_path):
    result = _make_cover(tmp_path, main_tag="nonexistent_tag_xyz")
    assert result["theme_id"] == "default"


# ---------------------------------------------------------------------------
# SVG content
# ---------------------------------------------------------------------------

def test_svg_has_no_external_resources(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in svg
    assert "cdn" not in svg.lower()
    assert "<image" not in svg


def test_svg_contains_site_title(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "coma.fm Radar" in svg


def test_svg_contains_issue_date(tmp_path):
    _make_cover(tmp_path, date="2026-05-26")
    svg = _cover_path(tmp_path, "2026-05-26", "en").read_text(encoding="utf-8")
    assert "2026-05-26" in svg


def test_svg_contains_main_tag_label(tmp_path):
    _make_cover(tmp_path, main_tag="surf")
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "Surf" in svg


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def test_output_path_in_expected_folder(tmp_path):
    result = _make_cover(tmp_path, date="2026-03-15")
    assert "covers/issues/2026-03-15" in result["output_file"]
    assert "cover-en.svg" in result["output_file"]


# ---------------------------------------------------------------------------
# detect_main_tag_from_items
# ---------------------------------------------------------------------------

def test_detect_main_tag_priority_aesthetic_over_genre():
    tags_typed = {"surf": "aesthetic", "country": "genre"}
    items = [
        {"matched_tags": "country"},
        {"matched_tags": "country"},
        {"matched_tags": "surf"},
    ]
    assert detect_main_tag_from_items(items, tags_typed) == "surf"


def test_detect_main_tag_empty_returns_none():
    assert detect_main_tag_from_items([], {}) is None


def test_detect_main_tag_most_frequent_fallback():
    tags_typed = {"a": "content_type", "b": "content_type"}
    items = [{"matched_tags": "b"}, {"matched_tags": "b"}, {"matched_tags": "a"}]
    assert detect_main_tag_from_items(items, tags_typed) == "b"

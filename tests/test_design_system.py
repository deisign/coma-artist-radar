import json
from pathlib import Path

import pytest

from scripts.build_css import build_css
from scripts.build_issue import render_html
from scripts.build_site import build_site
from scripts.build_tag_pages import build_tag_pages

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _css_content(tmp_path: Path) -> str:
    build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR)
    return (tmp_path / "dist" / "assets" / "style.css").read_text(encoding="utf-8")


def _make_issue_fixtures(tmp_path: Path) -> Path:
    content_dir = tmp_path / "content" / "issues"
    content_dir.mkdir(parents=True, exist_ok=True)
    base = {
        "issue_date": "2026-01-15", "draft": False,
        "generated_at": "2026-01-15T00:00:00Z", "min_score": 30,
        "total_items": 0, "items": [],
    }
    (content_dir / "2026-01-15.en.json").write_text(
        json.dumps({**base, "lang": "en"}), encoding="utf-8"
    )
    (content_dir / "2026-01-15.uk.json").write_text(
        json.dumps({**base, "lang": "uk"}), encoding="utf-8"
    )
    return content_dir


def _make_tagged_fixture(tmp_path: Path) -> Path:
    content_dir = tmp_path / "content" / "issues"
    content_dir.mkdir(parents=True, exist_ok=True)
    issue = {
        "issue_date": "2026-01-15", "lang": "en", "draft": False,
        "generated_at": "2026-01-15T00:00:00Z", "min_score": 30,
        "total_items": 1,
        "items": [{
            "id": 1, "title": "Test Item", "url": "https://example.com/t1",
            "source_name": "Test Source", "score": 50,
            "matched_tags": "country", "matched_genres": "country",
            "matched_artists": "", "published_at": "",
        }],
    }
    (content_dir / "2026-01-15.en.json").write_text(json.dumps(issue), encoding="utf-8")
    return content_dir


# ---------------------------------------------------------------------------
# build_css — file creation
# ---------------------------------------------------------------------------

def test_build_css_creates_file(tmp_path):
    build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR)
    assert (tmp_path / "dist" / "assets" / "style.css").exists()


def test_build_css_dry_run_no_file(tmp_path):
    build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR, dry_run=True)
    assert not (tmp_path / "dist" / "assets" / "style.css").exists()


def test_build_css_returns_summary_keys(tmp_path):
    summary = build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR)
    assert "output_file" in summary
    assert "bytes" in summary
    assert "dry_run" in summary


def test_build_css_nonzero_bytes(tmp_path):
    summary = build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR)
    assert summary["bytes"] > 0


def test_build_css_dry_run_flag_in_summary(tmp_path):
    summary = build_css(dist_dir=tmp_path / "dist", templates_dir=_TEMPLATES_DIR, dry_run=True)
    assert summary["dry_run"] is True


# ---------------------------------------------------------------------------
# CSS content — required classes present
# ---------------------------------------------------------------------------

def test_css_has_site_header(tmp_path):
    assert ".site-header" in _css_content(tmp_path)


def test_css_has_issue_card(tmp_path):
    assert ".issue-card" in _css_content(tmp_path)


def test_css_has_item_card(tmp_path):
    assert ".item-card" in _css_content(tmp_path)


def test_css_has_tag_pill(tmp_path):
    assert ".tag-pill" in _css_content(tmp_path)


def test_css_has_language_switch(tmp_path):
    assert ".language-switch" in _css_content(tmp_path)


def test_css_has_site_shell(tmp_path):
    assert ".site-shell" in _css_content(tmp_path)


def test_css_has_nav_links(tmp_path):
    assert ".nav-links" in _css_content(tmp_path)


def test_css_has_footer(tmp_path):
    assert ".footer" in _css_content(tmp_path)


def test_css_has_tag_grid(tmp_path):
    assert ".tag-grid" in _css_content(tmp_path)


def test_css_has_archive_list(tmp_path):
    assert ".archive-list" in _css_content(tmp_path)


def test_css_has_issue_list(tmp_path):
    assert ".issue-list" in _css_content(tmp_path)


def test_css_has_meta(tmp_path):
    assert ".meta" in _css_content(tmp_path)


def test_css_has_score(tmp_path):
    assert ".score" in _css_content(tmp_path)


def test_css_has_source(tmp_path):
    assert ".source" in _css_content(tmp_path)


def test_css_has_issue_cover(tmp_path):
    assert ".issue-cover" in _css_content(tmp_path)


# ---------------------------------------------------------------------------
# CSS content — palette and no forbidden values
# ---------------------------------------------------------------------------

def test_css_has_warm_bg_variable(tmp_path):
    assert "--bg: #17130f" in _css_content(tmp_path)


def test_css_no_pure_black_background(tmp_path):
    css = _css_content(tmp_path)
    assert "background: #000" not in css
    assert "background-color: #000" not in css
    assert "--bg: #000" not in css


def test_css_no_external_import(tmp_path):
    assert "@import url(" not in _css_content(tmp_path)


def test_css_no_google_fonts(tmp_path):
    assert "fonts.googleapis.com" not in _css_content(tmp_path)


def test_css_no_cdn(tmp_path):
    assert "cdn" not in _css_content(tmp_path).lower()


# ---------------------------------------------------------------------------
# Templates link to stylesheet
# ---------------------------------------------------------------------------

def test_index_html_links_stylesheet_with_base_path(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/assets/style.css" in content


def test_index_html_links_stylesheet_no_base_path(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="",
    )
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "/assets/style.css" in content


def test_archive_html_links_stylesheet(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    content = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/assets/style.css" in content


def test_issue_html_links_stylesheet_with_base_path(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "/coma-artist-radar/assets/style.css" in html


def test_issue_html_links_stylesheet_no_base_path(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="",
    )
    assert "/assets/style.css" in html


def test_tag_page_links_stylesheet(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    tag_html = (tmp_path / "dist" / "en" / "tags" / "country.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/assets/style.css" in tag_html


def test_tags_index_links_stylesheet(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    idx_html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/assets/style.css" in idx_html


# ---------------------------------------------------------------------------
# build_site CSS integration
# ---------------------------------------------------------------------------

def test_build_site_creates_css_file(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
    )
    assert (tmp_path / "dist" / "assets" / "style.css").exists()


def test_build_site_dry_run_no_css(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        dry_run=True,
    )
    assert not (tmp_path / "dist" / "assets" / "style.css").exists()


def test_build_site_css_not_counted_in_pages_written(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    summary = build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
    )
    assert summary["pages_written"] == 8


def test_build_site_css_not_in_output_files(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    summary = build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
    )
    assert len(summary["output_files"]) == 8
    assert not any("style.css" in f for f in summary["output_files"])

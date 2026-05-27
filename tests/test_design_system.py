import json
from pathlib import Path

import pytest

from scripts.build_css import build_css
from scripts.build_issue import render_html
from scripts.build_site import build_site
from scripts.build_tag_pages import build_tag_pages
from scripts.transmission_meta import make_issue_meta, make_page_meta

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
# CSS content — required classes present (Stage 18 baseline)
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
# CSS content — Stage 19 modernist classes
# ---------------------------------------------------------------------------

def test_css_has_brand_mark(tmp_path):
    assert ".brand-mark" in _css_content(tmp_path)


def test_css_has_hero(tmp_path):
    assert ".hero" in _css_content(tmp_path)


def test_css_has_section_rule(tmp_path):
    assert ".section-rule" in _css_content(tmp_path)


def test_css_has_issue_grid(tmp_path):
    assert ".issue-grid" in _css_content(tmp_path)


def test_css_has_item_grid(tmp_path):
    assert ".item-grid" in _css_content(tmp_path)


def test_css_has_archive_item(tmp_path):
    assert ".archive-item" in _css_content(tmp_path)


def test_css_has_item_number(tmp_path):
    assert ".item-number" in _css_content(tmp_path)


def test_css_has_brand_line(tmp_path):
    assert ".brand-line" in _css_content(tmp_path)


def test_css_has_hero_kicker(tmp_path):
    assert ".hero-kicker" in _css_content(tmp_path)


def test_css_has_hero_title(tmp_path):
    assert ".hero-title" in _css_content(tmp_path)


def test_css_has_hero_deck(tmp_path):
    assert ".hero-deck" in _css_content(tmp_path)


def test_css_has_hero_meta(tmp_path):
    assert ".hero-meta" in _css_content(tmp_path)


def test_css_has_section_title(tmp_path):
    assert ".section-title" in _css_content(tmp_path)


def test_css_has_archive_date(tmp_path):
    assert ".archive-date" in _css_content(tmp_path)


def test_css_has_item_title(tmp_path):
    assert ".item-title" in _css_content(tmp_path)


def test_css_has_item_meta(tmp_path):
    assert ".item-meta" in _css_content(tmp_path)


def test_css_has_issue_card_date(tmp_path):
    assert ".issue-card-date" in _css_content(tmp_path)


def test_css_has_issue_card_title(tmp_path):
    assert ".issue-card-title" in _css_content(tmp_path)


# ---------------------------------------------------------------------------
# CSS content — Stage 20 Pearl Broadcast Modernism classes
# ---------------------------------------------------------------------------

def test_css_has_masthead(tmp_path):
    assert ".masthead" in _css_content(tmp_path)


def test_css_has_brand_grid(tmp_path):
    assert ".brand-grid" in _css_content(tmp_path)


def test_css_has_signal_strip(tmp_path):
    assert ".signal-strip" in _css_content(tmp_path)


def test_css_has_frequency_lines(tmp_path):
    assert ".frequency-lines" in _css_content(tmp_path)


def test_css_has_program_grid(tmp_path):
    assert ".program-grid" in _css_content(tmp_path)


def test_css_has_issue_layout(tmp_path):
    assert ".issue-layout" in _css_content(tmp_path)


def test_css_has_entry_number(tmp_path):
    assert ".entry-number" in _css_content(tmp_path)


def test_css_has_archive_index(tmp_path):
    assert ".archive-index" in _css_content(tmp_path)


def test_css_has_taxonomy_board(tmp_path):
    assert ".taxonomy-board" in _css_content(tmp_path)


def test_css_has_tag_dossier(tmp_path):
    assert ".tag-dossier" in _css_content(tmp_path)


# ---------------------------------------------------------------------------
# CSS content — palette and no forbidden values
# ---------------------------------------------------------------------------

def test_css_has_warm_bg_variable(tmp_path):
    assert "--bg:" in _css_content(tmp_path)


def test_css_bg_is_warm_not_pure_black(tmp_path):
    css = _css_content(tmp_path)
    # Pearl Broadcast Modernism: light pearl paper background
    assert "--bg:" in css
    assert "#F3EBDD" in css


def test_css_no_pure_black_background(tmp_path):
    css = _css_content(tmp_path)
    assert "background: #000" not in css
    assert "background-color: #000" not in css
    assert "--bg: #000" not in css


def test_css_no_pure_white_token(tmp_path):
    css = _css_content(tmp_path)
    assert "--text: #fff" not in css
    assert "--bg: #fff" not in css


def test_css_no_external_import(tmp_path):
    assert "@import url(" not in _css_content(tmp_path)


def test_css_no_google_fonts(tmp_path):
    assert "fonts.googleapis.com" not in _css_content(tmp_path)


def test_css_no_cdn(tmp_path):
    assert "cdn" not in _css_content(tmp_path).lower()


# ---------------------------------------------------------------------------
# Index HTML — hero structure present
# ---------------------------------------------------------------------------

def test_index_html_has_hero(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert 'class="hero"' in html


def test_index_html_has_brand_mark(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "brand-mark" in html


def test_index_html_has_hero_title(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "hero-title" in html


def test_index_html_has_section_rule(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "section-rule" in html


# ---------------------------------------------------------------------------
# Index HTML — Stage 20 classes
# ---------------------------------------------------------------------------

def test_index_html_has_signal_strip(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "signal-strip" in html


def test_index_html_has_program_grid(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "program-grid" in html


# ---------------------------------------------------------------------------
# Issue HTML — cover and item-card present
# ---------------------------------------------------------------------------

def test_issue_html_has_item_card(tmp_path):
    html = render_html(
        items=[{
            "id": 1, "title": "Test Article", "url": "https://example.com",
            "source_name": "Test Source", "score": 80, "published_at": "",
            "matched_artists": "", "tags": [],
        }],
        issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "item-card" in html


def test_issue_html_has_issue_cover_class(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
        cover_image_url="/coma-artist-radar/assets/covers/issues/2026-01-15/cover-en.svg",
    )
    assert "issue-cover" in html


def test_issue_html_has_item_grid(tmp_path):
    html = render_html(
        items=[{
            "id": 1, "title": "Test", "url": "https://example.com",
            "source_name": "Src", "score": 50, "published_at": "",
            "matched_artists": "", "tags": [],
        }],
        issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "item-grid" in html


def test_issue_html_has_item_number(tmp_path):
    html = render_html(
        items=[{
            "id": 1, "title": "Test", "url": "https://example.com",
            "source_name": "Src", "score": 50, "published_at": "",
            "matched_artists": "", "tags": [],
        }],
        issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "item-number" in html


# ---------------------------------------------------------------------------
# Issue HTML — Stage 20 classes
# ---------------------------------------------------------------------------

def test_issue_html_has_issue_layout(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "issue-layout" in html


def test_issue_html_has_entry_number(tmp_path):
    html = render_html(
        items=[{
            "id": 1, "title": "Test", "url": "https://example.com",
            "source_name": "Src", "score": 50, "published_at": "",
            "matched_artists": "", "tags": [],
        }],
        issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "entry-number" in html


# ---------------------------------------------------------------------------
# Archive HTML — archive-item present
# ---------------------------------------------------------------------------

def test_archive_html_has_archive_list(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "archive-list" in html


def test_archive_html_has_archive_item_class(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "archive-item" in html


# ---------------------------------------------------------------------------
# Archive HTML — Stage 20 classes
# ---------------------------------------------------------------------------

def test_archive_html_has_archive_index(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "archive-index" in html


def test_archive_html_has_archive_row(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "archive-row" in html


# ---------------------------------------------------------------------------
# Tags index — tag-grid present
# ---------------------------------------------------------------------------

def test_tags_index_has_tag_grid(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "tag-grid" in html


def test_tags_index_has_brand_mark(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "brand-mark" in html


# ---------------------------------------------------------------------------
# Tags index / tag page — Stage 20 classes
# ---------------------------------------------------------------------------

def test_tags_index_has_taxonomy_board(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "taxonomy-board" in html


def test_tag_page_has_tag_dossier(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "country.html").read_text(encoding="utf-8")
    assert "tag-dossier" in html


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


# ---------------------------------------------------------------------------
# Stage 22 — Nocturnal Signal Refinement
# ---------------------------------------------------------------------------

def test_transmission_meta_tx_code_deterministic():
    meta = make_issue_meta("2026-01-15", "en", [])
    assert meta["tx_code"] == "TX-20260115-EN"
    assert meta["tx_code"] == make_issue_meta("2026-01-15", "en", [])["tx_code"]


def test_transmission_meta_tx_code_lang_uk():
    meta = make_issue_meta("2026-05-27", "uk", [])
    assert meta["tx_code"] == "TX-20260527-UK"


def test_transmission_meta_field_tags_from_items():
    items = [{"matched_tags": "country, americana"}, {"matched_tags": "surf"}]
    meta = make_issue_meta("2026-01-15", "en", items)
    assert "country" in meta["field_tags"]
    assert "americana" in meta["field_tags"]
    assert "surf" in meta["field_tags"]


def test_transmission_meta_signal_count():
    items = [{"matched_tags": ""}, {"matched_tags": "country"}]
    meta = make_issue_meta("2026-01-15", "en", items)
    assert meta["signal_count"] == 2


def test_transmission_meta_field_tags_label_uppercase():
    items = [{"matched_tags": "country"}]
    meta = make_issue_meta("2026-01-15", "en", items)
    assert "COUNTRY" in meta["field_tags_label"]


def test_transmission_meta_page_meta_section_code():
    meta = make_page_meta("HOME-SIGNAL")
    assert meta["section_code"] == "HOME-SIGNAL"
    assert meta["tx_code"] == "HOME-SIGNAL"


def test_transmission_meta_band_value():
    meta = make_issue_meta("2026-01-15", "en", [])
    assert "88" in meta["band"]
    assert "108" in meta["band"]


# CSS — Stage 22 new classes

def test_css_has_micro_label(tmp_path):
    assert ".micro-label" in _css_content(tmp_path)


def test_css_has_frequency_scale(tmp_path):
    assert ".frequency-scale" in _css_content(tmp_path)


def test_css_has_tx_code_class(tmp_path):
    assert ".tx-code" in _css_content(tmp_path)


def test_css_has_micro_grid(tmp_path):
    assert ".micro-grid" in _css_content(tmp_path)


def test_css_has_frequency_mark(tmp_path):
    assert ".frequency-mark" in _css_content(tmp_path)


def test_css_has_signal_dot(tmp_path):
    assert ".signal-dot" in _css_content(tmp_path)


def test_css_has_instrument_line(tmp_path):
    assert ".instrument-line" in _css_content(tmp_path)


def test_css_has_field_tags_class(tmp_path):
    assert ".field-tags" in _css_content(tmp_path)


# Issue HTML — Stage 22

def test_issue_html_contains_tx_code(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "TX-20260115-EN" in html


def test_issue_html_contains_band(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "BAND" in html
    assert "88" in html


def test_issue_html_contains_signals_label(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
    )
    assert "SIGNALS" in html


# Index HTML — Stage 22

def test_index_html_has_home_signal(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "HOME-SIGNAL" in html


def test_index_html_has_band_label(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "BAND" in html
    assert "88" in html


def test_index_html_has_frequency_marks(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "frequency-mark" in html


# Archive HTML — Stage 22

def test_archive_html_has_archive_log(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "ARCHIVE-LOG" in html


# Tags index — Stage 22

def test_tags_index_html_has_taxonomy_board_label(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "TAXONOMY-BOARD" in html


# Tag page — Stage 22

def test_tag_page_has_tag_dossier_label(tmp_path):
    content_dir = _make_tagged_fixture(tmp_path)
    build_tag_pages(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "tags" / "country.html").read_text(encoding="utf-8")
    assert "TAG-DOSSIER" in html


# Cover SVG — Stage 22

def test_cover_svg_contains_tx_code(tmp_path):
    from scripts.generate_issue_cover import generate_issue_cover
    generate_issue_cover(
        issue_date="2026-01-15",
        lang="en",
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_REPO_ROOT / "data" / "visual_themes.yaml",
        tags_path=_TAGS_PATH,
    )
    svg = (
        tmp_path / "dist" / "assets" / "covers" / "issues"
        / "2026-01-15" / "cover-en.svg"
    ).read_text(encoding="utf-8")
    assert "TX-20260115-EN" in svg


def test_cover_svg_contains_band(tmp_path):
    from scripts.generate_issue_cover import generate_issue_cover
    generate_issue_cover(
        issue_date="2026-01-15",
        lang="en",
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_REPO_ROOT / "data" / "visual_themes.yaml",
        tags_path=_TAGS_PATH,
    )
    svg = (
        tmp_path / "dist" / "assets" / "covers" / "issues"
        / "2026-01-15" / "cover-en.svg"
    ).read_text(encoding="utf-8")
    assert "BAND" in svg
    assert "88" in svg


# ---------------------------------------------------------------------------
# Stage 24 — Transmission Cover System
# ---------------------------------------------------------------------------

# CSS — new cover system classes

def test_css_has_cover_frame(tmp_path):
    assert ".cover-frame" in _css_content(tmp_path)


def test_css_has_cover_grid(tmp_path):
    assert ".cover-grid" in _css_content(tmp_path)


def test_css_has_cover_meta(tmp_path):
    assert ".cover-meta" in _css_content(tmp_path)


def test_css_has_cover_code(tmp_path):
    assert ".cover-code" in _css_content(tmp_path)


def test_css_has_cover_band(tmp_path):
    assert ".cover-band" in _css_content(tmp_path)


def test_css_has_cover_node(tmp_path):
    assert ".cover-node" in _css_content(tmp_path)


def test_css_has_cover_mini(tmp_path):
    assert ".cover-mini" in _css_content(tmp_path)


def test_css_has_issue_cover_large(tmp_path):
    assert ".issue-cover-large" in _css_content(tmp_path)


def test_css_has_signal_cluster(tmp_path):
    assert ".signal-cluster" in _css_content(tmp_path)


def test_css_has_registration_mark(tmp_path):
    assert ".registration-mark" in _css_content(tmp_path)


# Index HTML — miniature covers on homepage

def test_index_html_has_cover_mini(tmp_path):
    content_dir = _make_issue_fixtures(tmp_path)
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_path="/coma-artist-radar",
    )
    html = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "cover-mini" in html


# Issue HTML — large cover block

def test_issue_html_has_issue_cover_large(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
        cover_image_url="/coma-artist-radar/assets/covers/issues/2026-01-15/cover-en.svg",
    )
    assert "issue-cover-large" in html


def test_issue_html_has_cover_frame(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
        cover_image_url="/coma-artist-radar/assets/covers/issues/2026-01-15/cover-en.svg",
    )
    assert "cover-frame" in html


def test_issue_html_has_cover_meta(tmp_path):
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATES_DIR / "issue.html.j2",
        base_path="/coma-artist-radar",
        cover_image_url="/coma-artist-radar/assets/covers/issues/2026-01-15/cover-en.svg",
    )
    assert "cover-meta" in html

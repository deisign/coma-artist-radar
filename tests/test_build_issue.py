import json
import sqlite3
from pathlib import Path

import pytest

from scripts.build_issue import (
    _J2Renderer,
    build_issue,
    enrich_items,
    load_items,
    load_tag_map,
    render_html,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"
_TEMPLATE_PATH = _REPO_ROOT / "templates" / "issue.html.j2"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path: Path) -> Path:
    from scripts.init_db import init_db
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.close()
    return db_path


def _insert_item(
    db_path: Path,
    title: str = "Test Item",
    url: str = "https://example.com/item",
    source_name: str = "Test Source",
    score: int = 50,
    matched_tags: str = "country, americana",
    matched_genres: str = "country",
    matched_artists: str = "",
    included_in_issue: int = 0,
) -> int:
    now = "2024-01-01T00:00:00Z"
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "INSERT INTO items (title, url, source_name, source_type, score, "
        "matched_tags, matched_genres, matched_artists, included_in_issue, "
        "first_seen_at, last_seen_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            title, url, source_name, "magazine", score,
            matched_tags, matched_genres, matched_artists, included_in_issue,
            now, now, now, now,
        ),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def _run_build(tmp_path: Path, **kwargs) -> dict:
    db_path = kwargs.pop("db_path")
    return build_issue(
        db_path=db_path,
        issue_date=kwargs.pop("issue_date", "2026-01-01"),
        draft=kwargs.pop("draft", True),
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
        tags_path=_TAGS_PATH,
        template_path=_TEMPLATE_PATH,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# _J2Renderer unit tests
# ---------------------------------------------------------------------------

def test_renderer_variable_substitution():
    r = _J2Renderer()
    assert r.render("Hello {{ name }}!", {"name": "World"}) == "Hello World!"


def test_renderer_for_loop():
    r = _J2Renderer()
    out = r.render("{% for x in items %}{{ x }}{% endfor %}", {"items": ["a", "b", "c"]})
    assert out == "abc"


def test_renderer_if_true():
    r = _J2Renderer()
    out = r.render("{% if flag %}YES{% endif %}", {"flag": True})
    assert out == "YES"


def test_renderer_if_false():
    r = _J2Renderer()
    out = r.render("{% if flag %}YES{% else %}NO{% endif %}", {"flag": False})
    assert out == "NO"


def test_renderer_equality_condition():
    r = _J2Renderer()
    out = r.render('{% if lang == "en" %}English{% endif %}', {"lang": "en"})
    assert out == "English"


def test_renderer_dot_notation():
    r = _J2Renderer()
    out = r.render("{{ item.title }}", {"item": {"title": "My Title"}})
    assert out == "My Title"


def test_renderer_html_escapes_strings():
    r = _J2Renderer()
    out = r.render("{{ title }}", {"title": "A & B <test>"})
    assert "&amp;" in out
    assert "&lt;" in out


def test_renderer_nested_for():
    r = _J2Renderer()
    out = r.render(
        "{% for row in rows %}[{% for cell in row.cells %}{{ cell }}{% endfor %}]{% endfor %}",
        {"rows": [{"cells": ["a", "b"]}, {"cells": ["c"]}]},
    )
    assert out == "[ab][c]"


# ---------------------------------------------------------------------------
# load_tag_map
# ---------------------------------------------------------------------------

def test_load_tag_map_returns_dict():
    tag_map = load_tag_map(_TAGS_PATH)
    assert isinstance(tag_map, dict)
    assert "country" in tag_map
    assert "slug" in tag_map["country"]
    assert "label" in tag_map["country"]


def test_load_tag_map_country_slug():
    tag_map = load_tag_map(_TAGS_PATH)
    assert tag_map["country"]["slug"] == "country"


def test_load_tag_map_dark_jazz_slug():
    tag_map = load_tag_map(_TAGS_PATH)
    assert tag_map["dark_jazz"]["slug"] == "dark-jazz"


# ---------------------------------------------------------------------------
# enrich_items
# ---------------------------------------------------------------------------

def test_enrich_items_adds_tags_list():
    tag_map = load_tag_map(_TAGS_PATH)
    items = [{"matched_tags": "country, americana", "published_at": "", "matched_artists": ""}]
    enriched = enrich_items(items, tag_map)
    assert isinstance(enriched[0]["tags"], list)
    tag_ids = [t["id"] for t in enriched[0]["tags"]]
    assert "country" in tag_ids
    assert "americana" in tag_ids


def test_enrich_items_unknown_tag_skipped():
    tag_map = load_tag_map(_TAGS_PATH)
    items = [{"matched_tags": "nonexistent_tag", "published_at": "", "matched_artists": ""}]
    enriched = enrich_items(items, tag_map)
    assert enriched[0]["tags"] == []


def test_enrich_items_formats_iso_date():
    tag_map = load_tag_map(_TAGS_PATH)
    items = [{"matched_tags": "", "published_at": "2024-01-15T12:00:00Z", "matched_artists": ""}]
    enriched = enrich_items(items, tag_map)
    assert enriched[0]["published_at"] == "2024-01-15"


# ---------------------------------------------------------------------------
# build_issue — EN HTML
# ---------------------------------------------------------------------------

def test_build_issue_creates_en_html(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path, lang="en")

    en_html = tmp_path / "dist" / "en" / "issues" / "2026-01-01.html"
    assert en_html.exists()
    assert en_html in [tmp_path / f for f in summary["output_files"]] or any(
        "en/issues/2026-01-01.html" in f for f in summary["output_files"]
    )


def test_build_issue_creates_uk_html(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path, lang="uk")

    uk_html = tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html"
    assert uk_html.exists()


def test_build_issue_creates_both_langs_by_default(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path)

    assert (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").exists()
    assert (tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html").exists()
    assert summary["languages"] == ["en", "uk"]


def test_build_issue_creates_json(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en")

    json_path = tmp_path / "content" / "issues" / "2026-01-01.en.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["lang"] == "en"
    assert data["issue_date"] == "2026-01-01"
    assert isinstance(data["items"], list)


def test_json_contains_selected_items(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, title="High Score Item", score=80)

    _run_build(tmp_path, db_path=db_path, lang="en")

    json_path = tmp_path / "content" / "issues" / "2026-01-01.en.json"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "High Score Item"


# ---------------------------------------------------------------------------
# min-score and limit filtering
# ---------------------------------------------------------------------------

def test_item_below_min_score_excluded(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, title="Low Score", url="https://ex.com/low", score=10)
    _insert_item(db_path, title="High Score", url="https://ex.com/high", score=60)

    summary = _run_build(tmp_path, db_path=db_path, lang="en", min_score=30)

    assert summary["selected_items"] == 1
    html_path = tmp_path / "dist" / "en" / "issues" / "2026-01-01.html"
    html_content = html_path.read_text(encoding="utf-8")
    assert "High Score" in html_content
    assert "Low Score" not in html_content


def test_limit_restricts_items(tmp_path):
    db_path = _make_db(tmp_path)
    for i in range(5):
        _insert_item(db_path, title=f"Item {i}", url=f"https://ex.com/{i}", score=50 + i)

    # All items share the same source; disable source cap so the limit is the only constraint.
    summary = _run_build(tmp_path, db_path=db_path, lang="en", limit=3, max_per_source=0)

    assert summary["selected_items"] == 3


# ---------------------------------------------------------------------------
# HTML content tests
# ---------------------------------------------------------------------------

def test_tags_become_links_in_en_html(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, matched_tags="country, americana", score=50)

    _run_build(tmp_path, db_path=db_path, lang="en")

    html_content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'href="/en/tags/country.html"' in html_content
    assert 'href="/en/tags/americana.html"' in html_content


def test_tags_links_use_uk_path_in_uk_html(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, matched_tags="country", score=50)

    _run_build(tmp_path, db_path=db_path, lang="uk")

    html_content = (tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'href="/uk/tags/country.html"' in html_content


def test_music_tag_labels_not_translated_in_uk(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, matched_tags="country, americana, psychobilly", score=50)

    _run_build(tmp_path, db_path=db_path, lang="uk")

    html_content = (tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    tag_map = load_tag_map(_TAGS_PATH)
    # Tag labels must be English/international, not translated
    assert tag_map["country"]["label"] in html_content
    assert tag_map["americana"]["label"] in html_content
    assert tag_map["psychobilly"]["label"] in html_content


def test_draft_notice_shown_when_draft(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en", draft=True)

    html_content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "draft-notice" in html_content
    assert "Draft" in html_content


def test_uk_html_has_ukrainian_heading(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="uk")

    html_content = (tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "Радар" in html_content


def test_en_html_has_english_heading(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en")

    html_content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "coma.fm Radar" in html_content


def test_html_lang_attribute_set_correctly(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="uk")

    html_content = (tmp_path / "dist" / "uk" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'lang="uk"' in html_content


# ---------------------------------------------------------------------------
# Empty items case
# ---------------------------------------------------------------------------

def test_empty_items_produces_valid_html(tmp_path):
    db_path = _make_db(tmp_path)
    # No items inserted — or all below min-score
    _insert_item(db_path, score=5, url="https://ex.com/low2")

    summary = _run_build(tmp_path, db_path=db_path, lang="en", min_score=30)

    assert summary["selected_items"] == 0
    html_path = tmp_path / "dist" / "en" / "issues" / "2026-01-01.html"
    assert html_path.exists()
    html_content = html_path.read_text(encoding="utf-8")
    assert "no-items" in html_content or "No items" in html_content


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_output_files(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path)

    assert "output_files" in summary
    assert isinstance(summary["output_files"], list)
    assert len(summary["output_files"]) > 0


def test_summary_has_required_keys(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path)

    for key in ("issue_date", "languages", "selected_items", "output_files", "draft"):
        assert key in summary, f"Missing key: {key}"


def test_summary_issue_date_matches(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    summary = _run_build(tmp_path, db_path=db_path, issue_date="2026-05-25")

    assert summary["issue_date"] == "2026-05-25"


# ---------------------------------------------------------------------------
# Stage 12: base_path support
# ---------------------------------------------------------------------------

_GITHUB_BASE_PATH = "/coma-artist-radar"


def test_project_base_path_in_issue_nav(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en", base_path=_GITHUB_BASE_PATH)

    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/en/issues/2026-01-01.html" in content
    assert "/coma-artist-radar/uk/issues/2026-01-01.html" in content


def test_custom_domain_no_base_path_in_issue(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en", base_path="")

    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar" not in content


def test_project_base_path_no_bare_nav_links(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)

    _run_build(tmp_path, db_path=db_path, lang="en", base_path=_GITHUB_BASE_PATH)

    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'href="/en/issues/' not in content
    assert 'href="/uk/issues/' not in content


def test_project_base_path_in_tag_links(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, matched_tags="country", score=50)

    _run_build(tmp_path, db_path=db_path, lang="en", base_path=_GITHUB_BASE_PATH)

    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'href="/coma-artist-radar/en/tags/country.html"' in content


# ---------------------------------------------------------------------------
# Stage 17: cover image tests
# ---------------------------------------------------------------------------

def test_build_issue_creates_cover_svg(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", with_cover=True)
    cover = tmp_path / "dist" / "assets" / "covers" / "issues" / "2026-01-01" / "cover-en.svg"
    assert cover.exists()


def test_build_issue_html_contains_cover_img(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", with_cover=True)
    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'class="issue-cover"' in content


def test_build_issue_cover_url_includes_base_path(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", base_path=_GITHUB_BASE_PATH, with_cover=True)
    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/assets/covers/issues/2026-01-01/cover-en.svg" in content


def test_build_issue_no_cover_skips_svg(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", with_cover=False)
    cover = tmp_path / "dist" / "assets" / "covers" / "issues" / "2026-01-01" / "cover-en.svg"
    assert not cover.exists()


def test_build_issue_no_cover_html_has_no_cover_img(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", with_cover=False)
    content = (tmp_path / "dist" / "en" / "issues" / "2026-01-01.html").read_text(encoding="utf-8")
    assert 'class="issue-cover"' not in content


# ---------------------------------------------------------------------------
# Stage 22 — transmission metadata in issue HTML
# ---------------------------------------------------------------------------

def test_render_html_contains_tx_code():
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH,
        base_path="",
    )
    assert "TX-20260115-EN" in html


def test_render_html_tx_code_uk():
    html = render_html(
        items=[], issue_date="2026-05-27", lang="uk", draft=False,
        template_path=_TEMPLATE_PATH,
        base_path="",
    )
    assert "TX-20260527-UK" in html


def test_build_issue_html_contains_tx_code(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, score=50)
    _run_build(tmp_path, db_path=db_path, lang="en", issue_date="2026-03-10")
    content = (tmp_path / "dist" / "en" / "issues" / "2026-03-10.html").read_text(encoding="utf-8")
    assert "TX-20260310-EN" in content


# ---------------------------------------------------------------------------
# Stage 26A — Issue Hero Cleanup
# ---------------------------------------------------------------------------

def test_render_html_no_raw_payload_in_hero():
    """Hero must not expose raw Python list/dict structures."""
    items = [
        {
            "id": 1, "title": "Test Article", "url": "https://example.com",
            "source_name": "Test Source", "score": 80, "published_at": "",
            "matched_artists": "The Cramps", "tags": [],
            "matched_tags": "surf", "matched_genres": "surf",
        }
    ]
    html = render_html(
        items=items, issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    # Raw Python list/dict repr must not appear anywhere
    assert "'id':" not in html
    assert "&#x27;id&#x27;:" not in html
    assert "'source_name':" not in html
    assert "'matched_tags':" not in html


def test_render_html_no_raw_payload_empty_items():
    """Hero with no items must not render a raw empty list."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "[]" not in html
    assert "'id':" not in html


def test_render_html_has_tx_summary():
    """Hero must contain the editorial transmission summary."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "transmission-block" in html
    assert "tx-summary" in html
    assert "FIELD MONITORING LOG" in html.upper()


def test_render_html_tx_summary_uk():
    """UK hero must contain Ukrainian editorial summary."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="uk", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "transmission-block" in html
    # Ukrainian summary contains key word
    assert "журнал" in html.lower() or "ЖУРНАЛ" in html


def test_render_html_tx_summary_contains_signal_count():
    """Editorial summary must include the actual signal count."""
    items = [
        {
            "id": i, "title": f"Song {i}", "url": f"https://ex.com/{i}",
            "source_name": "Src", "score": 50, "published_at": "",
            "matched_artists": "", "tags": [], "matched_tags": "", "matched_genres": "",
        }
        for i in range(7)
    ]
    html = render_html(
        items=items, issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "7" in html


def test_render_html_hero_preserves_tx_code():
    """TX code must remain in the hero after cleanup."""
    html = render_html(
        items=[], issue_date="2026-05-10", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "TX-20260510-EN" in html


def test_render_html_hero_preserves_band():
    """BAND label must remain in the hero after cleanup."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "BAND" in html
    assert "88" in html


def test_render_html_hero_preserves_signals():
    """SIGNALS label must remain in the hero after cleanup."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert "SIGNALS" in html


def test_render_html_item_numbers_not_empty():
    """Entry numbers must render as '01', '02' — not empty string."""
    items = [
        {
            "id": 1, "title": "A Song", "url": "https://ex.com",
            "source_name": "Src", "score": 50, "published_at": "",
            "matched_artists": "", "tags": [], "matched_tags": "", "matched_genres": "",
        },
        {
            "id": 2, "title": "B Song", "url": "https://ex.com/2",
            "source_name": "Src", "score": 40, "published_at": "",
            "matched_artists": "", "tags": [], "matched_tags": "", "matched_genres": "",
        },
    ]
    html = render_html(
        items=items, issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert ">01<" in html
    assert ">02<" in html


def test_render_html_lang_label_uppercase():
    """Language in meta-grid must be uppercase (EN not en)."""
    html = render_html(
        items=[], issue_date="2026-01-15", lang="en", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    # The meta-grid Lang row must show uppercase "EN"
    assert ">EN<" in html


def test_render_html_lang_label_uk_uppercase():
    html = render_html(
        items=[], issue_date="2026-01-15", lang="uk", draft=False,
        template_path=_TEMPLATE_PATH, base_path="",
    )
    assert ">UK<" in html


# ---------------------------------------------------------------------------
# Stage 26B — Signal Type System
# ---------------------------------------------------------------------------

def _stage26b_item(title, matched_tags="", matched_genres="", source_type=""):
    return {
        "id": 1,
        "title": title,
        "url": "https://example.com/item",
        "source_name": "Example Source",
        "source_type": source_type,
        "score": 80,
        "published_at": "",
        "matched_artists": "",
        "matched_tags": matched_tags,
        "matched_genres": matched_genres,
        "tags": [],
    }


def test_classify_signal_type_prefers_review_over_release():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item("ALBUM REVIEW: A New Album From the Night Road")
    assert classify_signal_type(item) == "review"


def test_classify_signal_type_detects_reissue():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item("Classic swamp blues box set gets expanded reissue")
    assert classify_signal_type(item) == "reissue"


def test_classify_signal_type_detects_archive_signal():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item("Previously unreleased live recording from the vault")
    assert classify_signal_type(item) == "archive"


def test_classify_signal_type_falls_back_to_signal():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item("Nocturnal dispatch from a distant radio field")
    assert classify_signal_type(item) == "signal"


def test_render_html_shows_signal_type_label():
    html = render_html(
        items=[_stage26b_item("ALBUM REVIEW: A New Album From the Night Road")],
        issue_date="2026-01-15",
        lang="en",
        draft=False,
        template_path=_TEMPLATE_PATH,
        base_path="",
    )
    assert "signal-type" in html
    assert "Review signal" in html


def test_render_html_shows_uk_signal_type_label():
    html = render_html(
        items=[_stage26b_item("Interview with a late-night surf guitarist")],
        issue_date="2026-01-15",
        lang="uk",
        draft=False,
        template_path=_TEMPLATE_PATH,
        base_path="",
    )
    assert "signal-type" in html
    assert "Сигнал інтерв" in html


def test_build_issue_json_contains_signal_type(tmp_path):
    import sqlite3
    from scripts.build_issue import build_issue

    db_path = tmp_path / "radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE items ("
        "id INTEGER, title TEXT, url TEXT, source_name TEXT, source_type TEXT, "
        "published_at TEXT, score INTEGER, matched_artists TEXT, matched_tags TEXT, matched_genres TEXT"
        ")"
    )
    conn.execute(
        "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,
            "ALBUM REVIEW: A New Album From the Night Road",
            "https://example.com/review",
            "Example Source",
            "magazine",
            "2026-01-15T00:00:00Z",
            90,
            "",
            "",
            "",
        ),
    )
    conn.commit()
    conn.close()

    tags_path = tmp_path / "tags.yaml"
    tags_path.write_text("tags: []\n", encoding="utf-8")

    template_path = tmp_path / "issue.html.j2"
    template_path.write_text(_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    content_dir = tmp_path / "content"
    dist_dir = tmp_path / "dist"

    build_issue(
        db_path=db_path,
        issue_date="2026-01-15",
        lang="en",
        limit=10,
        min_score=30,
        draft=True,
        template_path=template_path,
        tags_path=tags_path,
        content_dir=content_dir,
        dist_dir=dist_dir,
        base_path="",
        with_cover=False,
    )

    data = json.loads((content_dir / "2026-01-15.en.json").read_text(encoding="utf-8"))
    assert data["items"][0]["signal_type"] == "review"
    assert data["items"][0]["signal_type_label"] == "Review signal"


# ---------------------------------------------------------------------------
# Stage 26C — Source Diversity / Editorial Selection
# ---------------------------------------------------------------------------

def _stage26c_candidate(source, score, title=None, matched_tags=""):
    return {
        "id": int(score),
        "title": title or f"Candidate {score}",
        "url": f"https://example.com/{source}/{score}",
        "source_name": source,
        "source_type": "magazine",
        "published_at": "",
        "score": score,
        "matched_artists": "",
        "matched_tags": matched_tags,
        "matched_genres": "",
    }


def test_select_editorial_items_limits_dominant_source_when_alternatives_exist():
    from scripts.build_issue import select_editorial_items

    candidates = [
        _stage26c_candidate("No Depression", 100 - i)
        for i in range(10)
    ] + [
        _stage26c_candidate(f"Other Source {i}", 80 - i)
        for i in range(10)
    ]

    selected = select_editorial_items(candidates, limit=10, max_per_source=3)
    no_depression_count = sum(1 for item in selected if item["source_name"] == "No Depression")

    assert len(selected) == 10
    assert no_depression_count == 3
    assert any(item["source_name"].startswith("Other Source") for item in selected)


def test_select_editorial_items_fills_from_dominant_source_when_needed():
    from scripts.build_issue import select_editorial_items

    candidates = [
        _stage26c_candidate("No Depression", 100 - i)
        for i in range(10)
    ]

    selected = select_editorial_items(candidates, limit=10, max_per_source=3)

    assert len(selected) == 10
    assert all(item["source_name"] == "No Depression" for item in selected)


def test_select_editorial_items_uses_strong_overflow_after_alternatives():
    from scripts.build_issue import select_editorial_items

    candidates = [
        _stage26c_candidate("No Depression", 100 - i)
        for i in range(10)
    ] + [
        _stage26c_candidate(f"Other Source {i}", 70 - i)
        for i in range(4)
    ]

    selected = select_editorial_items(candidates, limit=10, max_per_source=3)
    no_depression_count = sum(1 for item in selected if item["source_name"] == "No Depression")

    assert len(selected) == 10
    assert no_depression_count == 6


def test_select_editorial_items_priority_override_bypasses_source_cap():
    from scripts.build_issue import select_editorial_items

    candidates = [
        _stage26c_candidate("No Depression", 100, matched_tags="must_use"),
        _stage26c_candidate("No Depression", 99, matched_tags="must_use"),
        _stage26c_candidate("No Depression", 98, matched_tags="must_use"),
        _stage26c_candidate("No Depression", 97, matched_tags="must_use"),
        _stage26c_candidate("Other Source", 80),
    ]

    selected = select_editorial_items(candidates, limit=5, max_per_source=3)
    no_depression_count = sum(1 for item in selected if item["source_name"] == "No Depression")

    assert len(selected) == 5
    assert no_depression_count == 4


def test_build_issue_applies_source_diversity_to_json(tmp_path):
    import sqlite3
    from scripts.build_issue import build_issue

    db_path = tmp_path / "radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE items ("
        "id INTEGER, title TEXT, url TEXT, source_name TEXT, source_type TEXT, "
        "published_at TEXT, score INTEGER, matched_artists TEXT, matched_tags TEXT, matched_genres TEXT"
        ")"
    )

    rows = []
    item_id = 1
    for i in range(10):
        rows.append((
            item_id,
            f"No Depression item {i}",
            f"https://nodepression.example/{i}",
            "No Depression",
            "magazine",
            "2026-01-15T00:00:00Z",
            100 - i,
            "",
            "",
            "",
        ))
        item_id += 1

    for i in range(10):
        rows.append((
            item_id,
            f"Other item {i}",
            f"https://other.example/{i}",
            f"Other Source {i}",
            "magazine",
            "2026-01-15T00:00:00Z",
            80 - i,
            "",
            "",
            "",
        ))
        item_id += 1

    conn.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    tags_path = tmp_path / "tags.yaml"
    tags_path.write_text("tags: []\n", encoding="utf-8")

    template_path = tmp_path / "issue.html.j2"
    template_path.write_text(_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    content_dir = tmp_path / "content"
    dist_dir = tmp_path / "dist"

    build_issue(
        db_path=db_path,
        issue_date="2026-01-15",
        lang="en",
        limit=10,
        min_score=30,
        draft=True,
        template_path=template_path,
        tags_path=tags_path,
        content_dir=content_dir,
        dist_dir=dist_dir,
        base_path="",
        with_cover=False,
        max_per_source=3,
    )

    data = json.loads((content_dir / "2026-01-15.en.json").read_text(encoding="utf-8"))
    sources = [item["source_name"] for item in data["items"]]

    assert len(sources) == 10
    assert sources.count("No Depression") == 3
    assert any(source.startswith("Other Source") for source in sources)


# ---------------------------------------------------------------------------
# Stage 26D-A — Industry / Culture Signal Types
# ---------------------------------------------------------------------------

def test_classify_signal_type_detects_industry_angle():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item(
        "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
        matched_tags="country",
    )

    assert classify_signal_type(item) == "industry"


def test_classify_signal_type_detects_culture_angle():
    from scripts.build_issue import classify_signal_type

    item = _stage26b_item(
        "Paul McCartney Says This Pop Star Has a Similar Level of Fame",
        matched_tags="rock",
    )

    assert classify_signal_type(item) == "culture"


# ---------------------------------------------------------------------------
# Stage 26D-B — Field Evidence Helpers
# ---------------------------------------------------------------------------

def test_build_field_evidence_detects_artist_tag_genre_signal_and_source():
    from scripts.build_issue import build_field_evidence

    item = {
        "title": "ALBUM REVIEW: A signal from the field",
        "source_name": "No Depression",
        "source_type": "magazine",
        "matched_artists": "Paul McCartney",
        "matched_tags": "country",
        "matched_genres": "country",
        "signal_type": "review",
    }

    evidence = build_field_evidence(item)

    assert "artist_match" in evidence
    assert "tag_match" in evidence
    assert "genre_match" in evidence
    assert "review_signal" in evidence
    assert "source_signal" in evidence


def test_build_field_evidence_detects_industry_signal():
    from scripts.build_issue import build_field_evidence

    item = {
        "title": "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
        "source_name": "Saving Country Music",
        "source_type": "magazine",
        "matched_artists": "Kacey Musgraves",
        "matched_tags": "country",
        "matched_genres": "country",
    }

    evidence = build_field_evidence(item)

    assert "artist_match" in evidence
    assert "industry_signal" in evidence
    assert "source_signal" in evidence


def test_build_field_evidence_falls_back_to_weak_signal():
    from scripts.build_issue import build_field_evidence

    item = {
        "title": "Unmarked dispatch",
        "source_name": "",
        "source_type": "",
        "matched_artists": "",
        "matched_tags": "",
        "matched_genres": "",
    }

    assert build_field_evidence(item) == ["weak_signal"]


def test_localize_field_evidence_en():
    from scripts.build_issue import localize_field_evidence

    label = localize_field_evidence(["artist_match", "industry_signal", "source_signal"], "en")

    assert label == "Artist match · Industry signal · Source signal"


def test_localize_field_evidence_uk():
    from scripts.build_issue import localize_field_evidence

    label = localize_field_evidence(["artist_match", "culture_signal", "source_signal"], "uk")

    assert "Збіг артиста" in label
    assert "Культурний сигнал" in label
    assert "Сигнал джерела" in label


# ---------------------------------------------------------------------------
# Stage 26D-C — Editorial Angle Helper
# ---------------------------------------------------------------------------

def test_build_editorial_angle_industry_artist_en():
    from scripts.build_issue import build_editorial_angle

    item = {
        "title": "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
        "matched_artists": "Kacey Musgraves",
        "matched_tags": "country",
        "matched_genres": "country",
        "source_name": "Saving Country Music",
        "signal_type": "industry",
        "field_evidence": ["artist_match", "tag_match", "industry_signal", "source_signal"],
    }

    assert build_editorial_angle(item, "en") == "Industry / brand context around a coma.fm-field artist."


def test_build_editorial_angle_culture_artist_en():
    from scripts.build_issue import build_editorial_angle

    item = {
        "title": "Paul McCartney Says This Pop Star Has a Similar Level of Fame",
        "matched_artists": "Paul McCartney",
        "matched_tags": "rock",
        "matched_genres": "rock",
        "source_name": "American Songwriter",
        "signal_type": "culture",
        "field_evidence": ["artist_match", "tag_match", "culture_signal", "source_signal"],
    }

    assert build_editorial_angle(item, "en") == "Culture context around a coma.fm-field artist."


def test_build_editorial_angle_review_artist_uk():
    from scripts.build_issue import build_editorial_angle

    item = {
        "title": "ALBUM REVIEW: A Night Road Record",
        "matched_artists": "The Cramps",
        "matched_tags": "psychobilly",
        "matched_genres": "rockabilly",
        "source_name": "No Depression",
        "signal_type": "review",
        "field_evidence": ["artist_match", "tag_match", "review_signal", "source_signal"],
    }

    assert build_editorial_angle(item, "uk") == "Сигнал рецензії з артистичного поля coma.fm."


def test_build_editorial_angle_genre_field_en():
    from scripts.build_issue import build_editorial_angle

    item = {
        "title": "New instrumental surf compilation",
        "matched_artists": "",
        "matched_tags": "instrumental_surf",
        "matched_genres": "surf",
        "source_name": "Example Source",
        "signal_type": "release",
        "field_evidence": ["tag_match", "genre_match", "release_signal", "source_signal"],
    }

    assert build_editorial_angle(item, "en") == "Release signal from the coma.fm genre field."


# ---------------------------------------------------------------------------
# Stage 26D-D — Evidence / Angle Integration
# ---------------------------------------------------------------------------

def test_render_html_prepares_field_evidence_label_and_editorial_angle():
    html = render_html(
        items=[{
            "id": 1,
            "title": "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
            "url": "https://example.com/kacey",
            "source_name": "Saving Country Music",
            "source_type": "magazine",
            "score": 80,
            "published_at": "",
            "matched_artists": "Kacey Musgraves",
            "matched_tags": "country",
            "matched_genres": "country",
            "tags": [],
            "signal_type": "industry",
            "field_evidence": ["artist_match", "tag_match", "industry_signal", "source_signal"],
        }],
        issue_date="2026-01-15",
        lang="en",
        draft=False,
        template_path=_TEMPLATE_PATH,
        base_path="",
    )

    assert "Industry signal" in html
    assert "Industry / brand context around a coma.fm-field artist." in html


def test_build_issue_json_contains_field_evidence_and_editorial_angle(tmp_path):
    import sqlite3
    from scripts.build_issue import build_issue

    db_path = tmp_path / "radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE items ("
        "id INTEGER, title TEXT, url TEXT, source_name TEXT, source_type TEXT, "
        "published_at TEXT, score INTEGER, matched_artists TEXT, matched_tags TEXT, matched_genres TEXT"
        ")"
    )
    conn.execute(
        "INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            1,
            "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
            "https://example.com/kacey",
            "Saving Country Music",
            "magazine",
            "2026-01-15T00:00:00Z",
            80,
            "Kacey Musgraves",
            "country",
            "country",
        ),
    )
    conn.commit()
    conn.close()

    tags_path = tmp_path / "tags.yaml"
    tags_path.write_text("tags: []\n", encoding="utf-8")

    template_path = tmp_path / "issue.html.j2"
    template_path.write_text(_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    content_dir = tmp_path / "content"
    dist_dir = tmp_path / "dist"

    build_issue(
        db_path=db_path,
        issue_date="2026-01-15",
        lang="en",
        limit=10,
        min_score=30,
        draft=True,
        template_path=template_path,
        tags_path=tags_path,
        content_dir=content_dir,
        dist_dir=dist_dir,
        base_path="",
        with_cover=False,
    )

    data = json.loads((content_dir / "2026-01-15.en.json").read_text(encoding="utf-8"))
    item = data["items"][0]

    assert item["signal_type"] == "industry"
    assert "artist_match" in item["field_evidence"]
    assert "industry_signal" in item["field_evidence"]
    assert "Artist match" in item["field_evidence_label"]
    assert item["editorial_angle"] == "Industry / brand context around a coma.fm-field artist."


# ---------------------------------------------------------------------------
# Stage 26E-A — Editorial Sequencing Helpers
# ---------------------------------------------------------------------------

def test_editorial_sequence_rank_uses_signal_type():
    from scripts.build_issue import editorial_sequence_rank

    assert editorial_sequence_rank({"signal_type": "review"}) < editorial_sequence_rank({"signal_type": "culture"})
    assert editorial_sequence_rank({"signal_type": "culture"}) < editorial_sequence_rank({"signal_type": "industry"})


def test_editorial_sequence_rank_classifies_when_signal_type_missing():
    from scripts.build_issue import editorial_sequence_rank

    review_item = {"title": "ALBUM REVIEW: A record from the field", "score": 40}
    culture_item = {"title": "Paul McCartney says this pop star has a similar level of fame", "score": 100}

    assert editorial_sequence_rank(review_item) < editorial_sequence_rank(culture_item)


def test_sequence_editorial_items_puts_review_before_higher_scored_culture():
    from scripts.build_issue import sequence_editorial_items

    items = [
        {"title": "Culture item", "signal_type": "culture", "score": 100},
        {"title": "Review item", "signal_type": "review", "score": 65},
    ]

    ordered = sequence_editorial_items(items)

    assert [item["title"] for item in ordered] == ["Review item", "Culture item"]


def test_sequence_editorial_items_keeps_industry_context_late():
    from scripts.build_issue import sequence_editorial_items

    items = [
        {"title": "Industry item", "signal_type": "industry", "score": 100},
        {"title": "Radar signal", "signal_type": "signal", "score": 60},
        {"title": "Release item", "signal_type": "release", "score": 50},
    ]

    ordered = sequence_editorial_items(items)

    assert [item["title"] for item in ordered] == ["Release item", "Radar signal", "Industry item"]


def test_sequence_editorial_items_is_stable_for_same_rank_and_score():
    from scripts.build_issue import sequence_editorial_items

    items = [
        {"title": "First review", "signal_type": "review", "score": 80},
        {"title": "Second review", "signal_type": "review", "score": 80},
    ]

    ordered = sequence_editorial_items(items)

    assert [item["title"] for item in ordered] == ["First review", "Second review"]


# ---------------------------------------------------------------------------
# Stage 26E-B — Editorial Sequencing Integration
# ---------------------------------------------------------------------------

def test_build_issue_json_uses_editorial_sequence_order(tmp_path):
    import sqlite3
    from scripts.build_issue import build_issue

    db_path = tmp_path / "radar.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE items ("
        "id INTEGER, title TEXT, url TEXT, source_name TEXT, source_type TEXT, "
        "published_at TEXT, score INTEGER, matched_artists TEXT, matched_tags TEXT, matched_genres TEXT"
        ")"
    )

    rows = [
        (
            1,
            "Paul McCartney Says This Pop Star Has a Similar Level of Fame",
            "https://example.com/culture",
            "American Songwriter",
            "magazine",
            "2026-01-15T00:00:00Z",
            100,
            "Paul McCartney",
            "",
            "",
        ),
        (
            2,
            "Album Review – 49 Winchester’s Change Of Plans",
            "https://example.com/review",
            "Saving Country Music",
            "magazine",
            "2026-01-15T00:00:00Z",
            65,
            "49 Winchester",
            "country",
            "country",
        ),
        (
            3,
            "Why The New Kacey Musgraves Wal-Mart Partnership Feels Off Brand",
            "https://example.com/industry",
            "Saving Country Music",
            "magazine",
            "2026-01-15T00:00:00Z",
            90,
            "Kacey Musgraves",
            "country",
            "country",
        ),
    ]

    conn.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()

    tags_path = tmp_path / "tags.yaml"
    tags_path.write_text("tags: []\n", encoding="utf-8")

    template_path = tmp_path / "issue.html.j2"
    template_path.write_text(_TEMPLATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

    content_dir = tmp_path / "content"
    dist_dir = tmp_path / "dist"

    build_issue(
        db_path=db_path,
        issue_date="2026-01-15",
        lang="en",
        limit=3,
        min_score=30,
        draft=True,
        template_path=template_path,
        tags_path=tags_path,
        content_dir=content_dir,
        dist_dir=dist_dir,
        base_path="",
        with_cover=False,
        max_per_source=3,
    )

    data = json.loads((content_dir / "2026-01-15.en.json").read_text(encoding="utf-8"))
    titles = [item["title"] for item in data["items"]]
    signal_types = [item["signal_type"] for item in data["items"]]

    assert signal_types == ["review", "culture", "industry"]
    assert titles[0].startswith("Album Review")


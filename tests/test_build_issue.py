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

    summary = _run_build(tmp_path, db_path=db_path, lang="en", limit=3)

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

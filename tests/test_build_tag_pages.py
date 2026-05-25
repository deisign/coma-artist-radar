import csv
import json
from pathlib import Path

import pytest

from scripts.build_tag_pages import (
    build_tag_index,
    build_tag_pages,
    load_issue_jsons,
    load_tags,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"
_TAG_TEMPLATE = _REPO_ROOT / "templates" / "tag_page.html.j2"
_INDEX_TEMPLATE = _REPO_ROOT / "templates" / "tags_index.html.j2"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ISSUE_EN = {
    "issue_date": "2026-01-15",
    "lang": "en",
    "draft": True,
    "generated_at": "2026-01-15T00:00:00Z",
    "min_score": 30,
    "total_items": 2,
    "items": [
        {
            "id": 1,
            "title": "Surf Article",
            "url": "https://example.com/surf",
            "source_name": "Test Source",
            "published_at": "2026-01-14",
            "score": 75,
            "matched_artists": "The Ventures",
            "matched_tags": "surf, instrumental_surf",
            "matched_genres": "surf",
        },
        {
            "id": 2,
            "title": "Country Item",
            "url": "https://example.com/country",
            "source_name": "Test Source 2",
            "published_at": "2026-01-13",
            "score": 60,
            "matched_artists": "",
            "matched_tags": "country, unknown_genre_xyz",
            "matched_genres": "country",
        },
    ],
}

_ISSUE_UK = {**_ISSUE_EN, "lang": "uk"}


def _write_fixtures(tmp_path: Path, langs: list[str] | None = None) -> Path:
    content_dir = tmp_path / "content" / "issues"
    content_dir.mkdir(parents=True, exist_ok=True)
    for lng in (langs or ["en", "uk"]):
        fixture = {**_ISSUE_EN, "lang": lng}
        (content_dir / f"2026-01-15.{lng}.json").write_text(
            json.dumps(fixture, ensure_ascii=False), encoding="utf-8"
        )
    return content_dir


def _run_build(tmp_path: Path, **kwargs) -> dict:
    return build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=kwargs.pop("content_dir", _write_fixtures(tmp_path)),
        dist_dir=tmp_path / "dist",
        report_path=tmp_path / "reports" / "tag_pages_report.csv",
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# load_tags
# ---------------------------------------------------------------------------

def test_load_tags_returns_list():
    tags = load_tags(_TAGS_PATH)
    assert isinstance(tags, list)
    assert len(tags) > 0


def test_load_tags_surf_present():
    tags = load_tags(_TAGS_PATH)
    ids = [t["id"] for t in tags]
    assert "surf" in ids


def test_load_tags_has_required_fields():
    tags = load_tags(_TAGS_PATH)
    for tag in tags:
        assert "id" in tag
        assert "slug" in tag
        assert "label" in tag
        assert "type" in tag


# ---------------------------------------------------------------------------
# load_issue_jsons
# ---------------------------------------------------------------------------

def test_load_issue_jsons_en(tmp_path):
    content_dir = _write_fixtures(tmp_path)
    issues = load_issue_jsons(content_dir, "en")
    assert len(issues) == 1
    assert issues[0]["lang"] == "en"


def test_load_issue_jsons_uk(tmp_path):
    content_dir = _write_fixtures(tmp_path)
    issues = load_issue_jsons(content_dir, "uk")
    assert len(issues) == 1
    assert issues[0]["lang"] == "uk"


def test_load_issue_jsons_empty_dir(tmp_path):
    content_dir = tmp_path / "empty"
    content_dir.mkdir()
    assert load_issue_jsons(content_dir, "en") == []


# ---------------------------------------------------------------------------
# build_tag_index
# ---------------------------------------------------------------------------

def test_build_tag_index_surf():
    issues = [_ISSUE_EN]
    index = build_tag_index(issues)
    assert "surf" in index
    assert len(index["surf"]) == 1
    assert index["surf"][0]["item"]["title"] == "Surf Article"


def test_build_tag_index_deduplicates():
    issue_a = {**_ISSUE_EN, "issue_date": "2026-01-10"}
    issue_b = {**_ISSUE_EN, "issue_date": "2026-01-15"}
    index = build_tag_index([issue_a, issue_b])
    assert len(index["surf"]) == 1


def test_build_tag_index_unknown_tag():
    issues = [_ISSUE_EN]
    index = build_tag_index(issues)
    assert "unknown_genre_xyz" in index


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

def test_creates_en_index_html(tmp_path):
    _run_build(tmp_path, lang="en")
    assert (tmp_path / "dist" / "en" / "tags" / "index.html").exists()


def test_creates_uk_index_html(tmp_path):
    _run_build(tmp_path, lang="uk")
    assert (tmp_path / "dist" / "uk" / "tags" / "index.html").exists()


def test_creates_both_index_pages_by_default(tmp_path):
    _run_build(tmp_path)
    assert (tmp_path / "dist" / "en" / "tags" / "index.html").exists()
    assert (tmp_path / "dist" / "uk" / "tags" / "index.html").exists()


def test_index_html_contains_genre_heading(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "Genres" in html


def test_uk_index_html_contains_ukrainian_heading(tmp_path):
    _run_build(tmp_path, lang="uk")
    html = (tmp_path / "dist" / "uk" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "Карта тегів" in html


# ---------------------------------------------------------------------------
# Individual tag pages
# ---------------------------------------------------------------------------

def test_creates_surf_tag_page(tmp_path):
    _run_build(tmp_path, lang="en")
    assert (tmp_path / "dist" / "en" / "tags" / "surf.html").exists()


def test_slug_from_tags_yaml(tmp_path):
    _run_build(tmp_path, lang="en")
    # dark_jazz has slug "dark-jazz" in tags.yaml
    assert (tmp_path / "dist" / "en" / "tags" / "dark-jazz.html").exists()


def test_surf_page_contains_item_title(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "surf.html").read_text(encoding="utf-8")
    assert "Surf Article" in html


def test_surf_page_contains_artist(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "surf.html").read_text(encoding="utf-8")
    assert "The Ventures" in html


def test_surf_page_has_issue_link(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "surf.html").read_text(encoding="utf-8")
    assert "/en/issues/2026-01-15.html" in html


# ---------------------------------------------------------------------------
# UK language specifics
# ---------------------------------------------------------------------------

def test_uk_uses_description_uk(tmp_path):
    _run_build(tmp_path, lang="uk")
    html = (tmp_path / "dist" / "uk" / "tags" / "surf.html").read_text(encoding="utf-8")
    # description_uk for surf contains Ukrainian text
    assert "Surf" in html
    assert "музика" in html or "ревербі" in html or "дороги" in html


def test_music_label_not_translated_in_uk(tmp_path):
    _run_build(tmp_path, lang="uk")
    html = (tmp_path / "dist" / "uk" / "tags" / "surf.html").read_text(encoding="utf-8")
    # Label "Surf" must appear as-is (not translated)
    assert "<h1>Surf</h1>" in html or ">Surf<" in html


def test_uk_tag_page_uses_uk_path(tmp_path):
    _run_build(tmp_path, lang="uk")
    html = (tmp_path / "dist" / "uk" / "tags" / "surf.html").read_text(encoding="utf-8")
    assert "/uk/tags/" in html


def test_uk_index_uses_ukrainian_type_label(tmp_path):
    _run_build(tmp_path, lang="uk")
    html = (tmp_path / "dist" / "uk" / "tags" / "index.html").read_text(encoding="utf-8")
    assert "Жанри" in html


# ---------------------------------------------------------------------------
# Related tags
# ---------------------------------------------------------------------------

def test_related_tags_are_links(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "surf.html").read_text(encoding="utf-8")
    # surf has related_tags: instrumental_surf, garage_surf, surf_revival
    assert 'href="/en/tags/instrumental-surf.html"' in html or \
           'href="/en/tags/instrumental_surf.html"' in html


def test_related_tags_have_labels(tmp_path):
    _run_build(tmp_path, lang="en")
    html = (tmp_path / "dist" / "en" / "tags" / "surf.html").read_text(encoding="utf-8")
    assert "class=\"related-tag\"" in html


# ---------------------------------------------------------------------------
# Unknown tag
# ---------------------------------------------------------------------------

def test_unknown_tag_does_not_crash(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    assert "unknown_genre_xyz" in summary["unknown_tags"]


def test_unknown_tag_in_report(tmp_path):
    report_path = tmp_path / "reports" / "tag_pages_report.csv"
    content_dir = _write_fixtures(tmp_path)
    build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        report_path=report_path,
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        lang="en",
    )
    rows = list(csv.DictReader(report_path.open(encoding="utf-8")))
    unknown_rows = [r for r in rows if r["tag_id"] == "unknown_genre_xyz"]
    assert len(unknown_rows) == 1
    assert unknown_rows[0]["status"] == "unknown_tag"


# ---------------------------------------------------------------------------
# --lang filter
# ---------------------------------------------------------------------------

def test_lang_en_creates_only_en(tmp_path):
    _run_build(tmp_path, lang="en")
    assert (tmp_path / "dist" / "en" / "tags" / "index.html").exists()
    assert not (tmp_path / "dist" / "uk" / "tags" / "index.html").exists()


def test_lang_uk_creates_only_uk(tmp_path):
    _run_build(tmp_path, lang="uk")
    assert (tmp_path / "dist" / "uk" / "tags" / "index.html").exists()
    assert not (tmp_path / "dist" / "en" / "tags" / "index.html").exists()


def test_summary_languages_field(tmp_path):
    summary = _run_build(tmp_path)
    assert summary["languages"] == ["en", "uk"]


def test_summary_lang_en_only(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    assert summary["languages"] == ["en"]


# ---------------------------------------------------------------------------
# --dry-run
# ---------------------------------------------------------------------------

def test_dry_run_no_html(tmp_path):
    _run_build(tmp_path, lang="en", dry_run=True)
    assert not (tmp_path / "dist").exists()


def test_dry_run_no_report(tmp_path):
    report_path = tmp_path / "reports" / "tag_pages_report.csv"
    content_dir = _write_fixtures(tmp_path)
    build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        report_path=report_path,
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        lang="en",
        dry_run=True,
    )
    assert not report_path.exists()


def test_dry_run_pages_written_zero(tmp_path):
    summary = _run_build(tmp_path, lang="en", dry_run=True)
    assert summary["pages_written"] == 0


# ---------------------------------------------------------------------------
# Report CSV
# ---------------------------------------------------------------------------

def test_report_csv_created(tmp_path):
    report_path = tmp_path / "reports" / "tag_pages_report.csv"
    content_dir = _write_fixtures(tmp_path)
    build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        report_path=report_path,
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        lang="en",
    )
    assert report_path.exists()


def test_report_csv_has_correct_columns(tmp_path):
    report_path = tmp_path / "reports" / "tag_pages_report.csv"
    content_dir = _write_fixtures(tmp_path)
    build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        report_path=report_path,
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        lang="en",
    )
    rows = list(csv.DictReader(report_path.open(encoding="utf-8")))
    assert len(rows) > 0
    for col in ("tag_id", "slug", "label", "type", "lang", "item_count", "page_path", "status", "error"):
        assert col in rows[0]


def test_report_surf_row(tmp_path):
    report_path = tmp_path / "reports" / "tag_pages_report.csv"
    content_dir = _write_fixtures(tmp_path)
    build_tag_pages(
        tags_path=_TAGS_PATH,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        report_path=report_path,
        tag_template_path=_TAG_TEMPLATE,
        index_template_path=_INDEX_TEMPLATE,
        lang="en",
    )
    rows = list(csv.DictReader(report_path.open(encoding="utf-8")))
    surf_rows = [r for r in rows if r["tag_id"] == "surf"]
    assert len(surf_rows) == 1
    assert surf_rows[0]["item_count"] == "1"
    assert surf_rows[0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_required_keys(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    for key in ("languages", "tags_total", "tags_with_items", "pages_written",
                "unknown_tags", "output_files"):
        assert key in summary, f"Missing key: {key}"


def test_summary_tags_total_matches_yaml(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    tags = load_tags(_TAGS_PATH)
    assert summary["tags_total"] == len(tags)


def test_summary_tags_with_items(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    # surf and instrumental_surf are in items; country is too
    assert summary["tags_with_items"] >= 3


def test_summary_output_files_nonempty(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    assert len(summary["output_files"]) > 0


def test_summary_pages_written_includes_index(tmp_path):
    summary = _run_build(tmp_path, lang="en")
    # At minimum: 66 tag pages + 1 index = 67
    assert summary["pages_written"] >= 67

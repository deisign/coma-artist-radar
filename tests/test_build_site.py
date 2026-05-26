import json
from pathlib import Path

import pytest

from scripts.build_site import build_site, load_content_issues

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATES_DIR = _REPO_ROOT / "templates"

_ISSUE_EN = {
    "issue_date": "2026-01-15",
    "lang": "en",
    "draft": False,
    "generated_at": "2026-01-15T00:00:00Z",
    "min_score": 30,
    "total_items": 5,
    "items": [],
}

_ISSUE_UK = {
    "issue_date": "2026-01-15",
    "lang": "uk",
    "draft": True,
    "generated_at": "2026-01-15T00:00:00Z",
    "min_score": 30,
    "total_items": 3,
    "items": [],
}


def _make_fixtures(tmp_path: Path) -> Path:
    content_dir = tmp_path / "content" / "issues"
    content_dir.mkdir(parents=True, exist_ok=True)
    (content_dir / "2026-01-15.en.json").write_text(
        json.dumps(_ISSUE_EN), encoding="utf-8"
    )
    (content_dir / "2026-01-15.uk.json").write_text(
        json.dumps(_ISSUE_UK), encoding="utf-8"
    )
    return content_dir


def _run(tmp_path: Path, **kwargs) -> dict:
    content_dir = kwargs.pop("content_dir", _make_fixtures(tmp_path))
    return build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_url=kwargs.pop("base_url", "https://radar.coma.fm"),
        base_path=kwargs.pop("base_path", ""),
        dry_run=kwargs.pop("dry_run", False),
    )


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------

def test_creates_root_index(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "index.html").exists()


def test_creates_en_index(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "en" / "index.html").exists()


def test_creates_uk_index(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "uk" / "index.html").exists()


def test_creates_en_archive(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "en" / "archive.html").exists()


def test_creates_uk_archive(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "uk" / "archive.html").exists()


def test_creates_robots_txt(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "robots.txt").exists()


def test_creates_sitemap_xml(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "sitemap.xml").exists()


def test_creates_feed_xml(tmp_path):
    _run(tmp_path)
    assert (tmp_path / "dist" / "feed.xml").exists()


# ---------------------------------------------------------------------------
# Content checks
# ---------------------------------------------------------------------------

def test_sitemap_contains_issue_url(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "/en/issues/2026-01-15.html" in content


def test_sitemap_contains_uk_issue_url(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "/uk/issues/2026-01-15.html" in content


def test_sitemap_contains_root_url(tmp_path):
    _run(tmp_path, base_url="https://example.com")
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://example.com/" in content


def test_robots_contains_sitemap_directive(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "robots.txt").read_text(encoding="utf-8")
    assert "Sitemap:" in content


def test_robots_contains_sitemap_url(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "robots.txt").read_text(encoding="utf-8")
    assert "https://radar.coma.fm/sitemap.xml" in content


def test_robots_has_disallow_reports(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "robots.txt").read_text(encoding="utf-8")
    assert "Disallow: /reports/" in content


def test_en_index_shows_issue_date(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "2026-01-15" in content


def test_en_index_has_lang_attribute(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert 'lang="en"' in content


def test_uk_index_has_lang_attribute(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "uk" / "index.html").read_text(encoding="utf-8")
    assert 'lang="uk"' in content


def test_uk_index_has_ukrainian_title(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "uk" / "index.html").read_text(encoding="utf-8")
    assert "Радар" in content


def test_uk_index_has_ukrainian_navigation(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "uk" / "index.html").read_text(encoding="utf-8")
    assert "Останні" in content


def test_en_archive_contains_issue_link(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "/en/issues/2026-01-15.html" in content


def test_en_archive_shows_item_count(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "5" in content


def test_uk_archive_has_ukrainian_heading(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "uk" / "archive.html").read_text(encoding="utf-8")
    assert "Архів" in content


def test_feed_contains_issue_date(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "feed.xml").read_text(encoding="utf-8")
    assert "2026-01-15" in content


def test_feed_has_rss_element(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "feed.xml").read_text(encoding="utf-8")
    assert "<rss" in content


def test_feed_has_channel_title(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "feed.xml").read_text(encoding="utf-8")
    assert "coma.fm Radar" in content


def test_root_index_has_both_lang_links(tmp_path):
    _run(tmp_path)
    content = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    assert "/en/index.html" in content
    assert "/uk/index.html" in content


def test_sitemap_includes_tag_pages_if_present(tmp_path):
    _make_fixtures(tmp_path)
    tags_dir = tmp_path / "dist" / "en" / "tags"
    tags_dir.mkdir(parents=True)
    (tags_dir / "surf.html").write_text("<html></html>", encoding="utf-8")
    build_site(
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_url="https://radar.coma.fm",
    )
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "/en/tags/surf.html" in content


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

def test_dry_run_no_files(tmp_path):
    _run(tmp_path, dry_run=True)
    assert not (tmp_path / "dist").exists()


def test_dry_run_pages_written_zero(tmp_path):
    summary = _run(tmp_path, dry_run=True)
    assert summary["pages_written"] == 0


def test_dry_run_output_files_empty(tmp_path):
    summary = _run(tmp_path, dry_run=True)
    assert summary["output_files"] == []


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_output_files(tmp_path):
    summary = _run(tmp_path)
    assert "output_files" in summary
    assert len(summary["output_files"]) > 0


def test_summary_has_required_keys(tmp_path):
    summary = _run(tmp_path)
    for key in ("issues_total", "pages_written", "output_files", "base_url", "dry_run"):
        assert key in summary


def test_summary_issues_total(tmp_path):
    summary = _run(tmp_path)
    assert summary["issues_total"] == 1


def test_summary_base_url(tmp_path):
    summary = _run(tmp_path, base_url="https://example.com")
    assert summary["base_url"] == "https://example.com"


def test_summary_dry_run_flag(tmp_path):
    summary = _run(tmp_path, dry_run=True)
    assert summary["dry_run"] is True


def test_summary_pages_written(tmp_path):
    summary = _run(tmp_path)
    # root + en/index + uk/index + en/archive + uk/archive + robots + sitemap + feed = 8
    assert summary["pages_written"] == 8


def test_summary_output_files_count(tmp_path):
    summary = _run(tmp_path)
    assert len(summary["output_files"]) == 8


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_issues_renders_without_error(tmp_path):
    content_dir = tmp_path / "empty_issues"
    content_dir.mkdir(parents=True)
    summary = build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_url="https://radar.coma.fm",
    )
    assert (tmp_path / "dist" / "index.html").exists()
    assert summary["issues_total"] == 0


def test_no_issues_pages_written_still_8(tmp_path):
    content_dir = tmp_path / "empty_issues"
    content_dir.mkdir(parents=True)
    summary = build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_url="https://radar.coma.fm",
    )
    assert summary["pages_written"] == 8


def test_load_content_issues_empty_dir(tmp_path):
    content_dir = tmp_path / "empty"
    content_dir.mkdir()
    result = load_content_issues(content_dir)
    assert result == {"en": [], "uk": []}


def test_load_content_issues_sorted_newest_first(tmp_path):
    content_dir = tmp_path / "issues"
    content_dir.mkdir()
    for date in ("2026-01-10", "2026-01-20", "2026-01-15"):
        data = {**_ISSUE_EN, "issue_date": date}
        (content_dir / f"{date}.en.json").write_text(json.dumps(data), encoding="utf-8")
    result = load_content_issues(content_dir)
    dates = [iss["issue_date"] for iss in result["en"]]
    assert dates == ["2026-01-20", "2026-01-15", "2026-01-10"]


def test_load_content_issues_ignores_bad_files(tmp_path):
    content_dir = tmp_path / "issues"
    content_dir.mkdir()
    (content_dir / "2026-01-15.en.json").write_text(json.dumps(_ISSUE_EN), encoding="utf-8")
    (content_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
    (content_dir / "broken.en.json").write_text("{not json}", encoding="utf-8")
    result = load_content_issues(content_dir)
    assert len(result["en"]) == 1


def test_multiple_issues_in_sitemap(tmp_path):
    content_dir = tmp_path / "content" / "issues"
    content_dir.mkdir(parents=True)
    for date in ("2026-01-15", "2026-01-22"):
        data = {**_ISSUE_EN, "issue_date": date}
        (content_dir / f"{date}.en.json").write_text(json.dumps(data), encoding="utf-8")
    build_site(
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        base_url="https://radar.coma.fm",
    )
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "/en/issues/2026-01-15.html" in content
    assert "/en/issues/2026-01-22.html" in content


# ---------------------------------------------------------------------------
# Stage 12: base_path support
# ---------------------------------------------------------------------------

_GITHUB_BASE_URL = "https://deisign.github.io/coma-artist-radar"
_GITHUB_BASE_PATH = "/coma-artist-radar"


def test_project_base_path_in_en_index(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/uk/index.html" in content


def test_project_base_path_in_uk_index(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "uk" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/en/index.html" in content


def test_project_base_path_in_root_index(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/en/index.html" in content
    assert "/coma-artist-radar/uk/index.html" in content


def test_custom_domain_no_base_path_in_index(tmp_path):
    _run(tmp_path, base_path="")
    content = (tmp_path / "dist" / "en" / "index.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar" not in content


def test_project_sitemap_contains_github_pages_url(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "sitemap.xml").read_text(encoding="utf-8")
    assert "https://deisign.github.io/coma-artist-radar/en/index.html" in content


def test_root_index_no_bare_path_in_project_mode(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "index.html").read_text(encoding="utf-8")
    assert 'href="/uk/index.html"' not in content
    assert 'href="/en/index.html"' not in content


def test_project_archive_has_base_path(tmp_path):
    _run(tmp_path, base_url=_GITHUB_BASE_URL, base_path=_GITHUB_BASE_PATH)
    content = (tmp_path / "dist" / "en" / "archive.html").read_text(encoding="utf-8")
    assert "/coma-artist-radar/uk/archive.html" in content


def test_base_path_normalization_no_slash(tmp_path):
    summary = _run(tmp_path, base_path="coma-artist-radar")
    assert summary["base_path"] == "/coma-artist-radar"


def test_base_path_normalization_trailing_slash(tmp_path):
    summary = _run(tmp_path, base_path="/coma-artist-radar/")
    assert summary["base_path"] == "/coma-artist-radar"


def test_base_path_empty_string(tmp_path):
    summary = _run(tmp_path, base_path="")
    assert summary["base_path"] == ""


def test_base_path_root_slash(tmp_path):
    summary = _run(tmp_path, base_path="/")
    assert summary["base_path"] == ""


def test_summary_has_base_path_key(tmp_path):
    summary = _run(tmp_path, base_path=_GITHUB_BASE_PATH)
    assert "base_path" in summary
    assert summary["base_path"] == _GITHUB_BASE_PATH

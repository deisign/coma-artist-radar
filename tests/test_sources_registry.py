import csv
from pathlib import Path

import pytest

from scripts.validate_sources import (
    DEFAULT_SOURCES,
    check_source,
    discover_feed_from_html,
    load_sources,
    validate_all,
    validate_source_structure,
    write_report,
)


# ---------------------------------------------------------------------------
# Registry loading
# ---------------------------------------------------------------------------

def test_sources_yaml_loads():
    sources = load_sources()
    assert isinstance(sources, list)
    assert len(sources) > 0


def test_minimum_source_count():
    sources = load_sources()
    assert len(sources) >= 25


def test_all_sources_have_required_fields():
    sources = load_sources()
    required = {"id", "name", "site_url", "source_type", "priority", "active"}
    for source in sources:
        missing = required - set(source.keys())
        assert not missing, f"Source {source.get('id', '?')} missing fields: {missing}"


def test_all_sources_pass_structural_validation():
    sources = load_sources()
    for source in sources:
        ok, err = validate_source_structure(source)
        assert ok, f"Source {source.get('id', '?')} failed: {err}"


# ---------------------------------------------------------------------------
# Structural validation
# ---------------------------------------------------------------------------

def test_invalid_priority_caught():
    source = {
        "id": "test_source",
        "name": "Test",
        "site_url": "https://example.com",
        "source_type": "blog",
        "priority": "urgent",
        "active": True,
    }
    ok, err = validate_source_structure(source)
    assert not ok
    assert "priority" in err


def test_invalid_source_type_caught():
    source = {
        "id": "test_source",
        "name": "Test",
        "site_url": "https://example.com",
        "source_type": "twitter",
        "priority": "high",
        "active": True,
    }
    ok, err = validate_source_structure(source)
    assert not ok
    assert "source_type" in err


def test_invalid_paywall_caught():
    source = {
        "id": "test_source",
        "name": "Test",
        "site_url": "https://example.com",
        "source_type": "blog",
        "priority": "medium",
        "active": True,
        "paywall": "maybe",
    }
    ok, err = validate_source_structure(source)
    assert not ok
    assert "paywall" in err


def test_invalid_site_url_caught():
    source = {
        "id": "test_source",
        "name": "Test",
        "site_url": "ftp://example.com",
        "source_type": "blog",
        "priority": "medium",
        "active": True,
    }
    ok, err = validate_source_structure(source)
    assert not ok
    assert "site_url" in err


def test_missing_required_field_caught():
    source = {
        "name": "Test",
        "site_url": "https://example.com",
        "source_type": "blog",
        "priority": "medium",
    }
    ok, err = validate_source_structure(source)
    assert not ok
    assert "Missing" in err


def test_valid_source_passes():
    source = {
        "id": "test_ok",
        "name": "Good Source",
        "site_url": "https://example.com",
        "source_type": "magazine",
        "priority": "high",
        "active": True,
        "paywall": "false",
    }
    ok, err = validate_source_structure(source)
    assert ok
    assert err == ""


# ---------------------------------------------------------------------------
# Offline mode — no HTTP
# ---------------------------------------------------------------------------

def test_offline_mode_does_not_call_http(monkeypatch):
    called = []

    def _fake_probe(url, timeout=12):
        called.append(url)
        return 200, b""

    monkeypatch.setattr("scripts.validate_sources._http_probe", _fake_probe)

    source = {
        "id": "test_offline",
        "name": "Test",
        "site_url": "https://example.com",
        "feed_url": "https://example.com/feed/",
        "source_type": "blog",
        "priority": "medium",
        "active": True,
    }
    check_source(source, offline=True)
    assert called == [], "offline mode must not call _http_probe"


def test_offline_mode_row_has_empty_network_fields():
    source = {
        "id": "test_offline2",
        "name": "Test 2",
        "site_url": "https://example.com",
        "feed_url": None,
        "source_type": "blog",
        "priority": "low",
        "active": True,
    }
    row = check_source(source, offline=True)
    assert row["site_status"] == ""
    assert row["feed_status"] == ""
    assert row["feed_found"] == ""
    assert row["structural_ok"] == "true"


# ---------------------------------------------------------------------------
# RSS/Atom autodiscovery on local HTML
# ---------------------------------------------------------------------------

_HTML_WITH_RSS = b"""<!DOCTYPE html>
<html>
<head>
  <title>Test</title>
  <link rel="alternate" type="application/rss+xml" title="RSS" href="/feed/rss.xml" />
</head>
<body></body>
</html>"""

_HTML_WITH_ATOM = b"""<!DOCTYPE html>
<html>
<head>
  <link rel="alternate" type="application/atom+xml" title="Atom" href="https://example.com/atom.xml" />
</head>
</html>"""

_HTML_WITHOUT_FEED = b"""<!DOCTYPE html>
<html><head><title>No feed</title></head><body></body></html>"""


def test_discover_feed_from_rss_link():
    result = discover_feed_from_html(_HTML_WITH_RSS, "https://example.com")
    assert result == "https://example.com/feed/rss.xml"


def test_discover_feed_from_atom_link():
    result = discover_feed_from_html(_HTML_WITH_ATOM, "https://example.com")
    assert result == "https://example.com/atom.xml"


def test_discover_feed_returns_none_when_absent():
    result = discover_feed_from_html(_HTML_WITHOUT_FEED, "https://example.com")
    assert result is None


def test_discover_feed_relative_url_resolved():
    html = b'<link rel="alternate" type="application/rss+xml" href="rss.xml" />'
    result = discover_feed_from_html(html, "https://myblog.com/")
    assert result == "https://myblog.com/rss.xml"


# ---------------------------------------------------------------------------
# Report CSV written in offline mode
# ---------------------------------------------------------------------------

def test_report_csv_created_offline(tmp_path):
    sources = load_sources()
    rows = validate_all(sources, offline=True)
    report_path = tmp_path / "sources_report.csv"
    write_report(rows, report_path)

    assert report_path.exists()
    with report_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        written = list(reader)
    assert len(written) == len(sources)


def test_report_csv_has_correct_columns(tmp_path):
    sources = load_sources()[:3]
    rows = validate_all(sources, offline=True)
    report_path = tmp_path / "report.csv"
    write_report(rows, report_path)

    with report_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
    for col in ("id", "name", "site_url", "structural_ok", "site_status", "feed_found"):
        assert col in fieldnames, f"Missing column: {col}"


def test_report_offline_all_structural_ok(tmp_path):
    sources = load_sources()
    rows = validate_all(sources, offline=True)
    report_path = tmp_path / "report.csv"
    write_report(rows, report_path)

    with report_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            assert row["structural_ok"] == "true", (
                f"Source {row['id']} failed structural validation"
            )

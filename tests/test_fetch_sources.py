import csv
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from scripts.fetch_sources import (
    REPORT_FIELDS,
    fetch_and_store,
    load_sources_yaml,
    parse_feed_xml,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_RSS_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test RSS Feed</title>
    <link>https://example.com</link>
    <item>
      <title>First Item</title>
      <link>https://example.com/item/1</link>
      <pubDate>Mon, 01 Jan 2024 12:00:00 +0000</pubDate>
      <description>First item description.</description>
    </item>
    <item>
      <title>Second Item</title>
      <link>https://example.com/item/2</link>
      <pubDate>Tue, 02 Jan 2024 12:00:00 +0000</pubDate>
      <description>Second item description.</description>
    </item>
  </channel>
</rss>"""

_ATOM_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <id>https://example.com/atom</id>
  <entry>
    <title>Atom Entry One</title>
    <link rel="alternate" href="https://example.com/atom/1"/>
    <id>https://example.com/atom/1</id>
    <published>2024-01-01T12:00:00Z</published>
    <summary>Entry summary.</summary>
  </entry>
  <entry>
    <title>Atom Entry Two</title>
    <link rel="alternate" href="https://example.com/atom/2"/>
    <id>https://example.com/atom/2</id>
    <updated>2024-01-02T12:00:00Z</updated>
    <summary>Second entry.</summary>
  </entry>
</feed>"""

_BROKEN_XML = b"""<rss version="2.0"><channel><item><title>Unclosed"""


def _make_source(
    sid: str = "test_src",
    feed_url: str = "https://example.com/feed",
    active: bool = True,
) -> dict:
    return {
        "id": sid,
        "name": f"Test {sid}",
        "site_url": "https://example.com",
        "feed_url": feed_url,
        "source_type": "blog",
        "priority": "high",
        "active": active,
        "paywall": "false",
    }


def _item_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    (n,) = conn.execute("SELECT COUNT(*) FROM items").fetchone()
    conn.close()
    return n


def _seen_url_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    (n,) = conn.execute("SELECT COUNT(*) FROM seen_urls").fetchone()
    conn.close()
    return n


# ---------------------------------------------------------------------------
# parse_feed_xml — pure XML tests (no network, no DB)
# ---------------------------------------------------------------------------

def test_parse_rss_returns_two_items():
    items = parse_feed_xml(_RSS_FIXTURE)
    assert len(items) == 2


def test_parse_rss_item_fields():
    items = parse_feed_xml(_RSS_FIXTURE)
    assert items[0]["title"] == "First Item"
    assert items[0]["url"] == "https://example.com/item/1"
    assert items[0]["published_at"] is not None
    assert "2024" in items[0]["published_at"]


def test_parse_atom_returns_two_items():
    items = parse_feed_xml(_ATOM_FIXTURE)
    assert len(items) == 2


def test_parse_atom_item_fields():
    items = parse_feed_xml(_ATOM_FIXTURE)
    assert items[0]["title"] == "Atom Entry One"
    assert items[0]["url"] == "https://example.com/atom/1"
    assert items[0]["published_at"] == "2024-01-01T12:00:00Z"


def test_parse_broken_xml_raises():
    with pytest.raises(ET.ParseError):
        parse_feed_xml(_BROKEN_XML)


# ---------------------------------------------------------------------------
# fetch_and_store — RSS and Atom insertion
# ---------------------------------------------------------------------------

def test_rss_items_inserted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, report_path=tmp_path / "r.csv"
    )
    assert summary["inserted"] == 2
    assert _item_count(db_path) == 2


def test_atom_items_inserted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _ATOM_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, report_path=tmp_path / "r.csv"
    )
    assert summary["inserted"] == 2
    assert _item_count(db_path) == 2


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_url_not_inserted_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    rp = tmp_path / "r.csv"

    s1 = fetch_and_store([_make_source()], db_path, report_path=rp)
    s2 = fetch_and_store([_make_source()], db_path, report_path=rp)

    assert s1["inserted"] == 2
    assert s2["inserted"] == 0
    assert s2["skipped_duplicate"] == 2
    assert _item_count(db_path) == 2


# ---------------------------------------------------------------------------
# seen_urls
# ---------------------------------------------------------------------------

def test_seen_urls_updated_not_duplicated(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    rp = tmp_path / "r.csv"

    fetch_and_store([_make_source()], db_path, report_path=rp)
    fetch_and_store([_make_source()], db_path, report_path=rp)

    # 2 unique URLs → 2 rows, not 4
    assert _seen_url_count(db_path) == 2


def test_seen_urls_populated_after_first_fetch(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _ATOM_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    fetch_and_store([_make_source()], db_path, report_path=tmp_path / "r.csv")
    assert _seen_url_count(db_path) == 2


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write_to_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, dry_run=True, report_path=tmp_path / "r.csv"
    )
    assert summary["dry_run"] is True
    assert summary["items_found"] == 2
    # DB must not be created (or must have no items if it already existed)
    if db_path.exists():
        assert _item_count(db_path) == 0
    else:
        assert True


def test_dry_run_summary_inserted_equals_items_found(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _ATOM_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, dry_run=True, report_path=tmp_path / "r.csv"
    )
    assert summary["inserted"] == summary["items_found"]


# ---------------------------------------------------------------------------
# Error handling — broken XML
# ---------------------------------------------------------------------------

def test_broken_xml_increments_errors_does_not_crash(tmp_path, monkeypatch):
    def _mock(url, timeout=15):
        if "broken" in url:
            return 200, _BROKEN_XML
        return 200, _RSS_FIXTURE

    monkeypatch.setattr("scripts.fetch_sources._fetch_feed", _mock)

    sources = [
        _make_source("valid_src", "https://example.com/valid"),
        _make_source("broken_src", "https://broken.example.com/feed"),
    ]
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(sources, db_path, report_path=tmp_path / "r.csv")

    assert summary["errors"] == 1
    assert summary["inserted"] == 2
    assert _item_count(db_path) == 2


def test_network_error_increments_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (0, b""),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, report_path=tmp_path / "r.csv"
    )
    assert summary["errors"] == 1
    assert summary["inserted"] == 0


# ---------------------------------------------------------------------------
# Limit
# ---------------------------------------------------------------------------

def test_limit_restricts_sources_checked(tmp_path, monkeypatch):
    calls: list[str] = []

    def _mock(url, timeout=15):
        calls.append(url)
        return 200, _RSS_FIXTURE

    monkeypatch.setattr("scripts.fetch_sources._fetch_feed", _mock)

    sources = [
        _make_source("a", "https://a.example.com/feed"),
        _make_source("b", "https://b.example.com/feed"),
        _make_source("c", "https://c.example.com/feed"),
    ]
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(sources, db_path, limit=2, report_path=tmp_path / "r.csv")

    assert summary["sources_checked"] == 2
    assert len(calls) == 2


def test_limit_zero_checks_nothing(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: calls.append(url) or (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, limit=0, report_path=tmp_path / "r.csv"
    )
    assert summary["sources_checked"] == 0
    assert calls == []


# ---------------------------------------------------------------------------
# Inactive / no-feed sources
# ---------------------------------------------------------------------------

def test_inactive_source_skipped(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: calls.append(url) or (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source(active=False)], db_path, report_path=tmp_path / "r.csv"
    )
    assert summary["sources_with_feed"] == 0
    assert calls == []


def test_source_without_feed_url_skipped(tmp_path, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: calls.append(url) or (200, _RSS_FIXTURE),
    )
    source = {
        "id": "no_feed",
        "name": "No Feed",
        "site_url": "https://example.com",
        "feed_url": None,
        "source_type": "label",
        "priority": "high",
        "active": True,
    }
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store([source], db_path, report_path=tmp_path / "r.csv")
    assert summary["sources_with_feed"] == 0
    assert calls == []


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_all_required_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()], db_path, report_path=tmp_path / "r.csv"
    )
    for key in (
        "sources_total", "sources_with_feed", "sources_checked",
        "items_found", "inserted", "skipped_duplicate", "errors", "dry_run",
    ):
        assert key in summary, f"Missing key: {key}"


def test_sources_total_counts_all(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    sources = [
        _make_source("a", "https://a.example.com/feed"),
        _make_source("b", active=False),      # inactive, no feed_url matters
    ]
    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(sources, db_path, report_path=tmp_path / "r.csv")
    assert summary["sources_total"] == 2
    assert summary["sources_with_feed"] == 1


# ---------------------------------------------------------------------------
# Report CSV
# ---------------------------------------------------------------------------

def test_report_csv_created(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    report_path = tmp_path / "report.csv"

    fetch_and_store([_make_source()], db_path, report_path=report_path)

    assert report_path.exists()
    with report_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 1
    assert rows[0]["source_id"] == "test_src"
    assert rows[0]["inserted"] == "2"


def test_report_csv_has_all_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "scripts.fetch_sources._fetch_feed",
        lambda url, timeout=15: (200, _RSS_FIXTURE),
    )
    db_path = tmp_path / "test.sqlite"
    report_path = tmp_path / "report.csv"

    fetch_and_store([_make_source()], db_path, report_path=report_path)

    with report_path.open(encoding="utf-8") as fh:
        fieldnames = csv.DictReader(fh).fieldnames or []
    for col in REPORT_FIELDS:
        assert col in fieldnames, f"Missing column: {col}"


# ---------------------------------------------------------------------------
# offline-fixture path
# ---------------------------------------------------------------------------

def test_offline_fixture_used_instead_of_network(tmp_path):
    fixture_path = tmp_path / "feed.xml"
    fixture_path.write_bytes(_RSS_FIXTURE)

    db_path = tmp_path / "test.sqlite"
    # No monkeypatching — real _fetch_feed is never called
    summary = fetch_and_store(
        [_make_source()],
        db_path,
        offline_fixture=fixture_path,
        report_path=tmp_path / "r.csv",
    )
    assert summary["inserted"] == 2
    assert _item_count(db_path) == 2


def test_offline_atom_fixture(tmp_path):
    fixture_path = tmp_path / "atom.xml"
    fixture_path.write_bytes(_ATOM_FIXTURE)

    db_path = tmp_path / "test.sqlite"
    summary = fetch_and_store(
        [_make_source()],
        db_path,
        offline_fixture=fixture_path,
        report_path=tmp_path / "r.csv",
    )
    assert summary["inserted"] == 2

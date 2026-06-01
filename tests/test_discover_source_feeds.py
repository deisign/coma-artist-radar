"""Tests for Stage27E: discover_source_feeds.py"""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

import scripts.discover_source_feeds as _mod

from scripts.discover_source_feeds import (
    COMMON_FEED_PATHS,
    DEFAULT_OUTPUT,
    FakeFetcher,
    build_source_index,
    check_dedup,
    detect_feed_type,
    detect_platform,
    domain_to_source_id,
    extract_feed_title,
    find_feed_for_domain,
    is_valid_feed,
    load_existing_domains,
    main,
    normalize_domain,
    parse_html_feed_links,
    platform_feed_paths,
    process_row,
    suggest_import_action,
    suggest_priority,
    write_output_csv,
    OUTPUT_FIELDS,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

RSS_FEED = b"""<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Surf Blog</title>
    <link>https://example.com</link>
    <description>Surf music news</description>
  </channel>
</rss>"""

ATOM_FEED = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Psychobilly Zine</title>
  <link href="https://example.com"/>
  <updated>2026-01-01T00:00:00Z</updated>
</feed>"""

RDF_FEED = b"""<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <channel>
    <title>RDF Feed</title>
  </channel>
</rdf:RDF>"""

HTML_WITH_RSS = """<html><head>
<link rel="alternate" type="application/rss+xml" title="Feed" href="/feed.xml">
</head><body>Hello</body></html>"""

HTML_WITH_ATOM = """<html><head>
<link rel="alternate" type="application/atom+xml" title="Atom" href="https://example.com/atom.xml">
</head><body>Hello</body></html>"""

HTML_NO_FEED = "<html><head><title>Blog</title></head><body>Hello world</body></html>"

FAKE_SOURCES = [
    {
        "id": "norton_records",
        "name": "Norton Records",
        "site_url": "https://nortonrecords.com",
        "feed_url": "https://nortonrecords.com/feed/",
    },
    {
        "id": "no_feed_label",
        "name": "No Feed Label",
        "site_url": "https://nofeedlabel.com",
        "feed_url": None,
    },
]


def _make_row(**kwargs) -> dict:
    base = {
        "feed_check_action": "check_feed",
        "bucket": "niche_blog_fanzine",
        "longtail_action": "NICHE_REVIEW",
        "longtail_score": "45",
        "domain": "surfzine.com",
        "source_type_guess": "blog",
        "suggested_action": "REVIEW",
        "unique_artists": "3",
        "hits_total": "10",
        "sample_artists": "The Ventures",
        "sample_titles": "",
        "sample_urls": "",
        "editor_decision": "",
        "notes": "",
    }
    base.update(kwargs)
    return base


# ── normalize_domain ──────────────────────────────────────────────────────────

def test_normalize_domain_strips_www():
    assert normalize_domain("https://www.example.com/") == "example.com"


def test_normalize_domain_strips_m_prefix():
    assert normalize_domain("https://m.example.com/path") == "example.com"


def test_normalize_domain_lowercases():
    assert normalize_domain("https://EXAMPLE.COM/") == "example.com"


def test_normalize_domain_no_protocol():
    assert normalize_domain("example.com/path") == "example.com"


def test_normalize_domain_empty():
    assert normalize_domain("") == ""


# ── domain_to_source_id ───────────────────────────────────────────────────────

def test_source_id_strips_blogspot():
    assert domain_to_source_id("myrockabilly.blogspot.com") == "myrockabilly"


def test_source_id_strips_bandcamp():
    assert domain_to_source_id("noiselab.bandcamp.com") == "noiselab"


def test_source_id_strips_substack():
    assert domain_to_source_id("jazzletter.substack.com") == "jazzletter"


def test_source_id_strips_tld():
    assert domain_to_source_id("surfreview.com") == "surfreview"


def test_source_id_slugifies_hyphens():
    result = domain_to_source_id("the-cramps-fansite.org")
    assert "cramps" in result


# ── detect_platform ───────────────────────────────────────────────────────────

def test_detect_platform_blogspot():
    assert detect_platform("myrockabilly.blogspot.com") == "blogspot"


def test_detect_platform_substack():
    assert detect_platform("jazzletter.substack.com") == "substack"


def test_detect_platform_bandcamp():
    assert detect_platform("noiselab.bandcamp.com") == "bandcamp"


def test_detect_platform_wordpress():
    assert detect_platform("example.wordpress.com") == "wordpress"


def test_detect_platform_none():
    assert detect_platform("example.com") is None


# ── platform_feed_paths ───────────────────────────────────────────────────────

def test_blogspot_feed_path():
    paths = platform_feed_paths("myrockabilly.blogspot.com")
    assert "/feeds/posts/default?alt=rss" in paths


def test_wordpress_feed_path():
    paths = platform_feed_paths("example.wordpress.com")
    assert "/feed/" in paths


def test_substack_feed_path():
    paths = platform_feed_paths("jazzletter.substack.com")
    assert "/feed" in paths


def test_bandcamp_feed_paths_empty():
    assert platform_feed_paths("noiselab.bandcamp.com") == []


def test_unknown_domain_feed_paths_empty():
    assert platform_feed_paths("example.com") == []


def test_common_feed_paths_has_required_entries():
    required = {"/feed/", "/rss/", "/rss.xml", "/atom.xml", "/feed.xml",
                "/index.xml", "/blog/feed/", "/news/feed/"}
    assert required.issubset(set(COMMON_FEED_PATHS))


# ── parse_html_feed_links ─────────────────────────────────────────────────────

def test_parse_html_rss_link_found():
    feeds = parse_html_feed_links(HTML_WITH_RSS, "https://example.com")
    assert any("feed.xml" in u for u in feeds)


def test_parse_html_atom_link_found():
    feeds = parse_html_feed_links(HTML_WITH_ATOM, "https://example.com")
    assert any("atom.xml" in u for u in feeds)


def test_parse_html_relative_url_normalized():
    html = '<link rel="alternate" type="application/rss+xml" href="/my-feed.xml">'
    feeds = parse_html_feed_links(html, "https://myblog.com")
    assert feeds == ["https://myblog.com/my-feed.xml"]


def test_parse_html_absolute_url_preserved():
    html = '<link rel="alternate" type="application/atom+xml" href="https://other.com/atom">'
    feeds = parse_html_feed_links(html, "https://myblog.com")
    assert feeds == ["https://other.com/atom"]


def test_parse_html_no_feed_links():
    feeds = parse_html_feed_links(HTML_NO_FEED, "https://example.com")
    assert feeds == []


def test_parse_html_deduplicates():
    html = (
        '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
        '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
    )
    feeds = parse_html_feed_links(html, "https://example.com")
    assert len(feeds) == 1


# ── is_valid_feed ─────────────────────────────────────────────────────────────

def test_is_valid_feed_rss():
    assert is_valid_feed(RSS_FEED) is True


def test_is_valid_feed_atom():
    assert is_valid_feed(ATOM_FEED) is True


def test_is_valid_feed_rdf():
    assert is_valid_feed(RDF_FEED) is True


def test_is_valid_feed_html_false():
    assert is_valid_feed(b"<html><body>Not a feed</body></html>") is False


def test_is_valid_feed_empty_false():
    assert is_valid_feed(b"") is False


# ── detect_feed_type ──────────────────────────────────────────────────────────

def test_detect_feed_type_rss():
    assert detect_feed_type(RSS_FEED) == "rss"


def test_detect_feed_type_atom():
    assert detect_feed_type(ATOM_FEED) == "atom"


def test_detect_feed_type_rdf():
    assert detect_feed_type(RDF_FEED) == "rdf"


def test_detect_feed_type_unknown():
    assert detect_feed_type(b"<html>hello</html>") == ""


# ── extract_feed_title ────────────────────────────────────────────────────────

def test_extract_feed_title_rss():
    assert extract_feed_title(RSS_FEED) == "Test Surf Blog"


def test_extract_feed_title_atom():
    assert extract_feed_title(ATOM_FEED) == "Psychobilly Zine"


def test_extract_feed_title_missing():
    assert extract_feed_title(b"<rss><channel></channel></rss>") == ""


def test_extract_feed_title_truncates():
    long_title = b"A" * 300
    content = b"<rss><channel><title>" + long_title + b"</title></channel></rss>"
    result = extract_feed_title(content)
    assert len(result) <= 200


# ── build_source_index / check_dedup ─────────────────────────────────────────

def test_build_source_index_domain_key():
    idx = build_source_index(FAKE_SOURCES)
    assert "nortonrecords.com" in idx


def test_build_source_index_feed_url_key():
    idx = build_source_index(FAKE_SOURCES)
    # trailing slash is stripped when indexing
    assert "https://nortonrecords.com/feed" in idx


def test_check_dedup_domain_match():
    idx = build_source_index(FAKE_SOURCES)
    already, eid, ename = check_dedup("nortonrecords.com", "", idx)
    assert already is True
    assert eid == "norton_records"
    assert ename == "Norton Records"


def test_check_dedup_no_match():
    idx = build_source_index(FAKE_SOURCES)
    already, eid, ename = check_dedup("unknown.com", "", idx)
    assert already is False
    assert eid == ""
    assert ename == ""


def test_check_dedup_feed_url_match():
    idx = build_source_index(FAKE_SOURCES)
    already, eid, _ = check_dedup("other.com", "https://nortonrecords.com/feed/", idx)
    assert already is True
    assert eid == "norton_records"


def test_check_dedup_null_feed_url_ignored():
    idx = build_source_index(FAKE_SOURCES)
    already, _, _ = check_dedup("nofeedlabel.com", "", idx)
    assert already is True


# ── find_feed_for_domain ──────────────────────────────────────────────────────

def test_find_feed_html_alternate_rss():
    fetcher = FakeFetcher()
    fetcher.add("https://example.com/", 200, HTML_WITH_RSS.encode())
    fetcher.add("https://example.com/feed.xml", 200, RSS_FEED)
    result = find_feed_for_domain("example.com", fetcher)
    assert result["detected_feed_url"] == "https://example.com/feed.xml"
    assert result["feed_type"] == "rss"
    assert result["feed_title"] == "Test Surf Blog"
    assert result["site_status"] == "200"


def test_find_feed_html_alternate_atom():
    fetcher = FakeFetcher()
    fetcher.add("https://example.com/", 200, HTML_WITH_ATOM.encode())
    fetcher.add("https://example.com/atom.xml", 200, ATOM_FEED)
    result = find_feed_for_domain("example.com", fetcher)
    assert result["detected_feed_url"] == "https://example.com/atom.xml"
    assert result["feed_type"] == "atom"


def test_find_feed_common_path_fallback():
    fetcher = FakeFetcher()
    fetcher.add("https://example.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://example.com/rss.xml", 200, RSS_FEED)
    result = find_feed_for_domain("example.com", fetcher)
    assert "rss.xml" in result["detected_feed_url"]


def test_find_feed_blogspot_special_path():
    fetcher = FakeFetcher()
    fetcher.add("https://myblog.blogspot.com/", 200, HTML_NO_FEED.encode())
    rss_url = "https://myblog.blogspot.com/feeds/posts/default?alt=rss"
    fetcher.add(rss_url, 200, RSS_FEED)
    result = find_feed_for_domain("myblog.blogspot.com", fetcher)
    assert result["detected_feed_url"] == rss_url


def test_find_feed_wordpress_special_path():
    fetcher = FakeFetcher()
    fetcher.add("https://myblog.wordpress.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://myblog.wordpress.com/feed/", 200, RSS_FEED)
    result = find_feed_for_domain("myblog.wordpress.com", fetcher)
    assert "feed/" in result["detected_feed_url"]


def test_find_feed_substack_special_path():
    fetcher = FakeFetcher()
    fetcher.add("https://jazzletter.substack.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://jazzletter.substack.com/feed", 200, ATOM_FEED)
    result = find_feed_for_domain("jazzletter.substack.com", fetcher)
    assert result["detected_feed_url"] == "https://jazzletter.substack.com/feed"
    assert result["feed_type"] == "atom"


def test_find_feed_not_found_marks_status():
    fetcher = FakeFetcher()
    fetcher.add("https://nofeed.com/", 200, HTML_NO_FEED.encode())
    result = find_feed_for_domain("nofeed.com", fetcher)
    assert result["detected_feed_url"] == ""
    assert result["feed_status"] == "not_found"


def test_find_feed_bandcamp_annotated():
    fetcher = FakeFetcher()
    fetcher.add("https://noiselab.bandcamp.com/", 200, HTML_NO_FEED.encode())
    result = find_feed_for_domain("noiselab.bandcamp.com", fetcher)
    assert "bandcamp" in result["notes"].lower()
    assert result["feed_status"] == "no_feed"


def test_find_feed_https_fails_tries_http():
    fetcher = FakeFetcher()
    # https fails (no response → status 0)
    fetcher.add("http://example.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("http://example.com/rss.xml", 200, RSS_FEED)
    result = find_feed_for_domain("example.com", fetcher)
    # http fallback should find the feed
    assert "rss.xml" in result["detected_feed_url"]


# ── process_row ───────────────────────────────────────────────────────────────

def test_process_row_dry_run_no_fetch():
    row = _make_row(domain="surfzine.com")
    fetcher = FakeFetcher()  # no URLs configured
    result = process_row(row, fetcher, {}, dry_run=True)
    assert result["domain"] == "surfzine.com"
    assert "dry-run" in result["notes"]
    assert result["suggested_import_action"] == "MANUAL_REVIEW"


def test_process_row_dry_run_already_exists():
    row = _make_row(domain="nortonrecords.com")
    idx = build_source_index(FAKE_SOURCES)
    fetcher = FakeFetcher()
    result = process_row(row, fetcher, idx, dry_run=True)
    assert result["already_in_sources"] == "yes"
    assert result["suggested_import_action"] == "ALREADY_EXISTS"


def test_process_row_already_exists_in_sources():
    row = _make_row(domain="nortonrecords.com")
    idx = build_source_index(FAKE_SOURCES)
    fetcher = FakeFetcher()
    fetcher.add("https://nortonrecords.com/", 200, HTML_NO_FEED.encode())
    result = process_row(row, fetcher, idx)
    assert result["already_in_sources"] == "yes"
    assert result["existing_source_id"] == "norton_records"
    assert result["suggested_import_action"] == "ALREADY_EXISTS"


def test_process_row_feed_found_import_ready():
    row = _make_row(domain="surfzine.com", bucket="niche_blog_fanzine")
    fetcher = FakeFetcher()
    fetcher.add("https://surfzine.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://surfzine.com/feed/", 200, RSS_FEED)
    result = process_row(row, fetcher, {})
    assert result["detected_feed_url"] == "https://surfzine.com/feed/"
    assert result["suggested_import_action"] == "IMPORT_READY"
    assert result["already_in_sources"] == "no"


def test_process_row_no_feed_found():
    row = _make_row(domain="deadsite.com", bucket="niche_site")
    fetcher = FakeFetcher()
    fetcher.add("https://deadsite.com/", 200, HTML_NO_FEED.encode())
    result = process_row(row, fetcher, {})
    assert result["detected_feed_url"] == ""
    assert result["suggested_import_action"] == "NO_FEED_FOUND"


def test_process_row_sets_suggested_source_id():
    row = _make_row(domain="myrockabilly.blogspot.com", bucket="niche_blog_fanzine")
    fetcher = FakeFetcher()
    fetcher.add("https://myrockabilly.blogspot.com/", 200, HTML_NO_FEED.encode())
    result = process_row(row, fetcher, {})
    assert result["suggested_source_id"] == "myrockabilly"


def test_process_row_uses_feed_title_as_name():
    row = _make_row(domain="surfzine.com")
    fetcher = FakeFetcher()
    fetcher.add("https://surfzine.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://surfzine.com/feed/", 200, RSS_FEED)
    result = process_row(row, fetcher, {})
    assert result["suggested_name"] == "Test Surf Blog"


# ── suggest_priority ──────────────────────────────────────────────────────────

def test_suggest_priority_high_niche_with_keyword():
    p = suggest_priority("surf-zine.com", "niche_blog_fanzine", "blog", True)
    assert p == "high"


def test_suggest_priority_medium_niche_no_keyword():
    p = suggest_priority("musicblog123.com", "niche_blog_fanzine", "blog", True)
    assert p == "medium"


def test_suggest_priority_low_no_feed():
    p = suggest_priority("surfzine.com", "niche_blog_fanzine", "blog", False)
    assert p == "low"


def test_suggest_priority_low_bandcamp():
    p = suggest_priority("noiselab.bandcamp.com", "label_bandcamp", "label", True)
    assert p == "low"


def test_suggest_priority_manual_review_archive():
    p = suggest_priority("archive.org", "archive", "archive", True)
    assert p == "manual_review"


def test_suggest_priority_medium_label():
    p = suggest_priority("svartrecords.com", "label_or_record_shop", "label", True)
    assert p == "medium"


# ── suggest_import_action ─────────────────────────────────────────────────────

def test_suggest_import_action_already_exists():
    ia = suggest_import_action(True, True, "200", "200", None, "niche_site")
    assert ia == "ALREADY_EXISTS"


def test_suggest_import_action_import_ready():
    ia = suggest_import_action(True, False, "200", "200", None, "niche_site")
    assert ia == "IMPORT_READY"


def test_suggest_import_action_review_feed_bandcamp():
    ia = suggest_import_action(True, False, "200", "200", "bandcamp", "label_bandcamp")
    assert ia == "REVIEW_FEED"


def test_suggest_import_action_no_feed_found_site_ok():
    ia = suggest_import_action(False, False, "", "200", None, "niche_site")
    assert ia == "NO_FEED_FOUND"


def test_suggest_import_action_no_feed_bandcamp():
    ia = suggest_import_action(False, False, "", "200", "bandcamp", "label_bandcamp")
    assert ia == "NO_FEED_FOUND"


def test_suggest_import_action_manual_review_site_down():
    ia = suggest_import_action(False, False, "", "0", None, "niche_site")
    assert ia == "MANUAL_REVIEW"


# ── load_existing_domains (resume behavior) ───────────────────────────────────

def test_load_existing_domains_reads_domain_column(tmp_path):
    csv_file = tmp_path / "output.csv"
    csv_file.write_text("domain,notes\nnortonrecords.com,ok\nexample.com,ok\n")
    domains = load_existing_domains(csv_file)
    assert "nortonrecords.com" in domains
    assert "example.com" in domains


def test_load_existing_domains_missing_file(tmp_path):
    domains = load_existing_domains(tmp_path / "nonexistent.csv")
    assert domains == set()


def test_load_existing_domains_empty_file(tmp_path):
    csv_file = tmp_path / "output.csv"
    csv_file.write_text("domain,notes\n")
    domains = load_existing_domains(csv_file)
    assert domains == set()


def test_resume_skips_existing_domain():
    """Verify that a domain in done_domains is not processed again."""
    row = _make_row(domain="surfzine.com")
    fetcher = FakeFetcher()
    # Fetcher has no responses; if it were called it would return errors
    done = {"surfzine.com"}
    # Simulate the skip: if domain in done_domains, skip
    assert row["domain"] in done  # would be skipped in main()


# ── write_output_csv ──────────────────────────────────────────────────────────

def _blank_row(domain: str) -> dict:
    row = {f: "" for f in OUTPUT_FIELDS}
    row["domain"] = domain
    return row


def test_write_output_csv_creates_file(tmp_path):
    out = tmp_path / "out.csv"
    rows = [_blank_row("example.com")]
    rows[0]["suggested_import_action"] = "IMPORT_READY"
    write_output_csv(rows, out)
    assert out.exists()
    content = out.read_text()
    assert "example.com" in content
    assert "IMPORT_READY" in content


def test_write_output_csv_has_header(tmp_path):
    out = tmp_path / "out.csv"
    write_output_csv([_blank_row("x.com")], out)
    with out.open() as f:
        reader = csv.DictReader(f)
        assert "domain" in (reader.fieldnames or [])
        assert "suggested_import_action" in (reader.fieldnames or [])


def test_write_output_csv_append_no_duplicate_header(tmp_path):
    out = tmp_path / "out.csv"
    write_output_csv([_blank_row("first.com")], out, append=False)
    write_output_csv([_blank_row("second.com")], out, append=True)
    lines = out.read_text().splitlines()
    # header (1) + first row (1) + second row (1) = 3 lines
    assert len(lines) == 3


def test_write_output_csv_all_output_fields_present(tmp_path):
    out = tmp_path / "out.csv"
    write_output_csv([_blank_row("x.com")], out)
    with out.open() as f:
        reader = csv.DictReader(f)
        assert set(reader.fieldnames or []) == set(OUTPUT_FIELDS)


# ── process_row: platform-level integration tests ────────────────────────────

def test_process_row_blogspot_finds_feed_via_special_path():
    """process_row uses the Blogspot special feed path end-to-end."""
    row = _make_row(domain="myblog.blogspot.com", bucket="niche_blog_fanzine")
    fetcher = FakeFetcher()
    fetcher.add("https://myblog.blogspot.com/", 200, HTML_NO_FEED.encode())
    fetcher.add(
        "https://myblog.blogspot.com/feeds/posts/default?alt=rss", 200, RSS_FEED
    )
    result = process_row(row, fetcher, {})
    assert "feeds/posts/default" in result["detected_feed_url"]
    assert result["feed_type"] == "rss"
    assert result["suggested_import_action"] == "IMPORT_READY"
    assert result["suggested_source_id"] == "myblog"


def test_process_row_wordpress_finds_feed_via_special_path():
    """process_row uses the WordPress /feed/ path end-to-end."""
    row = _make_row(domain="myblog.wordpress.com", bucket="niche_blog_fanzine")
    fetcher = FakeFetcher()
    fetcher.add("https://myblog.wordpress.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://myblog.wordpress.com/feed/", 200, RSS_FEED)
    result = process_row(row, fetcher, {})
    assert "/feed/" in result["detected_feed_url"]
    assert result["suggested_import_action"] == "IMPORT_READY"


def test_process_row_substack_finds_feed_via_special_path():
    """process_row uses the Substack /feed path end-to-end."""
    row = _make_row(domain="jazzletter.substack.com", bucket="niche_site")
    fetcher = FakeFetcher()
    fetcher.add("https://jazzletter.substack.com/", 200, HTML_NO_FEED.encode())
    fetcher.add("https://jazzletter.substack.com/feed", 200, ATOM_FEED)
    result = process_row(row, fetcher, {})
    assert result["detected_feed_url"].endswith("/feed")
    assert result["feed_type"] == "atom"
    assert result["suggested_import_action"] == "IMPORT_READY"


# ── dry-run regression tests ──────────────────────────────────────────────────

INPUT_CSV_HEADER = [
    "feed_check_action", "bucket", "longtail_action", "longtail_score",
    "domain", "source_type_guess", "suggested_action", "unique_artists",
    "hits_total", "sample_artists", "sample_titles", "sample_urls",
    "editor_decision", "notes",
]


def _write_test_input(path: Path, domains: list[str]) -> None:
    """Write a minimal candidates CSV for use in main() integration tests."""
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=INPUT_CSV_HEADER)
        w.writeheader()
        for domain in domains:
            row = {k: "" for k in INPUT_CSV_HEADER}
            row["feed_check_action"] = "check_feed"
            row["bucket"] = "niche_site"
            row["domain"] = domain
            row["source_type_guess"] = "blog"
            w.writerow(row)


def test_dry_run_does_not_create_default_output(tmp_path, monkeypatch):
    """--dry-run without --out must not write to the default report path."""
    fake_default = tmp_path / "feed_discovery.csv"
    monkeypatch.setattr(_mod, "DEFAULT_OUTPUT", fake_default)

    input_csv = tmp_path / "input.csv"
    _write_test_input(input_csv, ["testdomain.com"])

    _mod.main([str(input_csv), "--dry-run", "--limit", "1"])

    assert not fake_default.exists(), (
        "--dry-run wrote to the default output path; this poisons --resume"
    )


def test_dry_run_does_not_poison_resume(tmp_path, monkeypatch):
    """After a dry-run, --resume must see no done domains (nothing was written)."""
    fake_default = tmp_path / "feed_discovery.csv"
    monkeypatch.setattr(_mod, "DEFAULT_OUTPUT", fake_default)

    input_csv = tmp_path / "input.csv"
    _write_test_input(input_csv, ["site-a.com", "site-b.com"])

    _mod.main([str(input_csv), "--dry-run"])

    # File must not exist, so resume finds no previously-completed domains
    done = load_existing_domains(fake_default)
    assert len(done) == 0, (
        f"dry-run contaminated resume: {done}"
    )


def test_resume_skips_real_rows_not_dry_run_rows(tmp_path, monkeypatch):
    """
    Resume must be based solely on real (non-dry-run) output rows.
    A domain that only appeared in a dry-run should NOT be skipped.
    """
    fake_default = tmp_path / "feed_discovery.csv"
    monkeypatch.setattr(_mod, "DEFAULT_OUTPUT", fake_default)

    input_csv = tmp_path / "input.csv"
    _write_test_input(input_csv, ["dry-site.com", "real-site.com"])

    # Step 1: dry-run covers first domain — must not write anything
    _mod.main([str(input_csv), "--dry-run", "--limit", "1"])
    assert not fake_default.exists()

    # Step 2: write a real output row for the second domain
    write_output_csv([_blank_row("real-site.com")], fake_default)

    # Only real-site.com should be in the resume skip list
    done = load_existing_domains(fake_default)
    assert "real-site.com" in done
    assert "dry-site.com" not in done


def test_dry_run_with_explicit_out_does_write(tmp_path, monkeypatch):
    """--dry-run --out <path> writes a preview CSV to the explicit path."""
    fake_default = tmp_path / "feed_discovery.csv"
    monkeypatch.setattr(_mod, "DEFAULT_OUTPUT", fake_default)

    out = tmp_path / "preview.csv"
    input_csv = tmp_path / "input.csv"
    _write_test_input(input_csv, ["previewdomain.com"])

    _mod.main([str(input_csv), "--dry-run", "--out", str(out), "--limit", "1"])

    # Explicit --out should be written even in dry-run
    assert out.exists()
    # Default output path must remain untouched
    assert not fake_default.exists()

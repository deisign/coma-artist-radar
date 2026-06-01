"""Tests for Stage27B: discover_artist_sources.py"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from scripts.discover_artist_sources import (
    CANDIDATE_FIELDS,
    DOMAIN_FIELDS,
    QUERY_TEMPLATES,
    FakeSearchProvider,
    aggregate_domains,
    cache_path,
    classify_domain,
    compute_domain_score,
    compute_suggested_action,
    generate_queries,
    load_artists,
    load_cache,
    normalize_domain,
    save_cache,
    slugify,
    write_candidates_csv,
    write_domain_csv,
)


# ── slugify ────────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Lou Reed") == "lou-reed"


def test_slugify_strips_punctuation():
    assert slugify("AC/DC") == "acdc"


def test_slugify_collapses_spaces():
    assert slugify("  The  Cramps  ") == "the-cramps"


def test_slugify_max_length():
    long = "a" * 100
    assert len(slugify(long)) <= 80


# ── normalize_domain ───────────────────────────────────────────────────────────

def test_normalize_domain_strips_www():
    assert normalize_domain("https://www.pitchfork.com/reviews/") == "pitchfork.com"


def test_normalize_domain_strips_m_prefix():
    assert normalize_domain("https://m.youtube.com/watch?v=abc") == "youtube.com"


def test_normalize_domain_lowercases():
    assert normalize_domain("https://ROLLINGSTONE.COM/path") == "rollingstone.com"


def test_normalize_domain_strips_port():
    assert normalize_domain("http://example.com:8080/path") == "example.com"


def test_normalize_domain_no_protocol():
    assert normalize_domain("pitchfork.com/reviews/album/test") == "pitchfork.com"


def test_normalize_domain_empty():
    assert normalize_domain("") == ""


# ── classify_domain ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("domain,expected_type,expected_action", [
    # wiki
    ("wikipedia.org",       "wiki",      "SKIP_WIKI"),
    ("en.wikipedia.org",    "wiki",      "SKIP_WIKI"),
    ("wikidata.org",        "wiki",      "SKIP_WIKI"),
    ("fandom.com",          "wiki",      "SKIP_WIKI"),
    # lyrics
    ("genius.com",          "lyrics",    "SKIP_LYRICS"),
    ("azlyrics.com",        "lyrics",    "SKIP_LYRICS"),
    # video
    ("youtube.com",         "video",     "SKIP_VIDEO_ONLY"),
    ("youtu.be",            "video",     "SKIP_VIDEO_ONLY"),
    ("vimeo.com",           "video",     "SKIP_VIDEO_ONLY"),
    # social
    ("facebook.com",        "social",    "SKIP_SOCIAL"),
    ("instagram.com",       "social",    "SKIP_SOCIAL"),
    ("x.com",               "social",    "SKIP_SOCIAL"),
    ("tiktok.com",          "social",    "SKIP_SOCIAL"),
    ("vk.com",              "social",    "SKIP_SOCIAL"),
    ("reddit.com",          "social",    "SKIP_SOCIAL"),
    # shop — explicit set
    ("amazon.com",          "shop",      "SKIP_SHOP"),
    ("etsy.com",            "shop",      "SKIP_SHOP"),
    # shop — regional pattern (amazon.ca, ebay.de, etc.)
    ("amazon.ca",           "shop",      "SKIP_SHOP"),
    ("amazon.co.uk",        "shop",      "SKIP_SHOP"),
    ("amazon.de",           "shop",      "SKIP_SHOP"),
    ("ebay.ca",             "shop",      "SKIP_SHOP"),
    ("ebay.co.uk",          "shop",      "SKIP_SHOP"),
    ("ebay.com",            "shop",      "SKIP_SHOP"),
    # streaming platforms — never editorial sources
    ("open.spotify.com",    "streaming", "SKIP_GENERIC"),
    ("spotify.com",         "streaming", "SKIP_GENERIC"),
    ("music.apple.com",     "streaming", "SKIP_GENERIC"),
    ("shazam.com",          "streaming", "SKIP_GENERIC"),
    ("reverbnation.com",    "streaming", "SKIP_GENERIC"),
    ("soundcloud.com",      "streaming", "SKIP_GENERIC"),
    ("bandcamp.com",        "streaming", "SKIP_GENERIC"),
    # magazine → IMPORT_CANDIDATE
    ("pitchfork.com",       "magazine",  "IMPORT_CANDIDATE"),
    ("stereogum.com",       "magazine",  "IMPORT_CANDIDATE"),
    # archive
    ("archive.org",         "archive",   "IMPORT_CANDIDATE"),
    # radio
    ("kexp.org",            "radio",     "IMPORT_CANDIDATE"),
    # database — reference, not editorial; capped at REVIEW by compute_suggested_action
    ("discogs.com",         "database",  "REVIEW"),
    ("musicbrainz.org",     "database",  "REVIEW"),
    ("allmusic.com",        "database",  "REVIEW"),  # reclassified from magazine
    # blog platforms
    ("blogspot.com",        "blog",      "REVIEW"),
    ("substack.com",        "blog",      "REVIEW"),
])
def test_classify_domain(domain, expected_type, expected_action):
    source_type, action = classify_domain(domain)
    assert source_type == expected_type, f"{domain}: type={source_type!r}, want {expected_type!r}"
    assert action == expected_action, f"{domain}: action={action!r}, want {expected_action!r}"


def test_classify_unknown_domain():
    source_type, action = classify_domain("someobscureblog.net")
    assert source_type == "unknown"
    assert action == "REVIEW"


# ── compute_domain_score ───────────────────────────────────────────────────────

def test_domain_score_formula():
    # unique_artists*5 + hi_hits*3 + hits_total + bonus
    # magazine bonus = 10
    score = compute_domain_score(
        hits_total=4, unique_artists=2, high_priority_hits=1, source_type="magazine"
    )
    assert score == 2 * 5 + 1 * 3 + 4 + 10  # 27


def test_domain_score_skip_social_negative():
    # With small realistic hit counts, social penalty (-100) drives score negative
    score = compute_domain_score(
        hits_total=3, unique_artists=1, high_priority_hits=0, source_type="social"
    )
    assert score < 0  # 1*5 + 0*3 + 3 - 100 = -92


def test_domain_score_unknown_is_moderate():
    score = compute_domain_score(
        hits_total=1, unique_artists=1, high_priority_hits=0, source_type="unknown"
    )
    assert score == 1 * 5 + 0 * 3 + 1 + 0  # 6


# ── compute_suggested_action ───────────────────────────────────────────────────

def test_suggested_action_skip_overrides_score():
    assert compute_suggested_action("social", 9999) == "SKIP_SOCIAL"
    assert compute_suggested_action("lyrics", 9999) == "SKIP_LYRICS"
    assert compute_suggested_action("wiki", 9999) == "SKIP_WIKI"
    assert compute_suggested_action("shop", 9999) == "SKIP_SHOP"
    assert compute_suggested_action("video", 9999) == "SKIP_VIDEO_ONLY"
    assert compute_suggested_action("forum", 9999) == "SKIP_FORUM_OR_TORRENT"
    assert compute_suggested_action("streaming", 9999) == "SKIP_GENERIC"


def test_suggested_action_score_thresholds():
    # Editorial types (magazine, blog, label, radio, archive) reach IMPORT_CANDIDATE
    # when score >= 20 AND unique_artists >= 2.
    assert compute_suggested_action("magazine", 25, unique_artists=2) == "IMPORT_CANDIDATE"
    assert compute_suggested_action("magazine", 20, unique_artists=2) == "IMPORT_CANDIDATE"
    assert compute_suggested_action("magazine", 10, unique_artists=2) == "REVIEW"
    assert compute_suggested_action("magazine", 5, unique_artists=2) == "REVIEW"
    assert compute_suggested_action("magazine", 4, unique_artists=2) == "SKIP_GENERIC"
    assert compute_suggested_action("magazine", 0, unique_artists=2) == "SKIP_GENERIC"
    # unknown type is capped at REVIEW regardless of score and artist count
    assert compute_suggested_action("unknown", 25, unique_artists=2) == "REVIEW"
    assert compute_suggested_action("unknown", 100, unique_artists=100) == "REVIEW"
    # Editorial types with unique_artists < 2 are also capped at REVIEW
    assert compute_suggested_action("magazine", 25, unique_artists=1) == "REVIEW"
    assert compute_suggested_action("magazine", 100, unique_artists=1) == "REVIEW"
    assert compute_suggested_action("magazine", 25, unique_artists=0) == "REVIEW"


def test_single_artist_cannot_produce_import_candidate():
    """unique_artists=1 must never yield IMPORT_CANDIDATE even with a high score."""
    for score in (20, 50, 100, 999):
        action = compute_suggested_action("magazine", score, unique_artists=1)
        assert action != "IMPORT_CANDIDATE", (
            f"magazine score={score} unique_artists=1 must not be IMPORT_CANDIDATE, got {action}"
        )


def test_two_artists_allows_import_candidate():
    """unique_artists >= 2 with a high score may produce IMPORT_CANDIDATE."""
    action = compute_suggested_action("magazine", 50, unique_artists=2)
    assert action == "IMPORT_CANDIDATE"


def test_database_type_never_import_candidate():
    """database source type must be capped at REVIEW regardless of score."""
    assert compute_suggested_action("database", 9999) == "REVIEW"
    assert compute_suggested_action("database", 100) == "REVIEW"
    assert compute_suggested_action("database", 20) == "REVIEW"
    assert compute_suggested_action("database", 5) == "REVIEW"
    assert compute_suggested_action("database", 4) == "SKIP_GENERIC"


# ── domain classification regression tests ─────────────────────────────────────

def test_discogs_is_never_import_candidate():
    """discogs.com is a reference database — must be REVIEW or lower, never IMPORT_CANDIDATE."""
    src_type, action = classify_domain("discogs.com")
    assert src_type == "database"
    assert action != "IMPORT_CANDIDATE", "discogs.com must never be IMPORT_CANDIDATE"

    # Even with a high aggregated score, compute_suggested_action must cap it
    high_score_action = compute_suggested_action("database", 500)
    assert high_score_action == "REVIEW"


def test_allmusic_is_database_not_magazine():
    """allmusic.com was reclassified from magazine to database — must be REVIEW."""
    src_type, action = classify_domain("allmusic.com")
    assert src_type == "database"
    assert action == "REVIEW"
    assert compute_suggested_action("database", 500) != "IMPORT_CANDIDATE"


def test_spotify_variants_are_streaming():
    """Both spotify.com and open.spotify.com must be SKIP_GENERIC."""
    for domain in ("spotify.com", "open.spotify.com", "api.spotify.com"):
        src_type, action = classify_domain(domain)
        assert src_type == "streaming", f"{domain} should be streaming, got {src_type}"
        assert action == "SKIP_GENERIC", f"{domain} should be SKIP_GENERIC, got {action}"


def test_shazam_is_streaming():
    src_type, action = classify_domain("shazam.com")
    assert src_type == "streaming"
    assert action == "SKIP_GENERIC"


def test_regional_ebay_is_shop():
    for domain in ("ebay.ca", "ebay.de", "ebay.com.au", "ebay.co.uk", "ebay.fr"):
        src_type, action = classify_domain(domain)
        assert src_type == "shop", f"{domain}: expected shop, got {src_type}"
        assert action == "SKIP_SHOP"


def test_regional_amazon_is_shop():
    for domain in ("amazon.ca", "amazon.de", "amazon.fr", "amazon.co.uk"):
        src_type, action = classify_domain(domain)
        assert src_type == "shop", f"{domain}: expected shop, got {src_type}"
        assert action == "SKIP_SHOP"


def test_fandom_is_wiki():
    src_type, action = classify_domain("fandom.com")
    assert src_type == "wiki"
    assert action == "SKIP_WIKI"


# ── bad-IMPORT_CANDIDATE regression tests (batch review 2026-06-01) ───────────

def test_unknown_type_never_import_candidate():
    """unknown source type must never reach IMPORT_CANDIDATE regardless of score."""
    for score in (20, 50, 100, 999):
        for artists in (1, 2, 10, 100):
            action = compute_suggested_action("unknown", score, unique_artists=artists)
            assert action != "IMPORT_CANDIDATE", (
                f"unknown score={score} artists={artists} → {action!r} — must not be IMPORT_CANDIDATE"
            )


def test_music_amazon_subdomains_are_shop():
    """music.amazon.com and music.amazon.co.uk are Amazon Music — must be SKIP_SHOP."""
    for domain in ("music.amazon.com", "music.amazon.co.uk"):
        src_type, action = classify_domain(domain)
        assert src_type == "shop", f"{domain}: expected shop, got {src_type!r}"
        assert action == "SKIP_SHOP", f"{domain}: expected SKIP_SHOP, got {action!r}"


def test_cis_social_platforms_not_import_candidate():
    """ok.ru and my.mail.ru are CIS social/platform domains — not editorial."""
    for domain in ("ok.ru", "my.mail.ru", "mail.ru"):
        src_type, action = classify_domain(domain)
        assert action != "IMPORT_CANDIDATE", f"{domain}: must not be IMPORT_CANDIDATE, got {action!r}"
        assert src_type == "social", f"{domain}: expected social, got {src_type!r}"


def test_pinterest_not_import_candidate():
    src_type, action = classify_domain("pinterest.com")
    assert src_type == "social"
    assert action == "SKIP_SOCIAL"


def test_quora_not_import_candidate():
    src_type, action = classify_domain("quora.com")
    assert src_type == "social"
    assert action == "SKIP_SOCIAL"


def test_imdb_not_import_candidate():
    """imdb.com is an entertainment database — not an editorial music source."""
    src_type, action = classify_domain("imdb.com")
    assert src_type == "database"
    assert action != "IMPORT_CANDIDATE"


def test_tvtropes_not_import_candidate():
    """tvtropes.org is a fan wiki — must be SKIP_WIKI."""
    src_type, action = classify_domain("tvtropes.org")
    assert src_type == "wiki"
    assert action == "SKIP_WIKI"


def test_user_rated_databases_not_import_candidate():
    """albumoftheyear.org, besteveralbums.com, viberate.com are user-rated databases."""
    for domain in ("albumoftheyear.org", "besteveralbums.com", "viberate.com", "grokipedia.com"):
        src_type, action = classify_domain(domain)
        assert src_type == "database", f"{domain}: expected database, got {src_type!r}"
        assert action != "IMPORT_CANDIDATE", f"{domain}: must not be IMPORT_CANDIDATE"


def test_piracy_aggregators_not_import_candidate():
    """Russian/CIS music aggregators and unlicensed streaming sites must be SKIP_GENERIC."""
    for domain in ("musify.club", "hitmos.me", "lightaudio.ru", "sonichits.com"):
        src_type, action = classify_domain(domain)
        assert src_type == "streaming", f"{domain}: expected streaming, got {src_type!r}"
        assert action == "SKIP_GENERIC", f"{domain}: expected SKIP_GENERIC, got {action!r}"


def test_pitchfork_still_import_candidate_with_enough_artists():
    """Classifier hardening must not break legitimate editorial domains."""
    src_type, _ = classify_domain("pitchfork.com")
    assert src_type == "magazine"
    action = compute_suggested_action("magazine", 261, unique_artists=23)
    assert action == "IMPORT_CANDIDATE"


def test_juno_is_shop():
    """juno.co.uk is a record retail shop — must be SKIP_SHOP."""
    src_type, action = classify_domain("juno.co.uk")
    assert src_type == "shop"
    assert action == "SKIP_SHOP"


# ── query template regression tests ───────────────────────────────────────────

def test_query_templates_include_music_context():
    """Default templates must include music/band/musician context for disambiguation."""
    from scripts.discover_artist_sources import QUERY_TEMPLATES
    # At least the first 3 templates (default batch) must have a music qualifier
    default_templates = QUERY_TEMPLATES[:3]
    music_words = {"music", "band", "musician", "album", "reissue", "discography"}
    for template in default_templates:
        lower = template.lower()
        assert any(w in lower for w in music_words), (
            f"Template {template!r} lacks music/band/musician context"
        )


def test_amphibian_man_queries_have_music_context():
    queries = generate_queries("Amphibian Man", QUERY_TEMPLATES[:3])
    music_words = {"music", "band", "musician", "album", "reissue", "discography"}
    for q in queries:
        assert any(w in q.lower() for w in music_words), (
            f"Query {q!r} lacks music disambiguation"
        )


def test_rolling_stones_queries_have_music_context():
    queries = generate_queries("The Rolling Stones", QUERY_TEMPLATES[:3])
    for q in queries:
        assert "rolling stones" in q.lower()
        assert any(w in q.lower() for w in ("music", "band", "musician", "album", "reissue"))


def test_queries_contain_artist_name():
    """Artist name must appear in every generated query."""
    artist = "Nick Cave"
    queries = generate_queries(artist, QUERY_TEMPLATES)
    for q in queries:
        assert artist in q, f"Artist name missing from query: {q!r}"


# ── artist loading ─────────────────────────────────────────────────────────────

def _make_artists_csv(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "artists.csv"
    fields = ["artist_raw", "artist_canonical", "track_count", "monitor_priority", "ignore", "notes"]
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return p


def test_load_artists_basic(tmp_path):
    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "Lou Reed", "artist_canonical": "Lou Reed",
         "track_count": 72, "monitor_priority": "high", "ignore": "false", "notes": ""},
        {"artist_raw": "Unknown", "artist_canonical": "Unknown",
         "track_count": 2, "monitor_priority": "low", "ignore": "false", "notes": ""},
    ])
    artists = load_artists(csv_path, limit=10)
    assert len(artists) == 2
    assert artists[0]["artist"] == "Lou Reed"
    assert artists[0]["priority"] == "high"
    assert artists[0]["track_count"] == 72


def test_load_artists_filters_ignored(tmp_path):
    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "A", "artist_canonical": "A",
         "track_count": 10, "monitor_priority": "high", "ignore": "true", "notes": ""},
        {"artist_raw": "B", "artist_canonical": "B",
         "track_count": 5, "monitor_priority": "low", "ignore": "false", "notes": ""},
    ])
    artists = load_artists(csv_path, limit=10)
    assert len(artists) == 1
    assert artists[0]["artist"] == "B"


def test_load_artists_priority_filter(tmp_path):
    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "High1", "artist_canonical": "High1",
         "track_count": 30, "monitor_priority": "high", "ignore": "false", "notes": ""},
        {"artist_raw": "Low1", "artist_canonical": "Low1",
         "track_count": 2, "monitor_priority": "low", "ignore": "false", "notes": ""},
    ])
    artists = load_artists(csv_path, priority="high")
    assert len(artists) == 1
    assert artists[0]["artist"] == "High1"


def test_load_artists_min_track_count(tmp_path):
    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "Big", "artist_canonical": "Big",
         "track_count": 50, "monitor_priority": "high", "ignore": "false", "notes": ""},
        {"artist_raw": "Small", "artist_canonical": "Small",
         "track_count": 3, "monitor_priority": "low", "ignore": "false", "notes": ""},
    ])
    artists = load_artists(csv_path, min_track_count=10)
    assert len(artists) == 1
    assert artists[0]["artist"] == "Big"


def test_load_artists_limit_and_offset(tmp_path):
    rows = [
        {"artist_raw": f"A{i}", "artist_canonical": f"A{i}",
         "track_count": i, "monitor_priority": "low", "ignore": "false", "notes": ""}
        for i in range(10)
    ]
    csv_path = _make_artists_csv(tmp_path, rows)
    artists = load_artists(csv_path, limit=3, offset=2)
    assert len(artists) == 3
    assert artists[0]["artist"] == "A2"
    assert artists[2]["artist"] == "A4"


# ── query generation ──────────────────────────────────────────────────────────

def test_generate_queries_uses_templates():
    queries = generate_queries("Link Wray", QUERY_TEMPLATES[:3])
    assert '"Link Wray" music album review' in queries
    assert '"Link Wray" band interview' in queries
    assert '"Link Wray" reissue music' in queries


def test_generate_queries_count():
    queries = generate_queries("X", QUERY_TEMPLATES[:2])
    assert len(queries) == 2


def test_generate_queries_quotes_artist():
    queries = generate_queries("The Cramps", QUERY_TEMPLATES[:1])
    assert queries[0].startswith('"The Cramps"')


# ── FakeSearchProvider ─────────────────────────────────────────────────────────

def test_fake_provider_deterministic():
    p = FakeSearchProvider()
    r1 = p.search('"Link Wray" album review', max_results=3)
    r2 = p.search('"Link Wray" album review', max_results=3)
    assert r1 == r2


def test_fake_provider_respects_max_results():
    p = FakeSearchProvider()
    results = p.search('"Elvis Costello" interview', max_results=2)
    assert len(results) <= 2


def test_fake_provider_result_fields():
    p = FakeSearchProvider()
    results = p.search('"Nick Cave" archive', max_results=5)
    assert results
    for r in results:
        assert "rank" in r
        assert "title" in r
        assert "url" in r
        assert "domain" in r
        assert "snippet" in r


def test_fake_provider_custom_map():
    custom = {'"Test" album review': [
        {"rank": 1, "title": "Custom", "url": "https://custom.com/", "domain": "custom.com", "snippet": "X"},
    ]}
    p = FakeSearchProvider(results_map=custom)
    results = p.search('"Test" album review')
    assert results[0]["title"] == "Custom"
    # Unknown query falls back to defaults
    fallback = p.search('"Unknown" interview')
    assert fallback[0]["domain"].startswith("example-music-")


# ── cache ──────────────────────────────────────────────────────────────────────

def test_save_and_load_cache(tmp_path):
    data = {
        "provider": "fake",
        "query": "test",
        "fetched_at": "2026-01-01T00:00:00+00:00",
        "results": [{"rank": 1, "title": "T", "url": "http://x.com", "domain": "x.com", "snippet": ""}],
    }
    p = tmp_path / "artist" / "query.json"
    save_cache(p, data)
    loaded = load_cache(p)
    assert loaded == data


def test_load_cache_returns_none_for_missing(tmp_path):
    assert load_cache(tmp_path / "nonexistent.json") is None


def test_cache_prevents_repeated_provider_calls(tmp_path):
    """Once a result is cached, re-loading it does not call the provider."""
    call_count = [0]
    provider = FakeSearchProvider()
    original_search = provider.search

    def counting_search(query, max_results=10):
        call_count[0] += 1
        return original_search(query, max_results)

    provider.search = counting_search

    query = '"Elvis Presley" album review'
    artist = "Elvis Presley"
    cpath = cache_path(artist, query, tmp_path)

    # First call: cache miss → provider called
    assert load_cache(cpath) is None
    results = provider.search(query, 5)
    assert call_count[0] == 1
    save_cache(cpath, {"provider": "fake", "query": query,
                       "fetched_at": "2026-01-01", "results": results})

    # Second retrieval: load from cache → no provider call
    cached = load_cache(cpath)
    assert cached is not None
    assert cached["results"] == results
    assert call_count[0] == 1  # unchanged


# ── aggregation ───────────────────────────────────────────────────────────────

def _make_candidate(artist="X", priority="high", domain="pitchfork.com",
                    title="T", url="https://pitchfork.com/r/1"):
    return {
        "artist": artist, "artist_priority": priority, "track_count": 10,
        "query": "q", "result_rank": 1, "title": title, "url": url,
        "domain": domain, "snippet": "", "provider": "fake",
        "cached": False, "fetched_at": "2026-01-01",
    }


def test_aggregate_domains_counts_hits():
    candidates = [
        _make_candidate(artist="A", domain="pitchfork.com"),
        _make_candidate(artist="B", domain="pitchfork.com"),
        _make_candidate(artist="A", domain="rollingstone.com"),
    ]
    rows = aggregate_domains(candidates)
    by_domain = {r["domain"]: r for r in rows}
    assert by_domain["pitchfork.com"]["hits_total"] == 2
    assert by_domain["pitchfork.com"]["unique_artists"] == 2
    assert by_domain["rollingstone.com"]["hits_total"] == 1


def test_aggregate_domains_high_priority_hits():
    candidates = [
        _make_candidate(artist="A", priority="high", domain="example.com"),
        _make_candidate(artist="B", priority="low", domain="example.com"),
    ]
    rows = aggregate_domains(candidates)
    row = rows[0]
    assert row["high_priority_artist_hits"] == 1


def test_aggregate_domains_sorted_by_score_descending():
    candidates = [
        _make_candidate(artist="A", domain="wikipedia.org"),   # skip/negative
        _make_candidate(artist="A", domain="pitchfork.com"),   # magazine/positive
        _make_candidate(artist="A", domain="pitchfork.com"),
        _make_candidate(artist="B", domain="pitchfork.com"),
    ]
    rows = aggregate_domains(candidates)
    scores = [r["domain_score"] for r in rows]
    assert scores == sorted(scores, reverse=True)


def test_aggregate_domains_skip_social():
    candidates = [
        _make_candidate(artist="A", domain="facebook.com", url="https://facebook.com/artist"),
    ]
    rows = aggregate_domains(candidates)
    assert rows[0]["suggested_action"] == "SKIP_SOCIAL"


def test_aggregate_domains_import_candidate():
    candidates = [
        _make_candidate(artist="A", priority="high", domain="pitchfork.com"),
        _make_candidate(artist="B", priority="high", domain="pitchfork.com"),
        _make_candidate(artist="C", priority="high", domain="pitchfork.com"),
    ]
    rows = aggregate_domains(candidates)
    assert rows[0]["suggested_action"] == "IMPORT_CANDIDATE"


def test_aggregate_empty_candidates():
    assert aggregate_domains([]) == []


def test_single_artist_domain_is_review_not_import_candidate():
    """A domain seen for only 1 unique artist must never be IMPORT_CANDIDATE.

    Regression: 'The Rolling Stones' boosts rollingstone.com because the band name
    contains the magazine name — but that is a name collision, not editorial signal.
    """
    candidates = [
        _make_candidate(artist="The Rolling Stones", priority="high",
                        domain="rollingstone.com", url="https://www.rollingstone.com/1"),
        _make_candidate(artist="The Rolling Stones", priority="high",
                        domain="rollingstone.com", url="https://www.rollingstone.com/2"),
        _make_candidate(artist="The Rolling Stones", priority="high",
                        domain="rollingstone.com", url="https://www.rollingstone.com/3"),
    ]
    rows = aggregate_domains(candidates)
    row = next(r for r in rows if r["domain"] == "rollingstone.com")
    assert row["unique_artists"] == 1
    assert row["suggested_action"] == "REVIEW", (
        f"unique_artists=1 must be REVIEW, got {row['suggested_action']!r}"
    )


def test_magazine_domain_two_artists_is_import_candidate():
    """A magazine domain seen across 2+ unique artists with a high score is IMPORT_CANDIDATE."""
    candidates = [
        _make_candidate(artist="Nick Cave", priority="high",
                        domain="pitchfork.com", url="https://pitchfork.com/1"),
        _make_candidate(artist="Nick Cave", priority="high",
                        domain="pitchfork.com", url="https://pitchfork.com/2"),
        _make_candidate(artist="Lou Reed", priority="high",
                        domain="pitchfork.com", url="https://pitchfork.com/3"),
    ]
    rows = aggregate_domains(candidates)
    row = next(r for r in rows if r["domain"] == "pitchfork.com")
    assert row["unique_artists"] == 2
    assert row["suggested_action"] == "IMPORT_CANDIDATE"


# ── CSV output ────────────────────────────────────────────────────────────────

def test_write_candidates_csv_fields(tmp_path):
    rows = [_make_candidate()]
    out = tmp_path / "candidates.csv"
    write_candidates_csv(rows, out)
    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == CANDIDATE_FIELDS
        data = list(reader)
    assert len(data) == 1
    assert data[0]["artist"] == "X"


def test_write_domain_csv_fields(tmp_path):
    domain_rows = aggregate_domains([_make_candidate()])
    out = tmp_path / "domains.csv"
    write_domain_csv(domain_rows, out)
    with out.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == DOMAIN_FIELDS
        data = list(reader)
    assert len(data) >= 1
    assert "domain" in data[0]
    assert "domain_score" in data[0]
    assert "suggested_action" in data[0]


def test_write_candidates_csv_creates_parent_dir(tmp_path):
    rows = [_make_candidate()]
    out = tmp_path / "nested" / "deep" / "candidates.csv"
    write_candidates_csv(rows, out)
    assert out.exists()


# ── integration: end-to-end with fake provider ────────────────────────────────

def test_end_to_end_fake_provider(tmp_path):
    """Run main() with fake provider on a temp CSV; both reports should be written."""
    from scripts.discover_artist_sources import main

    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "Howlin Wolf", "artist_canonical": "Howlin Wolf",
         "track_count": 25, "monitor_priority": "high", "ignore": "false", "notes": ""},
        {"artist_raw": "Bo Diddley", "artist_canonical": "Bo Diddley",
         "track_count": 18, "monitor_priority": "medium", "ignore": "false", "notes": ""},
    ])
    candidates_out = tmp_path / "candidates.csv"
    domains_out = tmp_path / "domains.csv"
    cache_out = tmp_path / "cache"

    # Patch ARTISTS_CSV inside the module
    import scripts.discover_artist_sources as mod
    original_csv = mod.ARTISTS_CSV
    try:
        mod.ARTISTS_CSV = csv_path
        rc = main([
            "--limit", "2",
            "--provider", "fake",
            "--queries-per-artist", "2",
            "--sleep", "0",
            "--candidates-report", str(candidates_out),
            "--domains-report", str(domains_out),
            "--cache-dir", str(cache_out),
        ])
    finally:
        mod.ARTISTS_CSV = original_csv

    assert rc == 0
    assert candidates_out.exists()
    assert domains_out.exists()

    with candidates_out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    assert rows[0]["artist"] in ("Howlin Wolf", "Bo Diddley")

    with domains_out.open(newline="", encoding="utf-8") as f:
        d_rows = list(csv.DictReader(f))
    assert len(d_rows) > 0
    assert "domain_score" in d_rows[0]


def test_dry_run_makes_no_provider_calls(tmp_path, capsys):
    """--dry-run must not call any provider and must not write reports."""
    from scripts.discover_artist_sources import main

    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "Test", "artist_canonical": "Test",
         "track_count": 5, "monitor_priority": "low", "ignore": "false", "notes": ""},
    ])
    candidates_out = tmp_path / "candidates.csv"
    domains_out = tmp_path / "domains.csv"

    import scripts.discover_artist_sources as mod
    original_csv = mod.ARTISTS_CSV
    try:
        mod.ARTISTS_CSV = csv_path
        rc = main([
            "--dry-run",
            "--limit", "1",
            "--provider", "fake",
            "--candidates-report", str(candidates_out),
            "--domains-report", str(domains_out),
            "--cache-dir", str(tmp_path / "cache"),
        ])
    finally:
        mod.ARTISTS_CSV = original_csv

    assert rc == 0
    assert not candidates_out.exists()
    assert not domains_out.exists()
    out = capsys.readouterr().out
    assert "dry_run" in out


def test_cache_reuse_across_runs(tmp_path):
    """Second run reuses cache; provider call count stays the same as first run."""
    from scripts.discover_artist_sources import main
    import scripts.discover_artist_sources as mod

    csv_path = _make_artists_csv(tmp_path, [
        {"artist_raw": "Muddy Waters", "artist_canonical": "Muddy Waters",
         "track_count": 40, "monitor_priority": "high", "ignore": "false", "notes": ""},
    ])
    candidates_out = tmp_path / "candidates.csv"
    domains_out = tmp_path / "domains.csv"
    cache_out = tmp_path / "cache"

    call_count = [0]
    original_csv = mod.ARTISTS_CSV
    try:
        mod.ARTISTS_CSV = csv_path
        # Patch FakeSearchProvider.search to count calls
        orig_search = FakeSearchProvider.search

        def counting_search(self, query, max_results=10):
            call_count[0] += 1
            return orig_search(self, query, max_results)

        FakeSearchProvider.search = counting_search

        common_args = [
            "--limit", "1", "--provider", "fake",
            "--queries-per-artist", "2", "--sleep", "0",
            "--candidates-report", str(candidates_out),
            "--domains-report", str(domains_out),
            "--cache-dir", str(cache_out),
        ]
        main(common_args)
        first_count = call_count[0]
        assert first_count == 2  # 1 artist × 2 queries

        main(common_args + ["--resume"])
        second_count = call_count[0]
        assert second_count == first_count  # cache used, no new calls
    finally:
        mod.ARTISTS_CSV = original_csv
        FakeSearchProvider.search = orig_search

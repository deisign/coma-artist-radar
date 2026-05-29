import csv
import sqlite3
from pathlib import Path

import pytest

from scripts.score_items import (
    REPORT_FIELDS,
    _match_artists,
    load_artists,
    score_item,
    score_items,
)

# ---------------------------------------------------------------------------
# Paths to real data files (committed to repo, no network)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"
_RULES_PATH = _REPO_ROOT / "data" / "tag_rules.yaml"
_GENRE_RADAR_PATH = _REPO_ROOT / "data" / "genre_radar.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_artists_csv(path: Path, rows: list[dict]) -> None:
    fields = ["artist_raw", "artist_canonical", "track_count", "monitor_priority", "ignore", "notes"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _make_db(tmp_path: Path) -> Path:
    from scripts.init_db import init_db
    db_path = tmp_path / "test.sqlite"
    conn = init_db(db_path)
    conn.close()
    return db_path


def _insert_item(
    db_path: Path,
    title: str,
    url: str = "https://example.com/item",
    source_id: str = "test_src",
    source_name: str = "Test Source",
    source_type: str = "blog",
    included_in_issue: int = 0,
) -> int:
    now = "2024-01-01T00:00:00Z"
    conn = sqlite3.connect(str(db_path))
    cur = conn.execute(
        "INSERT INTO items (title, url, source_id, source_name, source_type, "
        "included_in_issue, first_seen_at, last_seen_at, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, url, source_id, source_name, source_type, included_in_issue, now, now, now, now),
    )
    conn.commit()
    item_id = cur.lastrowid
    conn.close()
    return item_id


def _get_item_score(db_path: Path, item_id: int) -> int:
    conn = sqlite3.connect(str(db_path))
    (score,) = conn.execute("SELECT score FROM items WHERE id=?", (item_id,)).fetchone()
    conn.close()
    return score


def _get_item_fields(db_path: Path, item_id: int) -> dict:
    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT score, matched_artists, matched_tags, matched_genres FROM items WHERE id=?",
        (item_id,),
    ).fetchone()
    conn.close()
    return {
        "score": row[0],
        "matched_artists": row[1],
        "matched_tags": row[2],
        "matched_genres": row[3],
    }


# ---------------------------------------------------------------------------
# load_artists
# ---------------------------------------------------------------------------

def test_load_artists_filters_ignored(tmp_path):
    _write_artists_csv(
        tmp_path / "artists.csv",
        [
            {"artist_canonical": "The Meteors", "monitor_priority": "high", "ignore": "false"},
            {"artist_canonical": "coma.fm", "monitor_priority": "high", "ignore": "true"},
        ],
    )
    artists = load_artists(tmp_path / "artists.csv")
    assert len(artists) == 1
    assert artists[0]["artist_canonical"] == "The Meteors"


def test_load_artists_skips_empty_canonical(tmp_path):
    _write_artists_csv(
        tmp_path / "artists.csv",
        [
            {"artist_canonical": "", "monitor_priority": "high", "ignore": "false"},
            {"artist_canonical": "Nick Cave", "monitor_priority": "high", "ignore": "false"},
        ],
    )
    artists = load_artists(tmp_path / "artists.csv")
    assert len(artists) == 1
    assert artists[0]["artist_canonical"] == "Nick Cave"


# ---------------------------------------------------------------------------
# _match_artists
# ---------------------------------------------------------------------------

def test_exact_artist_match():
    artists = [{"artist_canonical": "The Meteors", "monitor_priority": "high"}]
    matched = _match_artists("New album from The Meteors!", artists)
    assert len(matched) == 1


def test_case_insensitive_match():
    artists = [{"artist_canonical": "Nick Cave", "monitor_priority": "high"}]
    matched = _match_artists("nick cave and the bad seeds", artists)
    assert len(matched) == 1


def test_short_artist_no_false_positive():
    # "U2" (2 chars) should not match as substring in "music" (no word boundary)
    artists = [{"artist_canonical": "U2", "monitor_priority": "medium"}]
    matched = _match_artists("this music is great", artists)
    assert len(matched) == 0


def test_long_artist_substring_match():
    artists = [{"artist_canonical": "The Stranglers", "monitor_priority": "high"}]
    # possessive: "The Stranglers'" — \b won't match but substring will (>= 5 chars)
    matched = _match_artists("The Stranglers' latest release", artists)
    assert len(matched) == 1


def test_ignored_artists_not_loaded(tmp_path):
    _write_artists_csv(
        tmp_path / "artists.csv",
        [{"artist_canonical": "coma.fm", "monitor_priority": "high", "ignore": "true"}],
    )
    artists = load_artists(tmp_path / "artists.csv")
    assert artists == []


# ---------------------------------------------------------------------------
# score_item unit tests (no DB, use real YAML files)
# ---------------------------------------------------------------------------

def _make_tag_data():
    from scripts.tag_item import load_tags, load_tag_rules
    from scripts.match_genres import load_genre_radar
    return (
        load_tags(_TAGS_PATH),
        load_tag_rules(_RULES_PATH),
        load_genre_radar(_GENRE_RADAR_PATH),
    )


def test_surf_guitar_gets_positive_score(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    item = {"title": "surf guitar reverb twang instrumental", "source_name": "Test Blog"}
    result = score_item(
        item, source_priority=None, artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result["score"] > 0
    all_tags = set(result["matched_tags"])
    assert "instrumental_surf" in all_tags or "surf" in all_tags


def test_surf_guitar_gets_surf_genre(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    item = {"title": "new surf guitar EP reverb", "source_name": "Surf Blog"}
    result = score_item(
        item, source_priority=None, artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert "surf" in result["matched_genres"]


def test_surf_forecast_gets_negative_tag_and_zero_score(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    item = {"title": "surf forecast waves this weekend surfboard rentals", "source_name": "Beach News"}
    result = score_item(
        item, source_priority=None, artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result["score"] == 0
    all_tags = set(result["matched_tags"])
    assert "sports_surfing" in all_tags or "seo_listicle" in all_tags


def test_high_priority_artist_boosts_score(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    artists = [{"artist_canonical": "Nick Cave", "monitor_priority": "high"}]
    item = {"title": "Nick Cave live concert review", "source_name": "Music Blog"}
    result = score_item(
        item, source_priority=None, artists=artists,
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result["score"] >= 50
    assert "Nick Cave" in result["matched_artists"]


def test_medium_priority_artist_bonus(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    artists = [{"artist_canonical": "Sanford Clark", "monitor_priority": "medium"}]
    item = {"title": "Sanford Clark rockabilly session", "source_name": "Rockabilly Blog"}
    result = score_item(
        item, source_priority=None, artists=artists,
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result["score"] >= 30
    assert "Sanford Clark" in result["matched_artists"]


def test_source_high_priority_adds_bonus(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    item = {"title": "reissue review", "source_name": "High Priority Blog"}
    result_high = score_item(
        item, source_priority="high", artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    result_none = score_item(
        item, source_priority=None, artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result_high["score"] > result_none["score"]


def test_seo_listicle_penalty(tmp_path):
    tag_registry, rules, genre_data = _make_tag_data()
    item = {"title": "top 10 best guitar albums ranked list", "source_name": "Generic Blog"}
    result = score_item(
        item, source_priority=None, artists=[],
        tag_registry=tag_registry, rules=rules, genre_data=genre_data,
        report_unknown_path=tmp_path / "unknown.csv",
    )
    assert result["score"] == 0
    assert "seo_listicle" in result["matched_tags"]


# ---------------------------------------------------------------------------
# score_items pipeline — DB integration
# ---------------------------------------------------------------------------

def test_score_items_updates_db(tmp_path):
    db_path = _make_db(tmp_path)
    item_id = _insert_item(db_path, "surf guitar reverb twang", url="https://ex.com/1")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    fields = _get_item_fields(db_path, item_id)
    assert fields["score"] > 0


def test_dry_run_does_not_update_db(tmp_path):
    db_path = _make_db(tmp_path)
    item_id = _insert_item(db_path, "surf guitar reverb twang", url="https://ex.com/2")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
        dry_run=True,
    )
    assert summary["dry_run"] is True
    assert summary["updated"] == 0
    # Score in DB must still be 0 (unchanged)
    assert _get_item_score(db_path, item_id) == 0


def test_used_item_skipped_by_default(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(
        db_path, "surf guitar", url="https://ex.com/3", included_in_issue=1
    )
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    assert summary["items_checked"] == 0
    assert summary["skipped"] == 1


def test_include_used_processes_used_items(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(
        db_path, "surf guitar reverb", url="https://ex.com/4", included_in_issue=1
    )
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
        include_used=True,
    )
    assert summary["items_checked"] == 1


def test_limit_restricts_items_processed(tmp_path):
    db_path = _make_db(tmp_path)
    for i in range(5):
        _insert_item(db_path, f"Item {i}", url=f"https://ex.com/item{i}")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
        limit=3,
    )
    assert summary["items_checked"] == 3
    assert summary["items_total"] == 5


def test_high_priority_artist_gets_high_score_in_db(tmp_path):
    db_path = _make_db(tmp_path)
    item_id = _insert_item(
        db_path, "Nick Cave new album release", url="https://ex.com/nc1"
    )
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(
        artists_path,
        [{"artist_canonical": "Nick Cave", "monitor_priority": "high", "ignore": "false"}],
    )

    score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    fields = _get_item_fields(db_path, item_id)
    assert fields["score"] >= 50
    assert "Nick Cave" in (fields["matched_artists"] or "")


# ---------------------------------------------------------------------------
# Report CSV
# ---------------------------------------------------------------------------

def test_report_csv_created(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, "surf guitar twang", url="https://ex.com/r1")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])
    report_path = tmp_path / "report.csv"

    score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=report_path,
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    assert report_path.exists()
    with report_path.open(encoding="utf-8") as fh:
        fieldnames = csv.DictReader(fh).fieldnames or []
    for col in REPORT_FIELDS:
        assert col in fieldnames, f"Missing column: {col}"


def test_report_csv_rows_match_processed_items(tmp_path):
    db_path = _make_db(tmp_path)
    for i in range(3):
        _insert_item(db_path, f"surf guitar item {i}", url=f"https://ex.com/rr{i}")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])
    report_path = tmp_path / "report.csv"

    score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=report_path,
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    with report_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 3


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_top_candidates(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, "Nick Cave surf guitar reverb", url="https://ex.com/tc1")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(
        artists_path,
        [{"artist_canonical": "Nick Cave", "monitor_priority": "high", "ignore": "false"}],
    )

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    assert "top_candidates" in summary
    assert isinstance(summary["top_candidates"], list)
    if summary["top_candidates"]:
        top = summary["top_candidates"][0]
        assert "id" in top and "title" in top and "score" in top


def test_summary_has_required_keys(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, "some item", url="https://ex.com/sk1")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])

    summary = score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )
    for key in ("items_total", "items_checked", "updated", "skipped", "errors", "dry_run", "top_candidates"):
        assert key in summary, f"Missing key: {key}"


def test_min_score_filters_report(tmp_path):
    db_path = _make_db(tmp_path)
    # Low-signal item
    _insert_item(db_path, "generic music news", url="https://ex.com/ms1")
    # High-signal item
    _insert_item(db_path, "surf guitar reverb twang instrumental", url="https://ex.com/ms2")
    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(artists_path, [])
    report_path = tmp_path / "report.csv"

    score_items(
        db_path=db_path, artists_path=artists_path,
        report_path=report_path,
        tags_path=_TAGS_PATH, rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
        min_score=30,
    )
    with report_path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    # Only high-signal item should pass min_score=30
    for row in rows:
        assert int(row["score"]) >= 30


# ---------------------------------------------------------------------------
# Stage 26G-A — Scoring Audit Summary
# ---------------------------------------------------------------------------

def test_summary_top_candidates_include_score_diagnostics(tmp_path):
    db_path = _make_db(tmp_path)
    _insert_item(db_path, "Nick Cave new album release", url="https://ex.com/audit1")

    artists_path = tmp_path / "artists.csv"
    _write_artists_csv(
        artists_path,
        [{"artist_canonical": "Nick Cave", "monitor_priority": "high", "ignore": "false"}],
    )

    summary = score_items(
        db_path=db_path,
        artists_path=artists_path,
        report_path=tmp_path / "r.csv",
        tags_path=_TAGS_PATH,
        rules_path=_RULES_PATH,
        genre_radar_path=_GENRE_RADAR_PATH,
        unknown_report_path=tmp_path / "unk.csv",
    )

    assert summary["top_candidates"]
    top = summary["top_candidates"][0]

    assert top["matched_artists"] == "Nick Cave"
    assert "why_score" in top
    assert "artist:Nick Cave" in top["why_score"]
    assert "source_name" in top
    assert "matched_tags" in top
    assert "matched_genres" in top


# ---------------------------------------------------------------------------
# Stage 26G-B — Safer Artist Matching
# ---------------------------------------------------------------------------

def test_ambiguous_them_does_not_match_pronoun():
    artists = [{"artist_canonical": "Them", "monitor_priority": "low"}]

    matched = _match_artists(
        "George Strait, Randy Travis Get New Spaces Dedicated to Them",
        artists,
    )

    assert matched == []


def test_america_does_not_match_inside_american_songwriter():
    artists = [{"artist_canonical": "America", "monitor_priority": "low"}]

    matched = _match_artists(
        "This George Thorogood Hit Was a Direct Response to The Rolling Stones American Songwriter",
        artists,
    )

    assert matched == []


def test_america_still_matches_exact_artist_name():
    artists = [{"artist_canonical": "America", "monitor_priority": "low"}]

    matched = _match_artists("America announce a reissue", artists)

    assert [m["artist_canonical"] for m in matched] == ["America"]


def test_contained_artist_duplicate_suppressed():
    artists = [
        {"artist_canonical": "The Rolling Stones", "monitor_priority": "high"},
        {"artist_canonical": "Rolling Stones", "monitor_priority": "low"},
    ]

    matched = _match_artists(
        "This George Thorogood Hit Was a Direct Response to The Rolling Stones’ Start Me Up",
        artists,
    )

    assert [m["artist_canonical"] for m in matched] == ["The Rolling Stones"]


def test_short_artist_word_boundary_still_matches():
    artists = [{"artist_canonical": "U2", "monitor_priority": "medium"}]

    matched = _match_artists("U2 announce a new archival release", artists)

    assert [m["artist_canonical"] for m in matched] == ["U2"]


"""Tests for Stage28A: select_items_with_diversity in build_issue.py."""
from __future__ import annotations

from scripts.build_issue import (
    _parse_artists,
    select_items_with_diversity,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _item(
    title: str,
    source_name: str,
    score: int,
    matched_artists: str = "",
    matched_tags: str = "",
) -> dict:
    return {
        "title": title,
        "source_name": source_name,
        "score": score,
        "matched_artists": matched_artists,
        "matched_tags": matched_tags,
        "url": f"https://example.com/{title.lower().replace(' ', '-')}",
        "source_type": "blog",
        "published_at": "2026-06-01T00:00:00Z",
        "matched_genres": "",
    }


def _selected_sources(items: list[dict]) -> list[str]:
    return [it["source_name"] for it in items]


def _source_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for it in items:
        k = it["source_name"]
        counts[k] = counts.get(k, 0) + 1
    return counts


def _artist_counts(items: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for it in items:
        for artist in _parse_artists(str(it.get("matched_artists") or "")):
            counts[artist] = counts.get(artist, 0) + 1
    return counts


# ── _parse_artists ─────────────────────────────────────────────────────────────

def test_parse_artists_single():
    assert _parse_artists("King Kurt") == ["king kurt"]


def test_parse_artists_multiple():
    assert _parse_artists("Pokey LaFarge, John Prine") == ["pokey lafarge", "john prine"]


def test_parse_artists_empty():
    assert _parse_artists("") == []


def test_parse_artists_whitespace_only():
    assert _parse_artists("  ,  ,  ") == []


def test_parse_artists_strips_whitespace():
    assert _parse_artists("  The Cramps  ,  Nekromantix  ") == [
        "the cramps", "nekromantix"
    ]


# ── source cap ────────────────────────────────────────────────────────────────

def test_source_cap_allows_up_to_max():
    candidates = [
        _item("A1", "Source A", 100),
        _item("A2", "Source A", 90),
        _item("A3", "Source A", 80),  # 3rd — should be skipped
        _item("B1", "Source B", 70),
    ]
    selected, evidence = select_items_with_diversity(candidates, issue_limit=10, max_source_items=2)
    sc = _source_counts(selected)
    assert sc.get("Source A", 0) == 2
    assert sc.get("Source B", 0) == 1


def test_source_cap_skips_third_item_from_same_source():
    candidates = [
        _item("A1", "Source A", 100),
        _item("A2", "Source A", 90),
        _item("A3", "Source A", 80),
    ]
    selected, evidence = select_items_with_diversity(candidates, issue_limit=10, max_source_items=2)
    assert len(selected) == 2
    skipped = [e for e in evidence if e["reason"] == "skipped_by_source_cap"]
    assert len(skipped) == 1
    assert skipped[0]["title"] == "A3"
    assert skipped[0]["source_name"] == "source a"


def test_source_cap_evidence_contains_required_fields():
    candidates = [
        _item("A1", "ND", 100),
        _item("A2", "ND", 90),
        _item("A3", "ND", 80),
    ]
    _, evidence = select_items_with_diversity(candidates, issue_limit=10, max_source_items=2)
    skipped = [e for e in evidence if e["reason"] == "skipped_by_source_cap"]
    assert len(skipped) == 1
    e = skipped[0]
    assert "reason" in e
    assert "source_name" in e
    assert "artist_name" in e
    assert "title" in e
    assert "score" in e
    assert e["score"] == 80


# ── artist cap ────────────────────────────────────────────────────────────────

def test_artist_cap_allows_up_to_max():
    candidates = [
        _item("K1", "Source A", 100, matched_artists="King Kurt"),
        _item("K2", "Source B", 90, matched_artists="King Kurt"),
        _item("K3", "Source C", 80, matched_artists="King Kurt"),  # 3rd — skipped
        _item("O1", "Source D", 70, matched_artists="Other Band"),
    ]
    selected, _ = select_items_with_diversity(candidates, issue_limit=10, max_artist_items=2)
    ac = _artist_counts(selected)
    assert ac.get("king kurt", 0) == 2
    assert ac.get("other band", 0) == 1


def test_artist_cap_skips_third_item_for_same_artist():
    candidates = [
        _item("K1", "Source A", 100, matched_artists="King Kurt"),
        _item("K2", "Source B", 90, matched_artists="King Kurt"),
        _item("K3", "Source C", 80, matched_artists="King Kurt"),
    ]
    selected, evidence = select_items_with_diversity(candidates, issue_limit=10, max_artist_items=2)
    assert len(selected) == 2
    skipped = [e for e in evidence if e["reason"] == "skipped_by_artist_cap"]
    assert len(skipped) == 1
    assert skipped[0]["artist_name"] == "king kurt"
    assert skipped[0]["title"] == "K3"


def test_artist_cap_evidence_contains_artist_name():
    candidates = [
        _item("A1", "S1", 100, matched_artists="Nekromantix"),
        _item("A2", "S2", 90, matched_artists="Nekromantix"),
        _item("A3", "S3", 80, matched_artists="Nekromantix"),
    ]
    _, evidence = select_items_with_diversity(candidates, issue_limit=10, max_artist_items=2)
    skipped = [e for e in evidence if e["reason"] == "skipped_by_artist_cap"]
    assert skipped[0]["artist_name"] == "nekromantix"
    assert skipped[0]["score"] == 80


# ── backfill / continue scanning ──────────────────────────────────────────────

def test_selector_backfills_with_lower_score_valid_item():
    """After capping Source A, lower-score item from Source B fills the slot."""
    candidates = [
        _item("A1", "Source A", 100),
        _item("A2", "Source A", 90),
        _item("A3", "Source A", 80),  # capped
        _item("B1", "Source B", 70),  # valid — should be selected
    ]
    selected, _ = select_items_with_diversity(candidates, issue_limit=3, max_source_items=2)
    titles = [it["title"] for it in selected]
    assert "A1" in titles
    assert "A2" in titles
    assert "B1" in titles
    assert "A3" not in titles


def test_selector_continues_past_multiple_capped_items():
    """Selector keeps scanning even if several consecutive items are capped."""
    candidates = [
        _item("A1", "ND", 100, "King Kurt"),
        _item("A2", "ND", 95, "King Kurt"),   # 2nd ND item, 2nd King Kurt
        _item("A3", "ND", 90, "King Kurt"),   # blocked by both source+artist cap
        _item("A4", "ND", 85, "King Kurt"),   # also blocked
        _item("B1", "Blues.Gr", 80, "Howlin Wolf"),
        _item("B2", "Blues.Gr", 75, "Muddy Waters"),
    ]
    selected, _ = select_items_with_diversity(candidates, issue_limit=4, max_source_items=2, max_artist_items=2)
    sources = _source_counts(selected)
    assert sources.get("ND", 0) <= 2
    assert sources.get("Blues.Gr", 0) <= 2
    assert len(selected) == 4


# ── no matched artist doesn't count against cap ───────────────────────────────

def test_no_artist_does_not_consume_artist_cap():
    candidates = [
        _item("N1", "ND", 100, matched_artists=""),   # no artist
        _item("N2", "ND", 90, matched_artists=""),    # no artist
        _item("K1", "UK", 80, matched_artists="King Kurt"),
        _item("K2", "UK", 70, matched_artists="King Kurt"),
    ]
    selected, _ = select_items_with_diversity(
        candidates, issue_limit=10, max_source_items=10, max_artist_items=2
    )
    ac = _artist_counts(selected)
    # Artist cap should not be triggered by empty-artist items
    assert "" not in ac  # empty string not counted
    assert ac.get("king kurt", 0) == 2


def test_empty_artist_items_dont_block_each_other():
    """Multiple items with no matched artist are each independently allowed."""
    candidates = [
        _item(f"N{i}", "ND", 100 - i, matched_artists="") for i in range(5)
    ]
    selected, _ = select_items_with_diversity(
        candidates, issue_limit=5, max_source_items=10, max_artist_items=2
    )
    assert len(selected) == 5


# ── multi-artist item counts against all listed artists ───────────────────────

def test_multi_artist_item_counts_all_artists():
    candidates = [
        _item("X1", "S1", 100, "John Prine, Pokey LaFarge"),  # 2 artists used
        _item("X2", "S2", 90, "John Prine"),    # John Prine now at cap
        _item("X3", "S3", 80, "John Prine"),    # blocked by artist cap
        _item("X4", "S4", 70, "Pokey LaFarge"), # Pokey LaFarge now at cap
        _item("X5", "S5", 60, "Pokey LaFarge"), # blocked by artist cap
        _item("X6", "S6", 50, "Nekromantix"),   # different artist — allowed
    ]
    selected, evidence = select_items_with_diversity(
        candidates, issue_limit=10, max_source_items=10, max_artist_items=2
    )
    ac = _artist_counts(selected)
    assert ac.get("john prine", 0) <= 2
    assert ac.get("pokey lafarge", 0) <= 2
    artist_skips = [e for e in evidence if e["reason"] == "skipped_by_artist_cap"]
    assert len(artist_skips) == 2
    assert any("john prine" in e["artist_name"] for e in artist_skips)
    assert any("pokey lafarge" in e["artist_name"] for e in artist_skips)


# ── fewer items when not enough valid candidates ──────────────────────────────

def test_returns_fewer_than_limit_when_capped():
    """If caps prevent reaching issue_limit, return fewer items (no violation)."""
    candidates = [
        _item("A1", "Source A", 100),
        _item("A2", "Source A", 90),
        _item("A3", "Source A", 80),  # capped
    ]
    selected, _ = select_items_with_diversity(candidates, issue_limit=5, max_source_items=2)
    assert len(selected) == 2  # fewer than 5, no cap violation


def test_returns_empty_for_zero_limit():
    candidates = [_item("A1", "S", 100)]
    selected, evidence = select_items_with_diversity(candidates, issue_limit=0)
    assert selected == []
    assert evidence == []


def test_returns_all_when_no_caps_triggered():
    candidates = [
        _item(f"Item{i}", f"Source{i}", 100 - i) for i in range(5)
    ]
    selected, evidence = select_items_with_diversity(candidates, issue_limit=5)
    assert len(selected) == 5
    assert evidence == []


# ── evidence completeness ─────────────────────────────────────────────────────

def test_evidence_includes_both_cap_types():
    candidates = [
        _item("A1", "ND", 100, "King Kurt"),
        _item("A2", "ND", 90, "King Kurt"),
        _item("A3", "ND", 80, "King Kurt"),   # both caps trigger (source first)
        _item("B1", "Psycho", 75, "King Kurt"),  # source ok, artist capped
    ]
    _, evidence = select_items_with_diversity(candidates, issue_limit=10, max_source_items=2, max_artist_items=2)
    reasons = {e["reason"] for e in evidence}
    assert "skipped_by_source_cap" in reasons
    assert "skipped_by_artist_cap" in reasons


def test_evidence_preserves_score():
    candidates = [
        _item("A1", "ND", 100),
        _item("A2", "ND", 80),
        _item("A3", "ND", 42),
    ]
    _, evidence = select_items_with_diversity(candidates, issue_limit=10, max_source_items=2)
    skipped = [e for e in evidence if e["reason"] == "skipped_by_source_cap"]
    assert skipped[0]["score"] == 42


# ── regression: observed 2026-06-01 distribution ─────────────────────────────

def test_regression_no_depression_uk_psychobilly_pattern():
    """
    Regression: live 2026-06-01 build had 3 No Depression, 3 UK Psychobilly Gig Guide,
    2 Blues.Gr, 3 King Kurt items — all over the cap.
    After diversity selection, no source exceeds 2 and no artist exceeds 2.
    """
    candidates = [
        # No Depression items (3) — scores 100, 95, 90
        _item("ND review 1", "No Depression", 100, "Steep Canyon Rangers"),
        _item("ND review 2", "No Depression", 95, "Jobi Riccio"),
        _item("ND review 3", "No Depression", 90, "Tom Waits"),
        # UK Psychobilly — 3 King Kurt items + 1 from a different source
        _item("KK press 1", "UK Psychobilly Gig Guide", 100, "King Kurt"),
        _item("KK press 2", "UK Psychobilly Gig Guide", 98, "King Kurt"),
        _item("KK press 3", "UK Psychobilly Gig Guide", 96, "King Kurt"),
        # King Kurt from a different source — triggers artist cap (not source cap)
        _item("KK other", "Psychobilly News", 94, "King Kurt"),
        # Blues.Gr — 2 items
        _item("Blues item 1", "Blues.Gr", 85, "Chicago"),
        _item("Blues item 2", "Blues.Gr", 80, "Chicago"),
        # Alternative filler items — lower scores
        _item("Surf item", "Surf Music and Art", 70, "Little Kahuna"),
        _item("Archive item", "American Archive", 65, ""),
        _item("Label item", "Norton Records", 60, "Link Wray"),
        _item("Zine item", "Mystification Zine", 55, ""),
    ]

    selected, evidence = select_items_with_diversity(
        candidates, issue_limit=10, max_source_items=2, max_artist_items=2
    )

    sc = _source_counts(selected)
    ac = _artist_counts(selected)

    # No source exceeds 2
    for source, count in sc.items():
        assert count <= 2, f"Source '{source}' has {count} items (cap=2)"

    # No artist exceeds 2
    for artist, count in ac.items():
        assert count <= 2, f"Artist '{artist}' has {count} items (cap=2)"

    # All 10 positions filled (enough valid candidates exist)
    assert len(selected) == 10

    # Evidence captures the overflows
    source_skips = [e for e in evidence if e["reason"] == "skipped_by_source_cap"]
    artist_skips = [e for e in evidence if e["reason"] == "skipped_by_artist_cap"]
    assert len(source_skips) > 0
    assert len(artist_skips) > 0

    # Specifically: 3rd No Depression and 3rd+ King Kurt items were skipped
    nd_skips = [e for e in source_skips if "no depression" in e["source_name"]]
    kk_skips = [e for e in artist_skips if "king kurt" in e["artist_name"]]
    assert len(nd_skips) >= 1
    assert len(kk_skips) >= 1

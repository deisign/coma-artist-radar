from pathlib import Path

import pytest

from scripts.generate_issue_cover import (
    detect_main_tag_from_items,
    generate_issue_cover,
    generate_issue_covers,
    get_theme,
    load_themes,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_THEMES_PATH = _REPO_ROOT / "data" / "visual_themes.yaml"
_TAGS_PATH = _REPO_ROOT / "data" / "tags.yaml"
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CONTENT_DIR = _REPO_ROOT / "content" / "issues"


def _cover_path(tmp_path: Path, date: str, lang: str) -> Path:
    return tmp_path / "dist" / "assets" / "covers" / "issues" / date / f"cover-{lang}.svg"


def _make_cover(tmp_path: Path, date: str = "2026-01-01", lang: str = "en",
                main_tag: str = "default", **kwargs) -> dict:
    return generate_issue_cover(
        issue_date=date,
        lang=lang,
        main_tag=main_tag,
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# File creation
# ---------------------------------------------------------------------------

def test_generate_cover_creates_en_svg(tmp_path):
    _make_cover(tmp_path, lang="en")
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()


def test_generate_cover_creates_uk_svg(tmp_path):
    _make_cover(tmp_path, lang="uk")
    assert _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_covers_both_langs(tmp_path):
    generate_issue_covers(
        issue_date="2026-01-01",
        languages=["en", "uk"],
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
    )
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()
    assert _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_covers_only_en(tmp_path):
    generate_issue_covers(
        issue_date="2026-01-01",
        languages=["en"],
        main_tag="default",
        dist_dir=tmp_path / "dist",
        templates_dir=_TEMPLATES_DIR,
        themes_path=_THEMES_PATH,
        tags_path=_TAGS_PATH,
    )
    assert _cover_path(tmp_path, "2026-01-01", "en").exists()
    assert not _cover_path(tmp_path, "2026-01-01", "uk").exists()


def test_generate_cover_dry_run_no_file(tmp_path):
    _make_cover(tmp_path, dry_run=True)
    assert not _cover_path(tmp_path, "2026-01-01", "en").exists()


# ---------------------------------------------------------------------------
# Theme selection
# ---------------------------------------------------------------------------

def test_surf_tag_selects_surf_theme(tmp_path):
    result = _make_cover(tmp_path, main_tag="surf")
    assert result["theme_id"] == "surf"


def test_unknown_tag_falls_back_to_default(tmp_path):
    result = _make_cover(tmp_path, main_tag="nonexistent_tag_xyz")
    assert result["theme_id"] == "default"


# ---------------------------------------------------------------------------
# SVG content
# ---------------------------------------------------------------------------

def test_svg_has_no_external_resources(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in svg
    assert "cdn" not in svg.lower()
    assert "<image" not in svg


def test_svg_contains_site_title(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "coma.fm Radar" in svg


def test_svg_contains_issue_date(tmp_path):
    _make_cover(tmp_path, date="2026-05-26")
    svg = _cover_path(tmp_path, "2026-05-26", "en").read_text(encoding="utf-8")
    assert "2026-05-26" in svg


def test_svg_contains_main_tag_label(tmp_path):
    _make_cover(tmp_path, main_tag="surf")
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "Surf" in svg


# ---------------------------------------------------------------------------
# Output path
# ---------------------------------------------------------------------------

def test_output_path_in_expected_folder(tmp_path):
    result = _make_cover(tmp_path, date="2026-03-15")
    assert "covers/issues/2026-03-15" in result["output_file"]
    assert "cover-en.svg" in result["output_file"]


# ---------------------------------------------------------------------------
# detect_main_tag_from_items
# ---------------------------------------------------------------------------

def test_detect_main_tag_priority_aesthetic_over_genre():
    tags_typed = {"surf": "aesthetic", "country": "genre"}
    items = [
        {"matched_tags": "country"},
        {"matched_tags": "country"},
        {"matched_tags": "surf"},
    ]
    assert detect_main_tag_from_items(items, tags_typed) == "surf"


def test_detect_main_tag_empty_returns_none():
    assert detect_main_tag_from_items([], {}) is None


def test_detect_main_tag_most_frequent_fallback():
    tags_typed = {"a": "content_type", "b": "content_type"}
    items = [{"matched_tags": "b"}, {"matched_tags": "b"}, {"matched_tags": "a"}]
    assert detect_main_tag_from_items(items, tags_typed) == "b"


# ---------------------------------------------------------------------------
# Stage 22 — transmission code in SVG cover
# ---------------------------------------------------------------------------

def test_svg_contains_tx_code(tmp_path):
    _make_cover(tmp_path, date="2026-01-15", lang="en")
    svg = _cover_path(tmp_path, "2026-01-15", "en").read_text(encoding="utf-8")
    assert "TX-20260115-EN" in svg


def test_svg_contains_tx_code_uk(tmp_path):
    _make_cover(tmp_path, date="2026-05-27", lang="uk")
    svg = _cover_path(tmp_path, "2026-05-27", "uk").read_text(encoding="utf-8")
    assert "TX-20260527-UK" in svg


def test_svg_contains_band_label(tmp_path):
    _make_cover(tmp_path, date="2026-01-15", lang="en")
    svg = _cover_path(tmp_path, "2026-01-15", "en").read_text(encoding="utf-8")
    assert "BAND" in svg
    assert "88" in svg


# ---------------------------------------------------------------------------
# Stage 24 — Transmission Cover System
# ---------------------------------------------------------------------------

def test_cover_mode_is_deterministic():
    from scripts.generate_issue_cover import cover_mode_from_tx_code
    mode1 = cover_mode_from_tx_code("TX-20260115-EN")
    mode2 = cover_mode_from_tx_code("TX-20260115-EN")
    assert mode1 == mode2
    assert mode1 in ["concentric", "frequency_bars", "modular_skyline", "tuner_scale", "horizon_signal"]


def test_cover_mode_differs_between_dates():
    from scripts.generate_issue_cover import cover_mode_from_tx_code
    dates = [
        "2026-01-01", "2026-02-15", "2026-03-22", "2026-04-10",
        "2026-06-05", "2026-07-20", "2026-09-03", "2026-11-18",
    ]
    modes = {cover_mode_from_tx_code(f"TX-{d.replace('-', '')}-EN") for d in dates}
    assert len(modes) > 1


def test_svg_contains_registration_marks(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "Registration marks" in svg


def test_svg_contains_frequency_marks_scale(tmp_path):
    _make_cover(tmp_path)
    svg = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    assert "88" in svg
    assert "108" in svg
    assert "96" in svg


def test_svg_is_valid_xml(tmp_path):
    import xml.etree.ElementTree as ET
    _make_cover(tmp_path)
    svg_text = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    ET.fromstring(svg_text)


def test_covers_differ_between_issue_dates(tmp_path):
    _make_cover(tmp_path, date="2026-01-01", lang="en", main_tag="default")
    _make_cover(tmp_path, date="2026-06-15", lang="en", main_tag="default")
    svg1 = _cover_path(tmp_path, "2026-01-01", "en").read_text(encoding="utf-8")
    svg2 = _cover_path(tmp_path, "2026-06-15", "en").read_text(encoding="utf-8")
    assert svg1 != svg2


# ---------------------------------------------------------------------------
# Stage 26F-A — Deterministic Cover Mode Detection
# ---------------------------------------------------------------------------

def test_detect_cover_mode_from_items_prefers_dominant_review_mode():
    from scripts.generate_issue_cover import detect_cover_mode_from_items

    items = [
        {"signal_type": "review"},
        {"signal_type": "review"},
        {"signal_type": "culture"},
    ]

    assert detect_cover_mode_from_items(items) == "modular_skyline"


def test_detect_cover_mode_from_items_maps_archive_and_reissue_to_horizon():
    from scripts.generate_issue_cover import detect_cover_mode_from_items

    assert detect_cover_mode_from_items([{"signal_type": "archive"}]) == "horizon_signal"
    assert detect_cover_mode_from_items([{"signal_type": "reissue"}]) == "horizon_signal"


def test_detect_cover_mode_from_items_maps_industry_to_frequency_bars():
    from scripts.generate_issue_cover import detect_cover_mode_from_items

    items = [
        {"signal_type": "industry"},
        {"signal_type": "industry"},
        {"signal_type": "review"},
    ]

    assert detect_cover_mode_from_items(items) == "frequency_bars"


def test_detect_cover_mode_from_items_uses_priority_on_count_tie():
    from scripts.generate_issue_cover import detect_cover_mode_from_items

    items = [
        {"signal_type": "culture"},
        {"signal_type": "review"},
    ]

    assert detect_cover_mode_from_items(items) == "modular_skyline"


def test_detect_cover_mode_from_items_returns_none_without_known_signal_types():
    from scripts.generate_issue_cover import detect_cover_mode_from_items

    assert detect_cover_mode_from_items([]) is None
    assert detect_cover_mode_from_items([{"signal_type": "unknown"}]) is None


# ---------------------------------------------------------------------------
# Stage 26F-B — Cover Mode Integration
# ---------------------------------------------------------------------------

def test_generate_issue_cover_uses_signal_type_cover_mode_from_content_json(tmp_path):
    import json
    from scripts.generate_issue_cover import generate_issue_cover

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    (content_dir / "2026-01-15.en.json").write_text(
        json.dumps({
            "items": [
                {"signal_type": "review", "matched_tags": ""},
                {"signal_type": "review", "matched_tags": ""},
                {"signal_type": "culture", "matched_tags": ""},
            ]
        }),
        encoding="utf-8",
    )

    result = generate_issue_cover(
        issue_date="2026-01-15",
        lang="en",
        main_tag="default",
        item_count=3,
        dist_dir=tmp_path / "dist",
        content_dir=content_dir,
    )

    assert result["cover_mode"] == "modular_skyline"


def test_generate_issue_cover_falls_back_to_tx_hash_without_signal_types(tmp_path):
    import json
    from scripts.generate_issue_cover import cover_mode_from_tx_code, generate_issue_cover

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)
    (content_dir / "2026-01-15.en.json").write_text(
        json.dumps({"items": [{"signal_type": "unknown", "matched_tags": ""}]}),
        encoding="utf-8",
    )

    result = generate_issue_cover(
        issue_date="2026-01-15",
        lang="en",
        main_tag="default",
        item_count=1,
        dist_dir=tmp_path / "dist",
        content_dir=content_dir,
    )

    assert result["cover_mode"] == cover_mode_from_tx_code("TX-20260115-EN")


def test_generate_issue_covers_summary_includes_cover_mode(tmp_path):
    import json
    from scripts.generate_issue_cover import generate_issue_covers

    content_dir = tmp_path / "content"
    content_dir.mkdir(parents=True)

    payload = json.dumps({
        "items": [
            {"signal_type": "review", "matched_tags": ""}
        ]
    })

    (content_dir / "2026-01-15.en.json").write_text(payload, encoding="utf-8")
    (content_dir / "2026-01-15.uk.json").write_text(payload, encoding="utf-8")

    result = generate_issue_covers(
        issue_date="2026-01-15",
        languages=["en", "uk"],
        main_tag="default",
        item_count=1,
        dist_dir=tmp_path / "dist",
        content_dir=content_dir,
    )

    assert result["cover_mode"] == "modular_skyline"

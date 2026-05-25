import pytest

from scripts.tag_item import tag_item


def test_surf_guitar_gives_instrumental_surf_and_surf():
    result = tag_item(title="surf guitar reverb instrumental")
    all_tags = [t for tags in result["tags"].values() for t in tags]
    assert "instrumental_surf" in all_tags
    assert "surf" in all_tags


def test_horrorbilly_gives_psychobilly_and_horrorbilly():
    result = tag_item(title="horrorbilly night at the graveyard")
    all_tags = [t for tags in result["tags"].values() for t in tags]
    assert "horrorbilly" in all_tags
    assert "psychobilly" in all_tags


def test_honky_tonk_gives_country_and_honky_tonk():
    result = tag_item(title="honky tonk deep cut new release")
    all_tags = [t for tags in result["tags"].values() for t in tags]
    assert "honky_tonk" in all_tags
    assert "country" in all_tags


def test_surf_forecast_gives_sports_surfing_negative():
    result = tag_item(title="surf forecast for the weekend")
    assert "sports_surfing" in result["negative_tags"]
    assert "sports_surfing" in result["tags"]["negative"]


def test_surf_forecast_not_high_surf_score():
    result = tag_item(title="surf forecast surf report", excerpt="surfboard rentals open")
    assert "surf" not in result["tags"]["genre"]
    assert "instrumental_surf" not in result["tags"]["subgenre"]
    assert result["score"] < 20


def test_top_10_gives_seo_listicle():
    result = tag_item(title="top 10 best guitar albums of all time")
    assert "seo_listicle" in result["negative_tags"]
    assert "seo_listicle" in result["tags"]["negative"]
    assert result["score"] < 20


def test_manual_tag_overrides_auto_confidence():
    result_auto = tag_item(title="psychobilly band")
    assert result_auto["tag_confidence"].get("psychobilly", 0) < 1.0

    result_manual = tag_item(title="psychobilly band", manual_tags=["psychobilly"])
    assert result_manual["tag_confidence"]["psychobilly"] == 1.0
    assert result_manual["tag_sources"]["psychobilly"] == "manual"


def test_manual_tag_added_even_without_auto_match():
    result = tag_item(title="jazz album from Paris", manual_tags=["surf"])
    assert "surf" in result["tag_confidence"]
    assert result["tag_confidence"]["surf"] == 1.0
    assert result["tag_sources"]["surf"] == "manual"

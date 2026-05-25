import pytest

from scripts.match_genres import load_genre_radar, match_text


@pytest.fixture(scope="module")
def genre_data():
    return load_genre_radar()


def test_psychobilly_detected_by_horrorbilly(genre_data):
    result = match_text("horrorbilly band releasing new album", genre_data)
    assert "psychobilly" in result["matched_genres"]
    assert result["genre_score"]["psychobilly"] > 0


def test_psychobilly_detected_by_punkabilly(genre_data):
    result = match_text("punkabilly speed and slap bass energy", genre_data)
    assert "psychobilly" in result["matched_genres"]
    assert result["genre_score"]["psychobilly"] > 0


def test_surf_detected_by_instrumental_surf(genre_data):
    result = match_text("new instrumental surf compilation on bandcamp", genre_data)
    assert "surf" in result["matched_genres"]
    assert result["genre_score"]["surf"] > 0


def test_surf_detected_by_surf_guitar(genre_data):
    result = match_text("surf guitar reverb-heavy twang review", genre_data)
    assert "surf" in result["matched_genres"]
    assert result["genre_score"]["surf"] > 0


def test_country_detected_by_honky_tonk(genre_data):
    result = match_text("honky tonk revival in Nashville underground", genre_data)
    assert "country" in result["matched_genres"]
    assert result["genre_score"]["country"] > 0


def test_country_detected_by_gothic_country(genre_data):
    result = match_text("gothic country from the swamps of Louisiana", genre_data)
    assert "country" in result["matched_genres"]
    assert result["genre_score"]["country"] > 0


def test_jazz_detected_by_dark_jazz(genre_data):
    result = match_text("dark jazz ensemble new album out now", genre_data)
    assert "jazz" in result["matched_genres"]
    assert result["genre_score"]["jazz"] > 0


def test_jazz_detected_by_jazz_noir(genre_data):
    result = match_text("jazz noir soundtrack for late-night cinema", genre_data)
    assert "jazz" in result["matched_genres"]
    assert result["genre_score"]["jazz"] > 0


def test_surf_forecast_not_high_score(genre_data):
    result = match_text("surf forecast for tomorrow morning", genre_data)
    assert result["genre_score"]["surf"] == 0
    assert "surf" not in result["matched_genres"]


def test_surfboard_not_high_score(genre_data):
    result = match_text("surfboard rentals near the beach", genre_data)
    assert result["genre_score"]["surf"] == 0
    assert "surf" not in result["matched_genres"]


def test_irrelevant_pop_text_no_genre(genre_data):
    result = match_text("top mainstream pop hits dominate the charts this week", genre_data)
    assert result["matched_genres"] == []
    assert all(v == 0 for v in result["genre_score"].values())

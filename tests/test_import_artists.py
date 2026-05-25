import csv
from pathlib import Path

import pytest

from scripts.import_artists import (
    build_artist_records,
    import_artists,
    normalize_artist,
    priority_for_count,
    should_ignore_artist,
)


def test_normalize_artist_strips_collapses_and_preserves_case():
    assert normalize_artist("  Nick   Cave & The Bad Seeds  ") == "Nick Cave & The Bad Seeds"


def test_should_ignore_empty_and_coma_fm_case_insensitive():
    assert should_ignore_artist("") is True
    assert should_ignore_artist("coma.fm") is True
    assert should_ignore_artist("COMA.FM") is True
    assert should_ignore_artist("The Cramps") is False


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "low"), (4, "low"), (5, "medium"), (19, "medium"), (20, "high"), (100, "high")],
)
def test_priority_for_count(count, expected):
    assert priority_for_count(count) == expected


def test_build_artist_records_counts_sorts_and_sets_priority():
    records = build_artist_records(
        [
            "The Cramps",
            "The Cramps",
            "  The   Cramps ",
            "Link Wray",
            "coma.fm",
            "",
        ]
    )

    by_artist = {record.artist_raw: record for record in records}
    assert by_artist["The Cramps"].track_count == 3
    assert by_artist["The Cramps"].monitor_priority == "low"
    assert by_artist["The Cramps"].artist_canonical == "The Cramps"
    assert by_artist["coma.fm"].ignore is True
    assert by_artist[""].ignore is True
    assert records[0].artist_raw == "The Cramps"


def test_import_artists_writes_expected_csv_files(tmp_path: Path):
    input_csv = tmp_path / "tracks.csv"
    raw_output = tmp_path / "artists_raw.csv"
    registry_output = tmp_path / "artists_registry.csv"

    with input_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Title", "Artist", "Album", "Duration", "Media Type"])
        writer.writeheader()
        for index in range(20):
            writer.writerow(
                {
                    "Title": f"Track {index}",
                    "Artist": "Amphibian Man",
                    "Album": "Demo",
                    "Duration": "00:02:00",
                    "Media Type": "track",
                }
            )
        writer.writerow(
            {
                "Title": "Station ID",
                "Artist": "coma.fm",
                "Album": "IDs",
                "Duration": "00:00:10",
                "Media Type": "track",
            }
        )

    records = import_artists(input_csv, raw_output, registry_output)

    assert raw_output.exists()
    assert registry_output.exists()
    assert len(records) == 2

    with registry_output.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["artist_raw"] == "Amphibian Man"
    assert rows[0]["track_count"] == "20"
    assert rows[0]["monitor_priority"] == "high"
    assert rows[0]["ignore"] == "false"
    assert rows[1]["artist_raw"] == "coma.fm"
    assert rows[1]["ignore"] == "true"


def test_import_artists_fails_for_missing_artist_column(tmp_path: Path):
    input_csv = tmp_path / "bad.csv"
    input_csv.write_text("Title,Album\nSong,Album\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Artist"):
        import_artists(input_csv, tmp_path / "raw.csv", tmp_path / "registry.csv")

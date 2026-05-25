#!/usr/bin/env python3
"""Import and normalize artist names from a Radio.co CSV export.

Outputs:
- data/artists_raw.csv
- data/artists_registry.csv
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REQUIRED_COLUMNS = {"Artist"}
DEFAULT_INPUT = Path("data/s4360dbc20.csv")
DEFAULT_RAW_OUTPUT = Path("data/artists_raw.csv")
DEFAULT_REGISTRY_OUTPUT = Path("data/artists_registry.csv")

RAW_FIELDS = ["artist_raw", "track_count", "ignore"]
REGISTRY_FIELDS = [
    "artist_raw",
    "artist_canonical",
    "track_count",
    "monitor_priority",
    "ignore",
    "notes",
]


@dataclass(frozen=True)
class ArtistRecord:
    artist_raw: str
    artist_canonical: str
    track_count: int
    monitor_priority: str
    ignore: bool
    notes: str


def normalize_artist(value: str | None) -> str:
    """Normalize artist text while preserving meaningful punctuation/case."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFC", value)
    return " ".join(normalized.strip().split())


def should_ignore_artist(artist: str) -> bool:
    """Return True for empty/service artist values that should not be monitored."""
    return artist == "" or artist.casefold() == "coma.fm"


def priority_for_count(track_count: int) -> str:
    if track_count >= 20:
        return "high"
    if track_count >= 5:
        return "medium"
    return "low"


def sniff_csv_dialect(path: Path) -> csv.Dialect:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(8192)
    try:
        return csv.Sniffer().sniff(sample)
    except csv.Error:
        return csv.excel


def read_artist_values(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Input CSV not found: {path}")

    dialect = sniff_csv_dialect(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, dialect=dialect)
        fieldnames = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - fieldnames
        if missing:
            raise ValueError(
                f"Input CSV is missing required column(s): {', '.join(sorted(missing))}"
            )
        return [normalize_artist(row.get("Artist")) for row in reader]


def build_artist_records(artists: Iterable[str]) -> list[ArtistRecord]:
    counts = Counter(normalize_artist(artist) for artist in artists)
    records: list[ArtistRecord] = []

    for artist_raw, track_count in counts.items():
        ignored = should_ignore_artist(artist_raw)
        notes = "ignored service/empty artist value" if ignored else ""
        records.append(
            ArtistRecord(
                artist_raw=artist_raw,
                artist_canonical=artist_raw,
                track_count=track_count,
                monitor_priority=priority_for_count(track_count),
                ignore=ignored,
                notes=notes,
            )
        )

    return sorted(records, key=lambda item: (-item.track_count, item.artist_raw.casefold()))


def bool_to_csv(value: bool) -> str:
    return "true" if value else "false"


def write_artists_raw(path: Path, records: list[ArtistRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "artist_raw": record.artist_raw,
                    "track_count": record.track_count,
                    "ignore": bool_to_csv(record.ignore),
                }
            )


def write_artists_registry(path: Path, records: list[ArtistRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REGISTRY_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "artist_raw": record.artist_raw,
                    "artist_canonical": record.artist_canonical,
                    "track_count": record.track_count,
                    "monitor_priority": record.monitor_priority,
                    "ignore": bool_to_csv(record.ignore),
                    "notes": record.notes,
                }
            )


def import_artists(input_csv: Path, raw_output: Path, registry_output: Path) -> list[ArtistRecord]:
    artists = read_artist_values(input_csv)
    records = build_artist_records(artists)
    write_artists_raw(raw_output, records)
    write_artists_registry(registry_output, records)
    return records


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import artists from a Radio.co CSV export.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Input Radio.co CSV path")
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT, help="Output raw artists CSV path")
    parser.add_argument(
        "--registry-output",
        type=Path,
        default=DEFAULT_REGISTRY_OUTPUT,
        help="Output artist registry CSV path",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        records = import_artists(args.input, args.raw_output, args.registry_output)
    except Exception as exc:  # noqa: BLE001 - CLI should report any import failure cleanly.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    total_unique = len(records)
    ignored = sum(1 for record in records if record.ignore)
    high = sum(1 for record in records if record.monitor_priority == "high" and not record.ignore)
    medium = sum(1 for record in records if record.monitor_priority == "medium" and not record.ignore)
    low = sum(1 for record in records if record.monitor_priority == "low" and not record.ignore)

    print(f"Input: {args.input}")
    print(f"Wrote: {args.raw_output}")
    print(f"Wrote: {args.registry_output}")
    print(f"Unique artist values: {total_unique}")
    print(f"Ignored: {ignored}")
    print(f"Priority high: {high}")
    print(f"Priority medium: {medium}")
    print(f"Priority low: {low}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

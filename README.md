# coma.fm Radar

Working repository for **coma.fm Radar**: a bilingual EN/UK music radar and editorial digest around the coma.fm music field.

Current implemented stage: **Stage 2 — Genre radar and canonical tag taxonomy**.

## Input

Place the Radio.co CSV export here:

```bash
data/s4360dbc20.csv
```

Expected columns:

```text
Title, Artist, Album, Duration, Media Type
```

## Run artist import

```bash
python3 scripts/import_artists.py
```

Outputs:

```text
data/artists_raw.csv
data/artists_registry.csv
```

`artists_registry.csv` fields:

```text
artist_raw, artist_canonical, track_count, monitor_priority, ignore, notes
```

Priority rules:

```text
high    >= 20 tracks
medium  5–19 tracks
low     1–4 tracks
```

Ignored artist values:

```text
empty values
coma.fm
```

## Run tests

```bash
pytest -q
```

---

## Stage 2 — Genre radar and canonical tag taxonomy

### Genre matcher

```bash
python3 scripts/match_genres.py --demo
python3 scripts/match_genres.py --text "horrorbilly psychobilly new album"
```

Output JSON fields:

```text
matched_genres       genres with score > 0, sorted by score
matched_core_tags    matched core tags per genre
matched_adjacent_tags matched adjacent tags per genre
negative_matches     matched negative tags per genre
genre_score          numeric score 0–100 per genre
```

### Item tagger

```bash
python3 scripts/tag_item.py --demo
python3 scripts/tag_item.py --title "surf guitar" --excerpt "instrumental twang"
python3 scripts/tag_item.py --title "honky tonk deep cut" --manual-tags "new_release,must_use"
```

Output JSON fields:

```text
tags            tags grouped by type (genre, subgenre, aesthetic, content_type, editorial, negative)
tag_confidence  per-tag confidence 0.0–1.0
tag_sources     per-tag source (keyword_match, parent_inference, manual)
negative_tags   list of matched negative tags
score           item score 0–100
```

Manual tags always override automatic tags (`confidence = 1.0`, `source = "manual"`).
Unknown manual tags are appended to `reports/unknown_tags.csv`.

### Stage 2 data files

```text
data/genre_radar.yaml   core genres with core/adjacent/negative/search/aesthetic tag lists
data/tags.yaml          canonical tag taxonomy — genre, subgenre, aesthetic, content_type, editorial, negative
data/tag_rules.yaml     keyword matching rules with include, exclude, score, confidence
```

---

## Current project skeleton

```text
data/
scripts/
tests/
reports/
docs/
inbox/
templates/
content/
dist/
```

The full project specification is stored in:

```text
docs/coma_fm_radar_spec_v0_1.md
```

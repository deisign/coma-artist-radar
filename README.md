# coma.fm Radar

Working repository for **coma.fm Radar**: a bilingual EN/UK music radar and editorial digest around the coma.fm music field.

Current implemented stage: **Stage 3 — Editorial Inbox / Human Intake**.

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

## Stage 3 — Editorial Inbox / Human Intake

### Edit the inbox

Add entries to `inbox/manual.md`. Each entry is a YAML block between `---` separators:

```yaml
---
type: link
title: "New surf compilation"
url: https://example.bandcamp.com/album/surf
notes: Great reverb-heavy sound, very coma.fm.
suggested_genres: surf, instrumental_surf
suggested_artists: The Shadowers
priority: high
status: new

---
type: editor_note
title: Surf without the sea
notes: >
  Instrumental surf давно відірвався від пляжу.
suggested_genres: surf, jazz_noir
priority: must_use
status: new
```

Supported types: `link`, `editor_note`

Priority values: `low` | `normal` | `high` | `must_use`

Status values: `new` | `reviewed` | `accepted` | `rejected` | `used` | `archived`

### Dry-run (preview without writing)

```bash
python3 scripts/import_human_submissions.py --dry-run
```

### Import into database

```bash
python3 scripts/import_human_submissions.py
```

Imports entries from `inbox/manual.md` into `data/coma_radar.sqlite`, table `human_submissions`.
Duplicate entries (same URL for links, same title for editor_notes) are silently skipped.

Custom options:

```bash
python3 scripts/import_human_submissions.py --inbox inbox/manual.md --db data/coma_radar.sqlite --submitted-by "Vadim"
```

Output JSON summary fields:

```text
total_in_file      total entries parsed from the inbox
new                entries added to the database
skipped_duplicate  entries skipped because they already exist
errors             validation errors
dry_run            true if --dry-run was passed
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 4 — Source Registry

### Edit the registry

Add or update sources in `data/sources_music.yaml`. Each source entry:

```yaml
- id: norton_records
  name: Norton Records
  site_url: https://nortonrecords.com
  feed_url: null
  source_type: label
  language: en
  region: us
  genre_tags:
    - surf
    - rockabilly
  priority: high
  active: true
  paywall: false
  notes: Optional free-text notes.
```

Valid `source_type` values:

```text
magazine | blog | label | bandcamp_editorial | festival |
archive | youtube_channel | podcast | newsletter | radio | official_artist_site
```

Valid `priority` values: `high` | `medium` | `low`

Valid `paywall` values: `false` | `partial` | `true` | `unknown`

### Structural validation (offline, no network)

```bash
python3 scripts/validate_sources.py --offline
```

### Full validation with HTTP probing and RSS autodiscovery

```bash
python3 scripts/validate_sources.py
```

Outputs:

```text
reports/sources_report.csv
```

Report fields:

```text
id, name, site_url, feed_url, source_type, priority, active,
structural_ok, site_status, feed_status, feed_found, discovered_feed_url, error
```

`feed_found` values:

```text
true        — explicit feed_url responded with HTTP 2xx
discovered  — RSS/Atom link found via HTML autodiscovery
false       — no feed found
(empty)     — offline mode or structural error
```

### Custom paths

```bash
python3 scripts/validate_sources.py --sources data/sources_music.yaml --report reports/sources_report.csv
```

### Run tests

```bash
python3 -m pytest -q tests
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

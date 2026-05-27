# coma.fm Radar

Working repository for **coma.fm Radar**: a bilingual EN/UK music radar and editorial digest around the coma.fm music field.

Current implemented stage: **Stage 25 — Signal Atmosphere / Ghost Transmission Layer**.

---

## Stage 25 — Signal Atmosphere / Ghost Transmission Layer

Pushes the Pearl Broadcast Modernism design from "Swiss-modernist web magazine" toward "late-night transmission archive from an alternate radio infrastructure". Not a redesign — an atmospheric refinement layer.

### What was added

**Signal noise layer** — The page background gains a diagonal paper grain (45° repeating gradient at ~1.2% opacity) and a secondary teal radial glow at the bottom-right corner. No bitmap assets, no external files.

**Controlled breathing room** — Hero padding increased from 54px to 72px; compact hero gains min-height 290px; issue-hero padding increased to 60px; taxonomy modules gain more vertical padding. Archive and tags hero sections gain `padding-bottom`.

**Metadata hierarchy** — All micro-grids now distinguish a `.dominant-signal` primary identifier from `.quiet-meta` secondary labels. The tx-code is dominant; NODE and BAND labels are quiet (38% opacity, slightly smaller). SIGNALS count remains at normal weight on issue pages.

**Frequency scale engineering feel** — The `.frequency-scale` ruler gains top and bottom borders, making it a sealed channel rather than a left-anchored strip.

**Geometric signal language** — New reusable CSS classes placed in templates:
- `.coordinate-mark` — engineering crosshair before each micro-grid
- `.ghost-trace` — dashed transmission remnant line in hero panels
- `.relay-line` — thin structural separator with endpoint dots

**Cover atmosphere** — Ghost scan register lines added to composition zone (5 lines, opacity 0.03–0.04). TX code enlarged from 42px to 46px, opacity raised to 0.82. Ghost TX echo added at very low opacity (0.05) in the composition zone. Redundant TX micro code at y=996 removed for silence.

### Restraint rules

- No neon, no fake CRT, no cyberpunk, no grunge effects
- No bitmap assets, no external files, no CDN dependencies
- No JavaScript, no npm, no node, no package.json
- All gradients at ≤ 12% opacity for the new grain layer
- Geometric elements (crosshairs, relay lines) at ≤ 25% opacity
- Keep editorial structure — breathing room only, not emptiness

### New CSS classes

| Class | Role |
|---|---|
| `.signal-noise` | Paper grain texture via repeating gradients |
| `.ghost-trace` | Dashed transmission remnant line |
| `.relay-line` | Structural separator with endpoint dots |
| `.coordinate-mark` | Engineering crosshair indicator |
| `.atmospheric-field` | Warm radial atmospheric background |
| `.quiet-meta` | Secondary metadata — whisper register (38% opacity) |
| `.dominant-signal` | Primary signal — authority register (full opacity) |
| `.print-drift` | Typographic tension via 1px offset |
| `.transmission-residue` | Ghost atmospheric fade at element base |

### Build commands

```bash
python scripts/build_css.py
python scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar --telegram-dry-run
python -m pytest -q tests
```

---

## Stage 24 — Transmission Cover System

Covers are now modular transmission posters generated deterministically from each issue's TX code. Every issue gets a unique visual composition selected from five geometric modes; the same issue always produces the same cover.

### Deterministic cover modes

Mode is selected by `sha256(tx_code)[0] % 5`:

| Mode | Composition |
|---|---|
| `concentric` | Asymmetric concentric circles — center shifted by hash, crosshair through focal point |
| `frequency_bars` | Vertical spectrum bars — heights derived from hash, left-anchored |
| `modular_skyline` | Rectangular column modules — varying heights, full-width grid |
| `tuner_scale` | FM dial (88–108 MHz) with deterministic needle position and signal halos |
| `horizon_signal` | Horizontal line structure — density and spacing derived from hash |

All modes share the same visual language: pearl paper background, left accent bar, registration marks, masthead, heavy rule, instrumentation scale.

### Modular signal composition

Every cover carries:
- **Registration marks** — print-style cross hairlines at all four corners
- **Outer registration frame** — thin line inset from edge
- **Column grid** — six faint vertical reference columns
- **TX code** — large broadcast identifier (42px) in the main zone
- **Frequency instrumentation** — 88–108 FM scale with tick marks
- **NODE / BAND** — compact metadata layer

### Cover integration

| Page | Cover element |
|---|---|
| Homepage issue cards | `.cover-mini` — compact thumbnail anchor |
| Issue page | `.issue-cover-large` inside `.cover-frame` with `.cover-meta` |

### New CSS classes

- `.cover-frame` / `.cover-grid` — structural wrapper
- `.cover-meta` — TX code + band + node row below cover
- `.cover-code` / `.cover-band` / `.cover-node` — individual metadata tokens
- `.cover-mini` — thumbnail for issue grid cards
- `.issue-cover-large` — full editorial cover on issue pages
- `.signal-cluster` — stacked signal metadata group
- `.registration-mark` — print registration corner mark

### Build commands

```bash
python scripts/build_css.py
python scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar --telegram-dry-run
python -m pytest -q tests
```

---

## Stage 20 — Pearl Broadcast Modernism

Visual redesign of the entire design system. Direction: Swiss International Style + Bauhaus functionalism + mid-century editorial graphics + streamline radio engineering + late-night Americana atmosphere.

**Core image:** "International radio bulletin typeset by a Swiss designer in 1961 for a late-night rock-and-roll station."

### Palette

| Token | Hex | Role |
|---|---|---|
| `--bg` | `#F3EBDD` | Pearl paper (primary background) |
| `--surface` | `#EFE6D6` | Warm ivory panels |
| `--surface-2` | `#E6D9C6` | Dusty cream blocks |
| `--text` | `#1F2523` | Graphite |
| `--muted` | `#6A5F52` | Muted brown |
| `--accent` | `#D86F32` | Burnt orange |
| `--accent-2` | `#2E8C8A` | Petrol teal |
| `--danger` | `#A93A32` | Oxide red |
| `--ochre` | `#C6A13A` | Ochre mustard |

### New design classes

- `.masthead` / `.brand-grid` — printed masthead header
- `.signal-strip` / `.signal-token` — broadcast genre bar
- `.frequency-lines` — CSS-only editorial texture
- `.program-grid` / `.program-card` — program listing
- `.issue-layout` / `.issue-hero` / `.issue-meta-panel` — magazine spread layout
- `.entry-list` / `.entry-card` / `.entry-number` — numbered editorial rows
- `.archive-index` / `.archive-row` — transmission log
- `.taxonomy-board` / `.taxonomy-module` — tag taxonomy board
- `.tag-dossier` / `.tag-strip` — signal dossier page

### Pages

| URL | Description |
|---|---|
| `/en/index.html` | Modernist radio bulletin landing |
| `/en/issues/YYYY-MM-DD.html` | Magazine spread / transmission sheet |
| `/en/archive.html` | Printed transmission log |
| `/en/tags/index.html` | Taxonomy board |
| `/en/tags/<tag>.html` | Signal dossier |

### Build commands

```bash
python scripts/build_css.py
python scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 \
  --base-url https://deisign.github.io/coma-artist-radar \
  --base-path /coma-artist-radar --telegram-dry-run
python -m pytest -q tests
```

---

## Stage 22 — Nocturnal Signal Refinement

Transmission metadata layer injected across all pages and the cover SVG. Direction: late-night radio broadcast instrumentation — every page carries a unique transmission code, band reference, and node identifier.

### Transmission metadata

Every issue, index, archive, tag page, and cover SVG now carries deterministic broadcast metadata generated by `scripts/transmission_meta.py`.

| Field | Example | Description |
|---|---|---|
| `tx_code` | `TX-20260527-EN` | Unique per issue × language |
| `band` | `88–108 FM` | FM broadcast band reference |
| `archive_node` | `COMA-RADAR` | Archive node identifier |
| `frequency_marks` | `[88, 92, 96, 100, 104, 108]` | Frequency scale ticks |
| `section_code` | `HOME-SIGNAL` | Per-section identifier |
| `field_tags` | `["surf", "post-punk"]` | Up to 5 dominant tags from items |

### Section codes

| Page | `section_code` |
|---|---|
| Index | `HOME-SIGNAL` |
| Archive | `ARCHIVE-LOG` |
| Tags index | `TAXONOMY-BOARD` |
| Tag page | `TAG-DOSSIER` |
| Issue | `TX-YYYYMMDD-LANG` |

### New CSS classes

- `.micro-grid` / `.micro-label` — compact metadata row
- `.tx-code` / `.transmission-code` — teal monospace transmission code
- `.frequency-scale` / `.frequency-mark` — FM frequency ruler
- `.signal-dot` — orange dot indicator
- `.instrument-line` — dashed broadcast separator
- `.field-tags` — uppercase tag series in orange

### Cover SVG

Issue covers now embed `TX-YYYYMMDD-LANG` and `BAND 88–108 FM` at the bottom of the SVG as nocturnal signal layer text.

---

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

## Stage 5 — SQLite schema and source sync

### Initialize the database

Create `data/coma_radar.sqlite` with the full schema (idempotent — safe to run multiple times):

```bash
python3 scripts/init_db.py
```

### Reset the database

Drop the existing database and create a fresh one:

```bash
python3 scripts/init_db.py --reset
```

### Inspect tables and row counts

```bash
python3 scripts/init_db.py --summary
```

Output JSON:

```json
{
  "tables": {
    "artists": 0,
    "human_submissions": 0,
    "issues": 0,
    "items": 0,
    "labels": 0,
    "seen_urls": 0,
    "sources": 0
  }
}
```

### Synchronize sources from YAML

Upsert all entries from `data/sources_music.yaml` into the `sources` table:

```bash
python3 scripts/sync_sources_to_db.py
```

Output JSON:

```json
{
  "total_in_yaml": 28,
  "inserted": 28,
  "updated": 0,
  "active": 27,
  "inactive": 1
}
```

Repeated runs update existing rows rather than inserting duplicates.

### Custom paths

```bash
python3 scripts/sync_sources_to_db.py --sources data/sources_music.yaml --db data/coma_radar.sqlite
```

### Schema tables

```text
artists          — imported from Radio.co CSV (stage 1)
sources          — source registry (stage 4/5)
labels           — standalone label index
items            — fetched and scored feed items
seen_urls        — deduplication index by url_hash
issues           — published digest issues
human_submissions — editorial inbox (stage 3)
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 6 — Feed fetching and item storage

### Dry-run (parse feeds, no DB writes)

```bash
python3 scripts/fetch_sources.py --dry-run --limit 5
```

### Fetch real feeds (live mode)

```bash
python3 scripts/fetch_sources.py --limit 5
python3 scripts/fetch_sources.py
```

### Fetch using a local XML fixture (no network)

```bash
python3 scripts/fetch_sources.py --offline-fixture path/to/feed.xml --limit 1
```

### Output JSON summary fields

```text
sources_total       total sources in the YAML
sources_with_feed   active sources with a feed_url
sources_checked     sources actually fetched (respects --limit)
items_found         items parsed from all feeds
inserted            new items written to the items table
skipped_duplicate   items already present (deduplicated by url_hash)
errors              sources that failed to fetch or parse
dry_run             true if --dry-run was passed
```

### Fetch report

Each run writes `reports/fetch_sources_report.csv`:

```text
source_id, source_name, feed_url, status, items_found, inserted, skipped_duplicate, error
```

### Custom paths

```bash
python3 scripts/fetch_sources.py \
  --sources data/sources_music.yaml \
  --db data/coma_radar.sqlite \
  --report reports/fetch_sources_report.csv \
  --limit 10
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 7 — Item scoring pipeline

### Dry-run (score without writing to DB)

```bash
python3 scripts/score_items.py --dry-run --limit 20
```

### Score items (live, updates DB)

```bash
python3 scripts/score_items.py --limit 20
python3 scripts/score_items.py
```

### Re-score items already used in an issue

```bash
python3 scripts/score_items.py --include-used --limit 20
```

### Only report items above a threshold

```bash
python3 scripts/score_items.py --min-score 30
```

### Output JSON summary fields

```text
items_total      total items in the database
items_checked    items processed this run
updated          items with score written to DB
skipped          items not processed (used or past limit)
errors           items that failed to score
dry_run          true if --dry-run was passed
top_candidates   top-10 items by score (id, title, score, url)
```

### Score report

Each run writes `reports/scored_items_report.csv`:

```text
item_id, title, url, source_name, matched_artists, matched_tags, matched_genres, score, why_score
```

`why_score` explains what contributed: `artist:Nick Cave+50; genre:surf+25; source:high+20`

### Scoring formula

```text
+50  matched artist — monitor_priority high
+30  matched artist — monitor_priority medium
+15  matched artist — monitor_priority low
+25  core genre tag (surf, country, jazz, psychobilly, blues, americana)
+15  subgenre tag
+10  aesthetic tag
+15  content_type: reissue / archive_release / interview / review /
                   new_release / label_profile / scene_report
+20  source priority high
+10  source priority medium
-50  negative tag
-30  seo_listicle / press_release_only / weak_source
```

Final score is clamped to 0–100.

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 8 — Static bilingual issue draft

### Build a draft issue (both EN and UK)

```bash
python3 scripts/build_issue.py --date 2026-05-25 --draft --limit 10
```

### Build for a single language

```bash
python3 scripts/build_issue.py --date 2026-05-25 --lang uk --draft --limit 10
python3 scripts/build_issue.py --date 2026-05-25 --lang en --draft --limit 10
```

### Build a published issue (no draft banner)

```bash
python3 scripts/build_issue.py --date 2026-05-25 --limit 50 --min-score 30
```

### Custom min-score and limit

```bash
python3 scripts/build_issue.py --date 2026-05-25 --draft --min-score 40 --limit 20
```

### Build for GitHub Pages project site

```bash
python3 scripts/build_issue.py --date 2026-05-25 --draft --limit 10 --base-path /coma-artist-radar
```

### Output files

```text
dist/en/issues/YYYY-MM-DD.html   — English issue page
dist/uk/issues/YYYY-MM-DD.html   — Ukrainian issue page
content/issues/YYYY-MM-DD.en.json — EN issue data draft
content/issues/YYYY-MM-DD.uk.json — UK issue data draft
```

`dist/` and `content/issues/*.json` are not committed to git.

### Output JSON summary fields

```text
issue_date       date of the issue
languages        languages built (["en", "uk"] or single)
selected_items   number of items included
output_files     list of written file paths
draft            true if --draft was passed
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 9 — Tag pages

### Build tag pages for both EN and UK

```bash
python3 scripts/build_tag_pages.py
```

### Build for a single language

```bash
python3 scripts/build_tag_pages.py --lang uk
python3 scripts/build_tag_pages.py --lang en
```

### Dry-run (render without writing files)

```bash
python3 scripts/build_tag_pages.py --dry-run
```

### Custom content and output dirs

```bash
python3 scripts/build_tag_pages.py --content-dir content/issues --dist-dir dist
```

### Output files

```text
dist/en/tags/index.html           — EN tag index (all tags grouped by type)
dist/uk/tags/index.html           — UK tag index
dist/en/tags/<slug>.html          — EN individual tag page
dist/uk/tags/<slug>.html          — UK individual tag page
```

`dist/` is not committed to git.

### Tag page report

```text
reports/tag_pages_report.csv
```

Fields:

```text
tag_id       tag identifier from tags.yaml
slug         URL slug
label        display label (always English/international)
type         genre | subgenre | aesthetic | content_type | editorial | negative
lang         en | uk
item_count   number of items with this tag
page_path    output file path
status       ok | dry_run | unknown_tag | error
error        error message if status is error
```

### Output JSON summary fields

```text
languages        languages built
tags_total       total tags in tags.yaml
tags_with_items  tags that have at least one item
pages_written    HTML files written
unknown_tags     tag IDs found in items but absent from tags.yaml
output_files     list of written file paths
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 10 — Static site for GitHub Pages

### Build the site (dry-run, no files written)

```bash
python3 scripts/build_site.py --dry-run
```

### Build the site (writes to dist/)

```bash
python3 scripts/build_site.py
```

### Specify a custom base URL

```bash
python3 scripts/build_site.py --base-url https://radar.coma.fm
```

### Output files

```text
dist/index.html           — language chooser landing page
dist/en/index.html        — EN homepage (latest issues)
dist/uk/index.html        — UK homepage (latest issues)
dist/en/archive.html      — EN issue archive
dist/uk/archive.html      — UK issue archive
dist/robots.txt           — robots.txt
dist/sitemap.xml          — sitemap (issues + tag pages)
dist/feed.xml             — RSS feed (latest EN issues)
```

`dist/` is not committed to git.

### Verify outputs

```bash
# Check robots.txt has Sitemap directive
grep Sitemap dist/robots.txt

# Check sitemap contains issue URLs
grep issues dist/sitemap.xml

# Check feed is valid XML
python3 -c "import xml.etree.ElementTree as ET; ET.parse('dist/feed.xml'); print('OK')"
```

### Output JSON summary fields

```text
issues_total    unique issue dates found in content/issues/
pages_written   number of files written
output_files    list of written file paths
base_url        base URL used for links
dry_run         true if --dry-run was passed
```

### Custom content and output dirs

```bash
python3 scripts/build_site.py --content-dir content/issues --dist-dir dist
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 11 — GitHub Pages deploy workflow

### How the deploy works

On every push to `main`, the workflow in `.github/workflows/pages.yml`:

1. Checks out the repository
2. Installs Python dependencies (`pytest`, `PyYAML`)
3. Runs the full test suite (`python -m pytest -q tests`)
4. Builds the static site (`python scripts/build_site.py --base-url https://radar.coma.fm`)
5. Builds tag pages (`python scripts/build_tag_pages.py`)
6. Uploads `dist/` as a GitHub Pages artifact
7. Deploys the artifact to GitHub Pages

### Trigger manually

Go to **Actions → Deploy coma.fm Radar to GitHub Pages → Run workflow** and click **Run workflow** to deploy without a push.

### Repository settings

In **Settings → Pages**, set the source to **GitHub Actions** (not a branch). The workflow handles everything else.

### Where to see the result

- Deployed site: `https://radar.coma.fm` (or `https://<owner>.github.io/<repo>` if custom domain is not configured)
- Workflow runs: **Actions** tab → **Deploy coma.fm Radar to GitHub Pages**

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 12 — Base path support for GitHub Pages project site

### Temporary GitHub Pages URL

While the custom domain is not connected, the site deploys at:

```
https://deisign.github.io/coma-artist-radar/
```

### Why --base-path is needed

GitHub project pages are served under a sub-path (`/coma-artist-radar/`), not the root. Without `--base-path`, all internal links like `/en/index.html` resolve to `https://deisign.github.io/en/index.html`, which is wrong.

With `--base-path /coma-artist-radar`, all internal links are prefixed correctly:

```
/coma-artist-radar/en/index.html
/coma-artist-radar/uk/index.html
/coma-artist-radar/en/issues/YYYY-MM-DD.html
```

### Build for the project site

```bash
python3 scripts/build_site.py \
  --base-url https://deisign.github.io/coma-artist-radar \
  --base-path /coma-artist-radar

python3 scripts/build_tag_pages.py --base-path /coma-artist-radar

python3 scripts/build_issue.py --date 2026-05-25 --draft --limit 10 --base-path /coma-artist-radar
```

### Build for a custom domain (no base-path needed)

```bash
python3 scripts/build_site.py --base-url https://radar.coma.fm
python3 scripts/build_tag_pages.py
```

When the custom domain `radar.coma.fm` is connected, remove `--base-path` from the workflow and set `--base-url https://radar.coma.fm`.

### base-path normalization rules

```
""                    →  ""                    (no prefix)
"/"                   →  ""                    (no prefix)
"coma-artist-radar"   →  "/coma-artist-radar"
"/coma-artist-radar/" →  "/coma-artist-radar"
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 13 — Daily draft pipeline

`scripts/build_daily_draft.py` runs the full local pipeline in one command:
sync sources → import inbox → fetch feeds → score items → build issue → build tag pages → build site.

### Build the first draft

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10
```

### Limit how many sources are fetched

Useful for quick smoke tests:

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5
```

### Build for the GitHub Pages project site (default)

The defaults already point to the GitHub Pages URL and base path:

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26
```

Equivalent long form:

```bash
python3 scripts/build_daily_draft.py \
  --date 2026-05-26 \
  --base-url https://deisign.github.io/coma-artist-radar \
  --base-path /coma-artist-radar
```

### Build for a custom domain

```bash
python3 scripts/build_daily_draft.py \
  --date 2026-05-26 \
  --base-url https://radar.coma.fm \
  --base-path ""
```

### Dry-run (no files written)

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26 --dry-run
```

### Check output after build

```bash
ls dist/
ls dist/en/issues/
ls dist/uk/issues/
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 14 — Issue quality gate

`scripts/validate_issue_content.py` checks issue JSON files against a set of
content rules before publication. It writes `reports/issue_quality_report.csv`
and exits with an appropriate code so it can be used in CI or pre-publish hooks.

### Why a quality gate is needed

Draft issues are built automatically from scored items. Before they are published,
the quality gate catches common problems:

- Items with score below the minimum threshold
- Negative tags (SEO listicles, celebrity gossip, etc.) that slipped through scoring
- Unknown tags not present in `data/tags.yaml`
- Duplicate URLs within a single issue
- EN and UK versions with mismatched item sets
- Excerpts or summaries that look like full article text
- Missing required fields (`title`, `url`, `source_name`)

Findings are categorised as **errors** (block publication) or **warnings** (advisory).

### Check all issues

```bash
python3 scripts/validate_issue_content.py
```

### Check a specific date

```bash
python3 scripts/validate_issue_content.py --date 2026-05-26
python3 scripts/validate_issue_content.py --date 2026-05-26 --lang en
```

### JSON summary output

```bash
python3 scripts/validate_issue_content.py --date 2026-05-26 --json
```

### Enable fail-on-warnings (strict mode)

```bash
python3 scripts/validate_issue_content.py --date 2026-05-26 --fail-on-warnings
```

Exits 1 if there are any warnings (default: only errors cause exit 1).

### Run daily draft with automatic validation

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 --validate
```

The pipeline exits 1 if validation finds errors, allowing CI to block deployment.

### Exit codes

| Situation | Exit code |
|-----------|-----------|
| No errors, no warnings | 0 |
| Only warnings, no `--fail-on-warnings` | 0 |
| Warnings + `--fail-on-warnings` | 1 |
| Errors present | 1 |

### Report file

`reports/issue_quality_report.csv` — one row per finding per item. Not committed to git.

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 15 — Design system

Adds a warm nocturnal editorial design system. All visual styles live in a single
CSS template rendered at build time — no external CDN, no Google Fonts.

### Palette

| Variable | Value | Role |
|----------|-------|------|
| `--bg` | `#17130f` | Page background (deep tobacco brown) |
| `--surface` | `#211a15` | Card / item background |
| `--surface-2` | `#2a211a` | Tag pill background |
| `--text` | `#f2e6d0` | Primary text (warm paper) |
| `--muted` | `#b8a98e` | Secondary text, labels |
| `--border` | `rgba(242,230,208,0.16)` | Subtle borders |
| `--accent` | `#e07a3f` | Links, dates, highlights |
| `--accent-2` | `#3a8c8c` | Scores, published badges |
| `--danger` | `#b6463a` | Draft notice background |

### Build CSS

```bash
python3 scripts/build_css.py
```

Reads `templates/style.css.j2`, renders with the Jinja2-subset renderer, writes
`dist/assets/style.css`. Supports `--dry-run` and `--dist-dir`.

### Full build with design system

```bash
python3 scripts/build_css.py
python3 scripts/build_site.py --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar
python3 scripts/build_issue.py --date 2026-05-26 --draft --limit 10 --base-path /coma-artist-radar
python3 scripts/build_tag_pages.py --base-path /coma-artist-radar
```

`build_site` automatically calls `build_css` internally — the CSS file is written
alongside the HTML pages but is not counted in `pages_written` or `output_files`.

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 17 — Generated issue covers / visual themes

Each issue gets an auto-generated SVG cover image (1200×630) based on its dominant
music tag or aesthetic. No external images, no external CDN, no raster dependencies —
pure inline SVG rendered at build time.

### Visual themes

Defined in `data/visual_themes.yaml`. Each theme maps a music style to a colour
palette and a decorative motif:

| Theme ID | Label | Motif |
|----------|-------|-------|
| `default` | Default | radio_tower |
| `surf` | Surf | reverb_wave |
| `instrumental_surf` | Instrumental Surf | reverb_wave |
| `psychobilly` | Psychobilly | lacquer_graves |
| `rockabilly` | Rockabilly | lacquer_graves |
| `jazz` | Jazz | smoke_signal |
| `jazz_noir` | Jazz Noir | midnight_window |
| `dark_jazz` | Dark Jazz | midnight_window |
| `blues` | Blues | dusty_vinyl |
| `country` | Country | dusty_vinyl |
| `ghost_americana` | Ghost Americana | desert_twang |
| `retro_future` | Retro Future | atomic_orbit |
| `lounge_noir` | Lounge Noir | midnight_window |

Main tag is detected automatically from item `matched_tags`, with priority:
aesthetic > genre > subgenre > content_type > editorial > most frequent.

### Generate a cover manually

```bash
python3 scripts/generate_issue_cover.py --date 2026-05-26 --lang all
python3 scripts/generate_issue_cover.py --date 2026-05-26 --lang en --main-tag surf
python3 scripts/generate_issue_cover.py --date 2026-05-26 --dry-run --json
```

Covers are written to `dist/assets/covers/issues/YYYY-MM-DD/cover-{lang}.svg`.

### Build issue with cover (default)

```bash
python3 scripts/build_issue.py --date 2026-05-26 --draft --limit 10 --base-path /coma-artist-radar
```

Cover generation is on by default. To skip:

```bash
python3 scripts/build_issue.py --date 2026-05-26 --no-cover
```

### Daily draft with cover

```bash
python3 scripts/build_daily_draft.py --date 2026-05-26 --base-path /coma-artist-radar
# Skip cover generation:
python3 scripts/build_daily_draft.py --date 2026-05-26 --no-cover
```

### Run tests

```bash
python3 -m pytest -q tests
```

---

## Stage 18 — Telegram dry-run packaging

Produces a short Telegram announcement for each issue without sending anything.
Real sending via Bot API will be added in a later stage.

### What is generated

A plain-text post saved to `reports/telegram/YYYY-MM-DD.{lang}.txt`:

- Ukrainian (`uk`): opens with "Сьогодні в полі:", closes with "Повний випуск: URL"
- English (`en`): opens with "In the field today:", closes with "Full issue: URL"
- Up to 3 items listed with music genre tags (editorial tags excluded)
- Capped at 1024 characters by default; item list is trimmed to fit
- Cover SVG URL included in the JSON summary when the cover exists

`reports/telegram/*.txt` are excluded from git (local artifacts only).

### Build Telegram draft

```bash
python scripts/build_telegram_draft.py --date 2026-05-26 --lang uk
python scripts/build_telegram_draft.py --date 2026-05-26 --lang en
```

Both commands write to `reports/telegram/` and print a JSON summary.

### Send wrapper (dry-run only)

```bash
python scripts/send_telegram.py --date 2026-05-26 --lang uk --dry-run
```

Passing `--send` exits immediately with an error — real sending is not yet implemented.

### Build with Telegram draft via daily pipeline

```bash
python scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar --telegram-dry-run
```

The `--telegram-dry-run` flag runs the UK draft after the issue/site build.
The pipeline summary will include a `telegram_summary` key.
Without the flag the Telegram step is skipped entirely — existing workflows are unaffected.

### Real sending (future)

Real delivery will use the Telegram Bot API via `TELEGRAM_BOT_TOKEN` secret.
No token is read or required at this stage.

### Run tests

```bash
python -m pytest -q tests
```

---

## Stage 19 — Layout / design polish v2 — modernist radio bulletin

Design direction: **Swiss International Style / Bauhaus / mid-century editorial**.
The site should feel like a bilingual music radar programme guide or record-sleeve index, not a SaaS dashboard.

### Design principles applied

- Strong grid with disciplined spacing rhythm (CSS custom property tokens)
- Asymmetric composition with a left-panel brand mark and gradient rule
- Large typographic hierarchy — `clamp()`-based hero title, label caps for section markers
- Horizontal rules as editorial dividers (`.section-rule`, `.brand-line`)
- Geometric item numbering via CSS counters (`.item-number::before`)
- Palette: deep tobacco `#1a1510`, aged paper `#ede0c4`, burnt orange `#c47820`, muted turquoise `#3a8080` — no pure black, no pure white
- No external CDN, no JS, no Google Fonts

### Pages to inspect

| Page | URL pattern |
|---|---|
| Language chooser | `dist/index.html` |
| Latest issues | `dist/en/index.html`, `dist/uk/index.html` |
| Archive | `dist/en/archive.html` |
| Issue | `dist/en/issues/YYYY-MM-DD.html` |
| Tag index | `dist/en/tags/index.html` |
| Tag page | `dist/en/tags/country.html` |

### Build the site

```bash
python scripts/build_css.py
python scripts/build_daily_draft.py --date 2026-05-26 --fetch-limit 5 --issue-limit 10 --base-url https://deisign.github.io/coma-artist-radar --base-path /coma-artist-radar --telegram-dry-run
```

### Run tests

```bash
python -m pytest -q tests
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

# coma.fm Radar

Working repository for **coma.fm Radar**: a bilingual EN/UK music radar and editorial digest around the coma.fm music field.

Current implemented stage: **Stage 15 — Design system**.

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

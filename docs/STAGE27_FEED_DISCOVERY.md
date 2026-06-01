# Stage 27E — Feed Discovery for Longtail Source Candidates

## Purpose

Stage 27E checks 132 longtail source candidates (produced by Stage 27D) for
RSS/Atom feeds, validates any feeds found, deduplicates them against the
existing source registry, and writes a review CSV for human editorial decision.

**What this stage does NOT do:**
- It does not modify `data/sources_music.yaml` (that remains a human editorial step).
- It does not import sources into the database.
- It does not make any destructive changes.

The output is a CSV in `reports/` that an editor reviews before manually
adding any domain to `data/sources_music.yaml`.

---

## Input

`reports/stage27e_feed_check_candidates.csv`

132 domains selected from Stage 27D longtail buckets:

| Bucket | Description |
|--------|-------------|
| `niche_blog_fanzine` | Fanzines and niche music blogs |
| `niche_site` | Niche music websites (reviews, interviews) |
| `label_or_record_shop` | Independent labels and record shops |
| `label_bandcamp` | Label pages on Bandcamp |
| `archive` | Music archive sites |

Only rows with `feed_check_action == check_feed` are probed. Rows with
`manual_review` are passed through with action `MANUAL_REVIEW`.

---

## Output

`reports/stage27e_feed_discovery.csv`

Key columns:

| Column | Meaning |
|--------|---------|
| `site_url` | Resolved homepage URL (after http/https attempt) |
| `site_status` | HTTP status of homepage fetch |
| `detected_feed_url` | First valid RSS/Atom feed URL found |
| `feed_status` | HTTP status when fetching the feed |
| `feed_title` | Title extracted from the feed XML |
| `feed_type` | `rss`, `atom`, or `rdf` |
| `already_in_sources` | `yes` if domain/feed already in `sources_music.yaml` |
| `existing_source_id` | Source ID if already registered |
| `suggested_source_id` | Proposed `id` slug for `sources_music.yaml` |
| `suggested_name` | Proposed human-readable name |
| `suggested_source_type` | Proposed `source_type` (blog, label, archive, …) |
| `suggested_priority` | `high`, `medium`, `low`, or `manual_review` |
| `suggested_import_action` | Editorial decision hint (see below) |
| `notes` | Fetch warnings, platform notes |

### `suggested_import_action` values

| Value | Meaning |
|-------|---------|
| `IMPORT_READY` | Valid feed found; not yet in registry; likely worth adding |
| `REVIEW_FEED` | Feed found but warrants closer inspection (e.g., Bandcamp) |
| `NO_FEED_FOUND` | Site reachable but no feed found |
| `ALREADY_EXISTS` | Domain or feed already in `sources_music.yaml` |
| `MANUAL_REVIEW` | Site unreachable or feed check ambiguous |
| `ERROR` | Unhandled exception during processing |

### `suggested_priority` logic

| Value | Condition |
|-------|-----------|
| `high` | Niche bucket with a niche-genre keyword in the domain AND valid feed |
| `medium` | Niche blog/site or label with valid feed, no specific keyword |
| `low` | No feed found, or Bandcamp (limited RSS utility) |
| `manual_review` | Archive domains or unclear cases |

---

## How to run

### Dry-run first (no network calls)

```bash
python scripts/discover_source_feeds.py --dry-run --limit 10
```

### Small pilot (20 domains)

```bash
python scripts/discover_source_feeds.py \
  reports/stage27e_feed_check_candidates.csv \
  --limit 20 \
  --sleep 1 \
  --resume
```

Always use `--sleep 1` or more. The script fetches each domain's homepage and
tries up to ~10 feed URL candidates per domain.

### Resume a partial run

If the run is interrupted, restart with `--resume` to skip already-processed
domains and append new rows:

```bash
python scripts/discover_source_feeds.py \
  reports/stage27e_feed_check_candidates.csv \
  --sleep 1 \
  --resume
```

### Full 132-domain check

Only run after the pilot looks sane:

```bash
python scripts/discover_source_feeds.py \
  reports/stage27e_feed_check_candidates.csv \
  --sleep 1.5 \
  --resume
```

### Process a slice (offset + limit)

```bash
python scripts/discover_source_feeds.py --offset 50 --limit 30 --sleep 1
```

---

## Output interpretation

After a run, a compact JSON summary is printed:

```json
{
  "total_input": 132,
  "processed": 132,
  "feed_found": 45,
  "no_feed": 71,
  "already_exists": 12,
  "import_ready": 33,
  "errors": 4
}
```

Review the CSV with any spreadsheet tool, filtering on `suggested_import_action`:

1. **`IMPORT_READY`** — top candidates to add. Verify `feed_title` and
   `detected_feed_url` make sense, then add an entry to `data/sources_music.yaml`.
2. **`REVIEW_FEED`** — check the feed URL manually before deciding.
3. **`NO_FEED_FOUND`** — set aside unless the site has clear editorial value and
   you can find a feed another way.
4. **`ALREADY_EXISTS`** — no action needed.
5. **`MANUAL_REVIEW`** / **`ERROR`** — investigate individually.

---

## Adding a source to sources_music.yaml

`sources_music.yaml` is **not modified automatically**. After reviewing the
output CSV, copy the suggested fields into a new entry manually:

```yaml
- id: example_blog
  name: Example Blog
  site_url: https://example.com
  feed_url: https://example.com/feed/
  source_type: blog
  language: en
  region: us
  genre_tags:
    - surf
    - garage_rock
  priority: high
  active: true
  paywall: false
```

Run `python scripts/validate_sources.py` afterwards to confirm the entry is
structurally valid.

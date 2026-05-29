# Stage 27B — Artist-driven Source Discovery

## Purpose

Stage 27B grows the source base for coma.fm Radar by running targeted web searches
for each artist in `data/artists_registry.csv`, collecting the result URLs, and
ranking the discovered domains by recurrence and editorial relevance.

**What this stage does NOT do:**
- It does not modify `data/sources_music.yaml` (that is a human editorial step).
- It does not add feeds to the database or generate issues.
- It does not make any destructive changes.

The output is two CSV reports in `reports/` that a human editor reviews before
promoting any domain to an actual source.

---

## How to run

### Safe pilot (5 high-priority artists, 2 queries each)

```bash
python scripts/discover_artist_sources.py \
  --limit 5 \
  --priority high \
  --queries-per-artist 2 \
  --max-results-per-query 10 \
  --sleep 2 \
  --resume
```

Always use `--sleep 2` or more. The default provider is `duckduckgo` and requires `ddgs`; `duckduckgo_html` is available as a stdlib-only fallback.

### Dry-run first (no network calls)

```bash
python scripts/discover_artist_sources.py --dry-run --limit 10 --priority high
```

Shows which artists and queries would be fetched, and which are already cached.

### Weekend batch — top 100 high-priority artists

```bash
python scripts/discover_artist_sources.py \
  --limit 100 \
  --priority high \
  --queries-per-artist 3 \
  --max-results-per-query 10 \
  --sleep 3 \
  --resume
```

Estimated time: ~100 artists × 3 queries × 3 s = ~15 minutes.
All results are cached; you can interrupt and resume safely.

### Process medium-priority artists (offset past the first 100)

```bash
python scripts/discover_artist_sources.py \
  --limit 200 \
  --priority medium \
  --queries-per-artist 2 \
  --sleep 2 \
  --resume
```

### Resume after interruption

Just rerun the same command with `--resume`. Already-cached (artist, query) pairs
are loaded from `cache/artist_sources/` and do not hit the network.

```bash
python scripts/discover_artist_sources.py \
  --limit 100 --priority high --queries-per-artist 3 --sleep 3 --resume
```

---

## Reports

| Report | Description |
|---|---|
| `reports/artist_source_candidates.csv` | One row per search result: artist, query, URL, domain, title, snippet |
| `reports/domain_source_ranking.csv` | One row per domain: aggregated hits, score, source type, suggested action |

### Inspecting top domains

```bash
# Top 20 domains by score
head -21 reports/domain_source_ranking.csv

# Import candidates only
awk -F, '$NF=="IMPORT_CANDIDATE"' reports/domain_source_ranking.csv | head -20

# All non-skip domains
python -c "
import csv
with open('reports/domain_source_ranking.csv') as f:
    for r in csv.DictReader(f):
        if not r['suggested_action'].startswith('SKIP'):
            print(r['domain_score'].rjust(5), r['suggested_action'].ljust(20), r['domain'])
" | head -30
```

---

## Suggested actions explained

| Action | Meaning |
|---|---|
| `IMPORT_CANDIDATE` | High-scoring editorial domain — worth adding to `sources_music.yaml` |
| `REVIEW` | Moderate score — check manually before adding |
| `SKIP_GENERIC` | Low score, not worth importing |
| `SKIP_SOCIAL` | Facebook, Instagram, X, Reddit, etc. |
| `SKIP_SHOP` | Amazon, eBay, merch stores |
| `SKIP_LYRICS` | Genius, AZLyrics, etc. |
| `SKIP_WIKI` | Wikipedia, Wikidata, fan wikis |
| `SKIP_VIDEO_ONLY` | YouTube, Vimeo |
| `SKIP_FORUM_OR_TORRENT` | Reddit forums, torrent sites, 4chan |

---

## Domain scoring formula

```
domain_score =
    unique_artists × 5
  + high_priority_artist_hits × 3
  + hits_total
  + source_type_bonus
```

Source type bonuses: `magazine=+10`, `label=+8`, `radio=+7`, `archive=+6`,
`blog=+5`, `database=+3`, `unknown=0`, `wiki=-30`, `video=-20`,
`lyrics=-50`, `social=-100`, `shop=-100`, `forum=-100`.

Skip-category domains always receive their SKIP action regardless of score.

---

## Cache

Results are cached in `cache/artist_sources/{artist-slug}/{query-slug}.json`.
Each file stores the provider name, query, fetch timestamp, and raw results.

The cache is permanent until manually deleted. This makes large batches resumable
and prevents redundant network requests across sessions.

---

## Provider

The default provider is `duckduckgo` and requires the optional `ddgs` package. It needs no API key.

A stdlib-only fallback provider is available as `--provider duckduckgo_html`; it scrapes DuckDuckGo's HTML results page and is more likely to hit bot-detection. Use `--sleep 2` or more to respect rate limits.

For tests or offline validation, use `--provider fake` which returns deterministic
synthetic results without any network calls.

```bash
# Validate script syntax and fake-provider output
python scripts/discover_artist_sources.py --dry-run --limit 3 --provider fake
```

---

## Workflow

```
artists_registry.csv
    ↓ load_artists()
artist list
    ↓ generate_queries()
(artist, query) pairs
    ↓ DDGSProvider or DuckDuckGoHTMLProvider / cache
raw search results → cache/artist_sources/
    ↓ aggregate_domains()
reports/artist_source_candidates.csv
reports/domain_source_ranking.csv
    ↓ human review
sources_music.yaml   ← edited manually, not by this script
```

#!/usr/bin/env python3
"""Stage27B: Artist-driven source discovery for coma.fm Radar.

Reads artists from data/artists_registry.csv, generates search queries,
collects results (cached), and produces two CSV reports:

  reports/artist_source_candidates.csv
  reports/domain_source_ranking.csv

Usage:
    python scripts/discover_artist_sources.py --dry-run --limit 5
    python scripts/discover_artist_sources.py --limit 10 --priority high --sleep 2
    python scripts/discover_artist_sources.py --resume --limit 100 --priority high

sources_music.yaml is NOT modified by this script.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── paths ──────────────────────────────────────────────────────────────────────
ARTISTS_CSV = _REPO_ROOT / "data" / "artists_registry.csv"
CACHE_DIR = _REPO_ROOT / "cache" / "artist_sources"
REPORT_CANDIDATES = _REPO_ROOT / "reports" / "artist_source_candidates.csv"
REPORT_DOMAINS = _REPO_ROOT / "reports" / "domain_source_ranking.csv"

# ── query templates ────────────────────────────────────────────────────────────
# All templates include a music/band/musician disambiguator to avoid pulling
# results for films, athletes, or public figures who share the artist's name.
QUERY_TEMPLATES = [
    '"{artist}" music album review',
    '"{artist}" band interview',
    '"{artist}" reissue music',
    '"{artist}" musician interview',
    '"{artist}" live session music',
    '"{artist}" discography review',
    '"{artist}" rockabilly OR psychobilly OR surf OR americana OR blues',
]

# ── CSV fields ─────────────────────────────────────────────────────────────────
CANDIDATE_FIELDS = [
    "artist", "artist_priority", "track_count", "query",
    "result_rank", "title", "url", "domain", "snippet",
    "provider", "cached", "fetched_at",
]

DOMAIN_FIELDS = [
    "domain", "hits_total", "unique_artists", "high_priority_artist_hits",
    "sample_artists", "sample_titles", "sample_urls",
    "domain_score", "source_type_guess", "suggested_action",
]

# ── domain classification data ─────────────────────────────────────────────────
_SOCIAL_DOMAINS = frozenset({
    "facebook.com", "instagram.com", "tiktok.com", "twitter.com", "x.com",
    "reddit.com", "threads.net", "snapchat.com", "tumblr.com", "myspace.com",
    "vk.com", "linkedin.com",
    # CIS social networks / platforms
    "ok.ru", "mail.ru", "my.mail.ru",
    # Social aggregators / Q&A — not editorial sources
    "pinterest.com", "quora.com",
})

_LYRICS_DOMAINS = frozenset({
    "genius.com", "songfacts.com", "azlyrics.com", "lyrics.com",
    "metrolyrics.com", "lyricsfreak.com", "musixmatch.com", "letras.mus.br",
    "absolutelyrics.com", "sing365.com",
})

_VIDEO_DOMAINS = frozenset({
    "youtube.com", "youtu.be", "vimeo.com", "dailymotion.com",
})

_SHOP_DOMAINS = frozenset({
    "etsy.com", "walmart.com", "target.com", "bestbuy.com",
    "merchbar.com", "redbubble.com",
    "juno.co.uk",  # record retail
})
# Amazon and eBay are matched by substring in classify_domain to catch regional
# ccTLDs (amazon.ca, ebay.de) and subdomains (music.amazon.com, music.amazon.co.uk).

_WIKI_DOMAINS = frozenset({
    "wikipedia.org", "wikidata.org", "wikimedia.org",
    "wikia.com", "fandom.com", "tvtropes.org",
})

_TORRENT_PATTERNS = (
    "piratebay", "1337x.to", "rutracker", "torrentz", "kickasstorrents",
    "4chan.org", "limetorrents",
)

_DATABASE_DOMAINS = frozenset({
    "discogs.com", "musicbrainz.org", "rateyourmusic.com", "allmusic.com",
    "last.fm", "setlist.fm", "secondhandsongs.com",
    # Entertainment/media databases — reference only, not editorial music sources
    "imdb.com",
    # User-rated/aggregator music databases
    "albumoftheyear.org", "besteveralbums.com", "viberate.com",
    "grokipedia.com",
})

# Streaming/discovery platforms and music aggregator/piracy sites:
# present in search results but not editorial sources. Always SKIP_GENERIC.
_STREAMING_DOMAINS = frozenset({
    "music.apple.com", "itunes.apple.com", "shazam.com",
    "reverbnation.com", "soundcloud.com", "tidal.com",
    "deezer.com", "pandora.com", "napster.com", "music.youtube.com",
    "bandcamp.com",
    # Russian/CIS music aggregators and unlicensed streaming sites
    "musify.club", "hitmos.me", "lightaudio.ru", "sonichits.com",
    # Search engine with music pages — not editorial
    "yandex.ru", "yandex.com",
})
# Spotify has subdomain variants (open.spotify.com, etc.) — matched by substring.
_STREAMING_PATTERNS = ("spotify.com",)

_RADIO_DOMAINS = frozenset({
    "kexp.org", "wfmu.org", "kcrw.com", "kpfa.org", "wxpn.org", "wnyc.org",
    "bbc.co.uk", "bbc.com",
})

# Keywords that appear as substrings in known editorial magazine domains.
# allmusic.com is classified as database (not magazine) — do not include here.
_MAGAZINE_KEYWORDS = frozenset({
    "pitchfork", "rollingstone", "stereogum", "spinmagazine", "thequietus",
    "uncut", "mojomag", "mojo4music", "thewire", "popmatters", "exclaim",
    "treblezine", "slantmagazine", "blurt", "magnetmagazine", "no-depression",
    "nodepression", "americanasongwriter", "countryuniverse", "savingcountrymusic",
    "honkytonkconfidential", "pastemagazine", "pastemusic", "consequenceofsound",
    "thelineofbestfit", "lineofbestfit",
})

_BLOG_PLATFORM_PATTERNS = ("blogspot.com", "wordpress.com", "substack.com", "medium.com")

# Source type → score bonus (negative = penalty)
_SOURCE_TYPE_BONUS: dict[str, int] = {
    "magazine": 10,
    "blog": 5,
    "label": 8,
    "radio": 7,
    "archive": 6,
    "database": 3,
    "streaming": -30,
    "unknown": 0,
    "social": -100,
    "lyrics": -50,
    "shop": -100,
    "wiki": -30,
    "video": -20,
    "forum": -100,
}

# Skip-category source types → forced suggested action (overrides score)
_SKIP_ACTIONS: dict[str, str] = {
    "social": "SKIP_SOCIAL",
    "lyrics": "SKIP_LYRICS",
    "shop": "SKIP_SHOP",
    "wiki": "SKIP_WIKI",
    "video": "SKIP_VIDEO_ONLY",
    "forum": "SKIP_FORUM_OR_TORRENT",
    "streaming": "SKIP_GENERIC",
}

# Only these editorial source types are eligible for IMPORT_CANDIDATE.
# Every other type (database, unknown, streaming, social, …) is capped at REVIEW or lower.
# This prevents unknown high-scoring domains from becoming import candidates.
_IMPORT_ELIGIBLE_TYPES = frozenset({"magazine", "blog", "label", "radio", "archive"})


# ── utilities ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a short filesystem-safe slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text).strip("-")
    return text[:80]


def normalize_domain(url: str) -> str:
    """Extract and normalize the domain from a URL."""
    if not url:
        return ""
    try:
        if "://" not in url:
            url = "https://" + url
        # Simple extraction without urllib.parse to avoid edge-case failures
        host = url.split("://", 1)[1].split("/")[0].split("?")[0].split("#")[0]
        host = host.lower().split(":")[0]  # strip port
        for prefix in ("www.", "m.", "mobile.", "amp."):
            if host.startswith(prefix):
                host = host[len(prefix):]
        return host
    except Exception:
        return ""


def classify_domain(domain: str) -> tuple[str, str]:
    """Return (source_type, suggested_action) for a domain.

    source_type: magazine | blog | label | radio | archive | database |
                 streaming | social | lyrics | video | shop | wiki | forum | unknown
    suggested_action: one of the IMPORT/REVIEW/SKIP_* codes
    """
    d = domain.lower()

    if d in _SOCIAL_DOMAINS:
        return "social", "SKIP_SOCIAL"

    if d in _LYRICS_DOMAINS:
        return "lyrics", "SKIP_LYRICS"

    if d in _VIDEO_DOMAINS:
        return "video", "SKIP_VIDEO_ONLY"

    # Streaming/discovery platforms (Spotify, Apple Music, Shazam, etc.)
    if d in _STREAMING_DOMAINS or any(p in d for p in _STREAMING_PATTERNS):
        return "streaming", "SKIP_GENERIC"

    # Shop: explicit set + substring checks for Amazon/eBay in all regional and
    # subdomain forms (amazon.ca, music.amazon.com, ebay.de, etc.)
    if d in _SHOP_DOMAINS or re.search(r'(?:^|\.)(amazon|ebay)\.', d):
        return "shop", "SKIP_SHOP"

    if any(w in d for w in _WIKI_DOMAINS):
        return "wiki", "SKIP_WIKI"

    if any(p in d for p in _TORRENT_PATTERNS):
        return "forum", "SKIP_FORUM_OR_TORRENT"

    # Reference/database domains — useful for discovery, not editorial import.
    # compute_suggested_action caps these at REVIEW.
    if d in _DATABASE_DOMAINS:
        return "database", "REVIEW"

    if "archive.org" in d:
        return "archive", "IMPORT_CANDIDATE"

    if d in _RADIO_DOMAINS:
        return "radio", "IMPORT_CANDIDATE"

    if any(m in d for m in _MAGAZINE_KEYWORDS):
        return "magazine", "IMPORT_CANDIDATE"

    if any(b in d for b in _BLOG_PLATFORM_PATTERNS):
        return "blog", "REVIEW"

    # Heuristic: domains containing "records" or "label" sub-segment
    if re.search(r"(records|recordings|label)\.", d):
        return "label", "REVIEW"

    return "unknown", "REVIEW"


def compute_domain_score(
    hits_total: int,
    unique_artists: int,
    high_priority_hits: int,
    source_type: str,
) -> int:
    """Deterministic domain scoring formula.

    score = unique_artists * 5
          + high_priority_artist_hits * 3
          + hits_total
          + source_type_bonus
    """
    bonus = _SOURCE_TYPE_BONUS.get(source_type, 0)
    return unique_artists * 5 + high_priority_hits * 3 + hits_total + bonus


def compute_suggested_action(
    source_type: str, score: int, unique_artists: int = 0
) -> str:
    """Map source_type + score + unique_artists to a suggested action string.

    Rules (in priority order):
    1. Skip-category types always return their SKIP_* action regardless of score.
    2. Only editorial types in _IMPORT_ELIGIBLE_TYPES (magazine, blog, label,
       radio, archive) can reach IMPORT_CANDIDATE. Everything else — database,
       unknown, streaming, etc. — is capped at REVIEW or lower.
    3. IMPORT_CANDIDATE also requires unique_artists >= 2 to prevent name-collision
       false positives (e.g. "The Rolling Stones" alone boosting rollingstone.com).
    """
    if source_type in _SKIP_ACTIONS:
        return _SKIP_ACTIONS[source_type]
    if source_type not in _IMPORT_ELIGIBLE_TYPES:
        return "REVIEW" if score >= 5 else "SKIP_GENERIC"
    if score >= 20 and unique_artists >= 2:
        return "IMPORT_CANDIDATE"
    if score >= 5:
        return "REVIEW"
    return "SKIP_GENERIC"


# ── artist loading ─────────────────────────────────────────────────────────────

def load_artists(
    csv_path: Path,
    limit: int = 10,
    offset: int = 0,
    priority: str = "all",
    min_track_count: int = 0,
) -> list[dict]:
    """Load and filter artists from the registry CSV."""
    artists = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("ignore", "false").strip().lower() == "true":
                continue
            row_priority = row.get("monitor_priority", "").strip()
            if priority != "all" and row_priority != priority:
                continue
            try:
                tc = int(row.get("track_count", 0) or 0)
            except ValueError:
                tc = 0
            if tc < min_track_count:
                continue
            name = row.get("artist_canonical") or row.get("artist_raw") or ""
            name = name.strip()
            if not name:
                continue
            artists.append({
                "artist": name,
                "priority": row_priority,
                "track_count": tc,
            })

    artists = artists[offset:]
    if limit > 0:
        artists = artists[:limit]
    return artists


# ── query generation ──────────────────────────────────────────────────────────

def generate_queries(artist: str, templates: list[str]) -> list[str]:
    """Generate search queries for an artist using the given templates."""
    return [t.format(artist=artist) for t in templates]


# ── search provider abstraction ───────────────────────────────────────────────

class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    def search(self, query: str, max_results: int = 10) -> list[dict]:
        """Return list of result dicts: {rank, title, url, domain, snippet}."""


class FakeSearchProvider(SearchProvider):
    """Deterministic fake provider — for tests and dry validation only."""
    name = "fake"

    def __init__(self, results_map: dict[str, list[dict]] | None = None):
        self._map = results_map or {}

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        if query in self._map:
            return self._map[query][:max_results]
        return self._default_results(query, max_results)

    def _default_results(self, query: str, n: int) -> list[dict]:
        m = re.search(r'"([^"]+)"', query)
        artist_name = m.group(1) if m else "artist"
        slug = slugify(artist_name)
        return [
            {
                "rank": i + 1,
                "title": f"Result {i + 1} for {artist_name}",
                "url": f"https://example-music-{i + 1}.com/{slug}",
                "domain": f"example-music-{i + 1}.com",
                "snippet": f"Snippet {i + 1} about {artist_name}.",
            }
            for i in range(min(n, 5))
        ]


class DDGSProvider(SearchProvider):
    """Search via the ddgs/duckduckgo_search library — no API key required.

    Install with: pip install ddgs
    """
    name = "duckduckgo"

    def __init__(self) -> None:
        self._DDGS = _import_ddgs()

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        # Strip quotes around the artist name — the library handles relevance
        # internally and strict-quote syntax can suppress results.
        clean = re.sub(r'"([^"]+)"', r'\1', query)
        try:
            with self._DDGS() as ddgs:
                raw = list(ddgs.text(clean, max_results=max_results))
        except Exception as exc:
            raise RuntimeError(f"DDGS search failed for {query!r}: {exc}") from exc

        results: list[dict] = []
        for i, r in enumerate(raw):
            url = r.get("href", "")
            domain = normalize_domain(url)
            if not url or not domain:
                continue
            results.append({
                "rank": i + 1,
                "title": r.get("title", ""),
                "url": url,
                "domain": domain,
                "snippet": r.get("body", ""),
            })
        return results


def _import_ddgs():
    """Import DDGS class from ddgs or duckduckgo_search (whichever is installed)."""
    import warnings
    # Prefer the newer package name
    try:
        from ddgs import DDGS
        return DDGS
    except ImportError:
        pass
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            from duckduckgo_search import DDGS
        return DDGS
    except ImportError:
        raise RuntimeError(
            "No DuckDuckGo search library found.\n"
            "Install with:  pip install ddgs\n"
            "Or use:        --provider fake   (for testing without network)\n"
            "Or use:        --provider duckduckgo_html  (stdlib-only HTML scraper)"
        )


class DuckDuckGoHTMLProvider(SearchProvider):
    """Scrape DuckDuckGo HTML results — stdlib only, no extra packages.

    Note: may be blocked by bot-detection on some server environments.
    Prefer the 'duckduckgo' provider (pip install ddgs) when possible.
    """
    name = "duckduckgo_html"

    _BASE = "https://html.duckduckgo.com/html/"
    _UA = "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) Gecko/20100101 Firefox/120.0"
    _TIMEOUT = 15

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        params = urlencode({"q": query, "kl": "us-en"})
        url = f"{self._BASE}?{params}"
        req = Request(url, headers={
            "User-Agent": self._UA,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        })
        try:
            with urlopen(req, timeout=self._TIMEOUT) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except URLError as exc:
            raise RuntimeError(
                f"DuckDuckGo HTML request failed: {exc}\n"
                "Check your network connection. If bot-detected, use:\n"
                "  pip install ddgs  # then --provider duckduckgo"
            ) from exc

        results = _parse_ddg_html(html)
        if not results:
            print(
                f"  [warn] No results from DuckDuckGo HTML for: {query!r}\n"
                "  Bot-detection likely. Use: pip install ddgs  then --provider duckduckgo",
                file=sys.stderr,
            )
        return results[:max_results]


def _extract_ddg_url(href: str) -> str:
    """Decode the actual target URL from a DuckDuckGo redirect href."""
    if not href:
        return ""
    if "uddg=" in href:
        try:
            idx = href.index("uddg=") + 5
            encoded = href[idx:].split("&")[0]
            return unquote(encoded)
        except Exception:
            pass
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    return href


def _parse_ddg_html(html: str) -> list[dict]:
    """Parse result links and snippets from DuckDuckGo HTML page."""
    # Match the full <a> tag with class containing "result__a"
    full_tags = re.findall(
        r"<a\b[^>]*result__a[^>]*>.*?</a>",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    snippets_raw = re.findall(
        r"<a\b[^>]*result__snippet[^>]*>(.*?)</a>",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    snippets = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets_raw]

    results: list[dict] = []
    for i, tag in enumerate(full_tags):
        href_m = re.search(r'href="([^"]*)"', tag, re.IGNORECASE)
        if not href_m:
            continue
        url = _extract_ddg_url(href_m.group(1))
        if not url or not url.startswith("http"):
            continue

        # Strip outer <a ...> and </a> to get inner content
        inner = re.sub(r"^<a\b[^>]*>", "", tag, flags=re.IGNORECASE)
        inner = re.sub(r"</a>$", "", inner, flags=re.IGNORECASE)
        title = re.sub(r"<[^>]+>", "", inner).strip()
        if not title:
            continue

        domain = normalize_domain(url)
        if not domain:
            continue

        results.append({
            "rank": len(results) + 1,
            "title": title,
            "url": url,
            "domain": domain,
            "snippet": snippets[i] if i < len(snippets) else "",
        })

    return results


def get_provider(name: str) -> SearchProvider:
    """Instantiate a provider by name; fail clearly if unavailable."""
    if name == "duckduckgo":
        return DDGSProvider()
    if name == "duckduckgo_html":
        return DuckDuckGoHTMLProvider()
    if name == "fake":
        return FakeSearchProvider()
    raise ValueError(
        f"Unknown provider: {name!r}. Available: duckduckgo, duckduckgo_html, fake"
    )


# ── cache ──────────────────────────────────────────────────────────────────────

def cache_path(artist: str, query: str, cache_dir: Path = CACHE_DIR) -> Path:
    return cache_dir / slugify(artist) / f"{slugify(query)}.json"


def load_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── aggregation ───────────────────────────────────────────────────────────────

def aggregate_domains(candidates: list[dict]) -> list[dict]:
    """Build domain ranking rows from flat candidate list."""
    domain_data: dict[str, dict] = defaultdict(lambda: {
        "hits_total": 0,
        "artists": set(),
        "high_priority_hits": 0,
        "titles": [],
        "urls": [],
    })

    for row in candidates:
        d = row.get("domain", "")
        if not d:
            continue
        dd = domain_data[d]
        dd["hits_total"] += 1
        dd["artists"].add(row["artist"])
        if row.get("artist_priority") == "high":
            dd["high_priority_hits"] += 1
        title = row.get("title", "")
        if title and title not in dd["titles"]:
            dd["titles"].append(title)
        url = row.get("url", "")
        if url and url not in dd["urls"]:
            dd["urls"].append(url)

    rows = []
    for domain, dd in domain_data.items():
        source_type, _ = classify_domain(domain)
        hits = dd["hits_total"]
        unique = len(dd["artists"])
        hi_hits = dd["high_priority_hits"]
        score = compute_domain_score(hits, unique, hi_hits, source_type)
        action = compute_suggested_action(source_type, score, unique_artists=unique)
        rows.append({
            "domain": domain,
            "hits_total": hits,
            "unique_artists": unique,
            "high_priority_artist_hits": hi_hits,
            "sample_artists": "; ".join(sorted(dd["artists"])[:5]),
            "sample_titles": "; ".join(dd["titles"][:3]),
            "sample_urls": "; ".join(dd["urls"][:3]),
            "domain_score": score,
            "source_type_guess": source_type,
            "suggested_action": action,
        })

    rows.sort(key=lambda r: -r["domain_score"])
    return rows


# ── report writing ────────────────────────────────────────────────────────────

def write_candidates_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_domain_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DOMAIN_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Stage27B: Artist-driven source discovery for coma.fm Radar"
    )
    p.add_argument("--limit", type=int, default=10,
                   help="Max artists to process (default: 10)")
    p.add_argument("--offset", type=int, default=0,
                   help="Skip first N artists in filtered list (default: 0)")
    p.add_argument("--priority", choices=["high", "medium", "low", "all"], default="all",
                   help="Filter by monitor_priority field (default: all)")
    p.add_argument("--min-track-count", type=int, default=0, dest="min_track_count",
                   help="Skip artists below this track count (default: 0)")
    p.add_argument("--queries-per-artist", type=int, default=3, dest="queries_per_artist",
                   help="How many query templates to use per artist (default: 3)")
    p.add_argument("--max-results-per-query", type=int, default=10, dest="max_results_per_query",
                   help="Max search results per query (default: 10)")
    p.add_argument("--sleep", type=float, default=2.0,
                   help="Seconds to sleep between provider calls (default: 2)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run",
                   help="Print what would be done without making any provider calls")
    p.add_argument("--resume", action="store_true",
                   help="Reuse cached results; skip provider calls for completed (artist, query) pairs")
    p.add_argument("--provider", default="duckduckgo",
                   choices=["duckduckgo", "duckduckgo_html", "fake"],
                   help="Search provider (default: duckduckgo; requires: pip install ddgs)")
    p.add_argument("--candidates-report", type=Path, default=REPORT_CANDIDATES,
                   dest="candidates_report")
    p.add_argument("--domains-report", type=Path, default=REPORT_DOMAINS,
                   dest="domains_report")
    p.add_argument("--cache-dir", type=Path, default=CACHE_DIR, dest="cache_dir")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    templates = QUERY_TEMPLATES[: args.queries_per_artist]
    artists = load_artists(
        ARTISTS_CSV,
        limit=args.limit,
        offset=args.offset,
        priority=args.priority,
        min_track_count=args.min_track_count,
    )

    if not artists:
        print(json.dumps({"status": "no_artists_matched", "candidates": 0, "domains": 0}))
        return 0

    if args.dry_run:
        print(f"[dry-run] {len(artists)} artists × {len(templates)} queries = "
              f"{len(artists) * len(templates)} calls (sleep={args.sleep}s)")
        for a in artists[:5]:
            print(f"  {a['artist']} ({a['priority']}, {a['track_count']} tracks)")
            for q in generate_queries(a["artist"], templates):
                cpath = cache_path(a["artist"], q, args.cache_dir)
                state = "CACHED" if cpath.exists() else "would fetch"
                print(f"    [{state}] {q!r}")
        if len(artists) > 5:
            print(f"  ... and {len(artists) - 5} more")
        print(json.dumps({
            "status": "dry_run",
            "artists": len(artists),
            "queries_per_artist": len(templates),
            "provider": args.provider,
        }))
        return 0

    provider = get_provider(args.provider)
    print(
        f"[stage27b] provider={provider.name} artists={len(artists)} "
        f"queries_per_artist={len(templates)} sleep={args.sleep}s",
        flush=True,
    )

    candidate_rows: list[dict] = []
    stats: dict[str, int] = {
        "artists_processed": 0,
        "cache_hits": 0,
        "provider_calls": 0,
        "results_collected": 0,
        "errors": 0,
    }
    first_provider_call = True

    for artist_info in artists:
        artist = artist_info["artist"]
        priority = artist_info["priority"]
        track_count = artist_info["track_count"]
        queries = generate_queries(artist, templates)

        for query in queries:
            cpath = cache_path(artist, query, args.cache_dir)
            cached_data = load_cache(cpath)

            if cached_data is not None:
                results = cached_data.get("results", [])
                fetched_at = cached_data.get("fetched_at", "")
                prov_name = cached_data.get("provider", provider.name)
                was_cached = True
                stats["cache_hits"] += 1
            else:
                if first_provider_call:
                    first_provider_call = False
                else:
                    time.sleep(args.sleep)
                try:
                    results = provider.search(query, max_results=args.max_results_per_query)
                    fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                    prov_name = provider.name
                    was_cached = False
                    stats["provider_calls"] += 1
                    save_cache(cpath, {
                        "provider": prov_name,
                        "query": query,
                        "fetched_at": fetched_at,
                        "results": results,
                    })
                except Exception as exc:
                    print(f"  [error] {artist!r} / {query!r}: {exc}", file=sys.stderr)
                    stats["errors"] += 1
                    continue

            for r in results:
                domain = r.get("domain") or normalize_domain(r.get("url", ""))
                candidate_rows.append({
                    "artist": artist,
                    "artist_priority": priority,
                    "track_count": track_count,
                    "query": query,
                    "result_rank": r.get("rank", ""),
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "domain": domain,
                    "snippet": r.get("snippet", ""),
                    "provider": prov_name,
                    "cached": was_cached,
                    "fetched_at": fetched_at,
                })
                stats["results_collected"] += 1

        stats["artists_processed"] += 1
        print(f"  done: {artist!r} ({priority}, {track_count} tracks)", flush=True)

    write_candidates_csv(candidate_rows, args.candidates_report)
    domain_rows = aggregate_domains(candidate_rows)
    write_domain_csv(domain_rows, args.domains_report)

    summary = {
        "status": "ok",
        **stats,
        "candidate_rows": len(candidate_rows),
        "domains_found": len(domain_rows),
        "import_candidates": sum(1 for r in domain_rows if r["suggested_action"] == "IMPORT_CANDIDATE"),
        "review": sum(1 for r in domain_rows if r["suggested_action"] == "REVIEW"),
        "reports": {
            "candidates": str(args.candidates_report),
            "domains": str(args.domains_report),
        },
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

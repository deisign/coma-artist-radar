#!/usr/bin/env python3
"""Build a static bilingual HTML issue from scored items in coma_radar.sqlite.

Usage:
    python3 scripts/build_issue.py --date 2026-05-25 --draft --limit 10
    python3 scripts/build_issue.py --date 2026-05-25 --lang uk --draft --limit 10
    python3 scripts/build_issue.py --date 2026-05-25
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_DB = _REPO_ROOT / "data" / "coma_radar.sqlite"
DEFAULT_TAGS = _REPO_ROOT / "data" / "tags.yaml"
DEFAULT_THEMES = _REPO_ROOT / "data" / "visual_themes.yaml"
DEFAULT_TEMPLATE = _REPO_ROOT / "templates" / "issue.html.j2"
DEFAULT_CONTENT_DIR = _REPO_ROOT / "content" / "issues"
DEFAULT_DIST_DIR = _REPO_ROOT / "dist"
DEFAULT_MIN_SCORE = 30
DEFAULT_LIMIT = 50
DEFAULT_MAX_PER_SOURCE = 3
DEFAULT_MAX_SOURCE_ITEMS = 2
DEFAULT_MAX_ARTIST_ITEMS = 2

def normalize_base_path(path: str) -> str:
    """Normalize base_path: '' or '/' -> '', 'foo' -> '/foo', '/foo/' -> '/foo'."""
    path = path.strip()
    if not path or path == "/":
        return ""
    if not path.startswith("/"):
        path = "/" + path
    return path.rstrip("/")


_LOCALE: dict[str, dict[str, str]] = {
    "en": {
        "heading": "coma.fm Radar",
        "intro": "A weekly digest of music from the coma.fm field.",
        "draft_notice": "Draft — not published",
        "no_items": "No items for this issue.",
        "tx_summary_tpl": "Field monitoring log — {band}. {count} signals on record.",
    },
    "uk": {
        "heading": "coma.fm Радар",
        "intro": "Щотижневий дайджест музики з поля coma.fm.",
        "draft_notice": "Чернетка — не опубліковано",
        "no_items": "Для цього випуску немає матеріалів.",
        "tx_summary_tpl": "Польовий журнал моніторингу — {band}. {count} сигналів зафіксовано.",
    },
}


_SIGNAL_TYPE_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "review": "Review signal",
        "reissue": "Reissue signal",
        "archive": "Archive signal",
        "interview": "Interview signal",
        "scene": "Scene signal",
        "release": "Release signal",
        "video": "Video signal",
        "industry": "Industry signal",
        "culture": "Culture signal",
        "editor_note": "Editor note",
        "signal": "Radar signal",
    },
    "uk": {
        "review": "Сигнал рецензії",
        "reissue": "Сигнал перевидання",
        "archive": "Архівний сигнал",
        "interview": "Сигнал інтерв’ю",
        "scene": "Сигнал сцени",
        "release": "Сигнал релізу",
        "video": "Відеосигнал",
        "industry": "Індустріальний сигнал",
        "culture": "Культурний сигнал",
        "editor_note": "Нотатка редактора",
        "signal": "Сигнал радара",
    },
}


_SIGNAL_TYPE_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("review", (
        " album review ", " review ", " reviews ", " реценз",
    )),
    ("interview", (
        " interview ", " q a ", " q and a ", " conversation ", " інтерв", " интервью ",
    )),
    ("reissue", (
        " reissue ", " reissued ", " remaster ", " remastered ", " box set ",
        " expanded edition ", " anniversary edition ", " перевид",
    )),
    ("archive", (
        " archive ", " archival ", " vault ", " unearthed ", " previously unreleased ",
        " live recording ", " lost tapes ", " demo recordings ", " архів",
    )),
    ("video", (
        " video ", " videoclip ", " music video ", " session video ", " відео ", " видео ",
    )),
    ("industry", (
        " wal mart ", " walmart ", " partnership ", " brand ", " off brand ",
        " licensing ", " publishing rights ", " catalog sale ", " business ",
        " deal ", " sponsor ", " endorsement ", " lawsuit ", " legal battle ",
    )),
    ("culture", (
        " pop star ", " fame ", " parallel ", " legacy ", " chart ",
        " on this day ", " topped the charts ", " born in ", " anniversary ",
        " similar level of fame ", " biography ",
    )),
    ("scene", (
        " scene ", " label profile ", " festival ", " profile ", " spotlight ", " reading room ",
    )),
    ("release", (
        " new album ", " new single ", " single ", " ep ", " lp ", " album ", " release ", " debut ",
    )),
)


def _signal_text(item: dict) -> str:
    raw = " ".join(
        str(item.get(key) or "")
        for key in (
            "title",
            "source_name",
            "source_type",
            "matched_artists",
            "matched_tags",
            "matched_genres",
        )
    )
    return " " + re.sub(r"[^a-zа-яіїєґ0-9]+", " ", raw.lower()).strip() + " "


def classify_signal_type(item: dict) -> str:
    """Return deterministic editorial signal type for an issue item."""
    text = _signal_text(item)
    for signal_type, needles in _SIGNAL_TYPE_RULES:
        if any(needle in text for needle in needles):
            return signal_type
    return "signal"


def localize_signal_type(signal_type: str, lang: str) -> str:
    """Return localized public label for a signal type."""
    labels = _SIGNAL_TYPE_LABELS.get(lang, _SIGNAL_TYPE_LABELS["en"])
    return labels.get(signal_type, labels["signal"])


_FIELD_EVIDENCE_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "artist_match": "Artist match",
        "tag_match": "Tag match",
        "genre_match": "Genre match",
        "source_signal": "Source signal",
        "weak_signal": "Weak signal",
        "review_signal": "Review signal",
        "reissue_signal": "Reissue signal",
        "archive_signal": "Archive signal",
        "interview_signal": "Interview signal",
        "scene_signal": "Scene signal",
        "release_signal": "Release signal",
        "video_signal": "Video signal",
        "industry_signal": "Industry signal",
        "culture_signal": "Culture signal",
        "editor_note_signal": "Editor note",
    },
    "uk": {
        "artist_match": "Збіг артиста",
        "tag_match": "Збіг тегу",
        "genre_match": "Збіг жанру",
        "source_signal": "Сигнал джерела",
        "weak_signal": "Слабкий сигнал",
        "review_signal": "Сигнал рецензії",
        "reissue_signal": "Сигнал перевидання",
        "archive_signal": "Архівний сигнал",
        "interview_signal": "Сигнал інтерв’ю",
        "scene_signal": "Сигнал сцени",
        "release_signal": "Сигнал релізу",
        "video_signal": "Відеосигнал",
        "industry_signal": "Індустріальний сигнал",
        "culture_signal": "Культурний сигнал",
        "editor_note_signal": "Нотатка редактора",
    },
}


def build_field_evidence(item: dict) -> list[str]:
    """Return deterministic evidence codes explaining why an item belongs in the issue."""
    evidence: list[str] = []

    if str(item.get("matched_artists") or "").strip():
        evidence.append("artist_match")
    if str(item.get("matched_tags") or "").strip():
        evidence.append("tag_match")
    if str(item.get("matched_genres") or "").strip():
        evidence.append("genre_match")

    signal_type = str(item.get("signal_type") or classify_signal_type(item))
    if signal_type and signal_type != "signal":
        evidence.append(f"{signal_type}_signal")

    if str(item.get("source_name") or "").strip() or str(item.get("source_type") or "").strip():
        evidence.append("source_signal")

    if not evidence:
        evidence.append("weak_signal")

    return evidence


def localize_field_evidence(evidence: list[str], lang: str) -> str:
    """Return localized compact evidence label."""
    labels = _FIELD_EVIDENCE_LABELS.get(lang, _FIELD_EVIDENCE_LABELS["en"])
    return " · ".join(labels.get(code, code.replace("_", " ").title()) for code in evidence)


def build_editorial_angle(item: dict, lang: str) -> str:
    """Return a short editorial angle for the selected signal."""
    signal_type = str(item.get("signal_type") or classify_signal_type(item))
    evidence = list(item.get("field_evidence") or build_field_evidence({**item, "signal_type": signal_type}))

    has_artist = "artist_match" in evidence
    has_tag_or_genre = "tag_match" in evidence or "genre_match" in evidence

    if lang == "uk":
        if signal_type == "industry":
            return "Індустріальний контекст навколо артиста з поля coma.fm." if has_artist else "Індустріальний сигнал із музичного моніторингу."
        if signal_type == "culture":
            return "Культурний контекст навколо артиста з поля coma.fm." if has_artist else "Культурний сигнал із музичного моніторингу."
        if has_artist:
            return f"{localize_signal_type(signal_type, lang)} з артистичного поля coma.fm."
        if has_tag_or_genre:
            return f"{localize_signal_type(signal_type, lang)} з жанрового поля coma.fm."
        return "Сигнал із моніторингу джерел coma.fm."

    if signal_type == "industry":
        return "Industry / brand context around a coma.fm-field artist." if has_artist else "Industry signal from monitored music sources."
    if signal_type == "culture":
        return "Culture context around a coma.fm-field artist." if has_artist else "Culture signal from monitored music sources."
    if has_artist:
        return f"{localize_signal_type(signal_type, lang)} from the coma.fm artist field."
    if has_tag_or_genre:
        return f"{localize_signal_type(signal_type, lang)} from the coma.fm genre field."
    return "Radar signal from monitored coma.fm sources."


# ---------------------------------------------------------------------------
# Minimal Jinja2-subset renderer
# ---------------------------------------------------------------------------

class _J2Renderer:
    """Renders a Jinja2-like template using only Python stdlib.

    Supported: {{ expr }}, {% for x in y %}...{% endfor %},
               {% if cond %}...{% else %}...{% endif %}, {# comment #},
               == and != comparisons in if-conditions, dot-notation lookups.
    """

    _TOK = re.compile(
        r"(\{%-?\s*.*?\s*-?%\}|\{\{-?\s*.*?\s*-?\}\}|\{#.*?#\})",
        re.DOTALL,
    )

    def render(self, src: str, ctx: dict) -> str:
        return "".join(self._seq(self._TOK.split(src), 0, ctx)[0])

    def _val(self, expr: str, ctx: dict):
        expr = expr.strip()
        if "|" in expr:
            expr = expr.split("|")[0].strip()
        parts = expr.split(".")
        v = ctx.get(parts[0])
        for p in parts[1:]:
            v = v.get(p) if isinstance(v, dict) else None
        return v

    def _cond(self, expr: str, ctx: dict) -> bool:
        for op in (" == ", " != "):
            if op in expr:
                lhs, rhs = expr.split(op, 1)
                lv = self._val(lhs, ctx)
                rv = rhs.strip().strip('"').strip("'")
                return (str(lv) == rv) if " == " in op else (str(lv) != rv)
        return bool(self._val(expr, ctx))

    def _out(self, val) -> str:
        if val is None:
            return ""
        if isinstance(val, str):
            return html.escape(val)
        return str(val)

    def _seq(self, toks: list, pos: int, ctx: dict) -> tuple[list, int]:
        result: list[str] = []
        n = len(toks)
        while pos < n:
            t = toks[pos]
            if not t:
                pos += 1
                continue
            if t.startswith("{#"):
                pos += 1
                continue
            if t.startswith("{{"):
                m = re.match(r"\{\{-?\s*(.*?)\s*-?\}\}", t, re.DOTALL)
                result.append(self._out(self._val(m.group(1), ctx)) if m else "")
                pos += 1
                continue
            if t.startswith("{%"):
                m = re.match(r"\{%-?\s*(.*?)\s*-?%\}", t, re.DOTALL)
                tag = m.group(1).strip() if m else ""
                pos += 1
                if re.match(r"for\s", tag):
                    fm = re.match(r"for\s+(\w+)\s+in\s+([\w.]+)", tag)
                    if fm:
                        body, pos = self._until(toks, pos, "for", "endfor")
                        coll = self._val(fm.group(2), ctx)
                        if isinstance(coll, (list, tuple)):
                            for item in coll:
                                r2, _ = self._seq(body, 0, {**ctx, fm.group(1): item})
                                result.extend(r2)
                elif re.match(r"if\s", tag):
                    if_b, else_b, pos = self._if_blocks(toks, pos)
                    chosen = if_b if self._cond(tag[3:], ctx) else else_b
                    r2, _ = self._seq(chosen, 0, ctx)
                    result.extend(r2)
                continue
            result.append(t)
            pos += 1
        return result, pos

    def _until(self, toks: list, pos: int, open_kw: str, close_kw: str) -> tuple[list, int]:
        body: list[str] = []
        depth = 1
        op = re.compile(r"\{%-?\s*" + re.escape(open_kw) + r"\s")
        cl = re.compile(r"\{%-?\s*" + re.escape(close_kw) + r"\s*-?%\}")
        while pos < len(toks) and depth:
            t = toks[pos]
            if op.search(t):
                depth += 1
            elif cl.search(t):
                depth -= 1
                if not depth:
                    pos += 1
                    break
            if depth:
                body.append(t)
            pos += 1
        return body, pos

    def _if_blocks(self, toks: list, pos: int) -> tuple[list, list, int]:
        if_b: list[str] = []
        else_b: list[str] = []
        in_else = False
        depth = 1
        if_re = re.compile(r"\{%-?\s*if\s")
        end_re = re.compile(r"\{%-?\s*endif\s*-?%\}")
        else_re = re.compile(r"\{%-?\s*else\s*-?%\}")
        while pos < len(toks) and depth:
            t = toks[pos]
            if if_re.search(t):
                depth += 1
            elif end_re.search(t):
                depth -= 1
                if not depth:
                    pos += 1
                    break
            elif else_re.search(t) and depth == 1:
                in_else = True
                pos += 1
                continue
            if depth:
                (else_b if in_else else if_b).append(t)
            pos += 1
        return if_b, else_b, pos


# ---------------------------------------------------------------------------
# Tag map
# ---------------------------------------------------------------------------

def load_tag_map(tags_path: Path = DEFAULT_TAGS) -> dict[str, dict]:
    """Return {tag_id: {slug, label}} from tags.yaml."""
    import yaml
    with tags_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {
        tag["id"]: {"slug": tag.get("slug", tag["id"]), "label": tag.get("label", tag["id"])}
        for tag in data.get("tags", [])
    }


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Recency filtering
# ---------------------------------------------------------------------------

def _parse_item_datetime(value: str | None) -> datetime | None:
    """Parse ISO/RFC feed dates into UTC datetimes."""
    text = str(value or "").strip()
    if not text:
        return None

    candidates = [text]
    if text.endswith("Z"):
        candidates.append(text[:-1] + "+00:00")

    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _issue_cutoff(issue_date: str, recency_days: int) -> datetime:
    issue_dt = _parse_item_datetime(issue_date)
    if issue_dt is None:
        issue_dt = datetime.now(tz=timezone.utc)
    return issue_dt - timedelta(days=recency_days)


def _is_recent_issue_item(
    item: dict,
    issue_date: str | None,
    recency_days: int | None,
    include_old_archive: bool = False,
) -> bool:
    """Return True when an item is eligible for a dated daily issue.

    Policy:
    - no recency_days means no filter;
    - must_use / high_priority bypass the filter;
    - published_at is authoritative;
    - first_seen_at is only a fallback when published_at cannot be parsed;
    - old archive/reissue items only bypass when explicitly requested.
    """
    if recency_days is None or recency_days <= 0 or not issue_date:
        return True

    if _has_priority_override(item):
        return True

    tags = _item_tag_ids(item)
    if include_old_archive and tags & {"archive", "archive_release", "reissue"}:
        return True

    cutoff = _issue_cutoff(issue_date, recency_days)

    published_at = _parse_item_datetime(str(item.get("published_at") or ""))
    if published_at is not None:
        return published_at >= cutoff

    first_seen_at = _parse_item_datetime(str(item.get("first_seen_at") or ""))
    if first_seen_at is not None:
        return first_seen_at >= cutoff

    return False


def load_items(
    db_path: Path,
    min_score: int = DEFAULT_MIN_SCORE,
    limit: int = DEFAULT_LIMIT,
    issue_date: str | None = None,
    recency_days: int | None = None,
    include_old_archive: bool = False,
) -> list[dict]:
    """Load top-scored items from the database, optionally filtered by recency."""
    query_limit = max(limit * 20, 200) if recency_days and recency_days > 0 else limit

    conn = sqlite3.connect(str(db_path))
    item_columns = {
        row[1]
        for row in conn.execute("PRAGMA table_info(items)").fetchall()
    }
    first_seen_expr = "first_seen_at" if "first_seen_at" in item_columns else "'' AS first_seen_at"
    rows = conn.execute(
        "SELECT id, title, url, source_name, source_type, published_at, "
        f"{first_seen_expr}, score, matched_artists, matched_tags, matched_genres "
        "FROM items "
        "WHERE score >= ? "
        "ORDER BY score DESC "
        "LIMIT ?",
        (min_score, query_limit),
    ).fetchall()
    conn.close()
    cols = [
        "id", "title", "url", "source_name", "source_type",
        "published_at", "first_seen_at", "score", "matched_artists",
        "matched_tags", "matched_genres",
    ]
    items = [dict(zip(cols, row)) for row in rows]
    if recency_days and recency_days > 0:
        items = [
            item for item in items
            if _is_recent_issue_item(
                item,
                issue_date=issue_date,
                recency_days=recency_days,
                include_old_archive=include_old_archive,
            )
        ]
    return items[:limit]


# ---------------------------------------------------------------------------
# Editorial selection
# ---------------------------------------------------------------------------

_PRIORITY_OVERRIDE_TAGS = {"must_use", "high_priority"}


def _source_key(item: dict) -> str:
    """Return stable source key for editorial source balancing."""
    source = str(item.get("source_name") or "").strip().lower()
    return source or "__unknown_source__"


def _item_tag_ids(item: dict) -> set[str]:
    tags = str(item.get("matched_tags") or "")
    return {tag.strip() for tag in tags.split(",") if tag.strip()}


def _has_priority_override(item: dict) -> bool:
    """Return True when an item may bypass editorial source caps."""
    return bool(_item_tag_ids(item) & _PRIORITY_OVERRIDE_TAGS)


def select_editorial_items(
    candidates: list[dict],
    limit: int = DEFAULT_LIMIT,
    max_per_source: int = DEFAULT_MAX_PER_SOURCE,
) -> list[dict]:
    """Select issue items with a soft source-diversity cap.

    Candidates are expected to be pre-sorted by score descending.
    The cap is soft: if there are not enough alternative sources, the
    selection is filled with the strongest overflow items.
    """
    if limit <= 0:
        return []

    selected: list[dict] = []
    overflow: list[dict] = []
    source_counts: dict[str, int] = {}

    for item in candidates:
        if len(selected) >= limit:
            break

        key = _source_key(item)
        current = source_counts.get(key, 0)
        can_bypass = _has_priority_override(item)

        if max_per_source <= 0 or current < max_per_source or can_bypass:
            selected.append(item)
            source_counts[key] = current + 1
        else:
            overflow.append(item)

    if len(selected) < limit:
        for item in overflow:
            if len(selected) >= limit:
                break
            selected.append(item)

    return selected


def _parse_artists(matched_artists: str) -> list[str]:
    """Return normalised artist names from a comma-separated matched_artists string."""
    return [a.strip().lower() for a in matched_artists.split(",") if a.strip()]


def select_items_with_diversity(
    candidates: list[dict],
    issue_limit: int,
    max_source_items: int = DEFAULT_MAX_SOURCE_ITEMS,
    max_artist_items: int = DEFAULT_MAX_ARTIST_ITEMS,
) -> tuple[list[dict], list[dict]]:
    """Select up to issue_limit items enforcing source and artist diversity caps.

    Candidates must be pre-sorted by score descending.  Items that exceed a cap
    are skipped (not removed from candidates) and recorded in the returned
    evidence list.  Items tagged must_use / high_priority bypass both caps.

    Returns:
        (selected, evidence)
        evidence: list of dicts with keys reason, source_name, artist_name,
                  title, score — one entry per skipped item.
    """
    if issue_limit <= 0:
        return [], []

    selected: list[dict] = []
    evidence: list[dict] = []
    source_counts: dict[str, int] = {}
    artist_counts: dict[str, int] = {}

    for item in candidates:
        if len(selected) >= issue_limit:
            break

        source = _source_key(item)
        artists = _parse_artists(str(item.get("matched_artists") or ""))
        score = item.get("score", 0)
        title = str(item.get("title") or "")
        can_bypass = _has_priority_override(item)

        # Source cap
        if (
            not can_bypass
            and max_source_items > 0
            and source_counts.get(source, 0) >= max_source_items
        ):
            evidence.append({
                "reason": "skipped_by_source_cap",
                "source_name": source,
                "artist_name": "",
                "title": title,
                "score": score,
            })
            continue

        # Artist cap — first matched artist that exceeds the cap blocks the item
        capping_artist = ""
        if not can_bypass and max_artist_items > 0:
            for artist in artists:
                if artist_counts.get(artist, 0) >= max_artist_items:
                    capping_artist = artist
                    break

        if capping_artist:
            evidence.append({
                "reason": "skipped_by_artist_cap",
                "source_name": source,
                "artist_name": capping_artist,
                "title": title,
                "score": score,
            })
            continue

        # Passes both caps
        selected.append(item)
        source_counts[source] = source_counts.get(source, 0) + 1
        for artist in artists:
            artist_counts[artist] = artist_counts.get(artist, 0) + 1

    return selected, evidence


# ---------------------------------------------------------------------------
# Editorial sequencing
# ---------------------------------------------------------------------------

_SIGNAL_SEQUENCE_RANK: dict[str, int] = {
    "editor_note": 5,
    "review": 10,
    "reissue": 20,
    "archive": 25,
    "interview": 30,
    "release": 40,
    "video": 45,
    "scene": 50,
    "signal": 60,
    "culture": 70,
    "industry": 80,
}


def _score_number(item: dict) -> float:
    try:
        return float(item.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def editorial_sequence_rank(item: dict) -> int:
    """Return deterministic editorial rank for issue ordering."""
    signal_type = str(item.get("signal_type") or classify_signal_type(item))
    return _SIGNAL_SEQUENCE_RANK.get(signal_type, _SIGNAL_SEQUENCE_RANK["signal"])


def sequence_editorial_items(items: list[dict]) -> list[dict]:
    """Order already-selected issue items by editorial rhythm.

    This does not select or filter items. It only sequences the final set:
    stronger editorial signals first, culture/industry context lower.
    """
    indexed = list(enumerate(items))
    ordered = sorted(
        indexed,
        key=lambda pair: (
            editorial_sequence_rank(pair[1]),
            -_score_number(pair[1]),
            pair[0],
        ),
    )
    return [item for _, item in ordered]


# ---------------------------------------------------------------------------
# Item enrichment
# ---------------------------------------------------------------------------

def _format_date(date_str: str) -> str:
    if not date_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str[:10] if len(date_str) >= 10 else date_str


def enrich_items(items: list[dict], tag_map: dict) -> list[dict]:
    """Add a structured 'tags' list to each item and format dates."""
    enriched = []
    for item in items:
        tags_str = str(item.get("matched_tags") or "")
        tag_ids = [t.strip() for t in tags_str.split(",") if t.strip()]
        tags = [
            {"id": tid, "slug": tag_map[tid]["slug"], "label": tag_map[tid]["label"]}
            for tid in tag_ids
            if tid in tag_map
        ]
        enriched.append({
            **item,
            "published_at": _format_date(str(item.get("published_at") or "")),
            "matched_artists": str(item.get("matched_artists") or ""),
            "tags": tags,
            "signal_type": classify_signal_type(item),
            "field_evidence": build_field_evidence(item),
        })
    return enriched


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_html(
    items: list[dict],
    issue_date: str,
    lang: str,
    draft: bool,
    template_path: Path = DEFAULT_TEMPLATE,
    base_path: str = "",
    cover_image_url: str | None = None,
    cover_alt: str = "",
) -> str:
    from scripts.transmission_meta import make_issue_meta
    base_path = normalize_base_path(base_path)
    locale = _LOCALE.get(lang, _LOCALE["en"])
    tm = make_issue_meta(issue_date, lang, items)

    # Pre-compute item indices so the template can use {{ item.index }}
    # without needing the |format filter which _J2Renderer does not support.
    indexed_items = []
    for i, item in enumerate(items):
        signal_type = str(item.get("signal_type") or classify_signal_type(item))
        evidence = list(item.get("field_evidence") or build_field_evidence({**item, "signal_type": signal_type}))
        enriched_item = {
            **item,
            "signal_type": signal_type,
            "field_evidence": evidence,
        }
        indexed_items.append({
            **enriched_item,
            "index": f"{i + 1:02d}",
            "signal_type_label": localize_signal_type(signal_type, lang),
            "field_evidence_label": localize_field_evidence(evidence, lang),
            "editorial_angle": build_editorial_angle(enriched_item, lang),
        })

    tx_summary = locale["tx_summary_tpl"].format(
        band=tm["band"],
        count=len(items),
    )

    ctx = {
        "lang": lang,
        "lang_label": lang.upper(),
        "title": f"coma.fm Radar — {issue_date} — {lang.upper()}",
        "description": locale["intro"],
        "issue_date": issue_date,
        "heading": locale["heading"],
        "intro": locale["intro"],
        "no_items_message": locale["no_items"],
        "draft": draft,
        "draft_notice": locale["draft_notice"],
        "items": indexed_items,
        "signal_count": tm["signal_count"],
        "nav_en_href": f"{base_path}/en/issues/{issue_date}.html",
        "nav_uk_href": f"{base_path}/uk/issues/{issue_date}.html",
        "tag_href_prefix": f"{base_path}/{lang}/tags",
        "asset_path": f"{base_path}/assets",
        "cover_image_url": cover_image_url or "",
        "cover_alt": cover_alt,
        "tx_code": tm["tx_code"],
        "band": tm["band"],
        "archive_node": tm["archive_node"],
        "frequency_marks": tm["frequency_marks"],
        "field_tags": tm["field_tags"],
        "field_tags_label": tm["field_tags_label"],
        "generated_label": tm["generated_label"],
        "timezone_label": tm["timezone_label"],
        "tx_summary": tx_summary,
    }
    template_src = template_path.read_text(encoding="utf-8")
    return _J2Renderer().render(template_src, ctx)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build_issue(
    db_path: Path = DEFAULT_DB,
    issue_date: str | None = None,
    lang: str | None = None,
    limit: int = DEFAULT_LIMIT,
    min_score: int = DEFAULT_MIN_SCORE,
    draft: bool = False,
    template_path: Path = DEFAULT_TEMPLATE,
    tags_path: Path = DEFAULT_TAGS,
    content_dir: Path = DEFAULT_CONTENT_DIR,
    dist_dir: Path = DEFAULT_DIST_DIR,
    base_path: str = "",
    with_cover: bool = True,
    themes_path: Path = DEFAULT_THEMES,
    max_per_source: int = DEFAULT_MAX_SOURCE_ITEMS,
    max_artist_items: int = DEFAULT_MAX_ARTIST_ITEMS,
    recency_days: int | None = None,
    include_old_archive: bool = False,
) -> dict:
    """Build HTML issue(s) and JSON drafts. Returns summary dict."""
    if issue_date is None:
        issue_date = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    languages = [lang] if lang else ["en", "uk"]
    tag_map = load_tag_map(tags_path)
    candidate_limit = max(limit * 5, limit)
    raw_candidates = load_items(
        db_path,
        min_score=min_score,
        limit=candidate_limit,
        issue_date=issue_date,
        recency_days=recency_days,
        include_old_archive=include_old_archive,
    )
    raw_items, diversity_evidence = select_items_with_diversity(
        raw_candidates,
        issue_limit=limit,
        max_source_items=max_per_source,
        max_artist_items=max_artist_items,
    )
    items = sequence_editorial_items(enrich_items(raw_items, tag_map))

    # Detect main tag once so both language covers share the same theme
    cover_main_tag: str | None = None
    if with_cover:
        from scripts.generate_issue_cover import (
            detect_main_tag_from_items as _detect_tag,
            load_tags_typed as _load_tags_typed,
        )
        cover_main_tag = _detect_tag(items, _load_tags_typed(tags_path))

    output_files: list[str] = []
    now_iso = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for lng in languages:
        cover_image_url: str | None = None
        cover_alt = ""
        if with_cover:
            from scripts.generate_issue_cover import generate_issue_cover as _gen_cover
            _gen_cover(
                issue_date=issue_date,
                lang=lng,
                main_tag=cover_main_tag,
                item_count=len(items),
                dist_dir=dist_dir,
                themes_path=themes_path,
                content_dir=content_dir,
            )
            bp = normalize_base_path(base_path)
            cover_image_url = f"{bp}/assets/covers/issues/{issue_date}/cover-{lng}.svg"
            cover_alt = f"coma.fm Radar {issue_date}"

        # --- HTML ---
        html_dir = dist_dir / lng / "issues"
        html_dir.mkdir(parents=True, exist_ok=True)
        html_path = html_dir / f"{issue_date}.html"
        html_content = render_html(
            items, issue_date, lng, draft, template_path, base_path,
            cover_image_url, cover_alt,
        )
        html_path.write_text(html_content, encoding="utf-8")
        try:
            output_files.append(str(html_path.relative_to(_REPO_ROOT)))
        except ValueError:
            output_files.append(str(html_path))

        # --- JSON ---
        content_dir.mkdir(parents=True, exist_ok=True)
        json_path = content_dir / f"{issue_date}.{lng}.json"
        issue_data = {
            "issue_date": issue_date,
            "lang": lng,
            "draft": draft,
            "generated_at": now_iso,
            "min_score": min_score,
            "total_items": len(items),
            "items": [
                {
                    "id": it["id"],
                    "title": it["title"],
                    "url": it["url"],
                    "source_name": it["source_name"],
                    "signal_type": it.get("signal_type", "signal"),
                    "signal_type_label": localize_signal_type(str(it.get("signal_type") or "signal"), lng),
                    "field_evidence": it.get("field_evidence", []),
                    "field_evidence_label": localize_field_evidence(list(it.get("field_evidence") or []), lng),
                    "editorial_angle": build_editorial_angle(it, lng),
                    "published_at": it["published_at"],
                    "score": it["score"],
                    "matched_artists": it["matched_artists"],
                    "matched_tags": it.get("matched_tags", ""),
                    "matched_genres": it.get("matched_genres", ""),
                }
                for it in items
            ],
        }
        json_path.write_text(
            json.dumps(issue_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        try:
            output_files.append(str(json_path.relative_to(_REPO_ROOT)))
        except ValueError:
            output_files.append(str(json_path))

    skipped_source = [e for e in diversity_evidence if e["reason"] == "skipped_by_source_cap"]
    skipped_artist = [e for e in diversity_evidence if e["reason"] == "skipped_by_artist_cap"]

    return {
        "issue_date": issue_date,
        "languages": languages,
        "selected_items": len(items),
        "output_files": output_files,
        "draft": draft,
        "recency_days": recency_days,
        "include_old_archive": include_old_archive,
        "diversity_evidence": {
            "skipped_by_source_cap": skipped_source,
            "skipped_by_artist_cap": skipped_artist,
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a static bilingual issue HTML from scored items."
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--date", dest="issue_date", default=None,
        help="Issue date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--lang", choices=["en", "uk"], default=None,
        help="Language to build (default: both en and uk)",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--min-score", type=int, default=DEFAULT_MIN_SCORE)
    parser.add_argument(
        "--recency-days", type=int, default=None, dest="recency_days",
        help="Only select items published within N days of the issue date; disabled by default.",
    )
    parser.add_argument(
        "--include-old-archive", action="store_true", dest="include_old_archive",
        help="Allow archive/reissue-tagged items to bypass the recency window.",
    )
    parser.add_argument(
        "--max-per-source",
        type=int,
        default=DEFAULT_MAX_SOURCE_ITEMS,
        dest="max_per_source",
        help=f"Max items per source in one issue (default: {DEFAULT_MAX_SOURCE_ITEMS})",
    )
    parser.add_argument(
        "--max-artist-items",
        type=int,
        default=DEFAULT_MAX_ARTIST_ITEMS,
        dest="max_artist_items",
        help=f"Max items per matched artist in one issue (default: {DEFAULT_MAX_ARTIST_ITEMS})",
    )
    parser.add_argument("--draft", action="store_true",
                        help="Mark output as draft")
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--base-path", default="", dest="base_path",
                        help="Base path prefix for internal links, e.g. /coma-artist-radar")
    parser.add_argument(
        "--no-cover", action="store_false", dest="with_cover",
        help="Skip cover image generation",
    )
    parser.set_defaults(with_cover=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: database not found: {args.db}", file=sys.stderr)
        return 1

    summary = build_issue(
        db_path=args.db,
        issue_date=args.issue_date,
        lang=args.lang,
        limit=args.limit,
        min_score=args.min_score,
        max_per_source=args.max_per_source,
        max_artist_items=args.max_artist_items,
        draft=args.draft,
        template_path=args.template,
        base_path=args.base_path,
        with_cover=args.with_cover,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

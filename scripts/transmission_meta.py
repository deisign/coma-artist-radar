"""Deterministic transmission metadata for coma.fm Radar pages."""
from __future__ import annotations

_FREQUENCY_MARKS = [88, 92, 96, 100, 104, 108]
_BAND = "88–108 FM"
_NODE = "COMA-RADAR"


def make_issue_meta(issue_date: str, lang: str, items: list[dict]) -> dict:
    """Generate deterministic transmission metadata for an issue page."""
    date_compact = issue_date.replace("-", "")
    tx_code = f"TX-{date_compact}-{lang.upper()}"

    field_tags: list[str] = []
    seen: set[str] = set()
    for item in items:
        tags_str = str(item.get("matched_tags") or "")
        for tid in (t.strip() for t in tags_str.split(",") if t.strip()):
            if tid not in seen:
                seen.add(tid)
                field_tags.append(tid)
            if len(field_tags) >= 5:
                break
        if len(field_tags) >= 5:
            break

    field_tags_label = (
        " / ".join(t.upper().replace("_", " ") for t in field_tags[:3])
        if field_tags else ""
    )

    return {
        "tx_code": tx_code,
        "band": _BAND,
        "signal_count": len(items),
        "archive_node": _NODE,
        "frequency_marks": _FREQUENCY_MARKS,
        "field_tags": field_tags,
        "field_tags_label": field_tags_label,
        "generated_label": "AUTOMATED FIELD REPORT",
        "timezone_label": "FIELD TIME",
    }


def make_page_meta(section_code: str) -> dict:
    """Generate transmission metadata for non-issue pages."""
    return {
        "tx_code": section_code,
        "band": _BAND,
        "archive_node": _NODE,
        "frequency_marks": _FREQUENCY_MARKS,
        "section_code": section_code,
        "field_tags": [],
        "field_tags_label": "",
    }

import sqlite3
from pathlib import Path

import pytest

from scripts.import_human_submissions import (
    _entry_hash,
    import_submissions,
    open_db,
    parse_inbox,
    validate_submission,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_inbox(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "manual.md"
    path.write_text(content, encoding="utf-8")
    return path


def _inbox_with(*entries: str) -> str:
    return "\n".join(f"---\n{e.strip()}\n" for e in entries)


def _row_count(db_path: Path) -> int:
    conn = sqlite3.connect(str(db_path))
    (n,) = conn.execute("SELECT COUNT(*) FROM human_submissions").fetchone()
    conn.close()
    return n


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def test_parse_inbox_returns_dicts(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        _inbox_with(
            "type: link\ntitle: Test\nurl: https://example.com\npriority: normal\nstatus: new"
        ),
    )
    entries = parse_inbox(inbox)
    assert len(entries) == 1
    assert entries[0]["title"] == "Test"


def test_parse_inbox_skips_header_and_empty_blocks(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        "# Header is ignored\n\n---\ntype: link\ntitle: Valid\nurl: https://example.com\npriority: normal\nstatus: new\n",
    )
    entries = parse_inbox(inbox)
    assert len(entries) == 1


def test_parse_inbox_handles_multiline_notes(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        "---\ntype: editor_note\ntitle: Deep note\nnotes: >\n  Line one.\n  Line two.\npriority: normal\nstatus: new\n",
    )
    entries = parse_inbox(inbox)
    assert entries[0]["notes"].startswith("Line one.")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_manual_link():
    entry = {
        "type": "link",
        "title": "Surf comp",
        "url": "https://example.bandcamp.com/surf",
        "priority": "high",
        "status": "new",
    }
    v = validate_submission(entry)
    assert v["source_type"] == "link"
    assert v["url"] == "https://example.bandcamp.com/surf"
    assert v["priority"] == "high"


def test_validate_editor_note_without_url():
    entry = {
        "type": "editor_note",
        "title": "Surf without the sea",
        "priority": "must_use",
        "status": "new",
    }
    v = validate_submission(entry)
    assert v["source_type"] == "editor_note"
    assert v["url"] is None
    assert v["priority"] == "must_use"


def test_validate_priority_must_use_preserved():
    entry = {"type": "link", "title": "T", "url": "https://x.com", "priority": "must_use", "status": "new"}
    v = validate_submission(entry)
    assert v["priority"] == "must_use"


def test_validate_invalid_priority_raises():
    entry = {"type": "link", "title": "T", "url": "https://x.com", "priority": "urgent", "status": "new"}
    with pytest.raises(ValueError, match="priority"):
        validate_submission(entry)


def test_validate_invalid_status_raises():
    entry = {"type": "link", "title": "T", "url": "https://x.com", "priority": "normal", "status": "maybe"}
    with pytest.raises(ValueError, match="status"):
        validate_submission(entry)


def test_validate_missing_title_raises():
    entry = {"type": "link", "url": "https://x.com", "priority": "normal", "status": "new"}
    with pytest.raises(ValueError, match="title"):
        validate_submission(entry)


def test_validate_invalid_source_type_raises():
    entry = {"type": "tweet", "title": "T", "priority": "normal", "status": "new"}
    with pytest.raises(ValueError, match="source_type"):
        validate_submission(entry)


# ---------------------------------------------------------------------------
# Import — happy path
# ---------------------------------------------------------------------------

def test_manual_link_imported(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        _inbox_with(
            "type: link\ntitle: Surf comp\nurl: https://bandcamp.example.com/surf\npriority: high\nstatus: new"
        ),
    )
    db_path = tmp_path / "test.sqlite"
    summary = import_submissions(parse_inbox(inbox), db_path)
    assert summary["new"] == 1
    assert _row_count(db_path) == 1


def test_editor_note_without_url_imported(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        _inbox_with(
            "type: editor_note\ntitle: Surf without the sea\nnotes: Great concept.\npriority: must_use\nstatus: new"
        ),
    )
    db_path = tmp_path / "test.sqlite"
    summary = import_submissions(parse_inbox(inbox), db_path)
    assert summary["new"] == 1

    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT source_type, url, priority FROM human_submissions").fetchone()
    conn.close()
    assert row[0] == "editor_note"
    assert row[1] is None
    assert row[2] == "must_use"


def test_priority_must_use_saved_in_db(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        _inbox_with(
            "type: link\ntitle: Must item\nurl: https://example.com/must\npriority: must_use\nstatus: new"
        ),
    )
    db_path = tmp_path / "test.sqlite"
    import_submissions(parse_inbox(inbox), db_path)

    conn = sqlite3.connect(str(db_path))
    (priority,) = conn.execute("SELECT priority FROM human_submissions").fetchone()
    conn.close()
    assert priority == "must_use"


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_duplicate_url_not_added_twice(tmp_path):
    entry_md = "type: link\ntitle: Duplicate test\nurl: https://example.com/dup\npriority: normal\nstatus: new"
    inbox = _write_inbox(tmp_path, _inbox_with(entry_md))
    db_path = tmp_path / "test.sqlite"

    s1 = import_submissions(parse_inbox(inbox), db_path)
    s2 = import_submissions(parse_inbox(inbox), db_path)

    assert s1["new"] == 1
    assert s2["new"] == 0
    assert s2["skipped_duplicate"] == 1
    assert _row_count(db_path) == 1


def test_duplicate_editor_note_not_added_twice(tmp_path):
    entry_md = "type: editor_note\ntitle: Same note\nnotes: Content.\npriority: normal\nstatus: new"
    inbox = _write_inbox(tmp_path, _inbox_with(entry_md))
    db_path = tmp_path / "test.sqlite"

    import_submissions(parse_inbox(inbox), db_path)
    s2 = import_submissions(parse_inbox(inbox), db_path)

    assert s2["skipped_duplicate"] == 1
    assert _row_count(db_path) == 1


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

def test_dry_run_does_not_write_to_db(tmp_path):
    inbox = _write_inbox(
        tmp_path,
        _inbox_with(
            "type: link\ntitle: Dry item\nurl: https://example.com/dry\npriority: normal\nstatus: new"
        ),
    )
    db_path = tmp_path / "test.sqlite"

    summary = import_submissions(parse_inbox(inbox), db_path, dry_run=True)

    assert not db_path.exists()
    assert summary["dry_run"] is True
    assert summary["new"] == 1


def test_dry_run_counts_valid_entries(tmp_path):
    entries = (
        "type: link\ntitle: A\nurl: https://example.com/a\npriority: normal\nstatus: new",
        "type: editor_note\ntitle: B\npriority: high\nstatus: new",
    )
    inbox = _write_inbox(tmp_path, _inbox_with(*entries))
    db_path = tmp_path / "test.sqlite"

    summary = import_submissions(parse_inbox(inbox), db_path, dry_run=True)
    assert summary["total_in_file"] == 2
    assert summary["new"] == 2


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_json_summary_contains_counts(tmp_path):
    entries = (
        "type: link\ntitle: S1\nurl: https://example.com/s1\npriority: low\nstatus: new",
        "type: link\ntitle: S2\nurl: https://example.com/s2\npriority: normal\nstatus: new",
    )
    inbox = _write_inbox(tmp_path, _inbox_with(*entries))
    db_path = tmp_path / "test.sqlite"

    summary = import_submissions(parse_inbox(inbox), db_path)

    for key in ("total_in_file", "new", "skipped_duplicate", "errors", "dry_run"):
        assert key in summary, f"Missing key in summary: {key}"

    assert summary["total_in_file"] == 2
    assert summary["new"] == 2
    assert isinstance(summary["new"], int)
    assert isinstance(summary["skipped_duplicate"], int)

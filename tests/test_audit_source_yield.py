import csv
import json
import sqlite3
from pathlib import Path

from scripts.audit_source_yield import audit_source_yield


def _make_db(path: Path) -> Path:
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            site_url TEXT NOT NULL,
            feed_url TEXT,
            source_type TEXT NOT NULL,
            language TEXT,
            region TEXT,
            genre_tags TEXT,
            priority TEXT,
            active INTEGER,
            paywall TEXT,
            notes TEXT
        );
        CREATE TABLE items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            url TEXT,
            source_id TEXT,
            source_name TEXT,
            source_type TEXT,
            published_at TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT,
            matched_artists TEXT,
            matched_tags TEXT,
            matched_genres TEXT,
            score INTEGER NOT NULL DEFAULT 0,
            included_in_issue INTEGER NOT NULL DEFAULT 0,
            issue_id TEXT
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO sources
        (id, name, site_url, feed_url, source_type, genre_tags, priority, active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("alpha", "Alpha Blog", "https://alpha.example", "https://alpha.example/feed", "blog", "surf", "high", 1),
            ("beta", "Beta Archive", "https://beta.example", "https://beta.example/feed", "blog", "archive", "low", 1),
            ("gamma", "Gamma Zine", "https://gamma.example", "", "magazine", "garage", "medium", 1),
        ],
    )
    conn.executemany(
        """
        INSERT INTO items
        (title, url, source_id, source_name, source_type, published_at, first_seen_at, last_seen_at, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("Alpha One", "https://alpha.example/1", "alpha", "Alpha Blog", "blog", "2026-06-01", "2026-06-01T01:00:00Z", "2026-06-01T01:00:00Z", 55),
            ("Alpha Two", "https://alpha.example/2", "alpha", "Alpha Blog", "blog", "2026-06-02", "2026-06-02T01:00:00Z", "2026-06-02T01:00:00Z", 35),
            ("Alpha Three", "https://alpha.example/3", "alpha", "Alpha Blog", "blog", "2026-05-31", "2026-05-31T01:00:00Z", "2026-05-31T01:00:00Z", 10),
            ("Beta One", "https://beta.example/1", "beta", "Beta Archive", "blog", "2026-01-01", "2026-06-01T01:00:00Z", "2026-06-01T01:00:00Z", 5),
            ("Beta Two", "https://beta.example/2", "beta", "Beta Archive", "blog", "2026-01-02", "2026-06-01T02:00:00Z", "2026-06-01T02:00:00Z", 10),
            ("Gamma One", "https://gamma.example/1", "gamma", "Gamma Zine", "magazine", "2026-06-01", "2026-06-01T01:00:00Z", "2026-06-01T01:00:00Z", 25),
        ],
    )
    conn.commit()
    conn.close()
    return path


def _write_review(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "score_summary": {
                    "top_candidates": [
                        {"source_name": "alpha blog", "title": "A"},
                        {"source_name": "Alpha Blog", "title": "B"},
                        {"source_name": "ALPHA BLOG", "title": "C"},
                    ]
                },
                "issue_summary": {
                    "diversity_evidence": {
                        "skipped_by_source_cap": [
                            {"source_name": "ALPHA BLOG", "title": "D"},
                            {"source_name": "Alpha Blog", "title": "E"},
                        ],
                        "skipped_by_artist_cap": [
                            {"source_name": "Alpha Blog", "title": "F"},
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _write_issue(content_dir: Path, date: str) -> None:
    content_dir.mkdir(parents=True)
    (content_dir / f"{date}.en.json").write_text(
        json.dumps(
            {
                "items": [
                    {"source_name": "ALPHA BLOG", "title": "A"},
                    {"source_name": "Gamma Zine", "title": "G"},
                ]
            }
        ),
        encoding="utf-8",
    )


def _run(tmp_path: Path, review: Path | None = None, content_dir: Path | None = None) -> dict:
    db = _make_db(tmp_path / "coma.sqlite")
    return audit_source_yield(
        date="2026-06-02",
        review_json=review,
        db_path=db,
        content_dir=content_dir or (tmp_path / "content"),
        out_base=tmp_path / "reports" / "source-yield-2026-06-02",
    )


def _row(report: dict, source_name: str) -> dict:
    return next(row for row in report["rows"] if row["source_name"] == source_name)


def test_basic_per_source_counts_and_written_outputs(tmp_path):
    review = _write_review(tmp_path / "review.json")
    content_dir = tmp_path / "issues"
    _write_issue(content_dir, "2026-06-02")

    report = _run(tmp_path, review=review, content_dir=content_dir)

    alpha = _row(report, "Alpha Blog")
    assert alpha["items_total"] == 3
    assert alpha["scored_ge_min"] == 2
    assert alpha["max_score"] == 55
    assert alpha["avg_score"] == 33.33
    assert alpha["newest_first_seen_at"] == "2026-06-02T01:00:00Z"
    assert alpha["oldest_first_seen_at"] == "2026-05-31T01:00:00Z"
    assert alpha["newest_published_at"] == "2026-06-02"
    assert alpha["has_feed"] is True
    assert alpha["active"] is True

    assert (tmp_path / "reports" / "source-yield-2026-06-02.csv").exists()
    assert (tmp_path / "reports" / "source-yield-2026-06-02.json").exists()

    csv_rows = list(csv.DictReader((tmp_path / "reports" / "source-yield-2026-06-02.csv").open(encoding="utf-8")))
    assert csv_rows[0]["source_name"] == "Alpha Blog"
    saved = json.loads((tmp_path / "reports" / "source-yield-2026-06-02.json").read_text(encoding="utf-8"))
    assert saved["summary"]["total_items"] == 6


def test_selected_items_from_issue_json(tmp_path):
    content_dir = tmp_path / "issues"
    _write_issue(content_dir, "2026-06-02")

    report = _run(tmp_path, content_dir=content_dir)

    assert _row(report, "Alpha Blog")["selected"] == 1
    assert _row(report, "Gamma Zine")["selected"] == 1
    assert report["summary"]["sources_with_selection"] == 2


def test_skipped_by_source_cap_from_review_json(tmp_path):
    review = _write_review(tmp_path / "review.json")

    report = _run(tmp_path, review=review)

    alpha = _row(report, "Alpha Blog")
    assert alpha["skipped_by_source_cap"] == 2
    assert alpha["skipped_by_artist_cap"] == 1
    assert "2 skipped by source cap" in alpha["notes"]


def test_archive_noise_flag(tmp_path):
    db = _make_db(tmp_path / "coma.sqlite")
    conn = sqlite3.connect(str(db))
    conn.executemany(
        """
        INSERT INTO items
        (title, url, source_id, source_name, source_type, published_at, first_seen_at, last_seen_at, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (f"Beta Extra {i}", f"https://beta.example/extra-{i}", "beta", "Beta Archive", "blog", "2026-01-01", "2026-06-01T01:00:00Z", "2026-06-01T01:00:00Z", 1)
            for i in range(8)
        ],
    )
    conn.commit()
    conn.close()

    report = audit_source_yield("2026-06-02", None, db, tmp_path / "missing-content", tmp_path / "out")

    beta = _row(report, "Beta Archive")
    assert beta["items_total"] == 10
    assert beta["archive_noise_flag"] is True
    assert "archive/noise candidate" in beta["notes"]


def test_saturation_flag(tmp_path):
    review = _write_review(tmp_path / "review.json")

    report = _run(tmp_path, review=review)

    alpha = _row(report, "Alpha Blog")
    assert alpha["top_candidates"] == 3
    assert alpha["saturation_flag"] is True
    assert report["summary"]["saturation_sources"] == 1


def test_low_yield_flag(tmp_path):
    report = _run(tmp_path)

    beta = _row(report, "Beta Archive")
    gamma = _row(report, "Gamma Zine")
    assert beta["low_yield_flag"] is True
    assert gamma["low_yield_flag"] is False
    assert "low yield active feed" in beta["notes"]


def test_missing_review_json_and_missing_issue_json_do_not_crash(tmp_path):
    report = _run(tmp_path, review=tmp_path / "missing-review.json", content_dir=tmp_path / "missing-content")

    alpha = _row(report, "Alpha Blog")
    assert alpha["top_candidates"] == 0
    assert alpha["selected"] == 0
    assert alpha["skipped_by_source_cap"] == 0
    assert report["summary"]["total_selected"] == 0


def test_newest_published_at_handles_rfc_dates(tmp_path):
    db = _make_db(tmp_path / "coma.sqlite")
    conn = sqlite3.connect(str(db))
    conn.execute(
        """
        INSERT INTO items
        (title, url, source_id, source_name, source_type, published_at, first_seen_at, last_seen_at, score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Alpha RFC Newer",
            "https://alpha.example/rfc-newer",
            "alpha",
            "Alpha Blog",
            "blog",
            "Wed, 03 Jun 2026 12:00:00 GMT",
            "2026-06-03T01:00:00Z",
            "2026-06-03T01:00:00Z",
            40,
        ),
    )
    conn.commit()
    conn.close()

    report = audit_source_yield("2026-06-02", None, db, tmp_path / "missing-content", tmp_path / "out")

    assert _row(report, "Alpha Blog")["newest_published_at"] == "Wed, 03 Jun 2026 12:00:00 GMT"

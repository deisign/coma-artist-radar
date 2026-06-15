import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.build_telegram_draft import (
    DEFAULT_BASE_PATH,
    DEFAULT_BASE_URL,
    build_telegram_draft,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_issue(content_dir: Path, date: str, lang: str, n_items: int = 3) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    items = [
        {
            "id": i,
            "title": f"Test Article {i}: About rockabilly and psychobilly bands performing live",
            "url": f"https://example.com/article-{i}",
            "source_name": "Test Source",
            "published_at": "2026-05-25",
            "score": 80,
            "matched_artists": "",
            "matched_tags": "rockabilly, psychobilly, review",
            "matched_genres": "rockabilly",
        }
        for i in range(1, n_items + 1)
    ]
    issue = {
        "issue_date": date,
        "lang": lang,
        "draft": True,
        "generated_at": "2026-05-25T10:00:00Z",
        "min_score": 30,
        "total_items": n_items,
        "items": items,
    }
    (content_dir / f"{date}.{lang}.json").write_text(
        json.dumps(issue), encoding="utf-8"
    )


def _kwargs(tmp_path: Path, date: str, lang: str, n_items: int = 3) -> dict:
    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, date, lang, n_items)
    return {
        "date": date,
        "lang": lang,
        "content_dir": content_dir,
        "dist_dir": tmp_path / "dist",
        "reports_dir": tmp_path / "reports" / "telegram",
    }


# ---------------------------------------------------------------------------
# Output file creation
# ---------------------------------------------------------------------------

def test_creates_uk_txt(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert Path(summary["output_file"]).exists()
    assert summary["output_file"].endswith(".uk.txt")


def test_creates_en_txt(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "en"))
    assert Path(summary["output_file"]).exists()
    assert summary["output_file"].endswith(".en.txt")


# ---------------------------------------------------------------------------
# Language-specific text content
# ---------------------------------------------------------------------------

def test_uk_text_contains_povnyi_vypusk(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.uk.txt").read_text(encoding="utf-8")
    assert "Повний випуск" in text


def test_en_text_contains_full_issue(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "en")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.en.txt").read_text(encoding="utf-8")
    assert "Full issue" in text


def test_uk_text_contains_sogodni_v_poli(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.uk.txt").read_text(encoding="utf-8")
    assert "Сьогодні в полі" in text


def test_en_text_contains_in_the_field_today(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "en")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.en.txt").read_text(encoding="utf-8")
    assert "In the field today" in text


def test_text_contains_radar_header(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.uk.txt").read_text(encoding="utf-8")
    assert "coma.fm Radar" in text
    assert "2026-05-25" in text


# ---------------------------------------------------------------------------
# URL construction with base_path
# ---------------------------------------------------------------------------

def test_default_issue_url_uses_radar_domain(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert DEFAULT_BASE_URL == "https://radar.coma.fm"
    assert DEFAULT_BASE_PATH == ""
    assert summary["issue_url"] == "https://radar.coma.fm/uk/issues/2026-05-25.html"


def test_issue_url_contains_base_path(tmp_path):
    # base_url already includes the base path; issue_url is base_url + /lang/issues/date.html
    summary = build_telegram_draft(
        **_kwargs(tmp_path, "2026-05-25", "uk"),
        base_url="https://example.github.io/coma-artist-radar",
        base_path="/coma-artist-radar",
    )
    assert summary["issue_url"] == "https://example.github.io/coma-artist-radar/uk/issues/2026-05-25.html"


def test_issue_url_en_contains_base_path(tmp_path):
    summary = build_telegram_draft(
        **_kwargs(tmp_path, "2026-05-25", "en"),
        base_url="https://example.github.io/coma-artist-radar",
        base_path="/coma-artist-radar",
    )
    assert summary["issue_url"] == "https://example.github.io/coma-artist-radar/en/issues/2026-05-25.html"


def test_cover_url_contains_base_path(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    cover_dir = kw["dist_dir"] / "assets" / "covers" / "issues" / "2026-05-25"
    cover_dir.mkdir(parents=True)
    (cover_dir / "cover-uk.svg").write_text("<svg/>", encoding="utf-8")
    summary = build_telegram_draft(
        **kw,
        base_url="https://example.github.io/coma-artist-radar",
        base_path="/coma-artist-radar",
    )
    assert summary["cover_url"] == (
        "https://example.github.io/coma-artist-radar/assets/covers/issues/2026-05-25/cover-uk.svg"
    )


def test_cover_url_none_when_cover_missing(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert summary["cover_url"] is None


def test_cover_missing_adds_warning(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert any("cover" in w.lower() for w in summary["warnings"])


# ---------------------------------------------------------------------------
# max_chars respected
# ---------------------------------------------------------------------------

def test_max_chars_respected(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk", n_items=5), max_chars=200)
    assert summary["chars"] <= 200


def test_max_chars_default_1024(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert summary["max_chars"] == 1024


def test_chars_in_summary(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    assert isinstance(summary["chars"], int)
    assert summary["chars"] > 0


# ---------------------------------------------------------------------------
# Music tags not translated
# ---------------------------------------------------------------------------

def test_music_tags_not_translated_uk(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.uk.txt").read_text(encoding="utf-8")
    assert "rockabilly" in text or "psychobilly" in text


def test_music_tags_not_translated_en(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "en")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.en.txt").read_text(encoding="utf-8")
    assert "rockabilly" in text or "psychobilly" in text


def test_editorial_tag_review_excluded(tmp_path):
    kw = _kwargs(tmp_path, "2026-05-25", "uk")
    build_telegram_draft(**kw)
    text = (kw["reports_dir"] / "2026-05-25.uk.txt").read_text(encoding="utf-8")
    # "review" is an editorial tag and should not appear as a tag label
    # (it may appear in titles though, so we check it's not in brackets)
    assert "[review" not in text and "review]" not in text


# ---------------------------------------------------------------------------
# Fewer than 3 items — warning
# ---------------------------------------------------------------------------

def test_fewer_than_3_items_gives_warning(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk", n_items=2))
    assert len(summary["warnings"]) > 0
    assert any("2" in w or "item" in w.lower() for w in summary["warnings"])


def test_1_item_gives_warning(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk", n_items=1))
    assert any("item" in w.lower() for w in summary["warnings"])


def test_3_items_no_item_count_warning(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk", n_items=3))
    item_count_warnings = [w for w in summary["warnings"] if "expected at least" in w.lower()]
    assert len(item_count_warnings) == 0


# ---------------------------------------------------------------------------
# Summary structure
# ---------------------------------------------------------------------------

def test_summary_has_required_keys(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"))
    for key in (
        "issue_date", "lang", "output_file", "issue_url",
        "cover_url", "chars", "max_chars", "item_count", "warnings", "dry_run",
    ):
        assert key in summary, f"Missing key: {key}"


def test_summary_dry_run_true(tmp_path):
    summary = build_telegram_draft(**_kwargs(tmp_path, "2026-05-25", "uk"), dry_run=True)
    assert summary["dry_run"] is True


# ---------------------------------------------------------------------------
# send_telegram.py — dry-run
# ---------------------------------------------------------------------------

def test_send_telegram_dry_run_returns_summary(tmp_path):
    from scripts.send_telegram import run_send
    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, "2026-05-25", "uk")
    summary = run_send(
        date="2026-05-25",
        lang="uk",
        dry_run=True,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        reports_dir=tmp_path / "reports" / "telegram",
    )
    assert "issue_url" in summary
    assert summary["dry_run"] is True


def test_send_telegram_dry_run_no_network(tmp_path, monkeypatch):
    import urllib.request

    def _no_network(*a, **kw):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)

    from scripts.send_telegram import run_send
    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, "2026-05-25", "uk")
    run_send(
        date="2026-05-25",
        lang="uk",
        dry_run=True,
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        reports_dir=tmp_path / "reports" / "telegram",
    )


def test_send_telegram_send_flag_returns_nonzero_without_credentials():
    from scripts.send_telegram import main
    result = main(["--date", "2026-05-25", "--lang", "uk", "--send"])
    assert result != 0


def test_send_telegram_send_flag_prints_credentials_error(capsys):
    from scripts.send_telegram import main
    main(["--date", "2026-05-25", "--lang", "uk", "--send"])
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "TELEGRAM_BOT_TOKEN" in combined
    assert "TELEGRAM_CHAT_ID" in combined


def test_send_telegram_send_raises_without_credentials(tmp_path, monkeypatch):
    from scripts.send_telegram import run_send

    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, "2026-05-25", "uk")

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        run_send(
            date="2026-05-25",
            lang="uk",
            send=True,
            content_dir=content_dir,
            dist_dir=tmp_path / "dist",
            reports_dir=tmp_path / "reports" / "telegram",
            posts_path=tmp_path / "data" / "telegram_posts.json",
        )


def test_send_telegram_send_records_post_ledger(tmp_path, monkeypatch):
    from scripts import send_telegram

    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, "2026-05-25", "uk")

    def fake_send(*, bot_token, chat_id, text):
        assert bot_token == "token"
        assert chat_id == "@channel"
        assert "coma.fm Radar" in text
        return {"ok": True, "result": {"message_id": 123}}

    monkeypatch.setattr(send_telegram, "send_telegram_message", fake_send)

    posts_path = tmp_path / "data" / "telegram_posts.json"
    summary = send_telegram.run_send(
        date="2026-05-25",
        lang="uk",
        send=True,
        bot_token="token",
        chat_id="@channel",
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        reports_dir=tmp_path / "reports" / "telegram",
        posts_path=posts_path,
    )

    assert summary["posted"] is True
    assert summary["message_id"] == 123

    data = json.loads(posts_path.read_text(encoding="utf-8"))
    assert data["posts"][0]["issue_date"] == "2026-05-25"
    assert data["posts"][0]["lang"] == "uk"
    assert data["posts"][0]["message_id"] == 123


def test_send_telegram_send_skips_already_recorded_post(tmp_path, monkeypatch):
    from scripts import send_telegram

    content_dir = tmp_path / "content" / "issues"
    _make_issue(content_dir, "2026-05-25", "uk")

    posts_path = tmp_path / "data" / "telegram_posts.json"
    posts_path.parent.mkdir(parents=True)
    posts_path.write_text(
        json.dumps({
            "posts": [
                {
                    "issue_date": "2026-05-25",
                    "lang": "uk",
                    "issue_url": "https://radar.coma.fm/uk/issues/2026-05-25.html",
                }
            ]
        }),
        encoding="utf-8",
    )

    def fail_send(*a, **kw):
        raise AssertionError("unexpected Telegram send")

    monkeypatch.setattr(send_telegram, "send_telegram_message", fail_send)

    summary = send_telegram.run_send(
        date="2026-05-25",
        lang="uk",
        send=True,
        bot_token="token",
        chat_id="@channel",
        content_dir=content_dir,
        dist_dir=tmp_path / "dist",
        reports_dir=tmp_path / "reports" / "telegram",
        posts_path=posts_path,
    )

    assert summary["posted"] is False
    assert summary["skipped"] is True
    assert "already recorded" in summary["reason"]


# ---------------------------------------------------------------------------
# build_daily_draft.py — --telegram-dry-run
# ---------------------------------------------------------------------------

_FETCH_SUMMARY = {
    "sources_total": 0, "sources_with_feed": 0, "sources_checked": 0,
    "items_found": 0, "inserted": 0, "skipped_duplicate": 0, "errors": 0, "dry_run": False,
}
_SCORE_SUMMARY = {
    "items_total": 0, "items_checked": 0, "updated": 0, "skipped": 0,
    "errors": 0, "dry_run": False, "top_candidates": [],
}
_ISSUE_SUMMARY = {
    "issue_date": "2026-01-01", "languages": ["en", "uk"],
    "selected_items": 3, "output_files": [], "draft": True,
}
_TAG_SUMMARY = {
    "languages": ["en", "uk"], "tags_total": 0, "tags_with_items": 0,
    "pages_written": 0, "unknown_tags": [], "output_files": [],
}
_SITE_SUMMARY = {
    "issues_total": 0, "pages_written": 0, "output_files": [],
    "base_url": DEFAULT_BASE_URL, "base_path": DEFAULT_BASE_PATH, "dry_run": False,
}
_TELEGRAM_SUMMARY = {
    "issue_date": "2026-01-01", "lang": "uk",
    "output_file": "/tmp/2026-01-01.uk.txt",
    "issue_url": "https://example.com/uk/issues/2026-01-01.html",
    "cover_url": None, "chars": 300, "max_chars": 1024,
    "item_count": 3, "warnings": [], "dry_run": True,
}


def _patch_pipeline(monkeypatch):
    for name, rv in [
        ("sync_sources", {}),
        ("load_sources_yaml", []),
        ("fetch_and_store", _FETCH_SUMMARY),
        ("score_items", _SCORE_SUMMARY),
        ("build_issue", _ISSUE_SUMMARY),
        ("build_tag_pages", _TAG_SUMMARY),
        ("build_site", _SITE_SUMMARY),
    ]:
        monkeypatch.setattr(f"scripts.build_daily_draft.{name}", MagicMock(return_value=rv))


def test_telegram_dry_run_includes_telegram_summary(monkeypatch, tmp_path):
    from scripts.build_daily_draft import run_pipeline

    _patch_pipeline(monkeypatch)
    tg_mock = MagicMock(return_value=_TELEGRAM_SUMMARY)
    monkeypatch.setattr("scripts.build_daily_draft.build_telegram_draft", tg_mock)

    summary = run_pipeline(
        date="2026-01-01",
        telegram_dry_run=True,
        db_path=tmp_path / "test.sqlite",
        sources_path=tmp_path / "sources.yaml",
        inbox_path=tmp_path / "manual.md",
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
    )

    assert "telegram_summary" in summary
    assert summary["telegram_summary"] is not None
    tg_mock.assert_called_once()


def test_no_telegram_dry_run_summary_is_none(monkeypatch, tmp_path):
    from scripts.build_daily_draft import run_pipeline

    _patch_pipeline(monkeypatch)

    summary = run_pipeline(
        date="2026-01-01",
        db_path=tmp_path / "test.sqlite",
        sources_path=tmp_path / "sources.yaml",
        inbox_path=tmp_path / "manual.md",
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
    )

    assert summary.get("telegram_summary") is None


def test_telegram_dry_run_calls_build_telegram_draft_with_uk(monkeypatch, tmp_path):
    from scripts.build_daily_draft import run_pipeline

    _patch_pipeline(monkeypatch)
    tg_mock = MagicMock(return_value=_TELEGRAM_SUMMARY)
    monkeypatch.setattr("scripts.build_daily_draft.build_telegram_draft", tg_mock)

    run_pipeline(
        date="2026-01-01",
        telegram_dry_run=True,
        db_path=tmp_path / "test.sqlite",
        sources_path=tmp_path / "sources.yaml",
        inbox_path=tmp_path / "manual.md",
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
    )

    _, kwargs = tg_mock.call_args
    assert kwargs.get("lang") == "uk"


def test_telegram_dry_run_file_not_found_gives_skipped_summary(monkeypatch, tmp_path):
    from scripts.build_daily_draft import run_pipeline

    _patch_pipeline(monkeypatch)
    monkeypatch.setattr(
        "scripts.build_daily_draft.build_telegram_draft",
        MagicMock(side_effect=FileNotFoundError("no issue")),
    )

    summary = run_pipeline(
        date="2026-01-01",
        telegram_dry_run=True,
        db_path=tmp_path / "test.sqlite",
        sources_path=tmp_path / "sources.yaml",
        inbox_path=tmp_path / "manual.md",
        content_dir=tmp_path / "content" / "issues",
        dist_dir=tmp_path / "dist",
    )

    assert summary["telegram_summary"] is not None
    assert summary["telegram_summary"].get("skipped") is True

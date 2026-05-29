import csv
from pathlib import Path

from scripts.audit_opml_sources import audit_opml, iter_opml_feeds, suggested_action


def _write_sample_opml(path: Path) -> None:
    path.write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<opml version="1.0">
  <body>
    <outline text="Music Mags">
      <outline text="No Depression" title="No Depression" type="rss" xmlUrl="https://nodepression.com/feed" htmlUrl="https://nodepression.com"/>
      <outline text="American Songwriter" type="rss" xmlUrl="https://americansongwriter.com/feed" htmlUrl="https://americansongwriter.com"/>
    </outline>
    <outline text="Nested">
      <outline text="Surf">
        <outline text="Surf Guitar 101" type="rss" xmlUrl="https://surf.example/feed" htmlUrl="https://surf.example"/>
      </outline>
    </outline>
    <outline text="Design">
      <outline text="Design Blog" type="rss" xmlUrl="https://design.example/feed" htmlUrl="https://design.example"/>
    </outline>
    <outline text="Duplicate Folder">
      <outline text="No Depression Copy" type="rss" xmlUrl="https://nodepression.com/feed" htmlUrl="https://nodepression.com"/>
    </outline>
  </body>
</opml>
""",
        encoding="utf-8",
    )


def test_iter_opml_feeds_is_recursive(tmp_path):
    opml = tmp_path / "feeds.opml"
    _write_sample_opml(opml)

    feeds = iter_opml_feeds(opml)

    assert len(feeds) == 5
    assert any(f["title"] == "Surf Guitar 101" and f["category_path"] == "Nested / Surf" for f in feeds)


def test_audit_opml_writes_csv_with_actions_and_duplicates(tmp_path):
    opml = tmp_path / "feeds.opml"
    out = tmp_path / "audit.csv"
    _write_sample_opml(opml)

    summary = audit_opml(opml, out)

    assert summary["outline_feeds"] == 5
    assert summary["unique_feed_urls"] == 4
    assert summary["duplicate_feed_urls"] == 1

    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert len(rows) == 5
    assert any(row["duplicate_url"] == "true" and row["suggested_action"] == "DUPLICATE" for row in rows)
    assert any(row["title"] == "Surf Guitar 101" and row["suggested_action"] == "IMPORT_CORE" for row in rows)


def test_suggested_action_skips_low_relevance_design_duplicate_safe():
    assert suggested_action("Design", "Layout Blog", "https://example.com/feed", 0, False) == "SKIP_NON_MUSIC"
    assert suggested_action("Music Mags", "Duplicate", "https://example.com/feed", 9, True) == "DUPLICATE"

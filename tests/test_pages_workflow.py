from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKFLOW = _REPO_ROOT / ".github" / "workflows" / "pages.yml"


def _content() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def test_workflow_file_exists():
    assert _WORKFLOW.exists()


def test_workflow_has_workflow_dispatch():
    assert "workflow_dispatch" in _content()


def test_workflow_has_push_main():
    content = _content()
    assert "push" in content
    assert "main" in content


def test_workflow_has_pages_write():
    assert "pages: write" in _content()


def test_workflow_has_id_token_write():
    assert "id-token: write" in _content()


def test_workflow_has_upload_pages_artifact():
    assert "actions/upload-pages-artifact" in _content()


def test_workflow_has_deploy_pages():
    assert "actions/deploy-pages" in _content()


def test_workflow_has_daily_draft_command():
    content = _content()
    assert "python scripts/build_daily_draft.py" in content
    assert "--base-url https://radar.coma.fm" in content
    assert '--base-path ""' in content
    assert "--fetch-limit 50" in content
    assert "--issue-limit 10" in content


def test_workflow_has_pytest():
    assert "python -m pytest -q tests" in _content()


def test_workflow_has_contents_write_for_published_state_commit():
    assert "contents: write" in _content()


def test_workflow_has_concurrency():
    assert "concurrency" in _content()


def test_workflow_artifact_path_is_dist():
    content = _content()
    assert "path: dist" in content


def test_workflow_deploy_needs_build():
    content = _content()
    assert "needs: build" in content


def test_workflow_uses_ubuntu():
    assert "ubuntu-latest" in _content()


def test_workflow_has_custom_domain_base_url():
    assert "https://radar.coma.fm" in _content()


def test_workflow_has_empty_base_path_for_custom_domain():
    assert '--base-path ""' in _content()


def test_workflow_builds_public_issue_with_deeper_fetch_and_publish():
    content = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")

    assert "--fetch-limit 50" in content
    assert "--issue-limit 10" in content
    assert "--publish" in content
    assert "--validate" in content
    assert "Assert public issue quality" in content
    assert "expected at least 3 items" in content
    assert "expected draft=false" in content


def test_workflow_writes_pages_cname():
    content = _content()
    assert "radar.coma.fm" in content
    assert "dist/CNAME" in content


def test_workflow_commits_published_issue_state():
    content = _content()
    assert "Commit published issue state" in content
    assert "data/published_items.json" in content
    assert "content/issues/${ISSUE_DATE}.en.json" in content
    assert "content/issues/${ISSUE_DATE}.uk.json" in content
    assert "[skip ci]" in content
    assert "git add -f content/issues/${ISSUE_DATE}.en.json content/issues/${ISSUE_DATE}.uk.json" in content
    assert "git push" in content


def test_workflow_has_telegram_job_after_deploy():
    content = _content()
    assert "telegram:" in content
    assert "needs: deploy" in content
    assert "github.event_name != 'push'" in content


def test_workflow_sends_telegram_from_secrets():
    content = _content()
    assert "TELEGRAM_BOT_TOKEN" in content
    assert "TELEGRAM_CHAT_ID" in content
    assert "python scripts/send_telegram.py" in content
    assert "--send" in content
    assert "--lang uk" in content


def test_workflow_commits_telegram_post_state():
    content = _content()
    assert "data/telegram_posts.json" in content
    assert "Record Telegram Radar post ${ISSUE_DATE} [skip ci]" in content

def test_workflow_runs_daily_at_1005_kyiv_summer_time():
    content = _content()
    assert 'cron: "5 7 * * *"' in content

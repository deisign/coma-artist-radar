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


def test_workflow_has_build_site_command():
    assert "python scripts/build_site.py" in _content()


def test_workflow_has_build_tag_pages_command():
    assert "python scripts/build_tag_pages.py" in _content()


def test_workflow_has_pytest():
    assert "python -m pytest -q tests" in _content()


def test_workflow_has_contents_read():
    assert "contents: read" in _content()


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


def test_workflow_has_github_pages_base_url():
    assert "https://deisign.github.io/coma-artist-radar" in _content()


def test_workflow_has_base_path():
    assert "--base-path /coma-artist-radar" in _content()

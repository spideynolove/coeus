from pathlib import Path


def test_active_repo_contains_only_rewrite_runtime_surface():
    root = Path(__file__).resolve().parent.parent

    for legacy_path in [
        "main.py",
        "mcp_server.py",
        "config.py",
        "embedders.py",
        "core",
        "storage",
        "watcher",
        "tests/test_ast_chunker.py",
        "tests/test_setup.py",
    ]:
        assert not (root / legacy_path).exists()

    assert (root / "coeus" / "interfaces" / "cli.py").exists()
    assert (root / "coeus" / "interfaces" / "mcp.py").exists()


def test_legacy_docs_are_archived_and_active_docs_match_rewrite_surface():
    root = Path(__file__).resolve().parent.parent

    archive_root = root / "docs" / "archive" / "legacy-coeus"
    assert archive_root.exists()
    assert any(archive_root.rglob("*.md"))

    readme = (root / "README.md").read_text()
    claude = (root / "CLAUDE.md").read_text()

    for content in [readme, claude]:
        assert "coeus run" in content
        assert "coeus show-run" in content
        assert "coeus list-runs" in content
        assert "coeus ingest" not in content
        assert "coeus ask" not in content
        assert "coeus watch" not in content
        assert "coeus setup" not in content

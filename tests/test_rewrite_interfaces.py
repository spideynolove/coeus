import importlib
import json
from pathlib import Path

from coeus.experiment import CorpusSource, ExperimentSpec, StageConfig, create_basic_spec
from coeus.interfaces.common import run_spec


def test_package_scripts_point_to_rewrite_interfaces():
    pyproject = Path("pyproject.toml").read_text()

    assert 'coeus = "coeus.interfaces.cli:main"' in pyproject
    assert 'coeus-mcp = "coeus.interfaces.mcp:main"' in pyproject
    assert 'coeus = "main:main"' not in pyproject
    assert 'coeus-mcp = "mcp_server:main"' not in pyproject


def test_rewrite_interface_modules_are_importable():
    importlib.import_module("coeus.interfaces.cli")
    importlib.import_module("coeus.interfaces.mcp")


def test_run_spec_resolves_paths_relative_to_spec_file_and_persists_spec(tmp_path):
    spec_root = tmp_path / "tmp_spec_paths"
    config_dir = spec_root / "configs"
    data_dir = spec_root / "data"
    config_dir.mkdir(parents=True)
    data_dir.mkdir()
    (data_dir / "doc.txt").write_text("alpha beta gamma\n")

    spec = ExperimentSpec(
        corpus=CorpusSource(
            type="local_directory",
            path="../data",
            extensions=[".txt"],
        ),
        stages=[
            StageConfig(name="candidate_gen", type="lexical", params={"limit": 5}),
            StageConfig(name="assembly", type="simple", params={"max_chunks": 3}),
        ],
        metadata={"queries": ["alpha"]},
    )
    spec_path = config_dir / "spec.json"
    spec.to_json(spec_path)

    summary = run_spec(spec_path, tmp_path / "artifacts")

    saved_spec_path = tmp_path / "artifacts" / "specs" / f"{summary['spec_id']}.json"

    assert summary["document_count"] == 1
    assert saved_spec_path.exists()
    saved_spec = json.loads(saved_spec_path.read_text())
    assert saved_spec["corpus"]["path"] == str(data_dir.resolve())
    assert saved_spec["corpus"]["type"] == "local_directory"


def test_create_basic_spec_reclassifies_relative_directory_after_resolution(tmp_path):
    spec_root = tmp_path / "tmp_spec_paths_recheck"
    config_dir = spec_root / "configs"
    data_dir = spec_root / "data"
    config_dir.mkdir(parents=True)
    data_dir.mkdir()
    (data_dir / "doc.txt").write_text("alpha beta gamma\n")

    spec = create_basic_spec("../data", queries=["alpha"])
    spec_path = config_dir / "spec.json"
    spec.to_json(spec_path)

    summary = run_spec(spec_path, tmp_path / "artifacts")

    saved_spec_path = tmp_path / "artifacts" / "specs" / f"{summary['spec_id']}.json"
    saved_spec = json.loads(saved_spec_path.read_text())

    assert summary["document_count"] == 1
    assert saved_spec["corpus"]["type"] == "local_directory"


def test_docs_match_rewrite_command_surface():
    readme = Path("README.md").read_text()
    claude = Path("CLAUDE.md").read_text()

    for content in (readme, claude):
        assert "coeus run" in content
        assert "coeus show-run" in content
        assert "coeus list-runs" in content
        assert "coeus ingest" not in content
        assert "coeus ask" not in content
        assert "coeus watch" not in content
        assert "coeus setup" not in content

    assert "run_experiment" in readme
    assert "get_run_summary" in readme
    assert "get_runs" in readme

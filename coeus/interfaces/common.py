import json
from pathlib import Path
from typing import Any, Optional
from coeus.artifacts import serialize_artifact
from coeus.experiment import ExperimentSpec
from coeus.runner import ExperimentRunner
from coeus.store import LocalFilesystemStore, LocalFilesystemStoreConfig

def get_store(root_dir: str | Path) -> LocalFilesystemStore:
    return LocalFilesystemStore(LocalFilesystemStoreConfig(root_dir=Path(root_dir)))

def load_spec(path: str | Path) -> ExperimentSpec:
    return ExperimentSpec.from_json(Path(path))

def run_spec(spec_path: str | Path, artifacts_dir: str | Path='artifacts') -> dict[str, Any]:
    store = get_store(artifacts_dir)
    runner = ExperimentRunner(store)
    spec = load_spec(spec_path)
    run_id = runner.run(spec)
    return serialize_artifact(runner.load_run(run_id))

def load_run_summary(run_id: str, artifacts_dir: str | Path='artifacts') -> dict[str, Any]:
    store = get_store(artifacts_dir)
    return serialize_artifact(store.load_run_summary(run_id))

def list_runs(artifacts_dir: str | Path='artifacts', spec_id: Optional[str]=None, status: Optional[str]=None) -> list[dict[str, Any]]:
    store = get_store(artifacts_dir)
    return store.list_runs(spec_id=spec_id, status=status)

def to_json(data: Any) -> str:
    return json.dumps(data, indent=2)

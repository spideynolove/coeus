from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Literal, Union
import json
import shutil
from datetime import datetime
from coeus.experiment import ExperimentSpec
from coeus.artifacts import DocumentArtifact, ChunkArtifact, CandidateArtifact, AssembledContext, StageFailure, QueryMetric, RunSummary, serialize_artifact

class ArtifactStoreError(Exception):
    pass

class ArtifactNotFound(ArtifactStoreError):
    pass

class ArtifactStore(ABC):

    @abstractmethod
    def save_spec(self, spec: ExperimentSpec) -> Path:
        pass

    @abstractmethod
    def load_spec(self, spec_id: str) -> ExperimentSpec:
        pass

    @abstractmethod
    def create_run(self, spec_id: str, run_id: str, started_at: datetime) -> Path:
        pass

    @abstractmethod
    def save_artifact(self, run_id: str, artifact_type: str, artifact: Any, artifact_id: Optional[str]=None) -> Path:
        pass

    @abstractmethod
    def load_artifact(self, run_id: str, artifact_type: str, artifact_id: Optional[str]=None) -> Any:
        pass

    @abstractmethod
    def save_run_summary(self, run_id: str, summary: RunSummary) -> Path:
        pass

    @abstractmethod
    def load_run_summary(self, run_id: str) -> RunSummary:
        pass

    @abstractmethod
    def list_runs(self, spec_id: Optional[str]=None, status: Optional[str]=None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def get_run_dir(self, run_id: str) -> Path:
        pass

@dataclass
class LocalFilesystemStoreConfig:
    root_dir: Union[str, Path]
    pretty_json: bool = True
    spec_dir: str = 'specs'
    runs_dir: str = 'runs'

    def __post_init__(self):
        if isinstance(self.root_dir, str):
            self.root_dir = Path(self.root_dir)

class LocalFilesystemStore(ArtifactStore):

    def __init__(self, config: LocalFilesystemStoreConfig):
        self.config = config
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        self.config.root_dir.mkdir(parents=True, exist_ok=True)
        (self.config.root_dir / self.config.spec_dir).mkdir(exist_ok=True)
        (self.config.root_dir / self.config.runs_dir).mkdir(exist_ok=True)

    def _spec_path(self, spec_id: str) -> Path:
        return self.config.root_dir / self.config.spec_dir / f'{spec_id}.json'

    def _run_dir(self, run_id: str) -> Path:
        return self.config.root_dir / self.config.runs_dir / run_id

    def _run_artifact_path(self, run_id: str, artifact_type: str) -> Path:
        return self._run_dir(run_id) / f'{artifact_type}.json'

    def _write_json(self, path: Path, data: Any) -> None:
        kwargs = {'indent': 2} if self.config.pretty_json else {}
        path.write_text(json.dumps(data, **kwargs))

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            raise ArtifactNotFound(f'Artifact not found: {path}')
        return json.loads(path.read_text())

    def _update_run_metadata(self, run_id: str, updates: Dict[str, Any]) -> None:
        metadata_path = self._run_dir(run_id) / 'metadata.json'
        metadata = self._read_json(metadata_path) if metadata_path.exists() else {}
        metadata.update({key: value for (key, value) in updates.items() if value is not None})
        self._write_json(metadata_path, metadata)

    def save_spec(self, spec: ExperimentSpec) -> Path:
        path = self._spec_path(spec.spec_id)
        self._write_json(path, spec.to_dict())
        return path

    def load_spec(self, spec_id: str) -> ExperimentSpec:
        path = self._spec_path(spec_id)
        data = self._read_json(path)
        return ExperimentSpec.from_dict(data)

    def create_run(self, spec_id: str, run_id: str, started_at: datetime) -> Path:
        run_dir = self._run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        metadata = {'run_id': run_id, 'spec_id': spec_id, 'started_at': started_at.isoformat(), 'status': 'running'}
        self._write_json(run_dir / 'metadata.json', metadata)
        return run_dir

    def save_artifact(self, run_id: str, artifact_type: str, artifact: Any, artifact_id: Optional[str]=None) -> Path:
        if artifact_id:
            artifact_dir = self._run_dir(run_id) / artifact_type
            artifact_dir.mkdir(exist_ok=True)
            path = artifact_dir / f'{artifact_id}.json'
        else:
            path = self._run_artifact_path(run_id, artifact_type)
        if hasattr(artifact, '__dataclass_fields__'):
            data = serialize_artifact(artifact)
        elif isinstance(artifact, list) and artifact and hasattr(artifact[0], '__dataclass_fields__'):
            data = [serialize_artifact(a) for a in artifact]
        else:
            data = artifact
        self._write_json(path, data)
        if artifact_type == 'status' and artifact_id is None and isinstance(data, dict):
            self._update_run_metadata(run_id, data)
        return path

    def load_artifact(self, run_id: str, artifact_type: str, artifact_id: Optional[str]=None) -> Any:
        if artifact_id:
            path = self._run_dir(run_id) / artifact_type / f'{artifact_id}.json'
        else:
            path = self._run_artifact_path(run_id, artifact_type)
        return self._read_json(path)

    def save_run_summary(self, run_id: str, summary: RunSummary) -> Path:
        path = self._run_artifact_path(run_id, 'summary')
        self._write_json(path, serialize_artifact(summary))
        self._update_run_metadata(run_id, {'status': summary.status, 'completed_at': summary.completed_at.isoformat() if summary.completed_at else None})
        return path

    def load_run_summary(self, run_id: str) -> RunSummary:
        data = self._read_json(self._run_artifact_path(run_id, 'summary'))
        return RunSummary(spec_id=data['spec_id'], run_id=data['run_id'], started_at=datetime.fromisoformat(data['started_at']), completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None, status=data['status'], document_count=data['document_count'], chunk_count=data['chunk_count'], failures=[StageFailure(stage=failure['stage'], stage_type=failure['stage_type'], error_type=failure['error_type'], error_message=failure['error_message'], timestamp=datetime.fromisoformat(failure['timestamp']), input_snapshot=failure.get('input_snapshot', {})) for failure in data.get('failures', [])], query_metrics=[QueryMetric(query=metric['query'], relevant_chunk_ids=metric['relevant_chunk_ids'], retrieved_chunk_ids=metric['retrieved_chunk_ids'], precision=metric['precision'], recall=metric['recall'], f1=metric['f1'], metadata=metric.get('metadata', {})) for metric in data.get('query_metrics', [])], metadata=data.get('metadata', {}))

    def list_runs(self, spec_id: Optional[str]=None, status: Optional[str]=None) -> List[Dict[str, Any]]:
        runs_dir = self.config.root_dir / self.config.runs_dir
        if not runs_dir.exists():
            return []
        runs = []
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            metadata_path = run_dir / 'metadata.json'
            if not metadata_path.exists():
                continue
            metadata = self._read_json(metadata_path)
            status_path = run_dir / 'status.json'
            if status_path.exists():
                metadata.update(self._read_json(status_path))
            if spec_id and metadata.get('spec_id') != spec_id:
                continue
            if status and metadata.get('status') != status:
                continue
            runs.append({'run_id': metadata['run_id'], 'spec_id': metadata['spec_id'], 'status': metadata['status'], 'started_at': metadata['started_at'], 'completed_at': metadata.get('completed_at'), 'run_dir': str(run_dir)})
        return sorted(runs, key=lambda r: r['started_at'], reverse=True)

    def get_run_dir(self, run_id: str) -> Path:
        run_dir = self._run_dir(run_id)
        if not run_dir.exists():
            raise ArtifactNotFound(f'Run not found: {run_id}')
        return run_dir

def default_store(root_dir: Optional[Path]=None) -> LocalFilesystemStore:
    if root_dir is None:
        root_dir = Path.cwd() / 'artifacts'
    config = LocalFilesystemStoreConfig(root_dir=root_dir)
    return LocalFilesystemStore(config)

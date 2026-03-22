from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Literal
from datetime import datetime
from pathlib import Path
import json
import hashlib

@dataclass(frozen=True)
class DocumentArtifact:
    id: str
    source: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()[:16]

@dataclass(frozen=True)
class ChunkArtifact:
    id: str
    document_id: str
    content: str
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class CandidateArtifact:
    chunk_id: str
    score: float
    method: str
    stage: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class AssembledContext:
    query: str
    chunk_ids: List[str]
    total_tokens_estimate: int
    assembly_method: str
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class StageFailure:
    stage: str
    stage_type: str
    error_type: str
    error_message: str
    timestamp: datetime
    input_snapshot: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class QueryMetric:
    query: str
    relevant_chunk_ids: List[str]
    retrieved_chunk_ids: List[str]
    precision: float
    recall: float
    f1: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class RunSummary:
    spec_id: str
    run_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    status: Literal['running', 'completed', 'failed', 'partial']
    document_count: int
    chunk_count: int
    failures: List[StageFailure] = field(default_factory=list)
    query_metrics: List[QueryMetric] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return self.status == 'failed' or len(self.failures) > 0

def generate_run_id(spec_id: str, timestamp: datetime) -> str:
    content = f'{spec_id}:{timestamp.isoformat()}'
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def serialize_artifact(artifact: Any) -> Dict[str, Any]:
    if isinstance(artifact, (DocumentArtifact, ChunkArtifact, CandidateArtifact, AssembledContext, StageFailure, QueryMetric, RunSummary)):
        from dataclasses import asdict
        data = asdict(artifact)
        data = _convert_datetime(data)
        return data
    raise TypeError(f'Cannot serialize artifact of type: {type(artifact)}')

def _convert_datetime(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: _convert_datetime(v) for (k, v) in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetime(item) for item in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return obj

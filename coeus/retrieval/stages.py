from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol
from pathlib import Path
from coeus.artifacts import DocumentArtifact, ChunkArtifact, CandidateArtifact, AssembledContext, StageFailure
from coeus.experiment import StageConfig

class StageContext:

    def __init__(self, run_id: str, spec_id: str, artifacts_dir: Path, metadata: Optional[Dict[str, Any]]=None):
        self.run_id = run_id
        self.spec_id = spec_id
        self.artifacts_dir = artifacts_dir
        self.metadata = metadata or {}

@dataclass
class StageResult:
    stage_name: str
    stage_type: str
    outputs: Dict[str, Any]
    duration_seconds: float
    failure: Optional[StageFailure] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class QueryTransform(ABC):

    @abstractmethod
    def transform(self, query: str, context: StageContext) -> str:
        pass

    @abstractmethod
    def stage_type(self) -> str:
        pass

class CandidateGenerator(ABC):

    @abstractmethod
    def generate(self, query: str, chunks: List[ChunkArtifact], context: StageContext) -> List[CandidateArtifact]:
        pass

    @abstractmethod
    def stage_type(self) -> str:
        pass

class CandidateFusion(ABC):

    @abstractmethod
    def fuse(self, candidates_list: List[List[CandidateArtifact]], context: StageContext) -> List[CandidateArtifact]:
        pass

    @abstractmethod
    def stage_type(self) -> str:
        pass

class CandidateReranker(ABC):

    @abstractmethod
    def rerank(self, candidates: List[CandidateArtifact], query: str, context: StageContext) -> List[CandidateArtifact]:
        pass

    @abstractmethod
    def stage_type(self) -> str:
        pass

class ContextAssembler(ABC):

    @abstractmethod
    def assemble(self, candidates: List[CandidateArtifact], chunks: Dict[str, ChunkArtifact], query: str, context: StageContext) -> AssembledContext:
        pass

    @abstractmethod
    def stage_type(self) -> str:
        pass

class StageFactory(ABC):
    _registry: Dict[str, type] = {}

    @classmethod
    def register(cls, stage_type: str, stage_class: type):
        cls._registry[stage_type] = stage_class

    @classmethod
    def create(cls, config: StageConfig) -> Any:
        stage_class = cls._registry.get(config.type)
        if stage_class is None:
            raise ValueError(f'Unknown stage type: {config.type}')
        return stage_class(**config.params)

    @classmethod
    def known_types(cls) -> List[str]:
        return list(cls._registry.keys())

@dataclass
class QueryTransformResult:
    original_query: str
    transformed_query: str
    method: str

@dataclass
class CandidateGenerationResult:
    query: str
    candidates: List[Dict[str, Any]]
    method: str
    total_candidates: int

@dataclass
class AssemblyResult:
    query: str
    chunk_ids: List[str]
    total_chunks: int
    total_tokens_estimate: int
    assembly_method: str

def create_stage_result(stage_name: str, stage_type: str, outputs: Dict[str, Any], duration_seconds: float, failure: Optional[StageFailure]=None) -> StageResult:
    return StageResult(stage_name=stage_name, stage_type=stage_type, outputs=outputs, duration_seconds=duration_seconds, failure=failure)

from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Literal
from pathlib import Path
import json
import hashlib

@dataclass(frozen=True)
class CorpusSource:
    type: Literal['local_files', 'local_directory']
    path: str
    extensions: Optional[List[str]] = None
    recursive: bool = True

@dataclass(frozen=True)
class StageConfig:
    name: str
    type: str
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

@dataclass(frozen=True)
class EvalSetRef:
    path: str
    format: Literal['jsonl', 'json'] = 'jsonl'

@dataclass(frozen=True)
class ExperimentSpec:
    corpus: CorpusSource
    stages: List[StageConfig]
    eval_set: Optional[EvalSetRef] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def spec_id(self) -> str:
        content = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExperimentSpec':
        corpus_data = data.pop('corpus')
        corpus = CorpusSource(**corpus_data)
        stages_data = data.pop('stages', [])
        stages = [StageConfig(**s) for s in stages_data]
        eval_data = data.pop('eval_set', None)
        eval_set = EvalSetRef(**eval_data) if eval_data else None
        return cls(corpus=corpus, stages=stages, eval_set=eval_set, metadata=data.pop('metadata', {}))

    def to_json(self, path: Optional[Path]=None) -> str:
        json_str = json.dumps(self.to_dict(), indent=2)
        if path:
            path.write_text(json_str)
        return json_str

    def resolved(self, base_dir: Path) -> 'ExperimentSpec':
        base_dir = base_dir.resolve()
        corpus_path = Path(self.corpus.path)
        resolved_corpus = corpus_path if corpus_path.is_absolute() else (base_dir / corpus_path).resolve()
        resolved_corpus_type = self.corpus.type
        if resolved_corpus.exists():
            resolved_corpus_type = 'local_directory' if resolved_corpus.is_dir() else 'local_files'
        resolved_eval = self.eval_set
        if self.eval_set:
            eval_path = Path(self.eval_set.path)
            resolved_eval_path = eval_path if eval_path.is_absolute() else (base_dir / eval_path).resolve()
            resolved_eval = replace(self.eval_set, path=str(resolved_eval_path))
        return replace(self, corpus=replace(self.corpus, type=resolved_corpus_type, path=str(resolved_corpus)), eval_set=resolved_eval)

    @classmethod
    def from_json(cls, path: Path) -> 'ExperimentSpec':
        return cls.from_dict(json.loads(path.read_text())).resolved(path.parent)

def create_basic_spec(corpus_path: str, eval_path: Optional[str]=None, **metadata) -> ExperimentSpec:
    corpus = CorpusSource(type='local_directory' if Path(corpus_path).is_dir() else 'local_files', path=corpus_path)
    stages = [StageConfig(name='candidate_gen', type='lexical', params={'limit': 10}), StageConfig(name='assembly', type='simple', params={'max_chunks': 5})]
    eval_set = EvalSetRef(path=eval_path) if eval_path else None
    return ExperimentSpec(corpus=corpus, stages=stages, eval_set=eval_set, metadata=metadata)

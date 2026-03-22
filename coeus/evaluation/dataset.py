from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

@dataclass
class EvalQuery:
    query_id: str
    query: str
    relevant_chunk_ids: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalDataset:
    name: str
    queries: List[EvalQuery]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def query_count(self) -> int:
        return len(self.queries)

    def get_query(self, query_id: str) -> Optional[EvalQuery]:
        for q in self.queries:
            if q.query_id == query_id:
                return q
        return None

    def to_jsonl(self, path: Path) -> None:
        with open(path, 'w') as f:
            for q in self.queries:
                record = {'query_id': q.query_id, 'query': q.query, 'relevant_chunk_ids': q.relevant_chunk_ids, 'metadata': q.metadata}
                f.write(json.dumps(record) + '\n')

    @classmethod
    def from_jsonl(cls, path: Path, name: Optional[str]=None) -> 'EvalDataset':
        queries = []
        with open(path, 'r') as f:
            for line in f:
                record = json.loads(line.strip())
                queries.append(EvalQuery(query_id=record['query_id'], query=record['query'], relevant_chunk_ids=record['relevant_chunk_ids'], metadata=record.get('metadata', {})))
        if name is None:
            name = path.stem
        return cls(name=name, queries=queries)

    def to_json(self, path: Path) -> None:
        data = {'name': self.name, 'queries': [{'query_id': q.query_id, 'query': q.query, 'relevant_chunk_ids': q.relevant_chunk_ids, 'metadata': q.metadata} for q in self.queries], 'metadata': self.metadata}
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    @classmethod
    def from_json(cls, path: Path) -> 'EvalDataset':
        with open(path, 'r') as f:
            data = json.load(f)
        queries = [EvalQuery(query_id=q['query_id'], query=q['query'], relevant_chunk_ids=q['relevant_chunk_ids'], metadata=q.get('metadata', {})) for q in data['queries']]
        return cls(name=data['name'], queries=queries, metadata=data.get('metadata', {}))

def create_mini_dataset() -> EvalDataset:
    return EvalDataset(name='mini', queries=[EvalQuery(query_id='q1', query='how do I authenticate a user?', relevant_chunk_ids=['auth_chunk_1'], metadata={'category': 'auth'}), EvalQuery(query_id='q2', query='how do I add two numbers?', relevant_chunk_ids=['calc_chunk_1'], metadata={'category': 'calculator'})], metadata={'description': 'Minimal test dataset'})

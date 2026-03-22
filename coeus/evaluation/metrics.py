from dataclasses import dataclass, field
from typing import List, Dict, Any, Set
from enum import Enum
from coeus.artifacts import QueryMetric
from coeus.evaluation.dataset import EvalQuery

class MetricType(Enum):
    PRECISION = 'precision'
    RECALL = 'recall'
    F1 = 'f1'
    HIT_RATE = 'hit_rate'
    MRR = 'mrr'

@dataclass
class MetricResult:
    name: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvalResult:
    query_id: str
    query: str
    retrieved_chunk_ids: List[str]
    relevant_chunk_ids: List[str]
    metrics: Dict[str, MetricResult]
    hits: List[str] = field(default_factory=list)

    @property
    def precision(self) -> float:
        if not self.retrieved_chunk_ids:
            return 0.0
        return len(self.hits) / len(self.retrieved_chunk_ids)

    @property
    def recall(self) -> float:
        if not self.relevant_chunk_ids:
            return 0.0
        return len(self.hits) / len(self.relevant_chunk_ids)

    @property
    def f1(self) -> float:
        (p, r) = (self.precision, self.recall)
        if p + r == 0:
            return 0.0
        return 2 * (p * r) / (p + r)

    @property
    def hit_rate(self) -> float:
        return 1.0 if self.hits else 0.0

    @property
    def mrr(self) -> float:
        retrieved_set = set(self.retrieved_chunk_ids)
        for (i, chunk_id) in enumerate(self.retrieved_chunk_ids):
            if chunk_id in self.relevant_chunk_ids:
                return 1.0 / (i + 1)
        return 0.0

@dataclass
class SummaryMetrics:
    total_queries: int
    avg_precision: float
    avg_recall: float
    avg_f1: float
    avg_hit_rate: float
    avg_mrr: float
    per_query_metrics: List[Dict[str, Any]] = field(default_factory=list)

def compute_eval_result(query_id: str, query: str, retrieved_chunk_ids: List[str], relevant_chunk_ids: List[str]) -> EvalResult:
    retrieved_set = set(retrieved_chunk_ids)
    relevant_set = set(relevant_chunk_ids)
    hits = list(retrieved_set & relevant_set)
    result = EvalResult(query_id=query_id, query=query, retrieved_chunk_ids=retrieved_chunk_ids, relevant_chunk_ids=relevant_chunk_ids, hits=hits, metrics={})
    result.metrics['precision'] = MetricResult(name=MetricType.PRECISION.value, value=result.precision, metadata={'denominator': len(retrieved_chunk_ids), 'hits': len(hits)})
    result.metrics['recall'] = MetricResult(name=MetricType.RECALL.value, value=result.recall, metadata={'denominator': len(relevant_chunk_ids), 'hits': len(hits)})
    result.metrics['f1'] = MetricResult(name=MetricType.F1.value, value=result.f1, metadata={'precision': result.precision, 'recall': result.recall})
    result.metrics['hit_rate'] = MetricResult(name=MetricType.HIT_RATE.value, value=result.hit_rate, metadata={'has_hit': len(hits) > 0})
    result.metrics['mrr'] = MetricResult(name=MetricType.MRR.value, value=result.mrr, metadata={'first_hit_rank': _first_hit_rank(retrieved_chunk_ids, relevant_chunk_ids)})
    return result

def _first_hit_rank(retrieved: List[str], relevant: List[str]) -> int:
    relevant_set = set(relevant)
    for (i, chunk_id) in enumerate(retrieved):
        if chunk_id in relevant_set:
            return i + 1
    return 0

def compute_summary(eval_results: List[EvalResult]) -> SummaryMetrics:
    if not eval_results:
        return SummaryMetrics(total_queries=0, avg_precision=0.0, avg_recall=0.0, avg_f1=0.0, avg_hit_rate=0.0, avg_mrr=0.0)
    total = len(eval_results)
    total_precision = sum((r.precision for r in eval_results))
    total_recall = sum((r.recall for r in eval_results))
    total_f1 = sum((r.f1 for r in eval_results))
    total_hit_rate = sum((r.hit_rate for r in eval_results))
    total_mrr = sum((r.mrr for r in eval_results))
    per_query = [{'query_id': r.query_id, 'precision': r.precision, 'recall': r.recall, 'f1': r.f1, 'hit_rate': r.hit_rate, 'mrr': r.mrr, 'retrieved_count': len(r.retrieved_chunk_ids), 'relevant_count': len(r.relevant_chunk_ids), 'hit_count': len(r.hits)} for r in eval_results]
    return SummaryMetrics(total_queries=total, avg_precision=total_precision / total, avg_recall=total_recall / total, avg_f1=total_f1 / total, avg_hit_rate=total_hit_rate / total, avg_mrr=total_mrr / total, per_query_metrics=per_query)

def to_query_metric(eval_result: EvalResult) -> QueryMetric:
    from coeus.artifacts import QueryMetric
    return QueryMetric(query=eval_result.query, relevant_chunk_ids=eval_result.relevant_chunk_ids, retrieved_chunk_ids=eval_result.retrieved_chunk_ids, precision=eval_result.precision, recall=eval_result.recall, f1=eval_result.f1, metadata={'query_id': eval_result.query_id, 'hit_rate': eval_result.hit_rate, 'mrr': eval_result.mrr})

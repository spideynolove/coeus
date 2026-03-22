import time
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from coeus.artifacts import RunSummary, ChunkArtifact, QueryMetric, StageFailure
from coeus.evaluation.dataset import EvalDataset, EvalQuery
from coeus.evaluation.metrics import compute_eval_result, compute_summary, to_query_metric
from coeus.store import ArtifactStore, ArtifactNotFound

class EvaluationError(Exception):
    pass

class RetrieverEvalResult:

    def __init__(self, dataset_name: str, query_results: List[Dict[str, Any]], summary: Dict[str, Any], duration_seconds: float):
        self.dataset_name = dataset_name
        self.query_results = query_results
        self.summary = summary
        self.duration_seconds = duration_seconds

class Evaluator:

    def __init__(self, store: ArtifactStore):
        self.store = store

    def evaluate_retrieval(self, run_id: str, retrieval_results: Dict[str, List[str]], dataset: EvalDataset, chunks: Dict[str, ChunkArtifact]) -> RetrieverEvalResult:
        start = time.perf_counter()
        query_results = []
        for eval_query in dataset.queries:
            query_id = eval_query.query_id
            retrieved_ids = retrieval_results.get(query_id, [])
            for chunk_id in eval_query.relevant_chunk_ids:
                if chunk_id not in chunks:
                    raise EvaluationError(f'Relevant chunk {chunk_id} not found in chunks')
            for chunk_id in retrieved_ids:
                if chunk_id not in chunks:
                    raise EvaluationError(f'Chunk {chunk_id} not found in chunks')
            eval_result = compute_eval_result(query_id=query_id, query=eval_query.query, retrieved_chunk_ids=retrieved_ids, relevant_chunk_ids=eval_query.relevant_chunk_ids)
            query_results.append({'query_id': eval_result.query_id, 'query': eval_result.query, 'retrieved_chunk_ids': eval_result.retrieved_chunk_ids, 'relevant_chunk_ids': eval_result.relevant_chunk_ids, 'hit_count': len(eval_result.hits), 'precision': eval_result.precision, 'recall': eval_result.recall, 'f1': eval_result.f1, 'hit_rate': eval_result.hit_rate, 'mrr': eval_result.mrr})
        total_queries = len(query_results)
        if total_queries == 0:
            summary = {'dataset_name': dataset.name, 'total_queries': 0, 'avg_precision': 0.0, 'avg_recall': 0.0, 'avg_f1': 0.0, 'avg_hit_rate': 0.0, 'avg_mrr': 0.0, 'per_query_metrics': query_results}
        else:
            total_precision = sum((qr['precision'] for qr in query_results))
            total_recall = sum((qr['recall'] for qr in query_results))
            total_f1 = sum((qr['f1'] for qr in query_results))
            total_hit_rate = sum((qr['hit_rate'] for qr in query_results))
            total_mrr = sum((qr['mrr'] for qr in query_results))
            summary = {'dataset_name': dataset.name, 'total_queries': total_queries, 'avg_precision': total_precision / total_queries, 'avg_recall': total_recall / total_queries, 'avg_f1': total_f1 / total_queries, 'avg_hit_rate': total_hit_rate / total_queries, 'avg_mrr': total_mrr / total_queries, 'per_query_metrics': query_results}
        duration = time.perf_counter() - start
        return RetrieverEvalResult(dataset_name=dataset.name, query_results=query_results, summary=summary, duration_seconds=duration)

    def save_evaluation(self, run_id: str, eval_result: RetrieverEvalResult) -> None:
        try:
            run_dir = self.store.get_run_dir(run_id)
        except ArtifactNotFound:
            import datetime
            self.store.create_run(spec_id='unknown', run_id=run_id, started_at=datetime.datetime.now())
            run_dir = self.store.get_run_dir(run_id)
        self.store.save_artifact(run_id=run_id, artifact_type='evaluation_summary', artifact=eval_result.summary)
        for qr in eval_result.query_results:
            self.store.save_artifact(run_id=run_id, artifact_type='evaluation_queries', artifact=qr, artifact_id=qr['query_id'])

    def load_evaluation(self, run_id: str) -> RetrieverEvalResult:
        summary = self.store.load_artifact(run_id, 'evaluation_summary')
        query_results = []
        runs_dir = self.store.get_run_dir(run_id)
        query_dir = runs_dir / 'evaluation_queries'
        if query_dir.exists():
            for query_file in query_dir.glob('*.json'):
                qr = self.store.load_artifact(run_id, 'evaluation_queries', artifact_id=query_file.stem)
                query_results.append(qr)
        return RetrieverEvalResult(dataset_name=summary['dataset_name'], query_results=query_results, summary=summary, duration_seconds=0.0)

    def update_run_summary_with_eval(self, run_id: str, eval_result: RetrieverEvalResult, spec_id: str, run_summary: RunSummary) -> RunSummary:
        query_metrics = []
        for qr in eval_result.query_results:
            qm = QueryMetric(query=qr['query'], relevant_chunk_ids=qr['relevant_chunk_ids'], retrieved_chunk_ids=qr['retrieved_chunk_ids'], precision=qr['precision'], recall=qr['recall'], f1=qr['f1'], metadata={'query_id': qr['query_id'], 'hit_rate': qr['hit_rate'], 'mrr': qr['mrr']})
            query_metrics.append(qm)
        from dataclasses import replace
        updated = replace(run_summary, query_metrics=query_metrics)
        return updated

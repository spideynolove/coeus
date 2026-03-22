import time
import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from coeus.experiment import ExperimentSpec, CorpusSource, StageConfig, EvalSetRef
from coeus.artifacts import DocumentArtifact, ChunkArtifact, RunSummary, StageFailure, generate_run_id
from coeus.store import ArtifactStore, ArtifactNotFound
from coeus.corpus.ingest import ingest_file, ingest_directory, IngestResult
from coeus.retrieval.baseline import BaselineRetriever
from coeus.retrieval.stages import StageFactory, StageContext, StageResult
from coeus.evaluation.dataset import EvalDataset
from coeus.evaluation.evaluator import Evaluator
from coeus.evaluation.evaluator import EvaluationError

class RunnerError(Exception):
    pass

class ExperimentRunner:

    def __init__(self, store: ArtifactStore):
        self.store = store

    def run(self, spec: ExperimentSpec) -> str:
        spec_id = spec.spec_id
        run_id = generate_run_id(spec_id, datetime.now())
        started_at = datetime.now()
        self.store.save_spec(spec)
        self.store.create_run(spec_id, run_id, started_at)
        failures = []
        documents = []
        chunks = []
        retrieval_results = {}
        eval_result = None
        try:
            ingest_start = time.perf_counter()
            try:
                ingest_result = self._ingest_corpus(spec)
                documents = ingest_result.documents
                chunks = ingest_result.chunks
                for doc in documents:
                    self.store.save_artifact(run_id, 'documents', doc, doc.id)
                for chunk in chunks:
                    self.store.save_artifact(run_id, 'chunks', chunk, chunk.id)
                ingest_duration = time.perf_counter() - ingest_start
                self.store.save_artifact(run_id, 'ingest_timing', {'duration_seconds': ingest_duration, 'document_count': len(documents), 'chunk_count': len(chunks), 'errors': ingest_result.errors})
            except Exception as e:
                failures.append(StageFailure(stage='ingest', stage_type='corpus', error_type=type(e).__name__, error_message=str(e), timestamp=datetime.now()))
                raise
            retrieval_start = time.perf_counter()
            try:
                retrieval_results = self._run_retrieval(spec, chunks, run_id, spec_id)
                retrieval_duration = time.perf_counter() - retrieval_start
                self.store.save_artifact(run_id, 'retrieval_timing', {'duration_seconds': retrieval_duration, 'query_count': len(retrieval_results)})
            except Exception as e:
                failures.append(StageFailure(stage='retrieval', stage_type='pipeline', error_type=type(e).__name__, error_message=str(e), timestamp=datetime.now()))
                raise
            if spec.eval_set:
                eval_start = time.perf_counter()
                try:
                    eval_result = self._run_evaluation(spec, retrieval_results, chunks, run_id)
                    eval_duration = time.perf_counter() - eval_start
                    self.store.save_artifact(run_id, 'evaluation_timing', {'duration_seconds': eval_duration, 'dataset_name': eval_result.dataset_name})
                except Exception as e:
                    failures.append(StageFailure(stage='evaluation', stage_type='dataset', error_type=type(e).__name__, error_message=str(e), timestamp=datetime.now()))
            else:
                eval_duration = 0.0
            completed_at = datetime.now()
            status = 'partial' if failures else 'completed'
            summary = RunSummary(spec_id=spec_id, run_id=run_id, started_at=started_at, completed_at=completed_at, status=status, document_count=len(documents), chunk_count=len(chunks), failures=failures, query_metrics=[], metadata={'total_duration_seconds': (completed_at - started_at).total_seconds(), 'evaluation_summary': eval_result.summary if eval_result else None})
            if eval_result:
                evaluator = Evaluator(self.store)
                summary = evaluator.update_run_summary_with_eval(run_id=run_id, eval_result=eval_result, spec_id=spec_id, run_summary=summary)
            self.store.save_run_summary(run_id, summary)
            self.store.save_artifact(run_id, 'status', {'status': status, 'completed_at': completed_at.isoformat()})
            return run_id
        except Exception as e:
            failed_at = datetime.now()
            summary = RunSummary(spec_id=spec_id, run_id=run_id, started_at=started_at, completed_at=failed_at, status='failed', document_count=len(documents), chunk_count=len(chunks), failures=failures, query_metrics=[], metadata={'error': str(e)})
            self.store.save_run_summary(run_id, summary)
            self.store.save_artifact(run_id, 'status', {'status': 'failed', 'completed_at': failed_at.isoformat()})
            raise RunnerError(f'Run {run_id} failed: {e}') from e

    def _ingest_corpus(self, spec: ExperimentSpec) -> IngestResult:
        source = spec.corpus
        path = Path(source.path)
        if not path.exists():
            raise RunnerError(f'Corpus path does not exist: {path}')
        if source.type == 'local_files':
            return ingest_file(path)
        elif source.type == 'local_directory':
            return ingest_directory(path, extensions=source.extensions, recursive=source.recursive)
        else:
            raise RunnerError(f'Unsupported corpus type: {source.type}')

    def _run_retrieval(self, spec: ExperimentSpec, chunks: List[ChunkArtifact], run_id: str, spec_id: str) -> Dict[str, List[str]]:
        gen_stage = None
        asm_stage = None
        for stage in spec.stages:
            if not stage.enabled:
                continue
            if stage.name == 'candidate_gen':
                gen_stage = stage
            elif stage.name == 'assembly':
                asm_stage = stage
        if gen_stage is None:
            raise RunnerError('No candidate generation stage found in spec')
        retriever = BaselineRetriever(gen_stage, asm_stage)
        context = StageContext(run_id=run_id, spec_id=spec_id, artifacts_dir=self.store.get_run_dir(run_id))
        query_results = {}
        assembly_results = {}
        for (query_id, query) in self._load_queries(spec):
            result = retriever.retrieve(query, chunks, context)
            query_results[query_id] = result
            assembly_results[query_id] = result['assembly']['chunk_ids']
        self.store.save_artifact(run_id, 'retrieval_results', query_results)
        return assembly_results

    def _run_evaluation(self, spec: ExperimentSpec, retrieval_results: Dict[str, List[str]], chunks: List[ChunkArtifact], run_id: str):
        if not spec.eval_set:
            return None
        dataset = self._load_eval_dataset(spec)
        chunk_lookup = {c.id: c for c in chunks}
        evaluator = Evaluator(self.store)
        eval_result = evaluator.evaluate_retrieval(run_id=run_id, retrieval_results=retrieval_results, dataset=dataset, chunks=chunk_lookup)
        evaluator.save_evaluation(run_id, eval_result)
        return eval_result

    def _load_eval_dataset(self, spec: ExperimentSpec) -> EvalDataset:
        if not spec.eval_set:
            raise RunnerError('No evaluation dataset configured')
        eval_path = Path(spec.eval_set.path)
        if not eval_path.exists():
            raise RunnerError(f'Evaluation dataset not found: {eval_path}')
        if spec.eval_set.format == 'jsonl':
            return EvalDataset.from_jsonl(eval_path)
        return EvalDataset.from_json(eval_path)

    def _load_queries(self, spec: ExperimentSpec) -> List[tuple[str, str]]:
        if spec.eval_set:
            dataset = self._load_eval_dataset(spec)
            return [(query.query_id, query.query) for query in dataset.queries]
        metadata_queries = spec.metadata.get('queries', [])
        loaded_queries = []
        for (index, query) in enumerate(metadata_queries):
            if isinstance(query, str):
                loaded_queries.append((f'query_{index + 1}', query))
            elif isinstance(query, dict) and 'query' in query:
                loaded_queries.append((query.get('query_id', f'query_{index + 1}'), query['query']))
        if loaded_queries:
            return loaded_queries
        raise RunnerError('No queries available for retrieval')

    def load_run(self, run_id: str) -> RunSummary:
        return self.store.load_run_summary(run_id)

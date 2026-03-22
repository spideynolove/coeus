from pathlib import Path

from coeus.evaluation.dataset import EvalDataset
from coeus.experiment import create_basic_spec
from coeus.runner import ExperimentRunner
from coeus.store import default_store


FIXTURE_CORPUS = Path("tests/fixtures/corpus")
FIXTURE_EVAL = Path("tests/fixtures/evaluation/eval.jsonl")


def test_runner_evaluates_dataset_queries_and_persists_eval_metrics(tmp_path):
    spec = create_basic_spec(str(FIXTURE_CORPUS), str(FIXTURE_EVAL))
    store = default_store(tmp_path / "artifacts")
    runner = ExperimentRunner(store)

    run_id = runner.run(spec)

    retrieval_results = store.load_artifact(run_id, "retrieval_results")
    dataset = EvalDataset.from_jsonl(FIXTURE_EVAL)

    assert set(retrieval_results) == {query.query_id for query in dataset.queries}
    assert retrieval_results["auth_1"]["assembly"]["chunk_ids"][0] == "doc_1ecf481e_f49c2751b6e375df_chunk_0_0c8df10d"

    evaluation_summary = store.load_artifact(run_id, "evaluation_summary")
    assert evaluation_summary["avg_hit_rate"] > 0.0

    summary = runner.load_run(run_id)
    assert len(summary.query_metrics) == dataset.query_count
    assert {metric.metadata["query_id"] for metric in summary.query_metrics} == {
        query.query_id for query in dataset.queries
    }

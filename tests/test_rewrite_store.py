from datetime import datetime

from coeus.artifacts import QueryMetric, RunSummary, StageFailure
from coeus.store import LocalFilesystemStore, LocalFilesystemStoreConfig


def test_run_summary_round_trips_failures_metrics_and_status(tmp_path):
    store = LocalFilesystemStore(LocalFilesystemStoreConfig(root_dir=tmp_path))
    started_at = datetime(2026, 3, 22, 12, 0, 0)
    completed_at = datetime(2026, 3, 22, 12, 1, 0)

    store.create_run("spec-1", "run-1", started_at)
    store.save_run_summary(
        "run-1",
        RunSummary(
            spec_id="spec-1",
            run_id="run-1",
            started_at=started_at,
            completed_at=completed_at,
            status="completed",
            document_count=2,
            chunk_count=3,
            failures=[
                StageFailure(
                    stage="evaluation",
                    stage_type="dataset",
                    error_type="ValueError",
                    error_message="invalid ground truth",
                    timestamp=completed_at,
                )
            ],
            query_metrics=[
                QueryMetric(
                    query="how does auth work?",
                    relevant_chunk_ids=["chunk-1"],
                    retrieved_chunk_ids=["chunk-1", "chunk-2"],
                    precision=0.5,
                    recall=1.0,
                    f1=2.0 / 3.0,
                    metadata={"query_id": "auth_1", "hit_rate": 1.0, "mrr": 1.0},
                )
            ],
            metadata={"avg_hit_rate": 1.0},
        ),
    )
    store.save_artifact(
        "run-1",
        "status",
        {"status": "completed", "completed_at": completed_at.isoformat()},
    )

    loaded = store.load_run_summary("run-1")

    assert loaded.failures[0].error_message == "invalid ground truth"
    assert loaded.query_metrics[0].metadata["query_id"] == "auth_1"
    assert loaded.status == "completed"

    runs = store.list_runs(status="completed")

    assert len(runs) == 1
    assert runs[0]["run_id"] == "run-1"
    assert runs[0]["status"] == "completed"
    assert runs[0]["completed_at"] == completed_at.isoformat()

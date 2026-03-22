from pathlib import Path

import pytest

from coeus.corpus.ingest import ingest_directory, ingest_file
from coeus.evaluation.dataset import EvalDataset, EvalQuery
from coeus.evaluation.evaluator import Evaluator, EvaluationError
from coeus.store import default_store


FIXTURE_CORPUS = Path("tests/fixtures/corpus")
FIXTURE_EVAL = Path("tests/fixtures/evaluation/eval.jsonl")


def test_directory_ingest_ids_are_stable_between_relative_and_absolute_paths():
    relative_result = ingest_directory(FIXTURE_CORPUS, extensions=[".py"])
    absolute_result = ingest_directory(FIXTURE_CORPUS.resolve(), extensions=[".py"])

    assert [document.id for document in relative_result.documents] == [
        document.id for document in absolute_result.documents
    ]
    assert [chunk.id for chunk in relative_result.chunks] == [
        chunk.id for chunk in absolute_result.chunks
    ]


def test_bundled_eval_fixture_references_real_chunk_ids():
    ingest_result = ingest_directory(FIXTURE_CORPUS.resolve(), extensions=[".py"])
    dataset = EvalDataset.from_jsonl(FIXTURE_EVAL)
    chunk_ids = {chunk.id for chunk in ingest_result.chunks}

    for query in dataset.queries:
        assert set(query.relevant_chunk_ids).issubset(chunk_ids)


def test_evaluator_rejects_missing_relevant_chunk_ids(tmp_path):
    evaluator = Evaluator(default_store(tmp_path / "artifacts"))
    dataset = EvalDataset(
        name="broken",
        queries=[
            EvalQuery(
                query_id="q1",
                query="broken",
                relevant_chunk_ids=["missing-chunk"],
            )
        ],
    )

    with pytest.raises(EvaluationError, match="Relevant chunk"):
        evaluator.evaluate_retrieval(
            run_id="run-1",
            retrieval_results={"q1": []},
            dataset=dataset,
            chunks={},
        )


def test_ingest_file_tracks_repeated_chunk_occurrences(tmp_path):
    path = tmp_path / "repeated.txt"
    path.write_text("repeat\nrepeat\nrepeat\nrepeat\n")

    result = ingest_file(path, chunk_size=len("repeat\n"))

    assert [chunk.start_line for chunk in result.chunks] == [1, 2, 3, 4]

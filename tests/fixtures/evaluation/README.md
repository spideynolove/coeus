# Evaluation Fixtures

This directory contains evaluation datasets for assessing retrieval quality.

## Format

Evaluation datasets use JSONL format (one JSON object per line):

```json
{"query_id": "q1", "query": "how do I X?", "relevant_chunk_ids": ["chunk_id_1"], "metadata": {}}
```

## Fields

- `query_id`: Unique identifier for the query
- `query`: Query text
- `relevant_chunk_ids`: List of chunk IDs that are ground-truth relevant
- `metadata`: Optional metadata (category, difficulty, etc.)

## Usage

These datasets are used to:
- Compute retrieval metrics (precision, recall, F1)
- Compare different retrieval pipelines
- Detect regressions in retrieval quality
- Establish baseline performance for V1

## Stability

Do not modify these files without updating the expected metric results.
They serve as the stable evaluation baseline for V1.

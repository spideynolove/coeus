# Coeus

Coeus is a retrieval research rewrite built around explicit experiment specs, deterministic corpus ingestion, baseline retrieval stages, and persisted evaluation artifacts.

## Install

Requires Python 3.10+.

```bash
uv tool install git+https://github.com/spideynolove/coeus
```

## CLI

The installable command surface is intentionally small:

```bash
coeus run path/to/spec.json
coeus show-run <run_id>
coeus list-runs
```

`coeus run` loads an experiment spec, persists the resolved spec in the artifact store, executes the runner, and prints the saved run summary as JSON.

`coeus show-run` prints a persisted run summary from the artifact store.

`coeus list-runs` lists runs with optional `--spec-id` and `--status` filters.

## Spec Shape

An experiment spec is JSON with:

- `corpus`
- `stages`
- optional `eval_set`
- optional `metadata`

Corpus and evaluation paths may be absolute or relative to the spec file.

Example:

```json
{
  "corpus": {
    "type": "local_directory",
    "path": "../fixtures/corpus",
    "extensions": [".py"]
  },
  "stages": [
    {
      "name": "candidate_gen",
      "type": "lexical",
      "params": {"limit": 10}
    },
    {
      "name": "assembly",
      "type": "simple",
      "params": {"max_chunks": 5}
    }
  ],
  "eval_set": {
    "path": "../fixtures/evaluation/eval.jsonl",
    "format": "jsonl"
  }
}
```

## Artifact Store

Runs are stored in a local filesystem artifact root with:

- persisted specs under `specs/`
- run metadata and summaries under `runs/<run_id>/`
- per-run documents, chunks, retrieval outputs, and evaluation outputs

## MCP

`coeus-mcp` exposes the same rewrite core through three thin tools:

- `run_experiment`
- `get_run_summary`
- `get_runs`

The MCP adapter calls the same runner and artifact-store code path as the CLI.

Register mcporter against the installed `coeus-mcp` executable on `PATH`, not a checkout file path:

```bash
npx mcporter config add coeus --command coeus-mcp --arg --transport --arg stdio
```

If you want to verify the registration before making calls, this should succeed:

```bash
npx mcporter list coeus --schema
```

## Development

```bash
source /home/hung/env/.venv/bin/activate
uv pip install -e .
python -m pytest tests/ -q
```

## License

MIT

# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Overview

Coeus is a retrieval research rewrite centered on experiment specs, explicit artifacts, deterministic ingestion, baseline retrieval, and evaluation-backed iteration.

## Architecture

### Entry Points
- **CLI** (`coeus/interfaces/cli.py`): `coeus run`, `coeus show-run`, `coeus list-runs`
- **MCP server** (`coeus/interfaces/mcp.py`): exposes `run_experiment`, `get_run_summary`, `get_runs`

### Core Modules
- **Experiment contracts** (`coeus/experiment.py`): canonical spec shape and spec serialization
- **Artifacts** (`coeus/artifacts.py`): document, chunk, failure, metric, and run summary records
- **Artifact store** (`coeus/store.py`): local filesystem persistence for specs and runs
- **Corpus pipeline** (`coeus/corpus/ingest.py`): deterministic file and directory ingestion into document and chunk artifacts
- **Retrieval pipeline** (`coeus/retrieval/`): explicit retrieval stages and baseline lexical pipeline
- **Evaluation** (`coeus/evaluation/`): datasets, metrics, and persisted evaluation summaries
- **Runner** (`coeus/runner.py`): single orchestration path for ingestion, retrieval, evaluation, and run persistence

### Interface Helpers
- **Common helpers** (`coeus/interfaces/common.py`): shared store/spec/run helpers used by both CLI and MCP adapters

## Command Surface

The installed commands are:

- `coeus run path/to/spec.json`
- `coeus show-run <run_id>`
- `coeus list-runs`

The installed MCP tools are:

- `run_experiment`
- `get_run_summary`
- `get_runs`

## Configuration

Experiment specs are JSON files. Relative corpus and evaluation paths are resolved against the spec file location before execution and the resolved spec is persisted under the artifact store `specs/` directory.

## Development Setup

```bash
source /home/hung/env/.venv/bin/activate
uv pip install -e .
```

## Testing

```bash
python -m pytest tests/ -q
```

Current test files:
- `tests/test_cutover_layout.py`
- `tests/test_rewrite_runner.py`
- `tests/test_rewrite_store.py`
- `tests/test_rewrite_ingest.py`
- `tests/test_rewrite_interfaces.py`

## Design Principles

1. One orchestration path through `ExperimentRunner`
2. Specs and run artifacts are the system of record
3. Retrieval behavior must be inspectable and evaluation-backed
4. CLI and MCP stay thin adapters over the same core
5. Silent fallbacks are worse than explicit failures

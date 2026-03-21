# Coeus Research Rewrite Design

**Date:** 2026-03-22

## Goal

Rewrite Coeus as a retrieval research platform focused on improving retrieval quality, not as a compatibility-preserving product refactor.

## Decisions

- Phase 1 does not preserve CLI, MCP, or storage compatibility.
- The rewritten system is a research platform, not a general agent-memory product.
- Retrieval quality is the primary success criterion.
- The architecture should treat both retrieval execution and evaluation as first-class concerns, with the retrieval engine slightly ahead of the eval layer.

## Recommended Approach

Recommended direction: `Composable Lab`

This approach keeps the core system small enough to reason about while making retrieval components easy to swap, compare, and benchmark. It avoids repeating the current repo's additive architecture and avoids prematurely rebuilding heavy infrastructure before the retrieval science is stable.

Alternative approaches considered:

1. `Research Kernel`
   A minimal core with corpus ingestion, retrieval, and evaluation.
   Trade-off: cleanest possible rewrite, but less flexible for rapid experimentation without an additional composition layer.

2. `Composable Lab`
   A research core built from pluggable pipeline stages with lightweight experiment registration.
   Trade-off: more upfront design work, but best aligned with fast retrieval iteration and meaningful quality comparisons.

3. `Full Research Platform`
   A broader platform with orchestration, worker management, and richer experiment infrastructure.
   Trade-off: highest complexity and highest risk of repeating the current codebase's over-engineering.

## Architecture

The rewritten Coeus should center on deterministic experiments. Given a corpus, a pipeline definition, and an evaluation set, the system should produce reproducible retrieval outputs, quality metrics, and enough metadata to compare runs precisely.

Top-level subsystems:

- `corpus`
  Handles ingestion, normalization, chunking, metadata extraction, and immutable source artifacts.

- `retrieval`
  Handles query transforms, candidate generation, fusion, reranking, and context assembly.

- `evaluation`
  Handles datasets, judgments, metrics, benchmark execution, and result reporting.

- `interfaces`
  Handles CLI, MCP, and any future UI or automation layers as thin adapters over the core APIs.

This architecture intentionally breaks from the current application shape:

- no module-import bootstrapping
- no duplicated wiring between CLI and MCP entry points
- no implicit retrieval side effects
- no product claims without eval-backed evidence

## Components And Data Flow

The primary control object should be an `ExperimentSpec`. It defines:

- corpus input
- pipeline stages
- stage parameters
- evaluation set
- run metadata needed for reproducibility

Running an `ExperimentSpec` produces a `RunArtifact` bundle containing:

- normalized documents and chunks used by the run
- retrieval candidates
- reranked outputs
- assembled context
- metrics
- run metadata

Expected execution flow:

1. corpus ingest creates normalized `DocumentArtifact` and `ChunkArtifact` records
2. retrieval runs as explicit stages: query transform, candidate generation, fusion, reranking, assembly
3. evaluation consumes run outputs against labeled queries or comparison tasks
4. interfaces submit specs, trigger runs, inspect artifacts, and fetch reports

Every stage boundary must be explicit and serializable. A change to any stage should be comparable against earlier runs without hidden behavior differences.

This design also rejects several behaviors present in the current codebase:

- live-file expansion as an implicit retrieval step
- silently discarded intermediate retrieval state
- hidden fallback behavior that changes experiment meaning
- final answer-shaped outputs as the only retained artifact

## Error Handling

The new system should prefer deterministic failure over silent fallback.

Rules:

- stage failures are explicit and attached to run artifacts
- optional components are declared in the experiment spec, not silently inferred
- storage writes use artifact transactions rather than partial writes across different stores
- import-time side effects are banned
- live-file expansion is banned unless explicitly declared as a stage

This is necessary because silent fallback corrupts evaluation and makes retrieval quality comparisons untrustworthy.

## Testing Strategy

Testing should move from entry-point confidence to pipeline confidence.

Required coverage:

- unit tests for each stage contract
- fixture corpora for deterministic retrieval tests
- golden evaluation runs for regression detection
- a small benchmark suite in CI to catch ranking and assembly regressions
- interface tests only for adapter correctness

The system should treat eval outputs as part of the regression surface, not just as optional reporting.

## Non-Goals For V1

- background workers
- job manager infrastructure
- token-savings marketing claims
- broad multi-tool setup automation as a core concern
- hidden compatibility layers for the old schema or command surface

## Consequences

Positive consequences:

- retrieval behavior becomes measurable and comparable
- architecture becomes easier to reason about
- research iteration speeds up because stages are explicit and replaceable

Costs:

- the rewrite is intentionally breaking
- existing public docs and interfaces will need replacement rather than patching
- the team must accept a sharper distinction between research artifacts and product adapters

## Initial Rewrite Shape

The first implementation phase should likely build a new package structure alongside the current one instead of mutating the existing modules in place. That allows the rewrite to establish new system boundaries before deciding what, if anything, should be retained from the current code.

Suggested initial structure:

- `coeus/` or `src/coeus/`
- `coeus/corpus/`
- `coeus/retrieval/`
- `coeus/evaluation/`
- `coeus/interfaces/`
- `tests/fixtures/`
- `tests/corpus/`
- `tests/retrieval/`
- `tests/evaluation/`

The implementation plan should decide exact paths after inspecting packaging constraints, but the rewrite should be organized around these subsystem boundaries.

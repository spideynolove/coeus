# Coeus Research Rewrite Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current Coeus application with a retrieval research platform centered on reproducible experiments, explicit artifacts, and evaluation-driven retrieval work.

**Architecture:** Build the rewrite in a new `coeus/` package beside the legacy modules, move the core into four subsystems (`corpus`, `retrieval`, `evaluation`, `interfaces`), and cut the old entrypoints over only after the new runner is stable. The rewrite treats experiments and artifacts as the system of record, not the current SQLite-first application flow.

**Tech Stack:** Python 3.10+, pytest, current packaging via `setuptools`, existing `mcp` dependency for the thin adapter, existing embedding dependencies only after the baseline retrieval pipeline is stable.

---

## V1 Definition

V1 is the smallest system that proves the new architecture is real and usable.

V1 must include:

- a new `coeus/` package with clear subsystem boundaries
- a corpus pipeline that ingests local files into normalized document and chunk artifacts
- a retrieval pipeline with explicit stages and deterministic intermediate outputs
- an evaluation layer that can score retrieval runs against labeled queries
- a local artifact store for experiment specs, run outputs, failures, and metrics
- a minimal CLI for running and inspecting experiments
- a minimal MCP adapter only after the CLI-backed runner is stable

V1 must not include:

- background workers
- file watching
- tool auto-registration and onboarding flows
- legacy job management
- token-savings claims or budget marketing
- storage migration from the current SQLite and zvec database
- compatibility shims for the old CLI or MCP surface

## Keep, Discard, And Migration Rules

Keep temporarily as reference material while the rewrite is in progress:

- `core/ingestor.py`
- `core/oracle.py`
- `core/ast_chunker.py`
- `storage/interface.py`
- `storage/zvec_store.py`
- `embedders.py`
- current tests that explain legacy behavior

Discard from the target architecture immediately, even if the files remain in the repo until cleanup:

- `core/job_manager.py`
- `watcher/watcher.py`
- setup automation as a core product concern
- the current import-time MCP boot pattern
- hidden fallback behavior that changes retrieval meaning
- the existing ledger and token-savings story

Migration stance for V1:

- no attempt to reuse the current database schema
- no attempt to read or write old run data
- no attempt to preserve the current command surface
- reindexing into the new artifact store is the expected path

## Execution Order

The rewrite should be executed in the following order and not reordered without a clear reason:

1. establish the new package and test layout
2. define the core experiment and artifact contracts
3. build local artifact persistence
4. build corpus ingestion into artifacts
5. build baseline retrieval stages
6. build evaluation and metrics
7. connect everything through a single experiment runner
8. expose the runner through a minimal CLI
9. expose the runner through a thin MCP adapter
10. delete the legacy application surface
11. rewrite repo documentation around the new architecture
12. add regression fixtures for retrieval-quality work

## Phase 0: Rewrite Preparation

### Task 0.1: Isolate The Rewrite

- create a dedicated worktree for the rewrite
- verify the worktree starts from the intended base commit
- confirm existing unrelated repository changes stay outside the rewrite scope

Completion criteria:

- rewrite work happens in an isolated worktree
- there is no ambiguity about which changes belong to the rewrite

### Task 0.2: Freeze The Legacy Architecture As Reference Only

- record which legacy modules are still useful as implementation reference
- record which legacy features are explicitly out of scope for V1
- mark the current design doc and this implementation plan as the source of truth

Completion criteria:

- the team has one agreed definition of V1
- nobody treats the old CLI, MCP, or database schema as mandatory constraints

## Phase 1: Package And Test Skeleton

### Task 1.1: Create The New Package Boundary

- create the top-level `coeus/` package
- create empty subsystem directories for `corpus`, `retrieval`, `evaluation`, and `interfaces`
- create matching test directories under `tests/`
- add fixture directories for corpus and evaluation data

Completion criteria:

- the rewrite has a package boundary independent from `core/`, `storage/`, and `watcher/`
- the test layout mirrors the new architecture

### Task 1.2: Wire Packaging For Parallel Development

- update packaging so the new `coeus/` package is installable without cutting over the old entrypoints yet
- keep legacy modules importable during the middle of the rewrite
- verify the repo can package both the legacy and new worlds during the transition

Completion criteria:

- the new package can be imported in tests
- the old package layout still exists only as temporary scaffolding

## Phase 2: Core Contracts

### Task 2.1: Define Experiment Specs

- define the canonical shape of an experiment spec
- include corpus source, stage list, stage configuration, evaluation set reference, and metadata needed for reproducibility
- decide how specs are serialized and reloaded

Completion criteria:

- every run can point to one explicit spec
- there is no hidden runtime configuration outside the spec

### Task 2.2: Define Artifact Types

- define the artifact types for documents, chunks, candidates, assembled context, failures, metrics, and run summaries
- make the artifact boundary explicit between subsystems
- ensure failure information is captured as part of the artifact model, not as console output only

Completion criteria:

- each subsystem knows what it receives and what it emits
- intermediate outputs can be inspected after a run

## Phase 3: Local Artifact Persistence

### Task 3.1: Create The Artifact Store Contract

- define the storage interface for saving and loading experiment specs, runs, and related artifacts
- keep the contract local and file-based for V1
- avoid any commitment to the old SQLite schema

Completion criteria:

- the storage boundary is defined before any subsystem writes data directly

### Task 3.2: Implement A Local Filesystem Store

- persist runs under a predictable artifact directory structure
- store enough metadata to inspect a run without re-executing it
- make failed runs persist their failures instead of disappearing

Completion criteria:

- a completed or failed run can be reopened and inspected later
- the artifact store is the single persistence path for V1

## Phase 4: Corpus Subsystem

### Task 4.1: Define Corpus Inputs And Outputs

- define what a corpus is for V1
- support local file and directory input only
- decide what normalized metadata must be preserved on documents and chunks

Completion criteria:

- corpus ingest has one clear input model and one clear artifact model

### Task 4.2: Build Deterministic Ingestion

- ingest files into document artifacts
- chunk documents into chunk artifacts
- keep the first chunking strategy simple and deterministic
- treat AST-aware chunking as a later enhancement, not a day-one dependency

Completion criteria:

- repeated ingest of the same corpus produces stable artifact shape
- there are no silent fallbacks that change chunk semantics without being recorded

### Task 4.3: Add Corpus Fixtures

- create small fixture corpora that cover at least one auth case and one non-auth case
- keep fixture data readable and stable
- use fixtures as the baseline input for retrieval and eval tests

Completion criteria:

- retrieval tests no longer depend on ad hoc temporary files

## Phase 5: Retrieval Subsystem

### Task 5.1: Define Stage Contracts

- define the contract for query transform, candidate generation, fusion, reranking, and assembly
- make each stage optional only when the experiment spec says so
- ensure each stage records its inputs and outputs in a way the run artifact can preserve

Completion criteria:

- stage boundaries are explicit and serializable
- retrieval composition is driven by the spec rather than hardcoded branching

### Task 5.2: Implement A Baseline Retrieval Pipeline

- start with one simple baseline retriever
- rank candidates deterministically
- emit candidate artifacts before any assembly step
- keep vector retrieval out of the critical path until the baseline pipeline is testable

Completion criteria:

- one end-to-end retrieval path works without external services
- retrieval outputs can be compared across runs

### Task 5.3: Add Assembly As A Distinct Stage

- move context assembly out of retrieval scoring
- record exactly which chunks were assembled and why
- ban implicit live-file expansion for V1

Completion criteria:

- assembly can be evaluated independently from ranking
- the system no longer hides retrieval behavior inside presentation logic

## Phase 6: Evaluation Subsystem

### Task 6.1: Define Evaluation Inputs

- define the evaluation dataset format
- decide how relevant chunks are referenced
- keep the format small enough to hand-author the first labeled set

Completion criteria:

- the runner can locate an evaluation set directly from the experiment spec

### Task 6.2: Implement Baseline Metrics

- start with a small set of retrieval metrics that are easy to validate
- record metrics per query and at run summary level
- keep metric definitions stable and documented

Completion criteria:

- two runs can be compared on the same corpus and eval set without manual interpretation

### Task 6.3: Persist Evaluation Results In Run Artifacts

- attach per-query results and summary metrics to the run artifact
- make failed or partial evaluation visible rather than silently omitted

Completion criteria:

- evaluation output becomes part of the permanent run record

## Phase 7: Experiment Runner

### Task 7.1: Orchestrate Corpus, Retrieval, And Evaluation

- create one runner that executes the full experiment flow
- make the runner the only place where subsystem order is coordinated
- pass all configuration through the experiment spec

Completion criteria:

- one command can produce a complete run artifact from corpus input to evaluation output

### Task 7.2: Enforce Deterministic Failure Handling

- stop execution when a required stage fails
- persist stage failures to the artifact store
- make partial success visible when a run completes with warnings or skipped work

Completion criteria:

- failures are inspectable after the run
- there are no swallowed exceptions that change run meaning

## Phase 8: CLI Adapter

### Task 8.1: Define The New Command Surface

- keep the CLI minimal
- include only the commands needed to run experiments and inspect artifacts
- do not port the old command list into the new architecture

Completion criteria:

- the command surface matches the research-platform goal
- commands map directly to runner and artifact-store capabilities

### Task 8.2: Cut Packaging Scripts Over To The New CLI

- point the package entrypoint at the new CLI only after the runner works
- keep the switch small and easy to verify

Completion criteria:

- the installable command runs against the new architecture
- the old `main.py` is no longer the real entrypoint

## Phase 9: MCP Adapter

### Task 9.1: Add A Thin MCP Layer

- expose only the smallest useful set of MCP tools
- have MCP call the same runner and artifact inspection logic as the CLI
- ban import-time initialization and global singleton boot logic

Completion criteria:

- MCP is an adapter over the core, not a second application stack

### Task 9.2: Verify CLI And MCP Share The Same Core Path

- confirm the two interfaces do not duplicate orchestration logic
- remove any interface-only retrieval behavior

Completion criteria:

- there is one core execution path and two thin adapters

## Phase 10: Legacy Removal

### Task 10.1: Remove Obsolete Modules

- delete `main.py`, `mcp_server.py`, `config.py`, `embedders.py`, `core/`, `storage/`, and `watcher/` only after the new CLI and MCP adapters are in place
- preserve git history as the record of the old architecture

Completion criteria:

- the repo has one architecture, not two competing ones

### Task 10.2: Remove Legacy Tests And Replace With New Coverage

- delete tests that only validate the old system shape
- keep or port only those cases that still express desired behavior under the new architecture

Completion criteria:

- the test suite describes the new system rather than anchoring the repo to the old one

## Phase 11: Documentation Rewrite

### Task 11.1: Rewrite The README

- explain Coeus as a retrieval research platform
- describe experiment specs, run artifacts, and evaluation
- remove claims tied to the old pointer-budget product framing

Completion criteria:

- the README matches the new system exactly

### Task 11.2: Rewrite CLAUDE.md

- explain the new package layout and core subsystems
- describe how to work on the runner, artifacts, retrieval, and evaluation layers
- remove references to deleted modules and stale concepts

Completion criteria:

- contributor guidance no longer points back at the legacy architecture

## Phase 12: Retrieval Regression Baseline

### Task 12.1: Create Stable Regression Fixtures

- add a small fixture corpus and labeled evaluation set that the team agrees to keep stable
- make this the baseline retrieval-quality check for future work

Completion criteria:

- the repo has a fixed reference point for retrieval-quality changes

### Task 12.2: Add A Regression Test For Baseline Quality

- run the baseline experiment against the stable fixture corpus
- assert the agreed minimum retrieval result for V1

Completion criteria:

- future retrieval changes can be measured against a known baseline

## Definition Of Done

The rewrite is complete when all of the following are true:

- the installable package runs through the new `coeus/` architecture
- one experiment spec can ingest a corpus, run retrieval, run evaluation, and persist artifacts
- run artifacts preserve intermediate outputs, failures, and metrics
- the CLI and MCP adapters both use the same core runner
- the legacy application surface has been deleted
- the README and `CLAUDE.md` describe only the new system
- the repo includes at least one stable retrieval regression fixture and baseline quality check

## Explicit Non-Goals During Execution

- do not port legacy commands simply because they existed
- do not add external-service dependencies to unblock architecture decisions
- do not preserve the current database schema
- do not rebuild setup automation before the research core exists
- do not introduce background orchestration before single-run execution is solid

# Legacy Architecture Reference

**Created:** 2026-03-22
**Purpose:** Record legacy modules for implementation reference during rewrite
**Source of Truth:** docs/plans/2026-03-22-coeus-research-rewrite-design.md and docs/plans/2026-03-22-coeus-research-rewrite-implementation.md

## Keep Temporarily as Implementation Reference

The following legacy modules may be useful for understanding existing patterns during the rewrite. They are NOT constraints on the new architecture.

| Module | Purpose | Reference Value |
|--------|---------|-----------------|
| `core/ingestor.py` | Chunk → embed → store pipeline | Ingestion patterns, file handling |
| `core/oracle.py` | Hybrid search orchestrator | Retrieval stage concepts |
| `core/ast_chunker.py` | Tree-sitter chunking at function/class boundaries | AST-aware chunking strategy |
| `storage/interface.py` | Document, Entity, SearchResult, Pointer types | Data structure patterns |
| `storage/zvec_store.py` | SQLite + zvec HNSW + FTS5 implementation | Storage patterns |
| `embedders.py` | Voyage AI / OpenRouter embedder interfaces | Embedding provider abstractions |
| `tests/test_ast_chunker.py` | AST chunker unit tests | Test patterns for chunking |
| `tests/test_setup.py` | Setup and registration tests | Test patterns |

## Explicitly Out of Scope for V1

The following legacy features are NOT part of the V1 rewrite:

- Background workers and job queues (`core/job_manager.py`)
- File watching (`watcher/watcher.py`)
- Setup automation and tool registration as core product concern
- Import-time MCP boot pattern with global singletons
- Hidden fallback behavior that changes retrieval meaning
- Ledger table and token-savings marketing claims
- Budgeter module (referenced in CLAUDE.md but never implemented)
- Pricing module (referenced in CLAUDE.md but never implemented)
- Legacy database schema migration or compatibility
- Legacy CLI command surface preservation
- Legacy MCP tool surface preservation

## New Architecture Constraints

The rewrite MUST:

- Use experiment specs as the system of record
- Emit explicit artifacts at every stage boundary
- Fail deterministically rather than silently falling back
- Keep retrieval evaluation as a first-class concern
- Treat CLI and MCP as thin adapters over the same core runner
- Avoid import-time side effects

## Migration Stance for V1

- No attempt to reuse current database schema
- No attempt to read or write old run data
- No attempt to preserve current command surface
- Reindexing into new artifact store is the expected path

## Sources of Truth

1. **Design Document:** docs/plans/2026-03-22-coeus-research-rewrite-design.md
2. **Implementation Plan:** docs/plans/2026-03-22-coeus-research-rewrite-implementation.md
3. **Critical Evaluation:** docs/coeus-critical-evaluation-debate.md

These documents define V1 goals, constraints, and success criteria.

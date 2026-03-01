# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Overview

Coeus is a local semantic memory system for AI agents. It indexes codebases and serves context via MCP using pointer-based RAG — returning file location references instead of full content, achieving 83–98% token reduction.

## Architecture

### Entry Points
- **CLI** (`main.py`): `coeus ingest`, `coeus ask`, `coeus search`, `coeus stats`, `coeus watch`, `coeus config`, `coeus job`, `coeus setup`
- **MCP server** (`mcp_server.py`): stdio/SSE server, exposes `coeus_query`, `coeus_search`, `coeus_ingest`, `coeus_decisions`, `coeus_stats`, `coeus_ping`, `coeus_reinit_oracle`

### Core Modules
- **Ingestor** (`core/ingestor.py`): chunk → embed → store pipeline; dispatches to AST chunker for code files, line-count fallback for others
- **Oracle** (`core/oracle.py`): hybrid search orchestrator — FastPath cache → zvec vector search → FTS5 → rank → assemble pointers/chunks
- **Budgeter** (`core/budgeter.py`): token-aware context assembly, max 3 chunks per file, imports pricing from `core/pricing.py`
- **Extractor** (`core/extractor.py`): regex-based entity extraction (problems, solutions, decisions, tasks)
- **FastPath** (`core/fastpath.py`): in-memory exact/prefix trie cache, warmed at Oracle init from indexed entities
- **Contextualizer** (`core/contextualizer.py`): `expand_chunk()` adds ±3 surrounding lines from source file at assembly time
- **AST Chunker** (`core/ast_chunker.py`): tree-sitter chunking at function/class boundaries for .py/.go/.js/.ts/.tsx/.rs
- **Setup** (`core/setup.py`): `coeus setup` logic — API key collection, tool detection, MCP registration

### Storage
- **ZvecStore** (`storage/zvec_store.py`): unified SQLite + zvec HNSW vectors + FTS5
- **Interface** (`storage/interface.py`): `Document`, `Entity`, `SearchResult`, `Pointer` types

### Infrastructure
- **Embedder** (`embedders.py`): Voyage AI (primary), OpenRouter (fallback)
- **Config** (`config.py`): env-based config, reads from `~/.coeus/.env`
- **Pricing** (`core/pricing.py`): `LLM_PRICING` and `EMBED_PRICING` dicts ($/MTok)
- **Watcher** (`watcher/watcher.py`): watchdog-based file monitoring

## Key Concepts

### Pointer-Based RAG
High-scoring results return full chunk content; lower-scoring results return lightweight `Pointer` objects (file path + line range). The `ContextBudgeter` assembles both within a token budget.

### Token Budgets
- `light`: 2,000 tokens
- `auto`: 4,000 tokens (default)
- `extra`: 8,000 tokens

### AST Chunking
When tree-sitter is installed, code files are split at function/class boundaries. Single oversized nodes are never split. Falls back to line-count chunking for unsupported extensions or missing grammars. `Chunk.section` stores the function/class name.

### HyDE (Hypothetical Document Embeddings)
Handled in the Claude Code skill (`CLAUDE_CODE_SKILL_CONTENT` in `core/setup.py`), not in Coeus itself. Claude rephrases conceptual queries as hypothetical answers before calling `coeus_query` — no extra API call needed.

## Configuration

Env vars or `~/.coeus/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `VOYAGE_API_KEY` | — | Voyage AI embeddings (recommended) |
| `OPENROUTER_API_KEY` | — | OpenRouter embeddings fallback |
| `COEUS_DATA` | `~/.coeus` | Data directory |
| `COEUS_EMBED_MODEL` | `voyage-3` | Embedding model |
| `COEUS_LLM_MODEL` | `anthropic/claude-3.5-sonnet` | Downstream model for savings calc |
| `COEUS_CHUNK_SIZE` | `1000` | Chunk size in characters |
| `COEUS_BUDGET` | `4000` | Default context budget in tokens |

## Development Setup

```bash
source /home/hung/env/.venv/bin/activate
uv pip install -e .
uv pip install -e ".[ast]"   # optional: tree-sitter chunking
```

Install from GitHub:
```bash
uv tool install git+https://github.com/spideynolove/coeus
```

## Testing

```bash
python -m pytest tests/ -v
```

Current test files:
- `tests/test_ast_chunker.py` — 12 unit tests + 4 integration tests for AST chunker and Ingestor dispatch
- `tests/test_setup.py` — 24 tests for setup/registration logic

## Database Schema

SQLite at `~/.coeus/coeus.db`:

- `documents` — id (MD5), content, embedding (zvec), source, project, start_line, end_line, metadata (JSON), created_at
- `docs_fts` — FTS5 virtual table on content
- `entities` — type, content, file_path, project, valid_from, valid_to
- `files` — source tracking for skip-if-unchanged

## Design Principles

1. **Single database**: SQLite + zvec, no ChromaDB
2. **Retrieval-only**: Coeus finds context; Claude generates answers
3. **Optional deps**: tree-sitter grammars fail gracefully
4. **No Windows**: Linux/Mac only (fcntl)
5. **No dead code**: if it's not imported, delete it
6. **Pricing in one place**: `core/pricing.py` only

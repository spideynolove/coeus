# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Coeus (formerly Kronos) is a local semantic memory system for AI agents that provides long-term memory for codebases with deep project context understanding. It uses a "pointer-based" approach that achieves 83-98% token reduction compared to traditional RAG, resulting in 5-50x cost savings on LLM API calls.

The system indexes files, extracts structured entities (decisions, tasks, problems, solutions), and enables hybrid vector + full-text search with intelligent context assembly.

## Architecture

The system follows a layered architecture:

### Entry Points
- **CLI (`main.py`)**: argparse-based command-line interface with subcommands: `ingest`, `ask`, `search`, `stats`, `watch`, `config`, `job`

### Application Layer
- **Ingestor** (`core/ingestor.py`): File ingestion pipeline (chunking, extraction, embedding)
- **Oracle** (`core/oracle.py`): Hybrid search orchestrator with query classification
- **Budgeter** (`core/budgeter.py`): Token-aware context assembly with file diversity limits (max 3 chunks per file)

### Domain Layer
- **Extractor** (`core/extractor.py`): Entity extraction from text using regex patterns
- **FastPath** (`core/fastpath.py`): Exact/prefix cache for low-latency lookups
- **Types** (`storage/interface.py`): Core data types: `Document`, `Entity`, `SearchResult`, `Pointer`

### Infrastructure Layer
- **ZvecStore** (`storage/zvec_store.py`): Unified SQLite storage with FTS5 for full-text search and vector storage (zvec)
- **Embedder** (`embedders.py`): Voyage AI (primary) and OpenRouter (fallback) embeddings
- **LLM** (`llms.py`): OpenRouter (cloud), Ollama (local), and GLM (Chinese-optimized) clients

### Supporting Modules
- **Config** (`config.py`): Environment-based configuration management
- **Async** (`async/watcher.py`): File monitoring for auto-indexing
- **Utils** (`utils/`): File I/O with POSIX locking, stemmer

## Key Concepts

### Pointer-Based RAG
Instead of returning full document chunks, Kronos returns lightweight pointers (`Pointer` dataclass) that reference specific file locations. This reduces token usage by 98% in typical queries.

### Token Budgeting
The `ContextBudgeter` assembles context within configurable token budgets:
- **light**: 2,000 tokens (quick queries)
- **auto**: 4,000 tokens (default)
- **extra**: 8,000 tokens (complex analysis)

### File Diversity
To ensure diverse sources in the context window, the budgeter limits to **3 chunks per file** (entities excluded).

### Entity Extraction
Structured knowledge extraction identifies:
- **Problems**: Issues or challenges mentioned
- **Solutions**: Proposed or implemented solutions
- **Decisions**: Architectural decisions with optional temporal validity
- **Tasks**: Todo items with completion status

## Configuration

Configuration is managed via environment variables or a `.env` file in the data directory (`~/.kronos` by default).

### Required Variables (choose one)
- `VOYAGE_API_KEY`: For Voyage AI embeddings (recommended)
- `OPENROUTER_API_KEY`: For OpenRouter embeddings/LLM (fallback)

### Optional Variables
- `KRONOS_DATA`: Data directory (default: `~/.kronos`)
- `KRONOS_EMBED_MODEL`: Embedding model (`voyage-3`, `voyage-3-lite`, `openai/text-embedding-3-small`)
- `KRONOS_LLM_MODEL`: LLM model (`anthropic/claude-3.5-sonnet`, etc.)
- `KRONOS_CHUNK_SIZE`: Chunk size in characters (default: 1000)
- `KRONOS_BUDGET`: Default context budget in tokens (default: 4000)

### Configuration Commands
```bash
kronos config               # Show current configuration
kronos config --init       # Create example .env file
```

## Running the System

### Installation Dependencies
The project requires Python 3.8+ and the following dependencies:
- `voyageai` (for Voyage AI embeddings)
- `requests` (HTTP client)
- `watchdog` (file monitoring)
- `python-dotenv` (configuration)
- `tenacity` (retry logic)
- `mcp` (Model Context Protocol for IDE integration)
- `pyyaml` (for VSCode Continue YAML config in setup)
- `numpy` (vector operations)
- `pytest` (testing, optional)

Optional dependencies:
- `zhipuai` (for GLM LLM provider)
- `tree-sitter` (AST-aware code chunking, optional)
- `tree-sitter-python`, `tree-sitter-go`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-rust` (language grammars, optional)

### Running the CLI
Ensure the virtual environment is activated (see Development Setup). Then:

```bash
# Index a directory
python main.py ingest /path/to/project --recursive --project my-project

# Ask a question about the codebase
python main.py ask "How does authentication work?" --project my-project

# Perform raw search (debugging)
python main.py search "database connection" --method hybrid --json

# View database statistics
python main.py stats

# Watch directory for changes
python main.py watch /path/to/project --project my-project --debounce 5.0
```

### Development Setup

#### Virtual Environment
The project uses `uv` for package management (per user's global CLAUDE.md). Set up the environment:
```bash
# Create and activate virtual environment
source /home/hung/env/.venv/bin/activate

# Install dependencies with uv
uv pip install voyageai requests watchdog python-dotenv tenacity mcp pyyaml numpy pytest zhipuai tree-sitter tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript tree-sitter-rust
```

#### Fixing Import Paths
Current imports reference `src_new.*` modules which don't exist in the directory structure. To run the code, you may need to:
1. Adjust imports to use relative imports (e.g., `from ..storage.interface import ...`)
2. Set `PYTHONPATH` to include the root directory
3. Install the package locally with `pip install -e .` (once `setup.py` is created)

#### Testing
No test suite exists yet. When adding tests, use `pytest` with the project's root as the Python path.

## Database Schema

The unified SQLite database (`kronos.db`) contains:

### `documents` table
- `id`: Unique identifier (MD5 hash)
- `content`: Text content
- `embedding`: Serialized numpy array (vector)
- `source`: File path
- `project`: Project name
- `start_line`, `end_line`: Line numbers in source file
- `created_at`: Timestamp

### `docs_fts` virtual table
- FTS5 index on `content` for full-text search

### `entities` table
- Structured knowledge entities with types and temporal metadata

### `files` table
- File tracking for change detection

## Development Notes

### Current State
- Early development version (v1.0)
- No test suite yet
- Import paths need fixing (`src_new.*` → local imports)
- No packaging setup (`setup.py` or `pyproject.toml`)

### Design Principles (from v1.0 blueprint)
1. **Single database**: SQLite + vectors (zvec) instead of SQLite + ChromaDB
2. **Interface segregation**: `StorageInterface`, `Embedder`, `LLM` abstractions
3. **Dependency injection**: No globals, wired in `main.py`
4. **No Windows code**: Linux/Mac native (`fcntl` only)
5. **Minimal dependencies**: 8 core dependencies
6. **Clean code**: Type hints, no dead code, English-only comments

### Common Development Tasks
- Fix import paths throughout the codebase
- Add unit tests for core modules
- Create packaging configuration (`pyproject.toml`)
- Implement async watcher functionality
- Add MCP server for IDE integration
- Implement job queue management

## References
- `docs/kronos_insights_consolidated.md`: Detailed architecture analysis and v1.0 design blueprint
- Environment variables documented in `main.py` help text
- Interface definitions in `storage/interface.py`, `embedders.py`, `llms.py`
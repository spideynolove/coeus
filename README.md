# Coeus

Local semantic memory for AI agents. Indexes your codebase and serves context to Claude Code, Cursor, and other tools via MCP — without dumping entire files into the context window.

**83–98% token reduction** through pointer-based RAG with hybrid vector + full-text search.

## How It Works

1. You index a codebase once (`coeus ingest`)
2. `coeus-mcp` runs as an MCP server in the background
3. Your AI tool (Claude Code, Cursor, etc.) queries it via the `coeus` skill
4. Coeus returns precise pointers and excerpts instead of raw files

## Install

Requires Python 3.10+. Install via uv:

```bash
uv tool install git+https://github.com/YOUR_USERNAME/coeus
```

Then run one-time setup:

```bash
coeus setup
```

Setup will:
- Ask for your API key(s) and save them to `~/.coeus/.env`
- Detect installed tools (Claude Code, Cursor, Windsurf, etc.)
- Register `coeus-mcp` with each detected tool automatically

## API Keys

You need **at least one** of:

| Key | Use | Get it |
|-----|-----|--------|
| `VOYAGE_API_KEY` | Embeddings (recommended) | [voyageai.com](https://dash.voyageai.com) |
| `OPENROUTER_API_KEY` | Embeddings fallback + LLM | [openrouter.ai/keys](https://openrouter.ai/keys) |

**Voyage AI** gives better embedding quality. First 200M tokens are free on `voyage-3`.
**OpenRouter** works as a fallback using `openai/text-embedding-3-small` ($0.02/MTok).

Both keys are optional if the other is set. `coeus setup` will prompt for whichever is missing.

## Usage

```bash
# Index a project
coeus ingest /path/to/project --recursive

# Ask a question
coeus ask "how does authentication work?"

# Raw search (debugging)
coeus search "JWT validation" --method hybrid

# Check what's indexed
coeus stats

# Watch for file changes and auto-index
coeus watch /path/to/project

# Show current config
coeus config
```

## MCP Tools (via Claude Code / Cursor)

Once set up, your AI tool uses these automatically through the `coeus` skill:

| Tool | Purpose |
|------|---------|
| `coeus_query` | Main search — returns assembled context within token budget |
| `coeus_search` | Raw results with relevance scores |
| `coeus_ingest` | Index a path from within the AI tool |
| `coeus_decisions` | List active architectural decisions |
| `coeus_stats` | Database statistics |
| `coeus_ping` | Health check |

## Configuration

All settings via environment variables or `~/.coeus/.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `VOYAGE_API_KEY` | — | Voyage AI embeddings |
| `OPENROUTER_API_KEY` | — | OpenRouter fallback |
| `COEUS_DATA` | `~/.coeus` | Data directory |
| `COEUS_EMBED_MODEL` | `voyage-3` | Embedding model |
| `COEUS_LLM_MODEL` | `anthropic/claude-3.5-sonnet` | Downstream model (for savings calc) |
| `COEUS_CHUNK_SIZE` | `1000` | Chunk size in characters |
| `COEUS_BUDGET` | `4000` | Default context budget in tokens |

## AST-Aware Chunking (optional)

Install tree-sitter for function/class boundary chunking instead of line-count splitting:

```bash
uv tool install --with "coeus[ast]" git+https://github.com/YOUR_USERNAME/coeus
```

Supported: Python, Go, JavaScript, TypeScript, Rust.

## Architecture

```
coeus ingest  →  chunk (AST/line)  →  embed  →  SQLite + zvec HNSW
coeus_query   →  FastPath cache  →  hybrid search  →  Contextualizer  →  Budgeter  →  pointers
```

- **FastPath** — exact/prefix cache, skips embedding API call for short queries
- **Contextualizer** — expands matched chunks with ±3 surrounding lines from source
- **Budgeter** — assembles context within token budget, max 3 chunks per file

## License

MIT

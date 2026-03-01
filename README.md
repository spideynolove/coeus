# Coeus

Local semantic memory system for AI agents. Reduces LLM API costs by 83-98% through pointer-based RAG with real zvec HNSW vector search.

## Features

- **zvec HNSW Search** - O(log n) vector search via Alibaba's zvec library
- **Hybrid Search** - Vector + FTS5 for precise results
- **Entity Extraction** - Problems, solutions, decisions, tasks
- **Pointer-Based RAG** - Lightweight references instead of full documents
- **MCP Integration** - Works with Claude Code, Cursor, Antigravity
- **Job Queue** - Async background processing
- **Shadow Accounting** - Track token/cost savings

## Install

```bash
pip install zvec voyageai watchdog python-dotenv mcp numpy
```

## Quick Start

```bash
export VOYAGE_API_KEY=your_key

python main.py ingest ./my-project --recursive
python main.py ask "How does authentication work?"
python main.py stats
```

## MCP Configuration (Claude Code)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "coeus": {
      "command": "python",
      "args": ["/path/to/coeus/mcp_server.py"],
      "env": {
        "VOYAGE_API_KEY": "your_key"
      }
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VOYAGE_API_KEY` | Voyage AI API key | Required |
| `OPENROUTER_API_KEY` | OpenRouter API key (fallback) | Optional |
| `COEUS_DATA` | Data directory | `~/.coeus` |
| `COEUS_EMBED_MODEL` | Embedding model | `voyage-3` |
| `COEUS_LLM_MODEL` | LLM model | `anthropic/claude-3.5-sonnet` |
| `COEUS_CHUNK_SIZE` | Chunk size | `1000` |
| `COEUS_BUDGET` | Default token budget | `4000` |

## CLI Commands

```bash
python main.py ingest <path>           Index files/directories
python main.py ask <query>             Query knowledge base
python main.py search <query>          Raw search (debug)
python main.py stats                   Database statistics
python main.py watch <path>            Monitor files for changes
python main.py config                  Show configuration
python main.py job list                List background jobs
python main.py job status <job_id>      Check job status
```

## MCP Tools

- `coeus_ping` - Health check
- `coeus_query` - Main search with context assembly
- `coeus_search` - Raw search results
- `coeus_stats` - Database statistics
- `coeus_ingest` - Index files
- `coeus_decisions` - Get active decisions
- `coeus_reinit_oracle` - Recover from Oracle lock

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌─────────────┐
│   Oracle    │───▶│  Context     │───▶│  Response   │
│ (Search)    │    │  Budgeter    │    │  Assembly  │
└─────────────┘    └──────────────┘    └─────────────┘
       │                   │
       ▼                   ▼
┌─────────────┐    ┌──────────────┐
│    zvec     │    │  SQLite FTS5 │
│  (Vectors)  │    │  (Keywords)  │
└─────────────┘    └──────────────┘
```

## License

MIT

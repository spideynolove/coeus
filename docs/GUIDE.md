# Coeus Guide — Using It Well

## Understanding the Output

When you run `coeus ask`, you get two types of results:

**Chunks** — Full content, high confidence match. These are the parts of your codebase most relevant to your question. Use these when you need to understand or modify something.

**Pointers** — File references, lower confidence. Instead of loading the full content, Coeus tells you *where* to look: `src/auth/jwt.rs:45-89 — "Token validation"`. This saves tokens while still guiding you.

The pointer-based approach is the core value of Coeus: a 300-file codebase costs ~2KB of context instead of 3MB.

## Budget Modes

| Mode | Tokens | Use for |
|------|--------|---------|
| `light` | 2,000 | Quick lookups, "where is X defined" |
| `auto` | 4,000 | Most questions (default) |
| `extra` | 8,000 | Architecture overviews, complex analysis |

```bash
coeus ask "how does auth work" --mode auto
coeus ask "full architecture overview" --mode extra
coeus ask "where is UserService defined" --mode light
```

## Per-Tool Usage

### Claude Code

The `coeus` skill is installed automatically. Invoke it naturally:
> "Use coeus to find how database connections are managed in my-project"

Or trigger it explicitly:
> "/coeus how does authentication work"

### Cursor / Windsurf / OpenCode

Add this to your `.cursorrules` or equivalent rules file in your project:

```
When asked to understand, explain, or modify code in an existing project:
1. First call the coeus MCP tool: coeus_query(query="<your question>", project="<project-name>")
2. Use the returned context to answer. Do not read files without checking coeus first.
3. For targeted lookups, use coeus_search instead.
```

### VSCode + Continue

In Continue chat, prefix questions with `@mcp coeus`:
> "@mcp coeus how does the storage layer work"

## File Extension Strategy

| Project type | Recommended extensions |
|-------------|----------------------|
| Python | `py,md,toml,txt` |
| Rust | `rs,toml,md` |
| TypeScript/JS | `ts,tsx,js,jsx,json,md` |
| Go | `go,mod,md` |
| Full-stack | `ts,tsx,rs,py,md,json,toml` |

Avoid ingesting `lock` files, `dist/`, `node_modules/`, `target/` — Coeus filters these automatically.

## Keeping the Index Fresh

Run the watcher in a background terminal:

```bash
coeus watch ~/my-project --project my-project
```

Or re-ingest after big changes — unchanged files are skipped automatically (hash-based).

## Multiple Projects

Each project gets its own namespace:

```bash
coeus ingest ~/project-a --project alpha
coeus ingest ~/project-b --project beta

coeus ask "how does auth work" --project alpha
coeus ask "database schema" --project beta
```

## Checking What's Indexed

```bash
coeus stats
```

Shows document count, entity count, projects, and database size.

## AST-Aware Chunking

When tree-sitter is installed, Coeus chunks code files along function and class boundaries instead of arbitrary line counts. This ensures function bodies are never split across chunks, which significantly improves semantic search quality.

Install language support:

```bash
uv pip install tree-sitter tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript tree-sitter-rust
```

Supported: Python, Go, JavaScript, TypeScript, Rust. Other file types use line-count chunking automatically.

## Configuration Reference

All settings in `~/.coeus/.env`:

```bash
# Embeddings (required — choose one)
VOYAGE_API_KEY=pa-...
OPENROUTER_API_KEY=sk-or-...

# Models
COEUS_EMBED_MODEL=voyage-3          # or openai/text-embedding-3-small
COEUS_LLM_MODEL=anthropic/claude-3.5-sonnet

# Storage
COEUS_DATA=~/.coeus                 # where DB lives
COEUS_CHUNK_SIZE=1000               # chars per chunk
COEUS_BUDGET=4000                   # default token budget
```

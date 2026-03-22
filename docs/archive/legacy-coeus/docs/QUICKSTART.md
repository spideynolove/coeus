# Coeus Quickstart — 5 Minutes to Working Memory

## 1. Install

```bash
# Recommended
uv tool install coeus-memory

# Or with pip
pip install coeus-memory
```

## 2. Setup (one command)

```bash
coeus setup
```

This will:
- Ask for your API key (Voyage AI or OpenRouter — get one free at voyage.ai or openrouter.ai)
- Detect your coding tools (Claude Code, Cursor, VSCode, Windsurf)
- Register Coeus with each one automatically

## 3. Index your first project

```bash
coeus ingest ~/my-project --recursive
```

Takes 1–5 minutes depending on project size. Progress shown per file.

## 4. Ask your first question

```bash
coeus ask "what does this project do and how is it structured"
```

Or in your coding tool (Claude Code, Cursor, etc.), just ask:
> "Use coeus to explain the architecture of my-project"

## 5. What's next?

- **Index more projects:** `coeus ingest ~/another-project --project myapp`
- **Learn the output:** Read [GUIDE.md](GUIDE.md) to understand chunks vs pointers
- **Keep it fresh:** `coeus watch ~/my-project` auto-indexes changes

## Supported Tools

| Tool | Setup method |
|------|-------------|
| Claude Code | Skill file (auto) + `/coeus` |
| Cursor | MCP registered in `~/.cursor/mcp.json` |
| VSCode + Continue | MCP in `~/.continue/config.yaml` |
| Windsurf | MCP in `~/.codeium/windsurf/mcp_config.json` |
| OpenCode | MCP in `~/.config/opencode/config.json` |

## API Keys

Coeus needs an embedding API key. Free tiers available:

| Provider | Free tier | Get key |
|----------|-----------|---------|
| **Voyage AI** (recommended) | 200M tokens | voyage.ai |
| **OpenRouter** | Pay-per-use, very cheap | openrouter.ai |

Store in `~/.coeus/.env`:
```
VOYAGE_API_KEY=pa-...
# or
OPENROUTER_API_KEY=sk-or-...
COEUS_EMBED_MODEL=openai/text-embedding-3-small
```

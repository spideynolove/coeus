import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

HOME = Path.home()

TOOL_CLAUDE_CODE = "claude-code"
TOOL_CURSOR = "cursor"
TOOL_VSCODE_CONTINUE = "vscode-continue"
TOOL_WINDSURF = "windsurf"
TOOL_OPENCODE = "opencode"
TOOL_CODEX = "codex"

def _tool_markers():
    return {
        TOOL_CLAUDE_CODE:     HOME / ".claude",
        TOOL_CURSOR:          HOME / ".cursor",
        TOOL_VSCODE_CONTINUE: HOME / ".continue",
        TOOL_WINDSURF:        HOME / ".codeium" / "windsurf",
        TOOL_OPENCODE:        HOME / ".config" / "opencode",
    }


def detect_tools() -> List[str]:
    return [tool for tool, path in _tool_markers().items() if path.exists()]


def mcp_config_cursor(mcp_server_path: str, python_path: str) -> Dict[str, Any]:
    return {
        "mcpServers": {
            "coeus": {
                "command": python_path,
                "args": [mcp_server_path],
                "env": {}
            }
        }
    }


def mcp_config_windsurf(mcp_server_path: str, python_path: str) -> Dict[str, Any]:
    return mcp_config_cursor(mcp_server_path, python_path)


def mcp_config_continue_yaml(mcp_server_path: str, python_path: str) -> Dict[str, Any]:
    return {
        "mcpServers": {
            "coeus": {
                "command": python_path,
                "args": [mcp_server_path]
            }
        }
    }


def mcp_config_opencode(mcp_server_path: str, python_path: str) -> Dict[str, Any]:
    return {
        "mcp": {
            "servers": {
                "coeus": {
                    "type": "stdio",
                    "command": python_path,
                    "args": [mcp_server_path]
                }
            }
        }
    }


def mcp_config_mcporter(mcp_server_path: str, python_path: str) -> Dict[str, Any]:
    return {
        "servers": {
            "coeus": {
                "command": python_path,
                "args": [mcp_server_path]
            }
        }
    }


def _merge_json(path: Path, new_data: Dict[str, Any]) -> None:
    if path.exists():
        try:
            existing = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {path}: {e}") from e
        for key, val in new_data.items():
            if key in existing and isinstance(existing[key], dict):
                existing[key].update(val)
            else:
                existing[key] = val
        path.write_text(json.dumps(existing, indent=2))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(new_data, indent=2))


def register_cursor(mcp_server_path: str, python_path: str,
                    config_path: Path = None) -> None:
    if config_path is None:
        config_path = HOME / ".cursor" / "mcp.json"
    _merge_json(config_path, mcp_config_cursor(mcp_server_path, python_path))


def register_windsurf(mcp_server_path: str, python_path: str,
                      config_path: Path = None) -> None:
    if config_path is None:
        config_path = HOME / ".codeium" / "windsurf" / "mcp_config.json"
    _merge_json(config_path, mcp_config_windsurf(mcp_server_path, python_path))


def register_vscode_continue(mcp_server_path: str, python_path: str,
                              config_path: Path = None) -> None:
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML required: uv pip install pyyaml")

    if config_path is None:
        config_path = HOME / ".continue" / "config.yaml"

    cfg = mcp_config_continue_yaml(mcp_server_path, python_path)
    if config_path.exists():
        existing = yaml.safe_load(config_path.read_text()) or {}
        existing.setdefault("mcpServers", {}).update(cfg["mcpServers"])
        cfg = existing

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(yaml.dump(cfg, default_flow_style=False))


def register_opencode(mcp_server_path: str, python_path: str,
                      config_path: Path = None) -> None:
    if config_path is None:
        config_path = HOME / ".config" / "opencode" / "config.json"
    cfg = mcp_config_opencode(mcp_server_path, python_path)
    if config_path.exists():
        try:
            existing = json.loads(config_path.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {config_path}: {e}") from e
        existing.setdefault("mcp", {}).setdefault("servers", {}).update(
            cfg["mcp"]["servers"]
        )
        config_path.write_text(json.dumps(existing, indent=2))
    else:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(cfg, indent=2))


def register_mcporter(mcp_server_path: str, python_path: str,
                      config_path: Path = None) -> None:
    if config_path is None:
        config_path = HOME / ".mcporter" / "mcporter.json"
    _merge_json(config_path, mcp_config_mcporter(mcp_server_path, python_path))


CLAUDE_CODE_SKILL_CONTENT = '''---
name: coeus
description: Semantic memory and codebase search via Coeus MCP. Use when you need to query, search, or learn about an indexed codebase. All tools called via mcporter to avoid context pollution.
---

# Coeus — Semantic Memory Search

Pointer-based RAG: retrieves relevant context from indexed codebases without dumping full files into context.

## Invocation Pattern

All tools called via mcporter:

```bash
npx mcporter call coeus.TOOL_NAME [args]
```

## Core Tools

### Query (main tool — use this for understanding)
```bash
npx mcporter call coeus.coeus_query \\
  query:"How does authentication work" \\
  mode:auto
```
Modes: `light` (2K tokens), `auto` (4K, default), `extra` (8K for deep analysis)

### Search (raw results with scores)
```bash
npx mcporter call coeus.coeus_search \\
  query:"database connection pooling" \\
  project:my-project \\
  limit:5
```

### Ingest a codebase
```bash
npx mcporter call coeus.coeus_ingest \\
  path:/path/to/project \\
  recursive:true
```

### List architectural decisions
```bash
npx mcporter call coeus.coeus_decisions project:my-project
```

### Check what\'s indexed
```bash
npx mcporter call coeus.coeus_stats
```

## HyDE — Better Recall for Conceptual Questions

For "how", "why", "explain", "what is", "architecture" queries, search quality improves when
the query describes an answer rather than a question. Before calling coeus_query:

1. Mentally draft: "What would the code/docs implementing this look like?" (2-3 sentences)
2. Use that description as the query instead of the raw question

Example:
- User asks: "how does authentication work?"
- Search with: `"JWT tokens validated in middleware AuthService handles login logout session storage"`

This is free — you are the LLM. No extra API call needed.

## Workflow: Learning a New Codebase

```bash
npx mcporter call coeus.coeus_ingest path:/path/to/repo recursive:true
npx mcporter call coeus.coeus_query query:"overall architecture and main components" mode:extra
npx mcporter call coeus.coeus_query query:"how does X work internally" mode:auto
npx mcporter call coeus.coeus_query query:"known problems limitations and technical debt" mode:auto
npx mcporter call coeus.coeus_decisions
```

## When to Use

- Before modifying an unfamiliar codebase
- To find where a feature is implemented
- To understand design decisions without reading all files

## Anti-Patterns

- Don\'t load coeus MCP in .claude.json alongside this skill
- Don\'t use coeus_search when coeus_query gives better assembled context
- Don\'t re-ingest unchanged codebases (skip-if-unchanged is automatic)
'''


def collect_api_keys(interactive: bool = True) -> Dict[str, Optional[str]]:
    voyage = os.getenv("VOYAGE_API_KEY")
    openrouter = os.getenv("OPENROUTER_API_KEY")
    if interactive and voyage is None and openrouter is None:
        print("No API keys found in environment. At least one is required.")
        voyage = input("VOYAGE_API_KEY (leave blank to skip): ").strip() or None
        openrouter = input("OPENROUTER_API_KEY (leave blank to skip): ").strip() or None
    return {"voyage": voyage, "openrouter": openrouter}


def write_env_file(keys: Dict[str, Optional[str]], env_path: Path) -> None:
    existing_lines: list[str] = []
    known_keys = {"VOYAGE_API_KEY", "OPENROUTER_API_KEY", "COEUS_EMBED_MODEL"}

    if env_path.exists():
        existing_lines = [
            line for line in env_path.read_text().splitlines()
            if line.strip() and not any(line.startswith(k + "=") for k in known_keys)
        ]

    new_lines = list(existing_lines)
    if keys.get("voyage"):
        new_lines.append(f"VOYAGE_API_KEY={keys['voyage']}")
    if keys.get("openrouter"):
        new_lines.append(f"OPENROUTER_API_KEY={keys['openrouter']}")
        if not keys.get("voyage"):
            new_lines.append("COEUS_EMBED_MODEL=openai/text-embedding-3-small")

    if new_lines:
        env_path.parent.mkdir(parents=True, exist_ok=True)
        env_path.write_text("\n".join(new_lines) + "\n")


def register_claude_code(mcp_server_path: str, python_path: str,
                         skill_path: Path = None,
                         mcporter_path: Path = None) -> None:
    if skill_path is None:
        skill_path = HOME / ".claude" / "skills" / "coeus" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(CLAUDE_CODE_SKILL_CONTENT)
    register_mcporter(mcp_server_path, python_path, mcporter_path)

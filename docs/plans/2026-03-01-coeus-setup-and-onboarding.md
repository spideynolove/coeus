# Coeus Setup, Multi-Tool Support & Beginner Guide — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a `coeus setup` command that auto-configures Coeus for any detected coding tool, plus beginner-friendly documentation.

**Architecture:** A new `core/setup.py` module handles tool detection, MCP config generation, and skill file writing. Each supported tool gets a dedicated registration function that writes the correct config format. Docs are written in `docs/` as standalone markdown files.

**Tech Stack:** Python stdlib only (pathlib, json, shutil) for setup logic; existing mcporter for Claude Code skill registration; YAML via PyYAML for Continue config.

---

## Task 1: Create `core/setup.py` — Tool Detection

**Files:**
- Create: `core/setup.py`
- Create: `tests/test_setup.py`

**Step 1: Write the failing tests**

```python
# tests/test_setup.py
import pytest
from pathlib import Path
from unittest.mock import patch
from core.setup import detect_tools, TOOL_CURSOR, TOOL_CLAUDE_CODE, TOOL_WINDSURF


def test_detect_tools_finds_cursor(tmp_path):
    cursor_dir = tmp_path / ".cursor"
    cursor_dir.mkdir()
    with patch("core.setup.HOME", tmp_path):
        found = detect_tools()
    assert TOOL_CURSOR in found


def test_detect_tools_ignores_missing(tmp_path):
    with patch("core.setup.HOME", tmp_path):
        found = detect_tools()
    assert found == []


def test_detect_tools_finds_multiple(tmp_path):
    (tmp_path / ".cursor").mkdir()
    (tmp_path / ".claude").mkdir()
    with patch("core.setup.HOME", tmp_path):
        found = detect_tools()
    assert TOOL_CURSOR in found
    assert TOOL_CLAUDE_CODE in found
```

**Step 2: Run to verify failure**

```bash
cd /home/hung/Public/gits/coeus
source /home/hung/env/.venv/bin/activate
python -m pytest tests/test_setup.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.setup'`

**Step 3: Implement `core/setup.py` — tool detection**

```python
from pathlib import Path
from typing import List

HOME = Path.home()

TOOL_CLAUDE_CODE = "claude-code"
TOOL_CURSOR = "cursor"
TOOL_VSCODE_CONTINUE = "vscode-continue"
TOOL_WINDSURF = "windsurf"
TOOL_OPENCODE = "opencode"
TOOL_CODEX = "codex"

_TOOL_MARKERS = {
    TOOL_CLAUDE_CODE:    HOME / ".claude",
    TOOL_CURSOR:         HOME / ".cursor",
    TOOL_VSCODE_CONTINUE: HOME / ".continue",
    TOOL_WINDSURF:       HOME / ".codeium" / "windsurf",
    TOOL_OPENCODE:       HOME / ".config" / "opencode",
    TOOL_CODEX:          HOME / ".codex",
}


def detect_tools() -> List[str]:
    return [tool for tool, path in _TOOL_MARKERS.items() if path.exists()]
```

**Step 4: Run tests — expect pass**

```bash
python -m pytest tests/test_setup.py::test_detect_tools_finds_cursor -v
python -m pytest tests/test_setup.py::test_detect_tools_ignores_missing -v
python -m pytest tests/test_setup.py::test_detect_tools_finds_multiple -v
```

Expected: 3 passed

**Step 5: Commit**

```bash
git add core/setup.py tests/test_setup.py
git commit -m "feat: add tool detection for coeus setup"
```

---

## Task 2: MCP Config Generators (pure functions, no I/O)

**Files:**
- Modify: `core/setup.py` (add generator functions)
- Modify: `tests/test_setup.py` (add generator tests)

**Step 1: Write failing tests**

```python
# append to tests/test_setup.py
import json
from core.setup import (
    mcp_config_cursor, mcp_config_windsurf,
    mcp_config_continue_yaml, mcp_config_opencode,
    mcp_config_mcporter,
)


def test_cursor_config_valid_json():
    cfg = mcp_config_cursor("/path/to/mcp_server.py", "/path/to/python")
    assert cfg["mcpServers"]["coeus"]["command"] == "/path/to/python"
    assert "/path/to/mcp_server.py" in cfg["mcpServers"]["coeus"]["args"]


def test_windsurf_config_same_schema_as_cursor():
    cursor = mcp_config_cursor("/p/mcp.py", "/p/python")
    windsurf = mcp_config_windsurf("/p/mcp.py", "/p/python")
    assert cursor == windsurf


def test_continue_config_is_dict_with_mcp_servers():
    cfg = mcp_config_continue_yaml("/p/mcp.py", "/p/python")
    assert "mcpServers" in cfg
    assert "coeus" in cfg["mcpServers"]


def test_mcporter_config_format():
    cfg = mcp_config_mcporter("/p/mcp.py", "/p/python")
    assert cfg["servers"]["coeus"]["command"] == "/p/python"
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_setup.py -k "config" -v
```

Expected: `ImportError` — functions don't exist yet

**Step 3: Add generator functions to `core/setup.py`**

```python
from typing import Dict, Any


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
```

**Step 4: Run tests**

```bash
python -m pytest tests/test_setup.py -v
```

Expected: all pass

**Step 5: Commit**

```bash
git add core/setup.py tests/test_setup.py
git commit -m "feat: add MCP config generators for all supported tools"
```

---

## Task 3: Registration Writers (I/O functions)

**Files:**
- Modify: `core/setup.py` (add register_* functions)
- Modify: `tests/test_setup.py` (add I/O tests using tmp_path)

**Step 1: Write failing tests**

```python
# append to tests/test_setup.py
import yaml
from core.setup import (
    register_cursor, register_windsurf,
    register_vscode_continue, register_opencode,
    register_claude_code,
)


def test_register_cursor_creates_file(tmp_path):
    config_path = tmp_path / ".cursor" / "mcp.json"
    register_cursor("/p/mcp.py", "/p/python", config_path)
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "mcpServers" in data


def test_register_cursor_merges_existing(tmp_path):
    config_path = tmp_path / ".cursor" / "mcp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcpServers": {"other": {"command": "x"}}}')
    register_cursor("/p/mcp.py", "/p/python", config_path)
    data = json.loads(config_path.read_text())
    assert "other" in data["mcpServers"]
    assert "coeus" in data["mcpServers"]


def test_register_vscode_continue_creates_yaml(tmp_path):
    config_path = tmp_path / ".continue" / "config.yaml"
    register_vscode_continue("/p/mcp.py", "/p/python", config_path)
    assert config_path.exists()
    data = yaml.safe_load(config_path.read_text())
    assert "mcpServers" in data


def test_register_claude_code_creates_skill_file(tmp_path):
    skill_path = tmp_path / ".claude" / "skills" / "coeus" / "SKILL.md"
    register_claude_code("/p/mcp.py", "/p/python", skill_path=skill_path)
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "coeus_query" in content
    assert "mcporter" in content
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_setup.py -k "register" -v
```

**Step 3: Add I/O registration functions to `core/setup.py`**

```python
import json
import sys


def _merge_json(path: Path, new_data: Dict[str, Any]) -> None:
    if path.exists():
        existing = json.loads(path.read_text())
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
    _merge_json(config_path, mcp_config_opencode(mcp_server_path, python_path))


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


def register_claude_code(mcp_server_path: str, python_path: str,
                         skill_path: Path = None,
                         mcporter_path: Path = None) -> None:
    if skill_path is None:
        skill_path = HOME / ".claude" / "skills" / "coeus" / "SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(CLAUDE_CODE_SKILL_CONTENT)
    register_mcporter(mcp_server_path, python_path, mcporter_path)
```

**Step 4: Install pyyaml and run tests**

```bash
uv pip install pyyaml
python -m pytest tests/test_setup.py -v
```

Expected: all pass

**Step 5: Commit**

```bash
git add core/setup.py tests/test_setup.py
git commit -m "feat: add registration writers for Cursor, VSCode, Windsurf, OpenCode, Claude Code"
```

---

## Task 4: Key Collection and `.env` Writer

**Files:**
- Modify: `core/setup.py`
- Modify: `tests/test_setup.py`

**Step 1: Write failing tests**

```python
# append to tests/test_setup.py
from core.setup import collect_api_keys, write_env_file


def test_collect_api_keys_from_env(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "va-test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    keys = collect_api_keys(interactive=False)
    assert keys["voyage"] == "va-test"
    assert keys["openrouter"] == "sk-or-test"


def test_collect_api_keys_returns_none_when_missing(monkeypatch):
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    keys = collect_api_keys(interactive=False)
    assert keys["voyage"] is None
    assert keys["openrouter"] is None


def test_write_env_file_creates_file(tmp_path):
    env_path = tmp_path / ".env"
    write_env_file({"voyage": "va-123", "openrouter": None}, env_path)
    content = env_path.read_text()
    assert "VOYAGE_API_KEY=va-123" in content
    assert "OPENROUTER_API_KEY" not in content


def test_write_env_file_skips_none_values(tmp_path):
    env_path = tmp_path / ".env"
    write_env_file({"voyage": None, "openrouter": "sk-or-456"}, env_path)
    content = env_path.read_text()
    assert "VOYAGE_API_KEY" not in content
    assert "OPENROUTER_API_KEY=sk-or-456" in content
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_setup.py -k "collect or write_env" -v
```

**Step 3: Add to `core/setup.py`**

```python
import os
from typing import Optional


def collect_api_keys(interactive: bool = True) -> Dict[str, Optional[str]]:
    keys = {
        "voyage": os.getenv("VOYAGE_API_KEY"),
        "openrouter": os.getenv("OPENROUTER_API_KEY"),
    }

    if not interactive:
        return keys

    if not keys["voyage"] and not keys["openrouter"]:
        print("\nNo API keys found in environment.")
        print("You need at least one: Voyage AI (voyage-3) or OpenRouter (text-embedding-3-small)")
        print()

        voyage = input("Voyage AI key (pa-...) or press Enter to skip: ").strip()
        if voyage:
            keys["voyage"] = voyage
        else:
            openrouter = input("OpenRouter key (sk-or-...) or press Enter to skip: ").strip()
            if openrouter:
                keys["openrouter"] = openrouter

    return keys


def write_env_file(keys: Dict[str, Optional[str]], env_path: Path) -> None:
    lines = []
    if keys.get("voyage"):
        lines.append(f"VOYAGE_API_KEY={keys['voyage']}")
    if keys.get("openrouter"):
        lines.append(f"OPENROUTER_API_KEY={keys['openrouter']}")
        if not keys.get("voyage"):
            lines.append("COEUS_EMBED_MODEL=openai/text-embedding-3-small")
    env_path.write_text("\n".join(lines) + "\n")
```

**Step 4: Run all tests**

```bash
python -m pytest tests/test_setup.py -v
```

Expected: all pass

**Step 5: Commit**

```bash
git add core/setup.py tests/test_setup.py
git commit -m "feat: add API key collection and .env writer"
```

---

## Task 5: `cmd_setup` — Wire Everything into the CLI

**Files:**
- Modify: `main.py` (add `setup` subparser and `cmd_setup`)
- No new tests needed (integration of already-tested components)

**Step 1: Add `setup` subparser to `create_parser()` in `main.py`**

After the `job_parser` block (line ~214), add:

```python
    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure Coeus and register with coding tools",
        description="One-time setup: API keys, MCP registration, skill files."
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use environment variables only, no prompts"
    )
    setup_parser.add_argument(
        "--tools",
        nargs="+",
        choices=["claude-code", "cursor", "vscode-continue", "windsurf", "opencode", "codex"],
        help="Register only specific tools (default: all detected)"
    )
```

**Step 2: Add `cmd_setup` function to `main.py`** (before `main()`)

```python
def cmd_setup(args: argparse.Namespace, config: Config) -> int:
    import sys
    from core.setup import (
        detect_tools, collect_api_keys, write_env_file,
        register_cursor, register_windsurf, register_vscode_continue,
        register_opencode, register_claude_code,
        TOOL_CLAUDE_CODE, TOOL_CURSOR, TOOL_VSCODE_CONTINUE,
        TOOL_WINDSURF, TOOL_OPENCODE,
    )

    print("Coeus Setup")
    print("=" * 40)

    print("\nStep 1: API Keys")
    keys = collect_api_keys(interactive=not args.non_interactive)

    if not keys.get("voyage") and not keys.get("openrouter"):
        print("  ✗ No API keys found. Run 'coeus setup' again after setting:")
        print("    export VOYAGE_API_KEY=your_key")
        print("    export OPENROUTER_API_KEY=your_key")
        return 1

    env_path = config.data_dir / ".env"
    write_env_file(keys, env_path)
    print(f"  ✓ Saved to {env_path}")

    print("\nStep 2: Detecting installed tools...")
    tools = args.tools or detect_tools()

    if not tools:
        print("  No supported tools detected.")
        print("  Supported: Claude Code, Cursor, VSCode+Continue, Windsurf, OpenCode")
    for tool in tools:
        print(f"  ✓ {tool}")

    mcp_path = str(Path(__file__).parent / "mcp_server.py")
    python_path = sys.executable

    print("\nStep 3: Registering with tools...")
    registrations = {
        TOOL_CLAUDE_CODE: lambda: register_claude_code(mcp_path, python_path),
        TOOL_CURSOR: lambda: register_cursor(mcp_path, python_path),
        TOOL_VSCODE_CONTINUE: lambda: register_vscode_continue(mcp_path, python_path),
        TOOL_WINDSURF: lambda: register_windsurf(mcp_path, python_path),
        TOOL_OPENCODE: lambda: register_opencode(mcp_path, python_path),
    }

    for tool in tools:
        if tool in registrations:
            try:
                registrations[tool]()
                print(f"  ✓ {tool}")
            except Exception as e:
                print(f"  ✗ {tool}: {e}")

    print("\nStep 4: Verifying connection...")
    try:
        from embedders import create_embedder
        from config import reset_config
        reset_config()
        cfg = get_config()
        provider = "voyage" if cfg.embedding_model.startswith("voyage") else "openrouter"
        embedder = create_embedder(provider, model=cfg.embedding_model)
        embedder.embed(["coeus setup test"])
        print(f"  ✓ Embedder OK ({cfg.embedding_model}, {embedder.dimension} dims)")
    except Exception as e:
        print(f"  ✗ Embedder failed: {e}")
        print("    Check your API key in ~/.coeus/.env")
        return 1

    print("\nSetup complete!")
    print("\nNext steps:")
    print("  coeus ingest /path/to/your/project --recursive")
    print("  coeus ask 'what does this project do'")
    return 0
```

**Step 3: Register the command in `main()`**

In the `commands` dict (around line 564):
```python
    commands = {
        ...
        "setup": cmd_setup,
    }
```

**Step 4: Manual smoke test**

```bash
source /home/hung/env/.venv/bin/activate
python main.py setup --non-interactive
```

Expected output:
```
Coeus Setup
========================================

Step 1: API Keys
  ✓ Saved to /home/hung/.coeus/.env

Step 2: Detecting installed tools...
  ✓ claude-code
  ✓ cursor   (if installed)

Step 3: Registering with tools...
  ✓ claude-code
  ✓ cursor

Step 4: Verifying connection...
  ✓ Embedder OK (openai/text-embedding-3-small, 1536 dims)

Setup complete!
```

**Step 5: Commit**

```bash
git add main.py
git commit -m "feat: add coeus setup command for one-command tool registration"
```

---

## Task 6: Write `docs/QUICKSTART.md` — Tier 1 Guide (5 min)

**Files:**
- Create: `docs/QUICKSTART.md`

**No tests.** Write the file directly.

**Step 1: Create `docs/QUICKSTART.md`**

Content must cover exactly:
1. Install (uv or pip)
2. Setup (one command)
3. Index one project
4. Ask one question
5. What to do next

```markdown
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
```

**Step 2: Commit**

```bash
git add docs/QUICKSTART.md
git commit -m "docs: add 5-minute quickstart guide"
```

---

## Task 7: Write `docs/GUIDE.md` — Tier 2 Guide (20 min)

**Files:**
- Create: `docs/GUIDE.md`

**Step 1: Create `docs/GUIDE.md`**

Content must cover:
- Understanding output: chunks vs pointers
- Budget modes and when to use each
- Per-tool usage patterns (how to invoke in each IDE)
- `.cursorrules` / rules snippet for non-Claude tools
- File extension strategy per project type

```markdown
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
```

**Step 2: Commit**

```bash
git add docs/GUIDE.md
git commit -m "docs: add comprehensive usage guide"
```

---

## Task 8: Add `--setup` to `coeus config --init` fallback + update README

**Files:**
- Modify: `main.py` (update help text to mention `coeus setup`)
- Modify: `README.md` if it exists, or create minimal one

**Step 1: Update parser epilog in `create_parser()` to mention setup**

In `main.py`, update the `epilog` in `create_parser()`:

```python
    epilog=textwrap.dedent("""
        Getting Started:
          coeus setup               # one-time setup, auto-detects tools
          coeus ingest ./my-project --recursive
          coeus ask "how does auth work?"

        Examples:
          coeus ingest ./my-project --recursive
          coeus ask "How does authentication work?"
          coeus search "database connection" --limit 5
          coeus stats
          coeus watch ./src --project my-app

        Environment Variables:
          VOYAGE_API_KEY        API key for Voyage AI embeddings
          OPENROUTER_API_KEY    API key for OpenRouter LLM access
          COEUS_DATA            Data directory (default: ~/.coeus)
          COEUS_EMBED_MODEL     Embedding model (voyage-3, openai/text-embedding-3-small)
          COEUS_LLM_MODEL       LLM model for chat
    """)
```

**Step 2: Add pyyaml to dependency list in CLAUDE.md / README**

Ensure `pyyaml` is listed alongside existing deps.

**Step 3: Commit**

```bash
git add main.py
git commit -m "docs: update CLI help text to highlight coeus setup"
```

---

## Summary

| Task | Deliverable | Tests |
|------|-------------|-------|
| 1 | `detect_tools()` | 3 unit tests |
| 2 | MCP config generators | 4 unit tests |
| 3 | Registration writers | 4 I/O tests |
| 4 | Key collection + `.env` writer | 4 unit tests |
| 5 | `cmd_setup` + CLI wiring | Manual smoke test |
| 6 | `docs/QUICKSTART.md` | — |
| 7 | `docs/GUIDE.md` | — |
| 8 | Help text + deps update | — |

**Run all tests at any point:**
```bash
cd /home/hung/Public/gits/coeus
source /home/hung/env/.venv/bin/activate
python -m pytest tests/ -v
```

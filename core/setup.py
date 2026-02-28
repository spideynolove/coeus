from pathlib import Path
from typing import Any, Dict, List

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
        TOOL_CODEX:           HOME / ".codex",
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

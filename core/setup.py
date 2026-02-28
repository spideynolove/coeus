from pathlib import Path
from typing import List

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

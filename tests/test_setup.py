import pytest
import json
from pathlib import Path
from unittest.mock import patch
from core.setup import detect_tools, TOOL_CURSOR, TOOL_CLAUDE_CODE, TOOL_WINDSURF, TOOL_OPENCODE
from core.setup import (
    mcp_config_cursor, mcp_config_windsurf,
    mcp_config_continue_yaml, mcp_config_opencode,
    mcp_config_mcporter, TOOL_VSCODE_CONTINUE, TOOL_CODEX,
)


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
    assert len(found) == 2
    assert TOOL_WINDSURF not in found
    assert TOOL_OPENCODE not in found


def test_cursor_config_valid_json():
    cfg = mcp_config_cursor("/path/to/mcp_server.py", "/path/to/python")
    server = cfg["mcpServers"]["coeus"]
    assert server["command"] == "/path/to/python"
    assert "/path/to/mcp_server.py" in server["args"]
    assert server["env"] == {}


def test_opencode_config_unique_schema():
    cfg = mcp_config_opencode("/p/mcp.py", "/p/python")
    server = cfg["mcp"]["servers"]["coeus"]
    assert server["type"] == "stdio"
    assert server["command"] == "/p/python"
    assert "/p/mcp.py" in server["args"]


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

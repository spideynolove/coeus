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
    register_claude_code("/p/mcp.py", "/p/python", skill_path=skill_path,
                         mcporter_path=tmp_path / "mcporter.json")
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "coeus_query" in content
    assert "mcporter" in content

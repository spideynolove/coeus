import pytest
import json
import yaml
from pathlib import Path
from unittest.mock import patch
from core.setup import detect_tools, TOOL_CURSOR, TOOL_CLAUDE_CODE, TOOL_WINDSURF, TOOL_OPENCODE
from core.setup import (
    mcp_config_cursor, mcp_config_windsurf,
    mcp_config_continue_yaml, mcp_config_opencode,
    mcp_config_mcporter, TOOL_VSCODE_CONTINUE,
)
from core.setup import (
    register_cursor, register_windsurf,
    register_vscode_continue, register_opencode,
    register_claude_code,
)
from core.setup import collect_api_keys, write_env_file


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
    cfg = mcp_config_cursor()
    server = cfg["mcpServers"]["coeus"]
    assert server["command"] == "coeus-mcp"
    assert server["args"] == []


def test_opencode_config_unique_schema():
    cfg = mcp_config_opencode()
    server = cfg["mcp"]["servers"]["coeus"]
    assert server["type"] == "stdio"
    assert server["command"] == "coeus-mcp"
    assert server["args"] == []


def test_windsurf_config_same_schema_as_cursor():
    assert mcp_config_cursor() == mcp_config_windsurf()


def test_continue_config_is_dict_with_mcp_servers():
    cfg = mcp_config_continue_yaml()
    assert "mcpServers" in cfg
    assert "coeus" in cfg["mcpServers"]


def test_mcporter_config_format():
    cfg = mcp_config_mcporter()
    assert cfg["servers"]["coeus"]["command"] == "coeus-mcp"


def test_register_cursor_creates_file(tmp_path):
    config_path = tmp_path / ".cursor" / "mcp.json"
    register_cursor(config_path)
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "mcpServers" in data


def test_register_cursor_merges_existing(tmp_path):
    config_path = tmp_path / ".cursor" / "mcp.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcpServers": {"other": {"command": "x"}}}')
    register_cursor(config_path)
    data = json.loads(config_path.read_text())
    assert "other" in data["mcpServers"]
    assert "coeus" in data["mcpServers"]


def test_register_vscode_continue_creates_yaml(tmp_path):
    config_path = tmp_path / ".continue" / "config.yaml"
    register_vscode_continue(config_path)
    assert config_path.exists()
    data = yaml.safe_load(config_path.read_text())
    assert "mcpServers" in data


def test_register_vscode_continue_merges_existing(tmp_path):
    config_path = tmp_path / ".continue" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text("models:\n  - name: gpt-4\nmcpServers:\n  other: {command: x}\n")
    register_vscode_continue(config_path)
    data = yaml.safe_load(config_path.read_text())
    assert "models" in data
    assert "other" in data["mcpServers"]
    assert "coeus" in data["mcpServers"]


def test_register_claude_code_creates_skill_file(tmp_path):
    skill_path = tmp_path / ".claude" / "skills" / "coeus" / "SKILL.md"
    register_claude_code(skill_path=skill_path,
                         mcporter_path=tmp_path / "mcporter.json")
    assert skill_path.exists()
    content = skill_path.read_text()
    assert "coeus_query" in content
    assert "mcporter" in content


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
    assert "COEUS_EMBED_MODEL=openai/text-embedding-3-small" in content


def test_write_env_file_does_nothing_when_all_none(tmp_path):
    env_path = tmp_path / ".env"
    write_env_file({"voyage": None, "openrouter": None}, env_path)
    assert not env_path.exists()


def test_collect_api_keys_one_key_present_no_prompt(monkeypatch):
    monkeypatch.setenv("VOYAGE_API_KEY", "va-test")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    keys = collect_api_keys(interactive=True)
    assert keys["voyage"] == "va-test"
    assert keys["openrouter"] is None


def test_register_windsurf_creates_file(tmp_path):
    config_path = tmp_path / ".codeium" / "windsurf" / "mcp_config.json"
    register_windsurf(config_path)
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert "mcpServers" in data


def test_register_windsurf_merges_existing(tmp_path):
    config_path = tmp_path / ".codeium" / "windsurf" / "mcp_config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"mcpServers": {"other": {"command": "x"}}}')
    register_windsurf(config_path)
    data = json.loads(config_path.read_text())
    assert "other" in data["mcpServers"]
    assert "coeus" in data["mcpServers"]


def test_register_opencode_creates_file(tmp_path):
    config_path = tmp_path / "config.json"
    register_opencode(config_path)
    assert config_path.exists()
    data = json.loads(config_path.read_text())
    assert data["mcp"]["servers"]["coeus"]["type"] == "stdio"


def test_register_opencode_merges_existing(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"mcp": {"servers": {"other-tool": {"command": "x"}}}}')
    register_opencode(config_path)
    data = json.loads(config_path.read_text())
    assert "other-tool" in data["mcp"]["servers"]
    assert "coeus" in data["mcp"]["servers"]


def test_write_env_file_merges_with_existing(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("CUSTOM_VAR=keep-me\nVOYAGE_API_KEY=old\n")
    write_env_file({"voyage": "new-key", "openrouter": None}, env_path)
    content = env_path.read_text()
    assert "CUSTOM_VAR=keep-me" in content
    assert "VOYAGE_API_KEY=new-key" in content
    assert "VOYAGE_API_KEY=old" not in content

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

import pytest
from core.ast_chunker import chunk_by_ast, AstChunk


def test_python_packs_small_functions_into_one_chunk():
    source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert len(chunks) == 1
    assert 'def foo' in chunks[0].content
    assert 'def bar' in chunks[0].content


def test_python_splits_when_packed_size_exceeds_chunk_size():
    big_fn = "def big():\n" + "    x = 1\n" * 60   # ~660 chars
    small_fn = "\ndef small():\n    return 1\n"
    source = big_fn + small_fn
    chunks = chunk_by_ast(source, '.py', chunk_size=500)
    assert len(chunks) == 2
    assert 'def big' in chunks[0].content
    assert 'def small' in chunks[1].content


def test_python_never_splits_single_oversized_function():
    big_fn = "def enormous():\n" + "    x = 1\n" * 200  # ~1800 chars
    chunks = chunk_by_ast(big_fn, '.py', chunk_size=100)
    assert len(chunks) == 1
    assert 'def enormous' in chunks[0].content


def test_python_captures_section_name():
    source = "def validate_jwt(token):\n    return True\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert chunks[0].section == 'validate_jwt'


def test_python_class_captured_as_section():
    source = "class AuthService:\n    def login(self):\n        pass\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert chunks[0].section == 'AuthService'


def test_unknown_extension_returns_empty():
    chunks = chunk_by_ast("# markdown content", '.md', chunk_size=1000)
    assert chunks == []


def test_no_top_level_defs_returns_empty():
    source = "import os\nimport sys\nX = 1\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert chunks == []


def test_go_function_boundary():
    source = "package main\n\nfunc Foo() int {\n\treturn 1\n}\n\nfunc Bar() int {\n\treturn 2\n}\n"
    chunks = chunk_by_ast(source, '.go', chunk_size=1000)
    assert len(chunks) == 1
    assert 'func Foo' in chunks[0].content
    assert 'func Bar' in chunks[0].content


def test_rust_function_boundary():
    source = "fn foo() -> i32 {\n    1\n}\n\nfn bar() -> i32 {\n    2\n}\n"
    chunks = chunk_by_ast(source, '.rs', chunk_size=1000)
    assert len(chunks) == 1
    assert 'fn foo' in chunks[0].content


def test_chunk_line_numbers_are_one_indexed():
    source = "def foo():\n    return 1\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 2

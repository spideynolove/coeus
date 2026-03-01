from core.ast_chunker import chunk_by_ast
from pathlib import Path
from unittest.mock import MagicMock
from core.ingestor import Ingestor


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


def test_packed_chunk_section_is_first_definition():
    source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert len(chunks) == 1
    assert chunks[0].section == 'foo'


def test_python_decorated_function_section_name():
    source = "@staticmethod\ndef compute():\n    return 1\n"
    chunks = chunk_by_ast(source, '.py', chunk_size=1000)
    assert chunks[0].section == 'compute'


def _make_ingestor(chunk_size=1000):
    storage = MagicMock()
    storage.is_file_indexed.return_value = False
    storage.insert_documents = MagicMock()
    storage.insert_entities = MagicMock()
    storage.mark_file_indexed = MagicMock()
    storage.delete_documents_by_source = MagicMock()
    embedder = MagicMock()
    embedder.embed.return_value = [[0.1] * 8]
    return Ingestor(storage, embedder, chunk_size=chunk_size)


def test_ingestor_uses_ast_for_python_file(tmp_path):
    py_file = tmp_path / "auth.py"
    py_file.write_text(
        "def login(user):\n    return True\n\n"
        "def logout(user):\n    return True\n"
    )
    ingestor = _make_ingestor(chunk_size=1000)
    stats = ingestor.ingest_file(py_file, "test")
    assert stats['chunks'] == 1
    call_args = ingestor.storage.insert_documents.call_args[0][0]
    assert len(call_args) == 1
    assert 'def login' in call_args[0].content
    assert 'def logout' in call_args[0].content


def test_ingestor_section_stored_in_metadata(tmp_path):
    py_file = tmp_path / "service.py"
    py_file.write_text("def process(data):\n    return data\n")
    ingestor = _make_ingestor()
    ingestor.ingest_file(py_file, "test")
    docs = ingestor.storage.insert_documents.call_args[0][0]
    assert docs[0].metadata == {"section": "process"}


def test_ingestor_falls_back_for_markdown(tmp_path):
    md_file = tmp_path / "README.md"
    content = "# Title\n\n" + "word " * 300 + "\n"
    md_file.write_text(content)
    ingestor = _make_ingestor(chunk_size=200)
    stats = ingestor.ingest_file(md_file, "test")
    assert stats['chunks'] > 1


def test_ingestor_falls_back_when_no_ast_nodes(tmp_path):
    py_file = tmp_path / "constants.py"
    py_file.write_text("X = 1\nY = 2\nZ = 3\n")
    ingestor = _make_ingestor(chunk_size=5)
    stats = ingestor.ingest_file(py_file, "test")
    assert stats['chunks'] >= 1

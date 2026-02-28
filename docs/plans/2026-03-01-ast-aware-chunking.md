# AST-Aware Chunking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Coeus's line-count chunker with a tree-sitter AST chunker for code files, so function and class bodies are never split across chunk boundaries.

**Architecture:** A new `core/ast_chunker.py` module wraps tree-sitter. It exposes one function: `chunk_by_ast(text, suffix, chunk_size) -> list[AstChunk]`. The existing `Ingestor._chunk_content` becomes the fallback for unsupported extensions (`.md`, `.json`, etc.). `Ingestor.ingest_file` dispatches to `chunk_by_ast` when the file extension is a known code language; if tree-sitter is not installed or returns no segments, it falls back gracefully. The `Chunk` class gains an optional `section` field (function/class name) which is stored in `Document.metadata`.

**Tech Stack:** `tree-sitter==0.25.2`, `tree-sitter-python`, `tree-sitter-go`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-rust` — all optional at runtime (ImportError → fallback).

---

## Task 1: Install tree-sitter and create `core/ast_chunker.py`

**Files:**
- Create: `core/ast_chunker.py`
- Create: `tests/test_ast_chunker.py`

**Step 1: Install tree-sitter packages**

```bash
cd /home/hung/Public/gits/coeus
source /home/hung/env/.venv/bin/activate
uv pip install tree-sitter tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript tree-sitter-rust
```

Expected output includes: `tree-sitter==0.25.2`, `tree-sitter-python==0.25.0`, `tree-sitter-go==0.25.0`, `tree-sitter-javascript==0.25.0`, `tree-sitter-typescript==0.23.2`, `tree-sitter-rust==0.24.0`

**Step 2: Write the failing tests**

```python
# tests/test_ast_chunker.py
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
```

**Step 3: Run to verify failure**

```bash
python -m pytest tests/test_ast_chunker.py -v
```

Expected: `ModuleNotFoundError: No module named 'core.ast_chunker'`

**Step 4: Implement `core/ast_chunker.py`**

```python
import importlib
from dataclasses import dataclass
from typing import Optional


@dataclass
class AstChunk:
    content: str
    start_line: int
    end_line: int
    section: Optional[str] = None


_GRAMMAR_MODULES = {
    '.py':  'tree_sitter_python',
    '.go':  'tree_sitter_go',
    '.js':  'tree_sitter_javascript',
    '.ts':  'tree_sitter_typescript',
    '.tsx': 'tree_sitter_typescript',
    '.rs':  'tree_sitter_rust',
}

_TOP_LEVEL_TYPES = {
    '.py':  {'function_definition', 'class_definition', 'decorated_definition'},
    '.go':  {'function_declaration', 'method_declaration', 'type_declaration'},
    '.js':  {'function_declaration', 'class_declaration', 'export_statement'},
    '.ts':  {'function_declaration', 'class_declaration', 'export_statement',
             'interface_declaration', 'type_alias_declaration'},
    '.tsx': {'function_declaration', 'class_declaration', 'export_statement',
             'interface_declaration'},
    '.rs':  {'function_item', 'struct_item', 'impl_item', 'enum_item', 'trait_item'},
}

_LANGUAGE_CACHE: dict = {}


def _get_language(suffix: str):
    if suffix in _LANGUAGE_CACHE:
        return _LANGUAGE_CACHE[suffix]
    module_name = _GRAMMAR_MODULES.get(suffix)
    if not module_name:
        _LANGUAGE_CACHE[suffix] = None
        return None
    try:
        from tree_sitter import Language
        mod = importlib.import_module(module_name)
        if suffix == '.tsx':
            lang = Language(mod.language_tsx())
        else:
            lang = Language(mod.language())
        _LANGUAGE_CACHE[suffix] = lang
        return lang
    except (ImportError, AttributeError):
        _LANGUAGE_CACHE[suffix] = None
        return None


def _node_name(node) -> Optional[str]:
    name_node = node.child_by_field_name('name')
    if name_node:
        return name_node.text.decode('utf-8', errors='replace')
    for child in node.children:
        if child.type in ('function_definition', 'class_definition',
                          'function_declaration', 'class_declaration',
                          'function_item', 'struct_item', 'impl_item',
                          'interface_declaration', 'type_alias_declaration'):
            return _node_name(child)
    return None


def chunk_by_ast(text: str, suffix: str, chunk_size: int) -> list:
    lang = _get_language(suffix)
    if lang is None:
        return []

    try:
        from tree_sitter import Parser
    except ImportError:
        return []

    node_types = _TOP_LEVEL_TYPES.get(suffix, set())
    parser = Parser(lang)
    tree = parser.parse(text.encode('utf-8', errors='replace'))
    lines = text.split('\n')

    segments = []
    for node in tree.root_node.children:
        if node.type in node_types:
            start = node.start_point[0]
            end = node.end_point[0]
            segments.append((start, end, _node_name(node)))

    if not segments:
        return []

    chunks = []
    pack_lines = []
    pack_start = segments[0][0]
    pack_end = segments[0][0]
    pack_section = segments[0][2]

    for start, end, name in segments:
        seg_lines = lines[start:end + 1]
        seg_text = '\n'.join(seg_lines)

        if pack_lines:
            combined = '\n'.join(pack_lines) + '\n' + seg_text
            if len(combined) > chunk_size:
                chunks.append(AstChunk(
                    content='\n'.join(pack_lines),
                    start_line=pack_start + 1,
                    end_line=pack_end + 1,
                    section=pack_section,
                ))
                pack_lines = seg_lines
                pack_start = start
                pack_end = end
                pack_section = name
            else:
                pack_lines.extend(seg_lines)
                pack_end = end
        else:
            pack_lines = seg_lines
            pack_start = start
            pack_end = end
            pack_section = name

    if pack_lines:
        chunks.append(AstChunk(
            content='\n'.join(pack_lines),
            start_line=pack_start + 1,
            end_line=pack_end + 1,
            section=pack_section,
        ))

    return chunks
```

**Step 5: Run tests — expect pass**

```bash
python -m pytest tests/test_ast_chunker.py -v
```

Expected: 10 passed

**Step 6: Commit**

```bash
git add core/ast_chunker.py tests/test_ast_chunker.py
git commit -m "feat: add AST-aware chunker using tree-sitter"
```

---

## Task 2: Wire AST chunker into `Ingestor`

**Files:**
- Modify: `core/ingestor.py` (lines 10-14, 42, 125-159)
- Modify: `tests/test_ast_chunker.py` (add integration tests)

**Step 1: Write failing integration tests**

Add these to the END of `tests/test_ast_chunker.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.ingestor import Ingestor, Chunk


def _make_ingestor(chunk_size=1000):
    storage = MagicMock()
    storage.is_file_indexed.return_value = False
    storage.insert_documents = MagicMock()
    storage.insert_entities = MagicMock()
    storage.mark_file_indexed = MagicMock()
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
    # Both small functions packed into 1 chunk
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
```

**Step 2: Run to verify failure**

```bash
python -m pytest tests/test_ast_chunker.py::test_ingestor_uses_ast_for_python_file -v
```

Expected: FAIL — `assert stats['chunks'] == 1` fails because currently line-count produces multiple chunks for two functions.

**Step 3: Modify `core/ingestor.py`**

Add `section: Optional[str] = None` to `Chunk`:

```python
class Chunk:
    def __init__(self, content: str, start_line: int, end_line: int,
                 section: Optional[str] = None):
        self.content = content
        self.start_line = start_line
        self.end_line = end_line
        self.section = section
```

Change the `from typing import` line to include `Optional` if not already present:
```python
from typing import List, Iterator, Dict, Any, Optional
```

Replace `ingest_file` — change the two lines that call `_chunk_content` (lines 42-43):

```python
        content = self._read_file(file_path)
        chunks = self._choose_chunker(file_path.suffix, content)
        extracted = self.extractor.extract(content)
```

Add `_choose_chunker` method after `_read_file`:

```python
    def _choose_chunker(self, suffix: str, text: str) -> List[Chunk]:
        try:
            from core.ast_chunker import chunk_by_ast, AstChunk
            ast_chunks = chunk_by_ast(text, suffix, self.chunk_size)
            if ast_chunks:
                return [
                    Chunk(c.content, c.start_line, c.end_line, c.section)
                    for c in ast_chunks
                ]
        except Exception:
            pass
        return self._chunk_content(text)
```

Update the `Document` construction in `ingest_file` to store section in metadata:

```python
            documents.append(Document(
                id=doc_id,
                content=chunk.content,
                source=str(file_path),
                project=project,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                metadata={"section": chunk.section} if chunk.section else None,
            ))
```

**Step 4: Run all tests**

```bash
python -m pytest tests/test_ast_chunker.py tests/test_setup.py -v
```

Expected: all pass (10 ast_chunker + 4 integration + 24 setup = 38 total)

**Step 5: Commit**

```bash
git add core/ingestor.py tests/test_ast_chunker.py
git commit -m "feat: wire AST chunker into ingestor with fallback to line-count"
```

---

## Task 3: Update dependency docs and `coeus setup`

**Files:**
- Modify: `CLAUDE.md` (add tree-sitter to optional deps)
- Modify: `core/setup.py` (add tree-sitter install hint to `cmd_setup` output? — no, that's in main.py)
- Modify: `docs/GUIDE.md` (mention AST chunking)

**Step 1: Update `CLAUDE.md`**

In the "Installation Dependencies" section, the existing list ends with:
```
- `pyyaml` (for VSCode Continue YAML config in setup)
```

Add after it:
```
- `tree-sitter` (AST-aware code chunking, optional)
- `tree-sitter-python`, `tree-sitter-go`, `tree-sitter-javascript`, `tree-sitter-typescript`, `tree-sitter-rust` (language grammars, optional)
```

In the dev setup command, add: `tree-sitter tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript tree-sitter-rust`

**Step 2: Add a note to `docs/GUIDE.md`**

Find the "File Extension Strategy" section and add above it:

```markdown
## AST-Aware Chunking

When tree-sitter is installed, Coeus chunks code files along function and class boundaries instead of arbitrary line counts. This ensures function bodies are never split across chunks, which significantly improves semantic search quality.

Install language support:

```bash
uv pip install tree-sitter tree-sitter-python tree-sitter-go tree-sitter-javascript tree-sitter-typescript tree-sitter-rust
```

Supported: Python, Go, JavaScript, TypeScript, Rust. Other file types use line-count chunking automatically.
```

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all pass

**Step 4: Commit**

```bash
git add CLAUDE.md docs/GUIDE.md
git commit -m "docs: document tree-sitter optional deps for AST chunking"
```

---

## Summary

| Task | Deliverable | Tests |
|------|-------------|-------|
| 1 | `core/ast_chunker.py` — 6 languages, packing, section names | 10 unit tests |
| 2 | `Ingestor._choose_chunker` + `Chunk.section` + metadata | 4 integration tests |
| 3 | `CLAUDE.md` + `docs/GUIDE.md` updated | — |

**Run all tests at any point:**
```bash
cd /home/hung/Public/gits/coeus
source /home/hung/env/.venv/bin/activate
python -m pytest tests/ -v
```

**Key behaviors to verify manually after implementation:**
```bash
# Ingest a Python file and check chunk boundaries
python main.py ingest /home/hung/Public/gits/coeus/core/ingestor.py --project coeus
python main.py stats

# Verify chunks align with functions (search for a known function name)
python main.py search "chunk_content" --method fts
```

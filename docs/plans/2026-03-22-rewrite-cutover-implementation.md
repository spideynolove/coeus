# Rewrite Cutover Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current `coeus` repo contents with the rewrite architecture and remove the legacy runtime surface from the active tree.

**Architecture:** Treat `/home/hung/Documents/spideynolove/coeus-rewrite` as the source of truth for active runtime code, tests, and current docs, but do not carry its legacy compatibility scaffolding forward. The target repo keeps only the rewrite `coeus/` package, thin CLI/MCP adapters, rewrite fixtures/tests/docs, and a small `docs/archive/legacy-coeus/` trail for superseded material.

**Tech Stack:** Python 3.10+, setuptools, pytest, local filesystem artifact store, MCP.

---

### Task 1: Add Cutover Regression Coverage

**Files:**
- Create: `tests/test_cutover_layout.py`

**Step 1: Write the failing test**

Write tests that assert:
- legacy runtime files and directories are absent from the active tree
- the active package exposes `coeus/interfaces/cli.py` and `coeus/interfaces/mcp.py`
- archived legacy docs exist under `docs/archive/legacy-coeus/`
- active docs mention `coeus run`, `coeus show-run`, `coeus list-runs`
- removed legacy tests are absent

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cutover_layout.py -q`
Expected: FAIL because the current repo still contains legacy runtime files and stale docs/tests.

**Step 3: Commit**

```bash
git add tests/test_cutover_layout.py
git commit -m "test: add rewrite cutover layout coverage"
```

### Task 2: Copy Rewrite Runtime Into The Active Repo

**Files:**
- Create: `coeus/`
- Create: `tests/fixtures/`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: Copy only the active rewrite runtime**

Copy from `/home/hung/Documents/spideynolove/coeus-rewrite/`:
- `coeus/`
- rewrite `README.md`
- rewrite `CLAUDE.md`
- rewrite `pyproject.toml`
- rewrite fixture-backed tests

Do not copy:
- `main.py`
- `mcp_server.py`
- `config.py`
- `embedders.py`
- `core/`
- `storage/`
- `watcher/`
- temporary artifact directories

**Step 2: Trim packaging to the rewrite only**

Update `pyproject.toml` so package discovery and `py-modules` no longer reference legacy runtime modules or directories.

**Step 3: Run focused tests**

Run: `python -m pytest tests/test_cutover_layout.py tests/test_rewrite_interfaces.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add coeus pyproject.toml README.md CLAUDE.md tests
git commit -m "feat: cut active repo over to rewrite runtime"
```

### Task 3: Delete Legacy Runtime And Misleading Tests

**Files:**
- Delete: `main.py`
- Delete: `mcp_server.py`
- Delete: `config.py`
- Delete: `embedders.py`
- Delete: `core/`
- Delete: `storage/`
- Delete: `watcher/`
- Delete: `tests/test_ast_chunker.py`
- Delete: `tests/test_setup.py`

**Step 1: Remove legacy runtime from the active repo**

Delete all runnable legacy modules and directories listed above.

**Step 2: Remove tests that only validate deleted architecture**

Delete the legacy tests if they are not rewritten to target the new runtime.

**Step 3: Run focused tests**

Run: `python -m pytest tests/test_cutover_layout.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: remove legacy runtime surface"
```

### Task 4: Archive Legacy Guidance

**Files:**
- Create: `docs/archive/legacy-coeus/`
- Move: superseded legacy docs from repo root and `docs/`

**Step 1: Move stale legacy docs into an explicit archive**

Archive:
- superseded root docs as needed
- legacy plans that describe setup/onboarding or AST chunker work for the old runtime
- stale architecture/evaluation notes that are not current for the rewrite
- old quickstart/guide material tied to the deleted command surface

**Step 2: Add a small archive marker**

Ensure the archive path makes it obvious the material is pre-rewrite and non-authoritative.

**Step 3: Run focused tests**

Run: `python -m pytest tests/test_cutover_layout.py -q`
Expected: PASS

**Step 4: Commit**

```bash
git add docs
git commit -m "docs: archive legacy coeus guidance"
```

### Task 5: Verify End-To-End

**Files:**
- Verify only

**Step 1: Run the rewrite test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS

**Step 2: Verify installable entrypoints**

Run a small import/CLI smoke test against:
- `coeus.interfaces.cli`
- `coeus.interfaces.mcp`

Expected: imports succeed and package scripts point to rewrite adapters.

**Step 3: Inspect git status**

Run: `git status --short`
Expected: only intended cutover changes remain.

**Step 4: Commit**

```bash
git add -A
git commit -m "chore: complete rewrite cutover"
```

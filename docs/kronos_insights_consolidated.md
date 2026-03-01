# Kronos Insights - Consolidated Reference

**Date:** 2026-02-28  
**Purpose:** Analysis and redesign blueprint for Kronos v1.0

---

## Part 1: Executive Summary

### What is Kronos?

Kronos is a **local semantic memory system** for AI agents providing:
- Long-term memory for codebases
- Deep project context understanding
- **83-98% token reduction** vs traditional RAG via "Pointer-based" approach
- **5-50x cost savings** on LLM API calls

### Core Value Proposition

```
Traditional RAG:          Kronos Pointers:
15,000 tokens/query       300 tokens/query
$0.021/query              $0.00042/query
                          
Savings: 98% fewer tokens, 50x cheaper
```

---

## Part 2: Current Architecture Analysis

### 2.1 Current Stack (Messy)

```
Kronos/
├── Root clutter (37+ files)      # Tests, scripts, experiments scattered
├── PowerShell/Batch (9 files)    # Windows-only scripts
├── src/                          # Main code
│   ├── modules/
│   │   ├── oracle.py            # Search orchestrator
│   │   ├── librarian.py         # Data layer (SQLite + ChromaDB)
│   │   ├── ingestor.py          # File ingestion
│   │   ├── context_budgeter.py  # Token management
│   │   ├── job_manager.py       # Async queue
│   │   ├── watcher.py           # File monitoring
│   │   └── ... (12+ modules)
│   ├── cli.py                   # Typer CLI
│   ├── server.py                # FastAPI
│   ├── mcp_server.py            # MCP (stdio/SSE)
│   └── locales/strings.py       # i18n (187 lines)
└── requirements.txt             # 18 dependencies
```

### 2.2 Key Problems Identified

| Problem | Impact | Solution |
|---------|--------|----------|
| Single-branch dev, no cleanup | 37 root clutter files | Delete 40+ files |
| Windows-specific code (`msvcrt`) | 150 lines of platform-specific code | Remove, use `fcntl` |
| Dual databases (SQLite + ChromaDB) | Complexity, backup issues | Unified zvec |
| Over-engineered i18n | 187 lines for EN/HR only | Remove, inline English |
| Typer + FastAPI + Rich | 6+ unnecessary deps | argparse only |
| Typer CLI | Heavy dependency | argparse (stdlib) |
| Comment language mix | Croatian + English | Standardize English |
| Dead code | Unreachable code in librarian.py | Delete |

### 2.3 Windows Code to Remove

**File: `src/utils/file_helper.py`** (lines 8-18, 73-122)
```python
# REMOVE: Windows-specific msvcrt imports
try:
    import msvcrt          # ← Windows-only
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

# REMOVE: Windows file locking
if HAS_MSVCRT:
    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
```

**File: `src/mcp_server.py`** (lines 21-55)
```python
# REMOVE: Windows stdout hijacking
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
sys.stdout = OutputDetector()
```

**File: `src/server.py`** (lines 626-653)
```python
# REMOVE: Windows process killing
subprocess.run(['netstat', '-ano'])      # Windows command
subprocess.run(['taskkill', '/F', '/PID', pid])  # Windows
```

---

## Part 3: The Librarian Mechanism

### Current Data Layer

The **Librarian** manages 4 storage backends:

```sql
-- 1. SQLite: files table (change tracking)
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    project TEXT,
    last_modified REAL,
    processed_at TEXT
);

-- 2. SQLite: FTS5 (keyword search)
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    path, project, content, stemmed_content,
    start_line UNINDEXED, end_line UNINDEXED
);

-- 3. SQLite: entities (structured knowledge)
CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    type TEXT,           -- 'decision', 'task', 'problem', 'solution'
    content TEXT,
    valid_from TEXT,     -- Temporal validity
    valid_to TEXT,
    superseded_by TEXT,  -- Decision versioning
    created_at TEXT
);

-- 4. ChromaDB: vectors (separate process)
# Collection: "kronos_memory"
# 768-dim embeddings, cosine similarity
```

### Problems with Current Design

1. **Two databases** to manage (SQLite + ChromaDB)
2. **No SQL JOINs** between metadata and vectors
3. **ChromaDB** requires C++ build tools
4. **Backup** requires two locations

---

## Part 4: v1.0 Design Principles

### 4.1 Clean Architecture Goals

```
┌─────────────────────────────────────────────────────────────┐
│  1. SINGLE DATABASE          zvec (SQLite + vectors)        │
│  2. INTERFACE SEGREGATION    StorageInterface, Embedder     │
│  3. DEPENDENCY INJECTION     No globals, wired in main      │
│  4. NO WINDOWS CODE          Linux/Mac native (fcntl)       │
│  5. MINIMAL DEPS             8 core dependencies            │
│  6. CLEAN CODE               Type hints, no dead code       │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 New Architecture

```
Entry Points:
  CLI (argparse) → Application Layer → Infrastructure Layer
  
Application Layer:
  ├─ Ingestor    (chunk, extract, embed)
  ├─ Oracle      (hybrid search)
  └─ Budgeter    (token assembly)

Domain Layer:
  ├─ Extractor   (decisions, tasks, problems)
  ├─ FastPath    (exact/prefix cache)
  └─ Types       (Pointer, Chunk, Entity)

Infrastructure Layer:
  ├─ ZvecStore   (SQLite + FTS5 + vectors)
  ├─ Embedder    (Voyage AI / OpenRouter)
  └─ LLM         (OpenRouter / Ollama / GLM)
```

### 4.3 zvec Storage Schema

```sql
-- Single database: kronos.db

CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    embedding BLOB,              -- Serialized numpy array
    source TEXT NOT NULL,        -- File path
    project TEXT DEFAULT 'default',
    start_line INTEGER DEFAULT 1,
    end_line INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- FTS5 for text search
CREATE VIRTUAL TABLE docs_fts USING fts5(
    content,
    content='documents',
    content_rowid='rowid'
);

-- Triggers keep FTS in sync
CREATE TRIGGER docs_ai AFTER INSERT ON documents BEGIN
    INSERT INTO docs_fts(rowid, content) VALUES (new.rowid, new.content);
END;

CREATE TABLE entities (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,          -- 'decision', 'task', 'problem', 'solution'
    content TEXT NOT NULL,
    file_path TEXT NOT NULL,
    project TEXT DEFAULT 'default',
    valid_from TEXT,
    valid_to TEXT,
    superseded_by INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE files (
    path TEXT PRIMARY KEY,       -- For change detection
    project TEXT,
    last_modified REAL,
    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 Interface Definitions

```python
# Storage Interface
class StorageInterface(ABC):
    def insert_documents(self, docs: List[Document]) -> None: ...
    def search_vector(self, embedding, limit=10) -> List[SearchResult]: ...
    def search_fts(self, query, limit=10) -> List[SearchResult]: ...
    def search_hybrid(self, embedding, query, limit=10) -> List[SearchResult]: ...

# Embedder Interface
class Embedder(ABC):
    @property
    def dimension(self) -> int: ...
    def embed(self, texts: List[str]) -> List[List[float]]: ...

# LLM Interface
class LLM(ABC):
    def complete(self, prompt: str) -> str: ...
```

---

## Part 5: Implementation Details

### 5.1 Unified Embedder Module

```python
# embedders.py - Voyage AI + OpenRouter (no local!)

class VoyageAIEmbedder(Embedder):
    DIMENSION = 1024  # voyage-3
    def __init__(self, api_key: str, model: str = "voyage-3")

class OpenRouterEmbedder(Embedder):
    DIMENSION = 1536  # text-embedding-3-small
    def __init__(self, api_key: str, model: str = "openai/text-embedding-3-small")

def create_embedder(provider: str, api_key: Optional[str] = None) -> Embedder
```

### 5.2 Unified LLM Module

```python
# llms.py - OpenRouter + Ollama + GLM

class OpenRouterLLM(LLM):
    # Multi-provider cloud access
    def complete(self, prompt: str, model: Optional[str] = None) -> str

class OllamaLLM(LLM):
    # Local LLM server
    def complete(self, prompt: str) -> str

class GLMLLM(LLM):
    # Chinese-optimized
    def complete(self, prompt: str) -> str

def create_llm(provider: str, api_key: Optional[str] = None) -> LLM
```

### 5.3 CLI Commands (argparse)

```bash
kronos ingest <path> [--recursive] [--project NAME]
kronos ask "query" [--project NAME] [--mode light|auto|extra]
kronos search "query" [--method vector|fts|hybrid] [--json]
kronos stats [--json]
kronos watch <path> [--debounce 5.0]
kronos config [--init]
kronos job {list|status}
```

---

## Part 6: Migration Roadmap

### Phase 1: Cleanup (Delete)

| Target | Count | Action |
|--------|-------|--------|
| Root test files | 10 | Delete |
| PowerShell scripts | 9 | Delete |
| Windows code | 150 lines | Remove |
| i18n system | 187 lines | Delete |
| Unused deps | 10 | Remove from requirements |
| Dead code | ~500 lines | Delete |

**Result:** ~40 files removed, ~2,000 lines deleted

### Phase 2: Restructure

```
kronos-v1/
├── src/
│   ├── __init__.py
│   ├── main.py              # argparse CLI
│   ├── config.py            # Environment config
│   ├── embedders.py         # Voyage + OpenRouter
│   ├── llms.py              # OpenRouter + Ollama + GLM
│   ├── core/
│   │   ├── ingestor.py
│   │   ├── oracle.py
│   │   ├── budgeter.py
│   │   ├── extractor.py
│   │   └── fastpath.py
│   ├── storage/
│   │   ├── interface.py
│   │   └── zvec_store.py
│   ├── async/
│   │   └── watcher.py
│   └── utils/
│       ├── file_io.py       # Linux/Mac only
│       └── stemmer.py
├── tests/
└── pyproject.toml           # 8 deps only
```

### Phase 3: Dependencies

**Before (18 deps):**
```
fastapi, uvicorn, python-dotenv, mcp, chromadb
sentence-transformers, langchain, openai, google-genai
typer, rich, watchdog, sqlite-utils, colorama
tqdm, pytest, httpx, tenacity
```

**After (8 deps):**
```
numpy                    # Vector operations
voyageai                 # Embeddings (primary)
watchdog                 # File monitoring
python-dotenv            # Config
tenacity                 # Retries
mcp                      # IDE integration
requests                 # HTTP (OpenRouter, Ollama)
pytest                   # Testing
```

---

## Part 7: Configuration

### Environment Variables

```bash
# Required (choose one)
export VOYAGE_API_KEY="pa-xxx"          # For Voyage AI embeddings
export OPENROUTER_API_KEY="sk-or-xxx"   # For OpenRouter embeddings/LLM

# Optional
export KRONOS_DATA="~/.kronos"
export KRONOS_EMBED_MODEL="voyage-3"
export KRONOS_LLM_MODEL="anthropic/claude-3.5-sonnet"
export KRONOS_CHUNK_SIZE="1000"
export KRONOS_BUDGET="4000"
```

### Config File (~/.kronos/.env)

```bash
VOYAGE_API_KEY=pa-xxxxxxxx
OPENROUTER_API_KEY=sk-or-xxxxxxxx
KRONOS_EMBED_MODEL=voyage-3
KRONOS_LLM_MODEL=anthropic/claude-3.5-sonnet
```

---

## Part 8: Comparison Summary

| Metric | Current | v1.0 Target | Change |
|--------|---------|-------------|--------|
| Python files | ~80 | ~19 | -76% |
| Lines of code | ~8,000 | ~2,500 | -69% |
| Dependencies | 18 | 8 | -56% |
| Windows code | 150+ lines | 0 | -100% |
| Databases | 2 (SQLite + ChromaDB) | 1 (zvec) | Unified |
| CLI framework | Typer | argparse | Simpler |
| i18n | 187 lines | 0 | Removed |

---

## Quick Reference

### Why Remove Local Embeddings?

- **sentence-transformers:** 80MB download, 384MB RAM, slower, inferior quality
- **Voyage AI:** Better quality, instant (you already have API key)
- **OpenRouter:** Flexible fallback

### Why zvec over ChromaDB?

- Single file (kronos.db) vs directory
- Native SQL JOINs
- No C++ build tools
- Simpler backup

### Why argparse over Typer?

- One less dependency
- Standard library
- Sufficient for CLI needs
- Faster import

### File Diversity Cap

ContextBudgeter limits to **3 chunks per file** to ensure diverse sources in context window.

### Token Budgets

| Mode | Tokens | Use Case |
|------|--------|----------|
| light | 2,000 | Quick queries |
| auto | 4,000 | Default |
| extra | 8,000 | Complex analysis |

---

*End of consolidated insights*

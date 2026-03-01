import os
import sys
import builtins
import contextlib
import io
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

ROOT_DIR = Path(__file__).parent

_real_stdout = sys.stdout
_real_stderr = sys.stderr
_real_print = builtins.print
_original_stdout_fd = os.dup(sys.stdout.fileno())


def mcp_safe_print(*args, **kwargs):
    kwargs['file'] = _real_stderr
    _real_print(*args, **kwargs)


builtins.print = mcp_safe_print


class OutputDetector:
    def write(self, text):
        if text.strip():
            _real_stderr.write(f"\n[STDOUT LEAK]: {repr(text)}\n")
            _real_stderr.flush()
        return len(text)

    def flush(self):
        _real_stderr.flush()

    def fileno(self):
        return 1


os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
sys.stdout = OutputDetector()

load_dotenv()

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import get_config
from core.oracle import Oracle
from core.budgeter import ContextBudgeter
from storage.zvec_store import ZvecStore
from embedders import create_embedder

_oracle = None
_oracle_ready = False
_oracle_error = None

import threading
_oracle_init_event = threading.Event()


def _init_oracle_background():
    global _oracle, _oracle_ready, _oracle_error
    try:
        config = get_config()
        embedder = create_embedder(
            provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
            model=config.embedding_model
        )
        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)
        _oracle = Oracle(storage, embedder)
        _oracle_ready = True
    except Exception as e:
        _oracle_error = str(e)
    finally:
        _oracle_init_event.set()


threading.Thread(target=_init_oracle_background, daemon=True).start()


def get_oracle():
    global _oracle
    if not _oracle_ready:
        _oracle_init_event.wait(timeout=30)
    if _oracle_error:
        raise RuntimeError(f"Oracle init failed: {_oracle_error}")
    if _oracle is None:
        raise RuntimeError("Oracle init timeout (30s)")
    return _oracle


mcp = FastMCP("coeus")


@mcp.tool()
def coeus_ping() -> str:
    return "🏓 pong! Coeus MCP server is alive."


@mcp.tool()
def coeus_reinit_oracle() -> str:
    global _oracle, _oracle_ready, _oracle_error, _oracle_init_event

    _oracle_ready = False
    _oracle_error = None
    _oracle_init_event = threading.Event()

    threading.Thread(target=_init_oracle_background, daemon=True).start()

    _oracle_init_event.wait(timeout=10)

    if _oracle_ready:
        return "✅ Oracle successfully reinitialized and ready!"
    elif _oracle_error:
        return f"❌ Error during reinitialization: {_oracle_error}"
    else:
        return "⏳ Reinitialization taking longer than expected (background). Check status in 10 seconds."


@mcp.tool()
def coeus_query(query: str, mode: str = "auto", client_model: str = "claude-3.5-sonnet") -> str:
    try:
        if not _oracle_ready:
            remaining = 30
            _oracle_init_event.wait(timeout=remaining)
            if not _oracle_ready:
                err = _oracle_error or "Unknown error (init timeout)"
                return f"❌ Oracle initialization failed: {err}. Try calling 'coeus_reinit_oracle' or restart Coeus server."

        oracle = get_oracle()

        limit = 30
        budget = 4000

        if mode == "light":
            limit = 15
            budget = 2000
        elif mode == "extra":
            limit = 60
            budget = 8000
        else:
            limit = 30
            budget = 4000

        budgeter = ContextBudgeter(budget)

        result = oracle.ask(query, None, limit)

        if not result.entities and not result.chunks:
            return f"No results found for query: {query}"

        context = budgeter.assemble(result)

        return context

    except Exception as e:
        return f"Error in coeus_query: {str(e)}"


@mcp.tool()
def coeus_search(query: str, project: str = None, limit: int = 5) -> str:
    try:
        oracle = get_oracle()
        result = oracle.ask(query, project, limit)

        if not result.entities and not result.chunks:
            return f"No results found for: '{query}'"

        output = [f"## Search Results for: {query}\n"]

        all_items = []
        for entity in result.entities:
            all_items.append(('entity', entity))
        for chunk in result.chunks:
            all_items.append(('chunk', chunk))

        for i, (item_type, item) in enumerate(all_items[:limit], 1):
            if item_type == 'entity':
                content = item.content
                source = item.file_path
                proj = item.project
                score = 1.0
            else:
                content = item.document.content
                source = item.document.source
                proj = item.document.project
                score = item.score

            source_name = Path(source).name if source else 'Unknown'
            relevance = round(score * 100, 1) if score else 0

            output.append(f"### Result {i} [{item_type.upper()}] (Relevance: {relevance}%)")
            output.append(f"**Source:** `{source_name}` | **Project:** {proj}\n")
            output.append(f"```\n{content[:500]}{'...' if len(content) > 500 else ''}\n```\n")

        return "\n".join(output)

    except Exception as e:
        return f"Error during search: {str(e)}"


@mcp.tool()
def coeus_stats() -> str:
    try:
        config = get_config()
        storage = ZvecStore(str(config.db_path))
        stats = storage.get_stats()

        output = [f"## 📊 Database Statistics\n"]
        output.append(f"| Metric | Value |")
        output.append(f"|---------|------------|")
        output.append(f"| **Documents** | {stats.get('total_documents', 0):,} |")
        output.append(f"| **Entities** | {stats.get('total_entities', 0):,} |")
        output.append(f"| **Projects** | {stats.get('project_count', 0)} |")
        output.append(f"| **Database Size** | {stats.get('db_size_mb', 0):.2f} MB |")
        output.append(f"| **Database Path** | {stats.get('db_path', 'N/A')} |")

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving statistics: {str(e)}"


@mcp.tool()
def coeus_ingest(path: str, recursive: bool = True) -> str:
    try:
        from core.ingestor import Ingestor

        config = get_config()
        embedder = create_embedder(
            provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
            model=config.embedding_model
        )
        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)
        ingestor = Ingestor(storage, embedder)

        full_path = Path(path).expanduser().resolve()
        if not full_path.exists():
            return f"Path does not exist: {full_path}"

        if full_path.is_file():
            result = ingestor.ingest_file(full_path, full_path.name)
            return f"✅ Indexed: `{full_path}` ({result['chunks']} chunks, {result['entities']} entities)"
        else:
            total_chunks = 0
            total_entities = 0

            for result in ingestor.ingest_directory(full_path, None, None, recursive):
                if 'error' not in result:
                    total_chunks += result.get('chunks', 0)
                    total_entities += result.get('entities', 0)

            return f"✅ Indexed: `{full_path}` (recursive={recursive})\nTotal: {total_chunks} chunks, {total_entities} entities"

    except Exception as e:
        return f"Error during ingestion: {str(e)}"


@mcp.tool()
def coeus_decisions(project: str = None) -> str:
    try:
        config = get_config()
        storage = ZvecStore(str(config.db_path))
        decisions = storage.get_active_decisions(project=project)

        if not decisions:
            filter_msg = f" for project '{project}'" if project else ""
            return f"No active decisions{filter_msg}."

        output = [f"## Active Decisions ({len(decisions)})\n"]

        for i, dec in enumerate(decisions, 1):
            content = dec['content']
            v_from = dec.get('valid_from') or 'N/A'
            v_to = dec.get('valid_to') or 'N/A'
            source = Path(dec['file_path']).name if dec.get('file_path') else 'Unknown'

            output.append(f"### {i}. {content[:100]}{'...' if len(content) > 100 else ''}")
            output.append(f"- **Valid:** {v_from} → {v_to}")
            output.append(f"- **Source:** `{source}`\n")

        return "\n".join(output)

    except Exception as e:
        return f"Error retrieving decisions: {str(e)}"


COEUS_SSE_PORT = int(os.environ.get("COEUS_PORT", "8765"))


def main():
    import logging
    import argparse

    parser = argparse.ArgumentParser(description="Coeus MCP Server")
    parser.add_argument("--sse", action="store_true", help="Run in SSE (HTTP) mode for multi-agent access")
    parser.add_argument("--port", type=int, default=COEUS_SSE_PORT, help=f"Port for SSE server (default: {COEUS_SSE_PORT})")
    args, _ = parser.parse_known_args()

    transport_mode = "sse" if args.sse else "stdio"

    logging.basicConfig(
        level=logging.INFO,
        format='[MCP Server] %(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )

    mcp_logger = logging.getLogger("coeus_mcp")
    mcp_logger.info(f"🚀 Coeus MCP Server starting... (transport: {transport_mode})")
    mcp_logger.info(f"📂 Root dir: {ROOT_DIR}")

    try:
        if transport_mode == "sse":
            mcp_logger.info(f"🌐 Starting SSE server on http://0.0.0.0:{args.port}")
            mcp_logger.info(f"📡 Clients connect to: http://localhost:{args.port}/sse")

            os.dup2(_original_stdout_fd, 1)
            sys.stdout = _real_stdout

            mcp.settings.host = "0.0.0.0"
            mcp.settings.port = args.port

            class HostRewriteMiddleware:
                def __init__(self, app):
                    self.app = app

                async def __call__(self, scope, receive, send):
                    if scope["type"] in ("http", "websocket"):
                        headers = list(scope.get("headers", []))
                        new_headers = []
                        for name, value in headers:
                            if name == b"host":
                                port = value.decode().split(":")[-1] if b":" in value else "8765"
                                new_headers.append((b"host", f"localhost:{port}".encode()))
                            else:
                                new_headers.append((name, value))
                        scope = dict(scope, headers=new_headers)
                    await self.app(scope, receive, send)

            import uvicorn
            _orig_config_init = uvicorn.Config.__init__

            def _patched_config_init(self_cfg, app, *a, **kw):
                wrapped = HostRewriteMiddleware(app)
                _orig_config_init(self_cfg, wrapped, *a, **kw)

            uvicorn.Config.__init__ = _patched_config_init
            mcp_logger.info("🛡️ HostRewriteMiddleware activated (Docker compatible)")

            mcp.run(transport="sse")
        else:
            mcp_logger.info("💬 Starting MCP stdio server...")

            os.dup2(_original_stdout_fd, 1)
            sys.stdout = _real_stdout

            mcp.run(transport="stdio")

    except KeyboardInterrupt:
        mcp_logger.info("⚠️ Server interrupted by user")
    except Exception as e:
        mcp_logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

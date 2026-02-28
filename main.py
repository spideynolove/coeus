#!/usr/bin/env python3

import argparse
import sys
import textwrap
from pathlib import Path
from typing import List, Optional

from __init__ import __version__
from config import get_config, Config


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coeus",
        description="Coeus - Semantic Memory System for AI Agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Getting Started:
              coeus setup               # one-time setup, auto-detects tools
              coeus ingest ./my-project --recursive
              coeus ask "how does auth work?"

            Examples:
              coeus ingest ./my-project --recursive
              coeus ask "How does authentication work?"
              coeus search "database connection" --limit 5
              coeus stats
              coeus watch ./src --project my-app

            Environment Variables:
              VOYAGE_API_KEY        API key for Voyage AI embeddings
              OPENROUTER_API_KEY    API key for OpenRouter LLM access
              COEUS_DATA            Data directory (default: ~/.coeus)
              COEUS_EMBED_MODEL     Embedding model (voyage-3, openai/text-embedding-3-small)
              COEUS_LLM_MODEL       LLM model for chat
        """)
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--data-dir",
        type=Path,
        help="Override data directory"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Index files and directories",
        description="Ingest files into the knowledge base."
    )
    ingest_parser.add_argument(
        "path",
        type=Path,
        help="File or directory to ingest"
    )
    ingest_parser.add_argument(
        "-p", "--project",
        help="Project name (default: directory name)"
    )
    ingest_parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="Recursively process subdirectories"
    )
    ingest_parser.add_argument(
        "--extensions",
        default=".py,.md,.js,.ts,.tsx,.json,.txt",
        help="Comma-separated list of file extensions to process"
    )
    ingest_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be ingested without indexing"
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Query the knowledge base",
        description="Ask a natural language question about your codebase."
    )
    ask_parser.add_argument(
        "query",
        help="Question to ask"
    )
    ask_parser.add_argument(
        "-p", "--project",
        help="Limit search to specific project"
    )
    ask_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)"
    )
    ask_parser.add_argument(
        "--mode",
        choices=["light", "auto", "extra"],
        default="auto",
        help="Context mode: light (2k tokens), auto (4k), extra (8k)"
    )
    ask_parser.add_argument(
        "--show-pointers",
        action="store_true",
        help="Show pointer references instead of full content"
    )

    search_parser = subparsers.add_parser(
        "search",
        help="Raw search (for debugging)",
        description="Perform raw search without context assembly."
    )
    search_parser.add_argument(
        "query",
        help="Search query"
    )
    search_parser.add_argument(
        "-p", "--project",
        help="Limit to project"
    )
    search_parser.add_argument(
        "-n", "--limit",
        type=int,
        default=10,
        help="Maximum results"
    )
    search_parser.add_argument(
        "--method",
        choices=["vector", "fts", "hybrid"],
        default="hybrid",
        help="Search method"
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    stats_parser = subparsers.add_parser(
        "stats",
        help="Show database statistics",
        description="Display information about indexed data."
    )
    stats_parser.add_argument(
        "--project",
        help="Show stats for specific project"
    )
    stats_parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    watch_parser = subparsers.add_parser(
        "watch",
        help="Monitor files for changes",
        description="Watch directory and auto-index changed files."
    )
    watch_parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Directory to watch (default: current directory)"
    )
    watch_parser.add_argument(
        "-p", "--project",
        help="Project name"
    )
    watch_parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        default=True,
        help="Watch subdirectories"
    )
    watch_parser.add_argument(
        "--debounce",
        type=float,
        default=5.0,
        help="Debounce interval in seconds (default: 5)"
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Show configuration",
        description="Display current configuration."
    )
    config_parser.add_argument(
        "--init",
        action="store_true",
        help="Create initial configuration file"
    )

    job_parser = subparsers.add_parser(
        "job",
        help="Job queue management",
        description="Manage background indexing jobs."
    )
    job_subparsers = job_parser.add_subparsers(dest="job_command")

    job_list = job_subparsers.add_parser("list", help="List jobs")
    job_list.add_argument("-n", "--limit", type=int, default=10)

    job_status = job_subparsers.add_parser("status", help="Check job status")
    job_status.add_argument("job_id", help="Job ID")

    setup_parser = subparsers.add_parser(
        "setup",
        help="Configure Coeus and register with coding tools",
        description="One-time setup: API keys, MCP registration, skill files."
    )
    setup_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Use environment variables only, no prompts"
    )
    setup_parser.add_argument(
        "--tools",
        nargs="+",
        choices=["claude-code", "cursor", "vscode-continue", "windsurf", "opencode"],
        help="Register only specific tools (default: all detected)"
    )

    return parser


def cmd_ingest(args: argparse.Namespace, config: Config) -> int:
    from core.ingestor import Ingestor
    from storage.zvec_store import ZvecStore
    from embedders import create_embedder

    path = args.path.expanduser().resolve()

    if not path.exists():
        print(f"Error: Path does not exist: {path}", file=sys.stderr)
        return 1

    project = args.project or path.name
    extensions = [e.strip() for e in args.extensions.split(",")]

    if args.dry_run:
        print(f"Would ingest: {path}")
        print(f"Project: {project}")
        print(f"Recursive: {args.recursive}")
        print(f"Extensions: {extensions}")
        return 0

    try:
        try:
            embedder = create_embedder(
                provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
                model=config.embedding_model
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)
        ingestor = Ingestor(storage, embedder)

        print(f"Indexing: {path}")
        print(f"Project: {project}")
        print()

        if path.is_file():
            stats = ingestor.ingest_file(path, project)
            print(f"Indexed: {stats['chunks']} chunks, {stats['entities']} entities")
        else:
            total_chunks = 0
            total_entities = 0

            for result in ingestor.ingest_directory(
                path, project, extensions, args.recursive
            ):
                if "error" in result:
                    print(f"  ✗ {result['file']}: {result['error']}")
                else:
                    marker = "✓" if result['status'] == 'indexed' else "○"
                    print(f"  {marker} {result['file']}: "
                          f"{result['chunks']} chunks, {result['entities']} entities")
                    total_chunks += result['chunks']
                    total_entities += result['entities']

            print()
            print(f"Total: {total_chunks} chunks, {total_entities} entities")

        storage.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_ask(args: argparse.Namespace, config: Config) -> int:
    from core.oracle import Oracle
    from core.budgeter import ContextBudgeter
    from storage.zvec_store import ZvecStore
    from embedders import create_embedder

    try:
        try:
            embedder = create_embedder(
                provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
                model=config.embedding_model
            )
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)
        oracle = Oracle(storage, embedder)

        budgets = {"light": 2000, "auto": 4000, "extra": 8000}
        budget = budgets.get(args.mode, 4000)
        budgeter = ContextBudgeter(budget)

        print(f"Query: {args.query}")
        print(f"Project: {args.project or 'all'}")
        print()

        result = oracle.ask(args.query, args.project, args.limit)

        if result.entities:
            print("Entities:")
            for entity in result.entities:
                print(f"  [{entity.type.upper()}] {entity.content[:80]}...")
            print()

        if args.show_pointers:
            print("Pointers:")
            for ptr in result.pointers:
                print(f"  📍 {ptr.file_path}:{ptr.line_start}-{ptr.line_end}")
                print(f"     Section: {ptr.section}")
        else:
            context = budgeter.assemble(result)
            print(context)

        storage.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_search(args: argparse.Namespace, config: Config) -> int:
    import json as json_module
    from storage.zvec_store import ZvecStore
    from embedders import create_embedder

    try:
        embedder = create_embedder(
            provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
            model=config.embedding_model
        )
        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)

        if args.method == "vector":
            embedding = embedder.embed_query(args.query)
            results = storage.search_vector(embedding, args.limit, args.project)
        elif args.method == "fts":
            results = storage.search_fts(args.query, args.limit, args.project)
        else:
            embedding = embedder.embed_query(args.query)
            results = storage.search_hybrid(embedding, args.query, args.limit, args.project)

        if args.json:
            output = [
                {
                    "content": r.document.content[:200],
                    "source": r.document.source,
                    "score": r.score,
                    "method": r.method
                }
                for r in results
            ]
            print(json_module.dumps(output, indent=2))
        else:
            print(f"Results ({args.method}):")
            for i, r in enumerate(results, 1):
                print(f"\n{i}. [{r.method}] Score: {r.score:.3f}")
                print(f"   Source: {r.document.source}")
                print(f"   Content: {r.document.content[:150]}...")

        storage.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_stats(args: argparse.Namespace, config: Config) -> int:
    import json as json_module
    from storage.zvec_store import ZvecStore

    try:
        storage = ZvecStore(str(config.db_path))
        stats = storage.get_stats()

        if args.json:
            print(json_module.dumps(stats, indent=2))
        else:
            print("Database Statistics")
            print("=" * 40)
            print(f"Documents:   {stats.get('total_documents', 0):,}")
            print(f"Entities:    {stats.get('total_entities', 0):,}")
            print(f"Projects:    {stats.get('project_count', 0)}")
            print(f"Database:    {config.db_path}")
            print(f"Size:        {stats.get('db_size_mb', 0):.2f} MB")

        storage.close()
        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_watch(args: argparse.Namespace, config: Config) -> int:
    from watcher.watcher import Watcher
    from core.ingestor import Ingestor
    from storage.zvec_store import ZvecStore
    from embedders import create_embedder

    try:
        embedder = create_embedder(
            provider="voyage" if config.embedding_model.startswith("voyage") else "openrouter",
            model=config.embedding_model
        )
        storage = ZvecStore(str(config.db_path), vector_dimension=embedder.dimension)
        ingestor = Ingestor(storage, embedder)

        def callback(files: set):
            for file_path in files:
                try:
                    stats = ingestor.ingest_file(file_path, args.project or "default")
                    print(f"  ✓ {file_path}: {stats['chunks']} chunks")
                except Exception as e:
                    print(f"  ✗ {file_path}: {e}")

        watcher = Watcher(args.path, callback, args.recursive, args.debounce)

        print(f"Watching: {args.path}")
        print(f"Project: {args.project or 'auto-detect'}")
        print(f"Debounce: {args.debounce}s")
        print()
        print("Press Ctrl+C to stop")

        watcher.run()

        return 0
    except ImportError:
        print("Error: watchdog required. Install: pip install watchdog", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_config(args: argparse.Namespace, config: Config) -> int:
    if args.init:
        config_path = config.data_dir / ".env"
        if config_path.exists():
            print(f"Configuration already exists: {config_path}")
            return 0

        example = """# Coeus Configuration
VOYAGE_API_KEY=your_voyage_key_here
OPENROUTER_API_KEY=your_openrouter_key_here

# Optional settings
# COEUS_EMBED_MODEL=voyage-3
# COEUS_LLM_MODEL=anthropic/claude-3.5-sonnet
# COEUS_CHUNK_SIZE=1000
"""
        config_path.write_text(example)
        print(f"Created configuration file: {config_path}")
        print("Edit this file to add your API keys")
        return 0

    print("Current Configuration")
    print("=" * 40)
    print(f"Data directory:    {config.data_dir}")
    print(f"Database:          {config.db_path}")
    print(f"Embedding model:   {config.embedding_model}")
    print(f"LLM model:         {config.llm_model}")
    print(f"Chunk size:        {config.chunk_size}")
    print(f"Context budget:    {config.context_budget}")
    print()

    valid, errors = config.is_valid()
    if valid:
        print("Status: ✓ Valid")
    else:
        print("Status: ✗ Invalid")
        for error in errors:
            print(f"  - {error}")

    return 0


def cmd_job(args: argparse.Namespace, config: Config) -> int:
    if not hasattr(args, 'job_command') or args.job_command is None:
        print("Usage: coeus job {list|status}")
        return 1

    from core.job_manager import JobManager

    try:
        jm = JobManager(str(config.db_path))

        if args.job_command == "list":
            jobs = jm.list_jobs(limit=args.limit)

            if not jobs:
                print("No jobs found.")
                return 0

            print("## Recent Jobs\n")
            print("| ID | Type | Status | Progress | Created |")
            print("|----|-----|--------|----------|----------|")

            for job in jobs:
                short_id = job['id'][:8]
                created = job['created_at'].split('T')[1][:8] if 'T' in job['created_at'] else job['created_at'][-8:]
                print(f"| `{short_id}` | `{job['type']}` | `{job['status']}` | `{job['progress']}%` | {created} |")

        elif args.job_command == "status":
            job = jm.get_job(args.job_id)

            if not job:
                print(f"Job with ID `{args.job_id}` not found.")
                return 1

            print(f"## Job Status: `{args.job_id}`")
            print(f"- **Type:** `{job['type']}`")
            print(f"- **Status:** `{job['status']}`")
            print(f"- **Progress:** `{job['progress']}%`")
            print(f"- **Created:** `{job['created_at']}`")

            if job.get('result'):
                print(f"\n**Result:**\n```json\n{job['result']}\n```")
            if job.get('error'):
                print(f"\n**Error:**\n```\n{job['error']}\n```")

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_setup(args: argparse.Namespace, config: Config) -> int:
    from core.setup import (
        detect_tools, collect_api_keys, write_env_file,
        register_cursor, register_windsurf, register_vscode_continue,
        register_opencode, register_claude_code,
        TOOL_CLAUDE_CODE, TOOL_CURSOR, TOOL_VSCODE_CONTINUE,
        TOOL_WINDSURF, TOOL_OPENCODE,
    )

    print("Coeus Setup")
    print("=" * 40)

    print("\nStep 1: API Keys")
    keys = collect_api_keys(interactive=not args.non_interactive)

    if not keys.get("voyage") and not keys.get("openrouter"):
        print("  No API keys found. Run 'coeus setup' again after setting:")
        print("    export VOYAGE_API_KEY=your_key")
        print("    export OPENROUTER_API_KEY=your_key")
        return 1

    env_path = config.data_dir / ".env"
    write_env_file(keys, env_path)
    print(f"  ✓ Saved to {env_path}")

    print("\nStep 2: Detecting installed tools...")
    tools = args.tools or detect_tools()

    if not tools:
        print("  No supported tools detected.")
        print("  Supported: Claude Code, Cursor, VSCode+Continue, Windsurf, OpenCode")
    for tool in tools:
        print(f"  ✓ {tool}")

    mcp_path = str(Path(__file__).parent / "mcp_server.py")
    python_path = sys.executable

    print("\nStep 3: Registering with tools...")
    registrations = {
        TOOL_CLAUDE_CODE: lambda: register_claude_code(mcp_path, python_path),
        TOOL_CURSOR: lambda: register_cursor(mcp_path, python_path),
        TOOL_VSCODE_CONTINUE: lambda: register_vscode_continue(mcp_path, python_path),
        TOOL_WINDSURF: lambda: register_windsurf(mcp_path, python_path),
        TOOL_OPENCODE: lambda: register_opencode(mcp_path, python_path),
    }

    for tool in tools:
        if tool in registrations:
            try:
                registrations[tool]()
                print(f"  ✓ {tool}")
            except Exception as e:
                print(f"  ✗ {tool}: {e}")

    print("\nStep 4: Verifying connection...")
    try:
        from embedders import create_embedder
        from config import reset_config
        reset_config()
        cfg = get_config()
        provider = "voyage" if cfg.embedding_model.startswith("voyage") else "openrouter"
        embedder = create_embedder(provider, model=cfg.embedding_model)
        embedder.embed(["coeus setup test"])
        print(f"  ✓ Embedder OK ({cfg.embedding_model}, {embedder.dimension} dims)")
    except Exception as e:
        print(f"  ✗ Embedder failed: {e}")
        print("    Check your API key in ~/.coeus/.env")
        return 1

    print("\nSetup complete!")
    print("\nNext steps:")
    print("  coeus ingest /path/to/your/project --recursive")
    print("  coeus ask 'what does this project do'")
    return 0


def main(args: Optional[List[str]] = None) -> int:
    parser = create_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.command is None:
        parser.print_help()
        return 0

    config = get_config()

    if parsed_args.data_dir:
        from config import reset_config
        import os
        os.environ["COEUS_DATA"] = str(parsed_args.data_dir)
        reset_config()
        config = get_config()

    commands = {
        "ingest": cmd_ingest,
        "ask": cmd_ask,
        "search": cmd_search,
        "stats": cmd_stats,
        "watch": cmd_watch,
        "config": cmd_config,
        "job": cmd_job,
        "setup": cmd_setup,
    }

    handler = commands.get(parsed_args.command)
    if handler:
        return handler(parsed_args, config)
    else:
        print(f"Unknown command: {parsed_args.command}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

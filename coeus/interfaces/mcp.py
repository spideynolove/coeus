import argparse
from mcp.server.fastmcp import FastMCP
from coeus.interfaces.common import list_runs, load_run_summary, run_spec

def build_server() -> FastMCP:
    server = FastMCP('coeus')

    @server.tool()
    def run_experiment(spec_path: str, artifacts_dir: str='artifacts') -> dict:
        return run_spec(spec_path, artifacts_dir)

    @server.tool()
    def get_run_summary(run_id: str, artifacts_dir: str='artifacts') -> dict:
        return load_run_summary(run_id, artifacts_dir)

    @server.tool()
    def get_runs(artifacts_dir: str='artifacts', spec_id: str | None=None, status: str | None=None) -> list[dict]:
        return list_runs(artifacts_dir, spec_id, status)
    return server

def main() -> None:
    parser = argparse.ArgumentParser(prog='coeus-mcp')
    parser.add_argument('--transport', choices=['stdio', 'sse'], default='stdio')
    (parsed, _) = parser.parse_known_args()
    build_server().run(transport=parsed.transport)

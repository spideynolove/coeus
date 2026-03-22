import argparse
from typing import Optional
from coeus.interfaces.common import list_runs, load_run_summary, run_spec, to_json

def main(args: Optional[list[str]]=None) -> int:
    parser = argparse.ArgumentParser(prog='coeus')
    subparsers = parser.add_subparsers(dest='command', required=True)
    run_parser = subparsers.add_parser('run')
    run_parser.add_argument('spec_path')
    run_parser.add_argument('--artifacts-dir', default='artifacts')
    show_parser = subparsers.add_parser('show-run')
    show_parser.add_argument('run_id')
    show_parser.add_argument('--artifacts-dir', default='artifacts')
    list_parser = subparsers.add_parser('list-runs')
    list_parser.add_argument('--artifacts-dir', default='artifacts')
    list_parser.add_argument('--spec-id')
    list_parser.add_argument('--status')
    parsed = parser.parse_args(args)
    if parsed.command == 'run':
        print(to_json(run_spec(parsed.spec_path, parsed.artifacts_dir)))
        return 0
    if parsed.command == 'show-run':
        print(to_json(load_run_summary(parsed.run_id, parsed.artifacts_dir)))
        return 0
    print(to_json(list_runs(parsed.artifacts_dir, parsed.spec_id, parsed.status)))
    return 0

from pathlib import Path
from typing import Optional


def expand_chunk(source: str, start_line: int, end_line: int, context_lines: int = 3) -> Optional[str]:
    path = Path(source)
    if not path.exists():
        return None
    try:
        lines = path.read_text(errors='replace').splitlines()
        lo = max(0, start_line - 1 - context_lines)
        hi = min(len(lines), end_line + context_lines)
        return '\n'.join(lines[lo:hi])
    except Exception:
        return None

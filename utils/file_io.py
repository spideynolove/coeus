import fcntl
from pathlib import Path
from typing import Dict, Any, Optional


def read_file_safe(
    file_path: Path,
    start_line: int = 1,
    end_line: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except (IOError, OSError):
                pass

            lines = f.readlines()

            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except:
                pass

        idx_start = max(0, start_line - 1)
        idx_end = end_line if end_line else len(lines)
        idx_end = min(idx_end, len(lines))

        if idx_start >= len(lines):
            return {
                'error': 'range_exceeds_file',
                'message': f'File has {len(lines)} lines, requested {start_line}'
            }

        content = ''.join(lines[idx_start:idx_end])

        return {
            'content': content,
            'lines_read': idx_end - idx_start,
            'status': 'success'
        }

    except FileNotFoundError:
        return {
            'error': 'file_not_found',
            'message': f'File does not exist: {file_path}'
        }
    except PermissionError:
        return {
            'error': 'permission_denied',
            'message': f'No permission to read: {file_path}'
        }
    except Exception as e:
        return {
            'error': 'unknown_error',
            'message': str(e)
        }

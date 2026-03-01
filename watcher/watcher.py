from pathlib import Path
from typing import Optional, Set, Callable
import threading
import time

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class CoeusEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        callback: Callable[[Set[str]], None],
        debounce_interval: float = 5.0
    ):
        self.callback = callback
        self.debounce_interval = debounce_interval
        self.pending_files: Set[str] = set()
        self.timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()

    def on_modified(self, event):
        if self._is_relevant(event):
            self._add_file(event.src_path)

    def on_created(self, event):
        if self._is_relevant(event):
            self._add_file(event.src_path)

    def _is_relevant(self, event) -> bool:
        if event.is_directory:
            return False

        path = Path(event.src_path)

        if path.suffix not in ['.py', '.md', '.js', '.ts', '.tsx', '.json', '.txt']:
            return False

        if any(p.startswith('.') for p in path.parts):
            return False

        return True

    def _add_file(self, file_path: str):
        with self.lock:
            self.pending_files.add(file_path)

            if self.timer:
                self.timer.cancel()

            self.timer = threading.Timer(
                self.debounce_interval,
                self._flush
            )
            self.timer.start()

    def _flush(self):
        with self.lock:
            files = self.pending_files.copy()
            self.pending_files.clear()
            self.timer = None

        if files:
            self.callback(files)


class Watcher:
    def __init__(
        self,
        path: Path,
        callback: Callable[[Set[str]], None],
        recursive: bool = True,
        debounce: float = 5.0
    ):
        if not WATCHDOG_AVAILABLE:
            raise ImportError("watchdog required. Install: pip install watchdog")

        self.path = Path(path)
        self.callback = callback
        self.recursive = recursive
        self.debounce = debounce

        self.handler = CoeusEventHandler(callback, debounce)
        self.observer = None

    def start(self):
        self.observer = Observer()
        self.observer.schedule(
            self.handler,
            str(self.path),
            recursive=self.recursive
        )
        self.observer.start()

    def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def run(self):
        self.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

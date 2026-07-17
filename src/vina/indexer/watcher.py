from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Generator, Optional

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
# Import the formal typing base class to satisfy static analysis
from watchdog.observers.api import BaseObserver

from .runner import delete_file, process_file

# Configure structured logging
logger = logging.getLogger(__name__)


class VinaEventHandler(FileSystemEventHandler):
    """
    Thread-safe event handler that debounces rapid filesystem events on a per-file basis.
    Prevents duplicate processing caused by atomic writes (e.g., VS Code, MS Word).
    """

    def __init__(self, debounce_interval_seconds: float = 0.5) -> None:
        super().__init__()
        self.debounce_interval = debounce_interval_seconds
        self._lock = threading.Lock()
        # Maps absolute file paths to their active debouncing timers
        self._timers: Dict[str, threading.Timer] = {}

    def _get_clean_path(self, os_path: str) -> str:
        """
        Normalizes paths across platforms. Uses strict=False because resolving 
        a deleted file path with strict=True can raise a FileNotFoundError.
        """
        return Path(os_path).resolve(strict=False).as_posix()

    def _debounce_process(self, filepath: str, is_delete: bool = False) -> None:
        """
        Schedules or reschedules an execution task for a specific filepath.
        Guarantees thread safety via a mutual exclusion lock.
        """
        with self._lock:
            # Cancel any existing timer running for this specific file
            if filepath in self._timers:
                self._timers[filepath].cancel()

            # Schedule the final event state execution
            timer = threading.Timer(
                self.debounce_interval,
                self._execute_and_clear,
                args=(filepath, is_delete),
            )
            self._timers[filepath] = timer
            timer.start()

    def _execute_and_clear(self, filepath: str, is_delete: bool) -> None:
        """Executes core runner logic and cleanly evicts the timer from memory."""
        try:
            if is_delete:
                logger.debug("Executing deletion pipeline for: %s", filepath)
                delete_file(filepath)
            else:
                logger.debug("Executing processing pipeline for: %s", filepath)
                process_file(filepath)
        except Exception:
            logger.exception("Pipeline failure for filesystem target: %s", filepath)
        finally:
            # Safely evict the timer from memory under lock parameters once completed
            with self._lock:
                self._timers.pop(filepath, None)

    def stop_all_timers(self) -> None:
        """Gracefully cancels all pending background tasks during observer teardown."""
        with self._lock:
            for timer in self._timers.values():
                timer.cancel()
            self._timers.clear()
            logger.info("All pending event timers successfully drained.")

    # --- Watchdog Event Dispatches ---

    def on_modified(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._debounce_process(self._get_clean_path(event.src_path))

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._debounce_process(self._get_clean_path(event.src_path))

    def on_deleted(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._debounce_process(self._get_clean_path(event.src_path), is_delete=True)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        old_path = self._get_clean_path(event.src_path)
        new_path = self._get_clean_path(event.dest_path)

        # Atomically un-schedule tasks for the old location and cue up the new target
        self._debounce_process(old_path, is_delete=True)
        self._debounce_process(new_path)


@contextmanager
def file_watcher_scope(target_folder: str) -> Generator[BaseObserver, None, None]:
    """
    Context manager ensuring deterministic resource allocation and deallocation
    for the filesystem Observer and its underlying threads.
    """
    path_target = Path(target_folder).resolve(strict=False)
    if not path_target.exists():
        raise FileNotFoundError(f"Target monitoring path does not exist: {path_target}")

    event_handler = VinaEventHandler()
    # At runtime, we still instantiate via the dynamic backend factory
    observer = Observer()
    
    observer.schedule(event_handler, str(path_target), recursive=True)
    observer.start()
    logger.info("Watcher engine initialized. Tracking changes in: %s", path_target)

    try:
        yield observer
    finally:
        logger.info("Stopping watcher engine, cleaning up resources...")
        observer.stop()
        event_handler.stop_all_timers()
        observer.join()
        logger.info("Watcher engine cleanly terminated.")
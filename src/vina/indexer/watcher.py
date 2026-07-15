import threading
import logging
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .runner import process_file, delete_file

logger = logging.getLogger(__name__)

#Github Copilot Really Messed the File, so i modified this File Again...... and i have to Test this Vina.exe for 1 Week to see if it works and monitorr bugs..
class VinaEventHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        self._timer = None
        self._lock = threading.Lock()

    def _debounce_process(self, filepath: str, is_delete: bool = False):
        """
        Debounce rapid filesystem events (e.g. Word/VS Code save)
        so we only process the final event.
        """
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(
                0.5,
                self._execute,
                args=(filepath, is_delete),
            )
            self._timer.start()

    def _execute(self, filepath: str, is_delete: bool):
        try:
            if is_delete:
                delete_file(filepath)
            else:
                process_file(filepath)
        except Exception:
            logger.exception("Failed processing filesystem event for %s", filepath)

    def on_modified(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path).resolve().as_posix()
        self._debounce_process(filepath)

    def on_created(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path).resolve().as_posix()
        self._debounce_process(filepath)

    def on_deleted(self, event):
        if event.is_directory:
            return

        filepath = Path(event.src_path).resolve().as_posix()
        self._debounce_process(filepath, is_delete=True)

    def on_moved(self, event):
        if event.is_directory:
            return

        old_path = Path(event.src_path).resolve().as_posix()
        new_path = Path(event.dest_path).resolve().as_posix()

        self._debounce_process(old_path, is_delete=True)
        self._debounce_process(new_path)


def start_watcher(target_folder: str):
    """Starts the filesystem watcher."""

    event_handler = VinaEventHandler()

    observer = Observer()
    observer.schedule(event_handler, target_folder, recursive=True)
    observer.start()

    logger.info(
        "Watcher started. Monitoring '%s' for changes...",
        target_folder,
    )

    return observer
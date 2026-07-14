# src/vina/indexer/watcher.py
import time
import threading
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
from .runner import process_file, delete_file

logger = logging.getLogger(__name__)

class VinaEventHandler(FileSystemEventHandler):
    # ... (keep the rest of the class exactly the same)
    def on_modified(self, event):
        if not event.is_directory:
            filepath = Path(event.src_path).resolve().as_posix()
            self._debounce_process(filepath)

    def on_created(self, event):
        if not event.is_directory:
            filepath = Path(event.src_path).resolve().as_posix()
            self._debounce_process(filepath)

    def on_deleted(self, event):
        if not event.is_directory:
            filepath = Path(event.src_path).resolve().as_posix()
            self._debounce_process(filepath, is_delete=True)

    def on_moved(self, event):
        if not event.is_directory:
            old_filepath = Path(event.src_path).resolve().as_posix()
            new_filepath = Path(event.dest_path).resolve().as_posix()
            self._debounce_process(old_filepath, is_delete=True)
            self._debounce_process(new_filepath)

def start_watcher(target_folder: str):
    """Starts the background file system watcher."""
    event_handler = VinaEventHandler()
    observer = Observer()
    observer.schedule(event_handler, target_folder, recursive=True)
    observer.start()
    logger.info("Watcher started. Monitoring '%s' for changes...", target_folder)
    return observer
"""
File watcher module for detecting new files in specified directories.
"""

import logging
import os
import time
from pathlib import Path
from threading import Event
from typing import Callable, List, Optional, Set

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class FileWatcherHandler(FileSystemEventHandler):
    """Handler for file system events."""
    
    def __init__(self, on_new_file: Callable[[str], None], watched_extensions: Optional[Set[str]] = None):
        """
        Initialize the file watcher handler.
        
        Args:
            on_new_file: Callback function to call when a new file is detected
            watched_extensions: Set of file extensions to watch (e.g., {'.txt', '.pdf'})
                               If None, watches all files
        """
        self.on_new_file = on_new_file
        self.watched_extensions = watched_extensions
        self.logger = logging.getLogger(__name__)
        
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
            
        file_path = event.src_path
        
        # Check file extension if filtering is enabled
        if self.watched_extensions:
            file_extension = Path(file_path).suffix.lower()
            if file_extension not in self.watched_extensions:
                return
                
        # Wait briefly to ensure file is completely written
        self._wait_for_stable_file(file_path)
        
        self.logger.info(f"New file detected: {file_path}")
        self.on_new_file(file_path)
        
    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file move events (treat as new file in destination)."""
        if event.is_directory:
            return
            
        dest_path = event.dest_path
        
        # Check file extension if filtering is enabled
        if self.watched_extensions:
            file_extension = Path(dest_path).suffix.lower()
            if file_extension not in self.watched_extensions:
                return
                
        self._wait_for_stable_file(dest_path)
        
        self.logger.info(f"File moved to watched location: {dest_path}")
        self.on_new_file(dest_path)
        
    def _wait_for_stable_file(self, file_path: str, max_wait: int = 10) -> None:
        """
        Wait for file to be stable (no size changes) before processing.
        
        Args:
            file_path: Path to the file to monitor
            max_wait: Maximum seconds to wait for stability
        """
        if not os.path.exists(file_path):
            return
            
        previous_size = -1
        wait_time = 0
        
        while wait_time < max_wait:
            try:
                current_size = os.path.getsize(file_path)
                if current_size == previous_size and current_size > 0:
                    break
                previous_size = current_size
                time.sleep(0.5)
                wait_time += 0.5
            except OSError:
                # File might be temporarily locked
                time.sleep(0.5)
                wait_time += 0.5


class FileWatcher:
    """Main file watcher class."""
    
    def __init__(self, watch_directories: List[str], on_new_file: Callable[[str], None],
                 watched_extensions: Optional[Set[str]] = None):
        """
        Initialize the file watcher.
        
        Args:
            watch_directories: List of directory paths to monitor
            on_new_file: Callback function to call when new files are detected
            watched_extensions: Set of file extensions to watch (optional)
        """
        self.watch_directories = watch_directories
        self.on_new_file = on_new_file
        self.watched_extensions = watched_extensions
        self.observer = Observer()
        self.is_running = Event()
        self.logger = logging.getLogger(__name__)
        
    def start(self) -> None:
        """Start monitoring the specified directories."""
        handler = FileWatcherHandler(self.on_new_file, self.watched_extensions)
        
        for directory in self.watch_directories:
            if not os.path.exists(directory):
                self.logger.warning(f"Watch directory does not exist: {directory}")
                continue
                
            self.logger.info(f"Starting to watch directory: {directory}")
            self.observer.schedule(handler, directory, recursive=True)
            
        self.observer.start()
        self.is_running.set()
        self.logger.info("File watcher started")
        
    def stop(self) -> None:
        """Stop monitoring directories."""
        if self.is_running.is_set():
            self.observer.stop()
            self.observer.join()
            self.is_running.clear()
            self.logger.info("File watcher stopped")
            
    def wait(self) -> None:
        """Wait for the file watcher to be stopped."""
        try:
            while self.is_running.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
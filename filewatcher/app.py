"""
Main application for file watching, SFTP transfer, and S3 upload coordination.
"""

import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from queue import Queue
from typing import Dict, List, Optional

from .file_watcher import FileWatcher
from .s3_uploader import S3Uploader, S3Config
from .sftp_manager import SFTPManager, SFTPConfig


class FileProcessorApp:
    """Main application coordinating file watching, SFTP, and S3 operations."""
    
    def __init__(self, config_dict: dict):
        """
        Initialize the application.
        
        Args:
            config_dict: Configuration dictionary
        """
        self.config = config_dict
        self.logger = self._setup_logging()
        
        # Initialize components
        self.file_watcher: Optional[FileWatcher] = None
        self.s3_uploader: Optional[S3Uploader] = None
        self.sftp_manager: Optional[SFTPManager] = None
        
        # Processing queue and control
        self.file_queue = Queue()
        self.shutdown_event = threading.Event()
        self.processing_thread: Optional[threading.Thread] = None
        
        # Track ongoing operations
        self.active_uploads: Dict[str, Future] = {}
        self.processed_files: set = set()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup application logging."""
        log_level = self.config.get('logging', {}).get('level', 'INFO')
        log_format = self.config.get('logging', {}).get('format', 
                                                       '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        logging.basicConfig(level=getattr(logging, log_level), format=log_format)
        return logging.getLogger(__name__)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        self.logger.info(f"Received signal {signum}, initiating shutdown...")
        self.shutdown()
        
    def initialize(self) -> bool:
        """Initialize all components."""
        try:
            # Initialize S3 uploader
            s3_config = self._create_s3_config()
            if s3_config:
                self.s3_uploader = S3Uploader(s3_config)
                self.logger.info("S3 uploader initialized")
            else:
                self.logger.warning("S3 configuration not provided, S3 uploads disabled")
                
            # Initialize SFTP manager if configured
            sftp_configs = self._create_sftp_configs()
            if sftp_configs:
                max_transfers = self.config.get('sftp', {}).get('max_concurrent_transfers', 5)
                self.sftp_manager = SFTPManager(sftp_configs, max_transfers)
                self.logger.info(f"SFTP manager initialized with {len(sftp_configs)} servers")
            else:
                self.logger.warning("SFTP configuration not provided, SFTP transfers disabled")
                
            # Initialize file watcher
            watch_dirs = self.config.get('file_watcher', {}).get('watch_directories', [])
            if not watch_dirs:
                self.logger.error("No watch directories specified")
                return False
                
            # Create watch directories if they don't exist
            for directory in watch_dirs:
                os.makedirs(directory, exist_ok=True)
                
            extensions = self.config.get('file_watcher', {}).get('watched_extensions')
            if extensions:
                extensions = set(ext.lower() for ext in extensions)
                
            self.file_watcher = FileWatcher(watch_dirs, self._on_new_file, extensions)
            self.logger.info(f"File watcher initialized for directories: {watch_dirs}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize application: {e}")
            return False
            
    def _create_s3_config(self) -> Optional[S3Config]:
        """Create S3 configuration from config dict."""
        s3_config = self.config.get('s3')
        if not s3_config:
            return None
            
        return S3Config(
            bucket_name=s3_config.get('bucket_name', ''),
            aws_access_key_id=s3_config.get('aws_access_key_id', ''),
            aws_secret_access_key=s3_config.get('aws_secret_access_key', ''),
            aws_session_token=s3_config.get('aws_session_token', ''),
            region_name=s3_config.get('region_name', 'us-east-1'),
            endpoint_url=s3_config.get('endpoint_url', ''),
            multipart_threshold=s3_config.get('multipart_threshold', 100 * 1024 * 1024),
            multipart_chunksize=s3_config.get('multipart_chunksize', 10 * 1024 * 1024),
            max_concurrency=s3_config.get('max_concurrency', 10)
        )
        
    def _create_sftp_configs(self) -> List[SFTPConfig]:
        """Create SFTP configurations from config dict."""
        sftp_configs = []
        sftp_servers = self.config.get('sftp', {}).get('servers', [])
        
        for server_config in sftp_servers:
            config = SFTPConfig(
                hostname=server_config.get('hostname', ''),
                port=server_config.get('port', 22),
                username=server_config.get('username', ''),
                password=server_config.get('password', ''),
                private_key_path=server_config.get('private_key_path', ''),
                timeout=server_config.get('timeout', 30)
            )
            sftp_configs.append(config)
            
        return sftp_configs
        
    def _on_new_file(self, file_path: str) -> None:
        """Handle new file detection."""
        if file_path not in self.processed_files:
            self.logger.info(f"Queueing new file for processing: {file_path}")
            self.file_queue.put(file_path)
            
    def start(self) -> None:
        """Start the application."""
        if not self.initialize():
            self.logger.error("Failed to initialize application")
            return
            
        self.logger.info("Starting file processor application")
        
        # Start processing thread
        self.processing_thread = threading.Thread(target=self._process_files, daemon=True)
        self.processing_thread.start()
        
        # Start file watcher
        if self.file_watcher:
            self.file_watcher.start()
            
        # Main loop
        try:
            while not self.shutdown_event.is_set():
                self._cleanup_completed_uploads()
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()
            
    def _process_files(self) -> None:
        """Process files from the queue."""
        while not self.shutdown_event.is_set():
            try:
                # Get file from queue with timeout
                try:
                    file_path = self.file_queue.get(timeout=1)
                except:
                    continue
                    
                if file_path in self.processed_files:
                    continue
                    
                self.logger.info(f"Processing file: {file_path}")
                
                # Process the file
                success = self._process_single_file(file_path)
                
                if success:
                    self.processed_files.add(file_path)
                    self.logger.info(f"File processing initiated: {file_path}")
                else:
                    self.logger.error(f"Failed to process file: {file_path}")
                    
                self.file_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in file processing thread: {e}")
                
    def _process_single_file(self, file_path: str) -> bool:
        """Process a single file (SFTP and/or S3 upload)."""
        success = True
        
        try:
            # SFTP transfer
            if self.sftp_manager:
                remote_path = self._get_remote_path(file_path)
                future = self.sftp_manager.upload_file(file_path, remote_path)
                self.active_uploads[f"sftp_{file_path}"] = future
                self.logger.info(f"SFTP upload queued: {file_path}")
                
            # S3 upload
            if self.s3_uploader:
                s3_key = self._get_s3_key(file_path)
                metadata = self._get_file_metadata(file_path)
                
                def progress_callback(bytes_transferred):
                    self.logger.debug(f"S3 upload progress for {file_path}: {bytes_transferred} bytes")
                    
                future = self.s3_uploader.executor.submit(
                    self.s3_uploader.upload_file, file_path, s3_key, progress_callback, metadata
                )
                self.active_uploads[f"s3_{file_path}"] = future
                self.logger.info(f"S3 upload queued: {file_path}")
                
        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {e}")
            success = False
            
        return success
        
    def _get_remote_path(self, file_path: str) -> str:
        """Generate remote path for SFTP upload."""
        filename = os.path.basename(file_path)
        remote_dir = self.config.get('sftp', {}).get('remote_directory', '/uploads')
        return f"{remote_dir}/{filename}"
        
    def _get_s3_key(self, file_path: str) -> str:
        """Generate S3 key for upload."""
        filename = os.path.basename(file_path)
        prefix = self.config.get('s3', {}).get('key_prefix', 'uploads')
        return f"{prefix}/{filename}"
        
    def _get_file_metadata(self, file_path: str) -> Dict[str, str]:
        """Generate metadata for file upload."""
        stat = os.stat(file_path)
        return {
            'original-path': file_path,
            'file-size': str(stat.st_size),
            'upload-timestamp': str(int(time.time()))
        }
        
    def _cleanup_completed_uploads(self) -> None:
        """Clean up completed upload futures."""
        completed_keys = []
        
        for key, future in self.active_uploads.items():
            if future.done():
                try:
                    result = future.result()
                    if result:
                        self.logger.info(f"Upload completed successfully: {key}")
                    else:
                        self.logger.error(f"Upload failed: {key}")
                except Exception as e:
                    self.logger.error(f"Upload failed with exception {key}: {e}")
                    
                completed_keys.append(key)
                
        for key in completed_keys:
            self.active_uploads.pop(key, None)
            
    def shutdown(self) -> None:
        """Shutdown the application gracefully."""
        self.logger.info("Shutting down application...")
        
        # Signal shutdown
        self.shutdown_event.set()
        
        # Stop file watcher
        if self.file_watcher:
            self.file_watcher.stop()
            
        # Wait for processing thread
        if self.processing_thread:
            self.processing_thread.join(timeout=5)
            
        # Wait for pending uploads
        self.logger.info("Waiting for pending uploads to complete...")
        for key, future in self.active_uploads.items():
            try:
                future.result(timeout=30)
            except Exception as e:
                self.logger.error(f"Upload {key} failed during shutdown: {e}")
                
        # Shutdown components
        if self.sftp_manager:
            self.sftp_manager.shutdown()
            
        if self.s3_uploader:
            self.s3_uploader.shutdown()
            
        self.logger.info("Application shutdown complete")
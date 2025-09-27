"""
SFTP manager for handling multiple concurrent SFTP file transfers.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable

import paramiko


@dataclass
class SFTPConfig:
    """Configuration for SFTP connection."""
    hostname: str
    port: int = 22
    username: str = ""
    password: str = ""
    private_key_path: str = ""
    timeout: int = 30


class SFTPSession:
    """Manages a single SFTP connection."""
    
    def __init__(self, config: SFTPConfig):
        """Initialize SFTP session with configuration."""
        self.config = config
        self.client: Optional[paramiko.SSHClient] = None
        self.sftp: Optional[paramiko.SFTPClient] = None
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        Establish SFTP connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare connection parameters
            connect_kwargs = {
                'hostname': self.config.hostname,
                'port': self.config.port,
                'timeout': self.config.timeout
            }
            
            # Authentication
            if self.config.private_key_path and os.path.exists(self.config.private_key_path):
                connect_kwargs['key_filename'] = self.config.private_key_path
            elif self.config.username and self.config.password:
                connect_kwargs['username'] = self.config.username
                connect_kwargs['password'] = self.config.password
            else:
                self.logger.error("No valid authentication method provided")
                return False
                
            if 'key_filename' not in connect_kwargs and self.config.username:
                connect_kwargs['username'] = self.config.username
                
            self.client.connect(**connect_kwargs)
            self.sftp = self.client.open_sftp()
            
            self.logger.info(f"SFTP connection established to {self.config.hostname}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to SFTP server {self.config.hostname}: {e}")
            self.disconnect()
            return False
            
    def disconnect(self) -> None:
        """Close SFTP connection."""
        try:
            if self.sftp:
                self.sftp.close()
                self.sftp = None
            if self.client:
                self.client.close()
                self.client = None
        except Exception as e:
            self.logger.error(f"Error during SFTP disconnect: {e}")
            
    def upload_file(self, local_path: str, remote_path: str,
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> bool:
        """
        Upload a file via SFTP.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
            progress_callback: Optional callback for upload progress (bytes_transferred, total_bytes)
            
        Returns:
            True if upload successful, False otherwise
        """
        if not self.sftp:
            self.logger.error("SFTP connection not established")
            return False
            
        try:
            # Ensure remote directory exists
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                self._ensure_remote_directory(remote_dir)
                
            # Upload the file
            self.logger.info(f"Uploading {local_path} to {self.config.hostname}:{remote_path}")
            
            if progress_callback:
                self.sftp.put(local_path, remote_path, callback=progress_callback)
            else:
                self.sftp.put(local_path, remote_path)
                
            self.logger.info(f"Successfully uploaded {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to upload {local_path}: {e}")
            return False
            
    def _ensure_remote_directory(self, remote_path: str) -> None:
        """Ensure remote directory exists, creating if necessary."""
        try:
            self.sftp.chdir(remote_path)
        except IOError:
            # Directory doesn't exist, try to create it
            try:
                self.sftp.mkdir(remote_path)
                self.logger.info(f"Created remote directory: {remote_path}")
            except IOError as e:
                self.logger.warning(f"Could not create remote directory {remote_path}: {e}")


class SFTPManager:
    """Manages multiple SFTP sessions for concurrent file transfers."""
    
    def __init__(self, sftp_configs: List[SFTPConfig], max_concurrent_transfers: int = 5):
        """
        Initialize SFTP manager.
        
        Args:
            sftp_configs: List of SFTP server configurations
            max_concurrent_transfers: Maximum number of concurrent transfers
        """
        self.sftp_configs = sftp_configs
        self.max_concurrent_transfers = max_concurrent_transfers
        self.executor = ThreadPoolExecutor(max_workers=max_concurrent_transfers)
        self.active_sessions: Dict[str, SFTPSession] = {}
        self.logger = logging.getLogger(__name__)
        
    def upload_file(self, local_path: str, remote_path: str,
                   server_index: int = 0,
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> Future:
        """
        Upload a file to specified SFTP server.
        
        Args:
            local_path: Local file path
            remote_path: Remote file path
            server_index: Index of SFTP server to use
            progress_callback: Optional progress callback
            
        Returns:
            Future object for the upload operation
        """
        if server_index >= len(self.sftp_configs):
            raise ValueError(f"Invalid server index: {server_index}")
            
        config = self.sftp_configs[server_index]
        session_key = f"{config.hostname}:{config.port}"
        
        return self.executor.submit(
            self._upload_file_worker, local_path, remote_path, config, session_key, progress_callback
        )
        
    def _upload_file_worker(self, local_path: str, remote_path: str, config: SFTPConfig,
                          session_key: str, progress_callback: Optional[Callable[[int, int], None]]) -> bool:
        """Worker function for file upload."""
        # Get or create SFTP session
        if session_key not in self.active_sessions:
            session = SFTPSession(config)
            if not session.connect():
                return False
            self.active_sessions[session_key] = session
        else:
            session = self.active_sessions[session_key]
            
        # Attempt upload
        try:
            return session.upload_file(local_path, remote_path, progress_callback)
        except Exception as e:
            self.logger.error(f"Upload failed for {local_path}: {e}")
            # Try to reconnect on failure
            session.disconnect()
            if session.connect():
                return session.upload_file(local_path, remote_path, progress_callback)
            else:
                # Remove failed session
                self.active_sessions.pop(session_key, None)
                return False
                
    def upload_multiple_files(self, file_mappings: List[tuple],
                            distribute_servers: bool = True) -> List[Future]:
        """
        Upload multiple files concurrently.
        
        Args:
            file_mappings: List of (local_path, remote_path) tuples
            distribute_servers: Whether to distribute files across available servers
            
        Returns:
            List of Future objects for upload operations
        """
        futures = []
        
        for i, (local_path, remote_path) in enumerate(file_mappings):
            if distribute_servers:
                server_index = i % len(self.sftp_configs)
            else:
                server_index = 0
                
            future = self.upload_file(local_path, remote_path, server_index)
            futures.append(future)
            
        return futures
        
    def close_all_sessions(self) -> None:
        """Close all active SFTP sessions."""
        for session in self.active_sessions.values():
            session.disconnect()
        self.active_sessions.clear()
        
    def shutdown(self) -> None:
        """Shutdown the SFTP manager and close all sessions."""
        self.close_all_sessions()
        self.executor.shutdown(wait=True)
        self.logger.info("SFTP manager shutdown complete")
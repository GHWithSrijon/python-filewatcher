"""
Python File Watcher with S3 Upload and SFTP Transfer capabilities.
"""

__version__ = "1.0.0"
__author__ = "File Watcher Team"

from .app import FileProcessorApp
from .file_watcher import FileWatcher
from .s3_uploader import S3Uploader, S3Config
from .sftp_manager import SFTPManager, SFTPConfig

__all__ = [
    "FileProcessorApp",
    "FileWatcher", 
    "S3Uploader",
    "S3Config",
    "SFTPManager", 
    "SFTPConfig"
]
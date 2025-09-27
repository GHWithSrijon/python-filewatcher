#!/usr/bin/env python3
"""
Main entry point for the file watcher application.
"""

import argparse
import os
import sys

from filewatcher.app import FileProcessorApp
from filewatcher.config import ConfigManager


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="File Watcher with S3 Upload and SFTP Transfer")
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.json",
        help="Path to configuration file (default: config.json)"
    )
    parser.add_argument(
        "--env-file",
        type=str,
        help="Path to .env file for environment variables"
    )
    parser.add_argument(
        "--generate-config",
        action="store_true",
        help="Generate a sample configuration file"
    )
    
    args = parser.parse_args()
    
    if args.generate_config:
        generate_sample_config(args.config)
        print(f"Sample configuration generated: {args.config}")
        return
        
    try:
        # Load configuration
        config_manager = ConfigManager(args.config, args.env_file)
        
        if not config_manager.validate_config():
            print("Configuration validation failed. Please check your configuration.")
            sys.exit(1)
            
        # Create and start application
        app = FileProcessorApp(config_manager.get_config())
        app.start()
        
    except KeyboardInterrupt:
        print("\nReceived interrupt signal, shutting down...")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


def generate_sample_config(config_path: str) -> None:
    """Generate a sample configuration file."""
    sample_config = {
        "file_watcher": {
            "watch_directories": ["./watched_files", "./incoming"],
            "watched_extensions": [".txt", ".pdf", ".jpg", ".png", ".doc", ".docx"]
        },
        "s3": {
            "bucket_name": "my-file-bucket",
            "aws_access_key_id": "YOUR_AWS_ACCESS_KEY_ID",
            "aws_secret_access_key": "YOUR_AWS_SECRET_ACCESS_KEY",
            "aws_session_token": "",
            "region_name": "us-east-1",
            "endpoint_url": "",
            "key_prefix": "uploads",
            "multipart_threshold": 104857600,
            "multipart_chunksize": 10485760,
            "max_concurrency": 10
        },
        "sftp": {
            "servers": [
                {
                    "hostname": "sftp.example.com",
                    "port": 22,
                    "username": "your_username",
                    "password": "your_password",
                    "private_key_path": "",
                    "timeout": 30
                }
            ],
            "remote_directory": "/uploads",
            "max_concurrent_transfers": 5
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        }
    }
    
    config_manager = ConfigManager()
    config_manager.config = sample_config
    config_manager.save_config(config_path)


if __name__ == "__main__":
    main()
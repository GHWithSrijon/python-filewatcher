"""
Configuration management for the file watcher application.
"""

import json
import os
from typing import Dict, Any, Optional

from dotenv import load_dotenv


class ConfigManager:
    """Manages application configuration from files and environment variables."""
    
    def __init__(self, config_file: Optional[str] = None, env_file: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            config_file: Path to JSON configuration file
            env_file: Path to .env file for environment variables
        """
        self.config_file = config_file
        self.env_file = env_file
        self.config: Dict[str, Any] = {}
        
        # Load environment variables
        if env_file and os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            load_dotenv()  # Load from .env in current directory if it exists
            
        # Load configuration
        self._load_config()
        
    def _load_config(self) -> None:
        """Load configuration from file and environment variables."""
        # Load from file if provided
        if self.config_file and os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                raise ValueError(f"Failed to load configuration file {self.config_file}: {e}")
        else:
            # Create default configuration
            self.config = self._create_default_config()
            
        # Override with environment variables
        self._apply_env_overrides()
        
    def _create_default_config(self) -> Dict[str, Any]:
        """Create default configuration."""
        return {
            "file_watcher": {
                "watch_directories": ["./watched_files"],
                "watched_extensions": None  # Watch all files
            },
            "s3": {
                "bucket_name": "",
                "aws_access_key_id": "",
                "aws_secret_access_key": "",
                "aws_session_token": "",
                "region_name": "us-east-1",
                "endpoint_url": "",
                "key_prefix": "uploads",
                "multipart_threshold": 100 * 1024 * 1024,  # 100MB
                "multipart_chunksize": 10 * 1024 * 1024,   # 10MB
                "max_concurrency": 10
            },
            "sftp": {
                "servers": [],
                "remote_directory": "/uploads",
                "max_concurrent_transfers": 5
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            }
        }
        
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        env_mappings = {
            # S3 configuration
            "AWS_ACCESS_KEY_ID": ("s3", "aws_access_key_id"),
            "AWS_SECRET_ACCESS_KEY": ("s3", "aws_secret_access_key"),
            "AWS_SESSION_TOKEN": ("s3", "aws_session_token"),
            "AWS_DEFAULT_REGION": ("s3", "region_name"),
            "S3_BUCKET_NAME": ("s3", "bucket_name"),
            "S3_ENDPOINT_URL": ("s3", "endpoint_url"),
            "S3_KEY_PREFIX": ("s3", "key_prefix"),
            
            # File watcher configuration  
            "WATCH_DIRECTORIES": ("file_watcher", "watch_directories"),
            "WATCHED_EXTENSIONS": ("file_watcher", "watched_extensions"),
            
            # SFTP configuration
            "SFTP_REMOTE_DIR": ("sftp", "remote_directory"),
            
            # Logging
            "LOG_LEVEL": ("logging", "level")
        }
        
        for env_var, (section, key) in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                if section not in self.config:
                    self.config[section] = {}
                    
                # Special handling for list values
                if key == "watch_directories" or key == "watched_extensions":
                    self.config[section][key] = [item.strip() for item in value.split(",")]
                else:
                    self.config[section][key] = value
                    
    def get_config(self) -> Dict[str, Any]:
        """Get the complete configuration dictionary."""
        return self.config
        
    def validate_config(self) -> bool:
        """
        Validate configuration for required fields.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        errors = []
        
        # Check file watcher configuration
        if not self.config.get("file_watcher", {}).get("watch_directories"):
            errors.append("No watch directories specified")
            
        # Check S3 configuration if S3 section exists
        s3_config = self.config.get("s3", {})
        if s3_config.get("bucket_name"):
            # If bucket name is provided, we need credentials
            if not (s3_config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID")):
                errors.append("S3 bucket specified but no AWS credentials found")
                
        # Check SFTP configuration if servers are specified
        sftp_config = self.config.get("sftp", {})
        if sftp_config.get("servers"):
            for i, server in enumerate(sftp_config["servers"]):
                if not server.get("hostname"):
                    errors.append(f"SFTP server {i} missing hostname")
                if not (server.get("password") or server.get("private_key_path")):
                    errors.append(f"SFTP server {i} missing authentication credentials")
                    
        if errors:
            for error in errors:
                print(f"Configuration error: {error}")
            return False
            
        return True
        
    def save_config(self, output_file: str) -> None:
        """
        Save current configuration to file.
        
        Args:
            output_file: Path to output file
        """
        try:
            with open(output_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            raise ValueError(f"Failed to save configuration to {output_file}: {e}")
            
    def add_sftp_server(self, hostname: str, username: str = "", password: str = "",
                       private_key_path: str = "", port: int = 22) -> None:
        """
        Add an SFTP server to the configuration.
        
        Args:
            hostname: SFTP server hostname
            username: Username for authentication
            password: Password for authentication
            private_key_path: Path to private key file
            port: SFTP server port
        """
        if "sftp" not in self.config:
            self.config["sftp"] = {"servers": [], "remote_directory": "/uploads", "max_concurrent_transfers": 5}
            
        server_config = {
            "hostname": hostname,
            "port": port,
            "username": username,
            "password": password,
            "private_key_path": private_key_path,
            "timeout": 30
        }
        
        self.config["sftp"]["servers"].append(server_config)
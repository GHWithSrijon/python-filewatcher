# Python File Watcher with S3 Upload and SFTP Transfer

A robust Python application that monitors directories for new files and automatically transfers them to multiple destinations including S3 buckets and SFTP servers. Designed for high-performance scenarios with support for concurrent transfers, multipart uploads, and multiple file sizes.

## Features

### Core Capabilities
- **🔍 File Detection**: Real-time monitoring of specified directories for new files
- **☁️ S3 Upload**: Automatic upload to S3 with intelligent multipart upload for large files
- **📡 SFTP Transfer**: Concurrent SFTP transfers to multiple servers
- **⚡ Concurrent Processing**: Multiple files processed simultaneously with configurable concurrency
- **📊 Multi-size Support**: Optimized handling for files of various sizes (small to very large)
- **🛡️ Error Handling**: Robust error handling with automatic retry mechanisms

### Design Elements
- **File Watcher**: Uses `watchdog` library for efficient file system monitoring
- **Multiple SFTP Sessions**: ThreadPoolExecutor manages concurrent SFTP connections
- **Multipart Upload**: Automatic multipart upload for large S3 files (>100MB by default)
- **Configurable**: JSON and environment variable configuration support
- **Extensible**: Modular design allows easy extension and customization

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd python-filewatcher
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Method 1: JSON Configuration File

Create a `config.json` file or generate a sample:

```bash
python main.py --generate-config
```

Example configuration:
```json
{
  "file_watcher": {
    "watch_directories": ["./watched_files", "./incoming"],
    "watched_extensions": [".txt", ".pdf", ".jpg", ".png", ".doc", ".docx"]
  },
  "s3": {
    "bucket_name": "my-file-bucket",
    "aws_access_key_id": "YOUR_AWS_ACCESS_KEY_ID", 
    "aws_secret_access_key": "YOUR_AWS_SECRET_ACCESS_KEY",
    "region_name": "us-east-1",
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
        "timeout": 30
      }
    ],
    "remote_directory": "/uploads",
    "max_concurrent_transfers": 5
  },
  "logging": {
    "level": "INFO"
  }
}
```

### Method 2: Environment Variables

Create a `.env` file:
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_DEFAULT_REGION=us-east-1

# S3 Configuration  
S3_BUCKET_NAME=my-file-bucket
S3_KEY_PREFIX=uploads

# File Watcher Configuration
WATCH_DIRECTORIES=./watched_files,./incoming
WATCHED_EXTENSIONS=.txt,.pdf,.jpg,.png

# SFTP Configuration
SFTP_REMOTE_DIR=/uploads

# Logging
LOG_LEVEL=INFO
```

## Usage

### Basic Usage

```bash
# Use default config.json
python main.py

# Use specific configuration file
python main.py --config /path/to/config.json

# Use environment file
python main.py --env-file /path/to/.env
```

### Programmatic Usage

```python
from filewatcher import FileProcessorApp
from filewatcher.config import ConfigManager

# Load configuration
config_manager = ConfigManager("config.json")
config = config_manager.get_config()

# Create and start application
app = FileProcessorApp(config)
app.start()  # Runs until interrupted
```

## Architecture

### Components

1. **FileWatcher**: Monitors directories using the `watchdog` library
   - Detects file creation and move events
   - Waits for file stability before processing
   - Supports file extension filtering

2. **SFTPManager**: Manages multiple concurrent SFTP connections
   - Connection pooling and reuse
   - Automatic reconnection on failures
   - Load balancing across multiple servers

3. **S3Uploader**: Handles S3 uploads with multipart support
   - Automatic multipart upload for large files
   - Concurrent part uploads
   - Progress tracking and metadata support

4. **FileProcessorApp**: Main coordinator
   - Queues detected files for processing
   - Coordinates SFTP and S3 uploads
   - Manages application lifecycle

### Flow Diagram

```
New File Detected → File Queue → Process File → SFTP Upload (concurrent)
                                              → S3 Upload (multipart if large)
```

## Performance Characteristics

- **File Detection**: Real-time using OS file system events
- **Concurrent Transfers**: Up to 5 SFTP + 10 S3 uploads simultaneously (configurable)
- **Large File Handling**: Multipart uploads with 10MB chunks by default
- **Memory Efficient**: Streams large files without loading entirely into memory
- **Fault Tolerant**: Automatic retries and graceful error handling

## Configuration Reference

### File Watcher Settings
- `watch_directories`: List of directories to monitor
- `watched_extensions`: File extensions to watch (null = all files)

### S3 Settings
- `bucket_name`: Target S3 bucket
- `multipart_threshold`: File size threshold for multipart upload (default: 100MB)
- `multipart_chunksize`: Size of each multipart chunk (default: 10MB)
- `max_concurrency`: Maximum concurrent uploads (default: 10)

### SFTP Settings
- `servers`: List of SFTP server configurations
- `max_concurrent_transfers`: Maximum concurrent SFTP transfers (default: 5)
- `remote_directory`: Remote directory for uploads

## Testing

Run the included tests:
```bash
python tests/test_file_watcher.py
```

## Dependencies

- `watchdog>=3.0.0` - File system monitoring
- `boto3>=1.28.0` - AWS S3 integration
- `paramiko>=3.3.0` - SFTP support
- `python-dotenv>=1.0.0` - Environment variable support

## License

This project is available under the MIT License.

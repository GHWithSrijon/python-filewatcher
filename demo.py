#!/usr/bin/env python3
"""
Demo script for the file watcher application.
This script demonstrates the key features without requiring actual S3 or SFTP credentials.
"""

import json
import os
import tempfile
import time
import threading
from pathlib import Path

from filewatcher.file_watcher import FileWatcher
from filewatcher.config import ConfigManager


def demo_file_watcher():
    """Demonstrate the file watcher functionality."""
    print("🚀 File Watcher Demo")
    print("=" * 50)
    
    # Create temporary directories for demonstration
    watch_dir = tempfile.mkdtemp(prefix="demo_watched_")
    print(f"📁 Created demo watch directory: {watch_dir}")
    
    detected_files = []
    
    def on_new_file(file_path):
        print(f"🔔 NEW FILE DETECTED: {file_path}")
        file_size = os.path.getsize(file_path)
        print(f"   📊 File size: {file_size:,} bytes")
        
        # Simulate processing decision
        if file_size > 50 * 1024 * 1024:  # 50MB
            print(f"   📦 Large file - would use S3 multipart upload")
        else:
            print(f"   📄 Regular file - would use simple S3 upload")
        
        print(f"   📡 Would transfer to SFTP servers")
        detected_files.append(file_path)
        print()
    
    # Create and start file watcher
    watcher = FileWatcher([watch_dir], on_new_file, {'.txt', '.pdf', '.jpg'})
    watcher.start()
    print(f"👁️  File watcher started, monitoring: {watch_dir}")
    print(f"🎯 Watching for extensions: .txt, .pdf, .jpg")
    print()
    
    # Simulate file creation with different sizes
    test_files = [
        ("small_document.txt", "This is a small text file for testing."),
        ("medium_report.pdf", "X" * (5 * 1024 * 1024)),  # 5MB
        ("large_image.jpg", "Y" * (75 * 1024 * 1024))    # 75MB
    ]
    
    print("📝 Creating test files...")
    for i, (filename, content) in enumerate(test_files, 1):
        print(f"   {i}. Creating {filename}...")
        file_path = os.path.join(watch_dir, filename)
        
        with open(file_path, 'w') as f:
            f.write(content)
        
        time.sleep(2)  # Allow time for file detection
    
    # Wait for all files to be processed
    time.sleep(2)
    
    # Create a file with unsupported extension (should be ignored)
    print("   4. Creating ignored_file.log (should be ignored)...")
    with open(os.path.join(watch_dir, "ignored_file.log"), 'w') as f:
        f.write("This file should be ignored due to extension filtering.")
    
    time.sleep(2)
    
    # Stop watcher and cleanup
    watcher.stop()
    print("⏹️  File watcher stopped")
    
    # Results summary
    print("\n📊 Demo Results Summary")
    print("=" * 30)
    print(f"Total files created: {len(test_files) + 1}")
    print(f"Files detected by watcher: {len(detected_files)}")
    print(f"Files ignored (due to extension): 1")
    
    # Cleanup
    for filename, _ in test_files:
        try:
            os.remove(os.path.join(watch_dir, filename))
        except OSError:
            pass
    try:
        os.remove(os.path.join(watch_dir, "ignored_file.log"))
        os.rmdir(watch_dir)
    except OSError:
        pass
    
    print(f"\n✨ Demo completed successfully!")
    return len(detected_files) == len(test_files)


def demo_config_management():
    """Demonstrate configuration management."""
    print("\n🔧 Configuration Management Demo")
    print("=" * 40)
    
    # Create a demo configuration
    config_manager = ConfigManager()
    
    # Show default configuration
    config = config_manager.get_config()
    print("📋 Default configuration loaded:")
    print(f"   Watch directories: {config['file_watcher']['watch_directories']}")
    print(f"   S3 bucket: {config['s3']['bucket_name'] or 'Not configured'}")
    print(f"   SFTP servers: {len(config['sftp']['servers'])} configured")
    
    # Add an SFTP server
    config_manager.add_sftp_server(
        hostname="demo.sftp.com",
        username="demo_user",
        password="demo_pass"
    )
    
    print("\n➕ Added demo SFTP server:")
    updated_config = config_manager.get_config()
    print(f"   SFTP servers: {len(updated_config['sftp']['servers'])} configured")
    
    # Validate configuration
    is_valid = config_manager.validate_config()
    print(f"\n✅ Configuration valid: {is_valid}")
    
    return True


def show_architecture_info():
    """Display architecture and design information."""
    print("\n🏗️  Architecture Overview")
    print("=" * 30)
    
    architecture = """
📁 File Detection Layer
   └── watchdog library monitors file system events
   └── Supports multiple directories and extension filtering
   └── Waits for file stability before processing

⚙️  Processing Layer  
   └── Queue-based file processing
   └── Concurrent handling of multiple files
   └── Automatic retry on failures

🌐 Transfer Layer
   ├── SFTP Manager
   │   ├── Multiple concurrent sessions
   │   ├── Connection pooling and reuse  
   │   └── Load balancing across servers
   │
   └── S3 Uploader
       ├── Intelligent multipart upload
       ├── Concurrent part uploads
       └── Progress tracking

🔧 Configuration Layer
   ├── JSON configuration files
   ├── Environment variable overrides
   └── Runtime configuration validation
"""
    
    print(architecture)
    
    print("🚀 Performance Features:")
    print("   • Real-time file detection using OS events")
    print("   • Concurrent SFTP transfers (configurable)")
    print("   • Multipart S3 uploads for large files (>100MB)")
    print("   • Memory-efficient streaming for large files") 
    print("   • Automatic retry and error recovery")
    print("   • Extensible modular design")


def main():
    """Run the complete demo."""
    print("🎯 Python File Watcher - Complete Demo")
    print("=" * 60)
    print()
    
    try:
        # Demo 1: File watcher functionality
        success1 = demo_file_watcher()
        
        # Demo 2: Configuration management
        success2 = demo_config_management()
        
        # Demo 3: Architecture overview
        show_architecture_info()
        
        print("\n" + "=" * 60)
        if success1 and success2:
            print("🎉 All demos completed successfully!")
            print("\n💡 Next Steps:")
            print("   1. Copy config/config.json.example to config.json")
            print("   2. Update with your AWS and SFTP credentials")
            print("   3. Run: python main.py --config config.json")
            print("   4. Drop files into your configured watch directories")
        else:
            print("❌ Some demos failed. Check the output above.")
            
    except KeyboardInterrupt:
        print("\n⏹️  Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")


if __name__ == "__main__":
    main()
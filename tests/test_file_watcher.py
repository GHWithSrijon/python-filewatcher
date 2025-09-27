#!/usr/bin/env python3
"""
Simple test script to validate the file watcher functionality.
"""

import os
import sys
import tempfile
import time
import threading
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filewatcher.file_watcher import FileWatcher


def test_file_watcher():
    """Test the file watcher functionality."""
    print("🔍 Testing File Watcher...")
    
    # Create temporary directory for testing
    test_dir = tempfile.mkdtemp()
    detected_files = []
    
    def on_new_file(file_path):
        print(f"📁 Detected new file: {file_path}")
        detected_files.append(file_path)
    
    # Create file watcher
    watcher = FileWatcher([test_dir], on_new_file)
    watcher.start()
    
    # Give watcher time to start
    time.sleep(1)
    
    # Create test files
    test_files = ["test1.txt", "test2.pdf", "test3.jpg"]
    created_files = []
    
    for filename in test_files:
        file_path = os.path.join(test_dir, filename)
        with open(file_path, 'w') as f:
            f.write(f"Test content for {filename}")
        created_files.append(file_path)
        print(f"📄 Created test file: {file_path}")
        time.sleep(0.5)  # Small delay between file creations
    
    # Wait for file detection
    time.sleep(2)
    
    # Stop watcher
    watcher.stop()
    
    # Cleanup
    for file_path in created_files:
        try:
            os.remove(file_path)
        except OSError:
            pass
    os.rmdir(test_dir)
    
    # Validate results
    print(f"\n📊 Results:")
    print(f"  Created files: {len(created_files)}")
    print(f"  Detected files: {len(detected_files)}")
    
    if len(detected_files) == len(created_files):
        print("✅ File watcher test PASSED!")
        return True
    else:
        print("❌ File watcher test FAILED!")
        print(f"  Expected to detect {len(created_files)} files, but detected {len(detected_files)}")
        return False


if __name__ == "__main__":
    success = test_file_watcher()
    sys.exit(0 if success else 1)
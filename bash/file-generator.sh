#!/bin/bash

# Target directory
TARGET_DIR="/Users/srijon/workspace/filewatcher-project/data"
mkdir -p "$TARGET_DIR"

# Create 10MB file
echo "🛠️ Generating 10MB file..."
dd if=/dev/urandom of="$TARGET_DIR/random_10MB.bin" bs=1M count=10 status=progress

# Create 3GB file
echo "🛠️ Generating 3GB file..."
dd if=/dev/urandom of="$TARGET_DIR/random_3GB.bin" bs=1M count=3072 status=progress

# Create 5GB file
echo "🛠️ Generating 5GB file..."
dd if=/dev/urandom of="$TARGET_DIR/random_5GB.bin" bs=1M count=5120 status=progress

# Create 10GB file
# echo "🛠️ Generating 10GB file..."
# dd if=/dev/urandom of="$TARGET_DIR/random_10GB.bin" bs=1M count=10240 status=progress


for i in {1..10}; do
  filename="$TARGET_DIR/file_${i}.bin"
  echo "🛠️ Creating $filename"
  dd if=/dev/urandom of="$filename" bs=1M count=2 status=none
done

echo "✅ All files created."

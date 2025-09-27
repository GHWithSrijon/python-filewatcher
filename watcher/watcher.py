import os
import time
from datetime import datetime
import signal
import threading
import hashlib
import boto3
from diskcache import Cache
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent
import logging

WATCH_DIR = "/app/data"
CACHE_DIR = "/app/cache"
S3_BUCKET = "staging"
S3_ENDPOINT = os.getenv("AWS_ENDPOINT_URL", "http://localstack:4566")
LOG_DIR = "/app/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/watcher.log"),
        logging.StreamHandler()  # Optional: still prints to console
    ]
)

stop_event = threading.Event()
cache = Cache(CACHE_DIR)


def shutdown_handler(signum, frame):
    logging.debug("\n🛑 Shutdown signal received. Cleaning up...")
    stop_event.set()

signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)

class FileEventHandler(FileSystemEventHandler):
    def queue_file(self, filepath):
        cache.set(filepath, {
            "timestamp": time.time(),
            "retries": 0
        })
        logging.debug(f"📥 Queued: {filepath}")
    def on_created(self, event):
        logging.debug(event)
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            self.queue_file(event.src_path)
    def on_modified(self, event):
        logging.debug(event)
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            self.queue_file(event.src_path)
    def on_created(self, event):
        logging.debug(event)
        if isinstance(event, FileCreatedEvent) and not event.is_directory:
            self.queue_file(event.src_path)
        

class UploadWorker(threading.Thread):
    def __init__(self, delay=10, max_retries=3):
        super().__init__(daemon=True)
        self.delay = delay
        self.max_retries = max_retries
        self.s3 = boto3.client("s3", endpoint_url=S3_ENDPOINT)
        self.metrics = {
            "processed": 0,
            "uploaded": 0,
            "failed": 0,
            "skipped": 0,
        }

    def process_file(self, filepath):
        logging.debug(f"Processing: {filepath}")
        self.metrics["processed"] += 1
        entry = cache.get(filepath)
        # Validate entry and file existence
        if not entry or not os.path.exists(filepath):
            self.metrics["skipped"] += 1
            cache.delete(filepath)
            return

        # Check if file is still being written to
        last_modified = os.path.getmtime(filepath)
        if time.time() - last_modified < self.delay:
            return  # Skip if modified recently

        retries = entry.get("retries", 0)
        if retries >= self.max_retries:
            logging.debug(f"⚠️ Max retries exceeded: {filepath}")
            self.metrics["failed"] += 1
            cache.delete(filepath)
            return

        checksum = self.compute_checksum(filepath)
        key = os.path.basename(filepath)
        try:
            self.s3.upload_file(filepath, S3_BUCKET, key)
            logging.debug(f"✅ Uploaded: {key} (SHA256: {checksum})")
            self.metrics["uploaded"] += 1
            cache.delete(filepath)
        except Exception as e:
            logging.debug(f"❌ Upload failed: {key} → {e}")
            self.metrics["failed"] += 1
            entry["retries"] = retries + 1
            cache.set(filepath, entry)
    
    def run(self):
        logging.debug("🚀 Upload worker started.")
        # Execute when the thread starts
        while not stop_event.is_set():
            time.sleep(self.delay)
            for filepath in list(cache.iterkeys()):               
                self.process_file(filepath)

    def compute_checksum(self, filepath):
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def summary(self):
        logging.debug("\n📊 Upload Summary:")
        for k, v in self.metrics.items():
            logging.debug(f"  {k.capitalize()}: {v}")

if __name__ == "__main__":
    os.makedirs(CACHE_DIR, exist_ok=True)
    handler = FileEventHandler()
    observer = Observer()
    observer.schedule(handler, WATCH_DIR, recursive=False)
    observer.start()

    # Start upload worker thread
    worker = UploadWorker()
    worker.start()

    try:
        while not stop_event.is_set():
            time.sleep(1)
    finally:
        logging.debug("🧹 Stopping services...")
        observer.stop()
        observer.join()
        worker.join(timeout=5)
        worker.summary()
        cache.close()
        logging.debug("✅ Shutdown complete.")

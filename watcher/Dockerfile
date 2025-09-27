FROM python:3.11-slim
WORKDIR /app
COPY watcher.py .
RUN pip install watchdog diskcache boto3
CMD ["python", "watcher.py"]

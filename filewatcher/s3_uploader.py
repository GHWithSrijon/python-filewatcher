"""
S3 uploader with multipart upload support for handling large files efficiently.
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from dataclasses import dataclass
from typing import Optional, Callable, List, Dict

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


@dataclass
class S3Config:
    """Configuration for S3 uploads."""
    bucket_name: str
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    region_name: str = "us-east-1"
    endpoint_url: str = ""  # For S3-compatible services
    multipart_threshold: int = 100 * 1024 * 1024  # 100 MB
    multipart_chunksize: int = 10 * 1024 * 1024   # 10 MB
    max_concurrency: int = 10


class S3Uploader:
    """Handles S3 uploads with multipart support."""
    
    def __init__(self, config: S3Config):
        """
        Initialize S3 uploader.
        
        Args:
            config: S3 configuration
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = self._create_s3_client()
        self.executor = ThreadPoolExecutor(max_workers=config.max_concurrency)
        
    def _create_s3_client(self):
        """Create and configure S3 client."""
        try:
            session = boto3.Session()
            
            client_kwargs = {
                'service_name': 's3',
                'region_name': self.config.region_name
            }
            
            # Add credentials if provided
            if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                client_kwargs['aws_access_key_id'] = self.config.aws_access_key_id
                client_kwargs['aws_secret_access_key'] = self.config.aws_secret_access_key
                
            if self.config.aws_session_token:
                client_kwargs['aws_session_token'] = self.config.aws_session_token
                
            if self.config.endpoint_url:
                client_kwargs['endpoint_url'] = self.config.endpoint_url
                
            return session.client(**client_kwargs)
            
        except NoCredentialsError:
            self.logger.error("AWS credentials not found. Please configure credentials.")
            raise
        except Exception as e:
            self.logger.error(f"Failed to create S3 client: {e}")
            raise
            
    def upload_file(self, local_path: str, s3_key: str,
                   progress_callback: Optional[Callable[[int], None]] = None,
                   metadata: Optional[Dict[str, str]] = None) -> bool:
        """
        Upload a file to S3 with automatic multipart handling.
        
        Args:
            local_path: Path to local file
            s3_key: S3 object key
            progress_callback: Optional callback for progress updates (bytes_transferred)
            metadata: Optional metadata to attach to object
            
        Returns:
            True if upload successful, False otherwise
        """
        if not os.path.exists(local_path):
            self.logger.error(f"File not found: {local_path}")
            return False
            
        file_size = os.path.getsize(local_path)
        
        try:
            self.logger.info(f"Uploading {local_path} to s3://{self.config.bucket_name}/{s3_key}")
            
            # Use multipart upload for large files
            if file_size >= self.config.multipart_threshold:
                return self._multipart_upload(local_path, s3_key, file_size, progress_callback, metadata)
            else:
                return self._simple_upload(local_path, s3_key, progress_callback, metadata)
                
        except Exception as e:
            self.logger.error(f"Failed to upload {local_path}: {e}")
            return False
            
    def _simple_upload(self, local_path: str, s3_key: str,
                      progress_callback: Optional[Callable[[int], None]] = None,
                      metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file using simple PUT operation."""
        try:
            extra_args = {}
            if metadata:
                extra_args['Metadata'] = metadata
                
            # Create progress wrapper if callback provided
            if progress_callback:
                def upload_callback(bytes_transferred):
                    progress_callback(bytes_transferred)
                    
                self.client.upload_file(
                    local_path, self.config.bucket_name, s3_key,
                    ExtraArgs=extra_args, Callback=upload_callback
                )
            else:
                self.client.upload_file(
                    local_path, self.config.bucket_name, s3_key,
                    ExtraArgs=extra_args
                )
                
            self.logger.info(f"Successfully uploaded {local_path} using simple upload")
            return True
            
        except ClientError as e:
            self.logger.error(f"Simple upload failed: {e}")
            return False
            
    def _multipart_upload(self, local_path: str, s3_key: str, file_size: int,
                         progress_callback: Optional[Callable[[int], None]] = None,
                         metadata: Optional[Dict[str, str]] = None) -> bool:
        """Upload file using multipart upload."""
        try:
            # Initiate multipart upload
            create_kwargs = {}
            if metadata:
                create_kwargs['Metadata'] = metadata
                
            response = self.client.create_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                **create_kwargs
            )
            upload_id = response['UploadId']
            
            self.logger.info(f"Initiated multipart upload for {local_path}, upload_id: {upload_id}")
            
            # Calculate parts
            parts = []
            part_size = self.config.multipart_chunksize
            part_count = (file_size + part_size - 1) // part_size
            
            # Upload parts concurrently
            futures = []
            bytes_uploaded = 0
            
            with open(local_path, 'rb') as file:
                for part_number in range(1, part_count + 1):
                    start_byte = (part_number - 1) * part_size
                    end_byte = min(start_byte + part_size - 1, file_size - 1)
                    part_data = file.read(end_byte - start_byte + 1)
                    
                    future = self.executor.submit(
                        self._upload_part, upload_id, part_number, part_data, s3_key
                    )
                    futures.append((future, part_number, len(part_data)))
                    
            # Collect results
            for future, part_number, part_size in futures:
                try:
                    etag = future.result()
                    parts.append({
                        'ETag': etag,
                        'PartNumber': part_number
                    })
                    bytes_uploaded += part_size
                    
                    if progress_callback:
                        progress_callback(bytes_uploaded)
                        
                except Exception as e:
                    self.logger.error(f"Part {part_number} upload failed: {e}")
                    # Abort multipart upload on failure
                    self._abort_multipart_upload(upload_id, s3_key)
                    return False
                    
            # Complete multipart upload
            parts.sort(key=lambda x: x['PartNumber'])
            
            self.client.complete_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            self.logger.info(f"Successfully completed multipart upload for {local_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Multipart upload failed: {e}")
            self._abort_multipart_upload(upload_id, s3_key)
            return False
            
    def _upload_part(self, upload_id: str, part_number: int, part_data: bytes, s3_key: str) -> str:
        """Upload a single part of a multipart upload."""
        try:
            response = self.client.upload_part(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                PartNumber=part_number,
                UploadId=upload_id,
                Body=part_data
            )
            return response['ETag']
        except Exception as e:
            self.logger.error(f"Failed to upload part {part_number}: {e}")
            raise
            
    def _abort_multipart_upload(self, upload_id: str, s3_key: str) -> None:
        """Abort a multipart upload."""
        try:
            self.client.abort_multipart_upload(
                Bucket=self.config.bucket_name,
                Key=s3_key,
                UploadId=upload_id
            )
            self.logger.info(f"Aborted multipart upload {upload_id}")
        except Exception as e:
            self.logger.error(f"Failed to abort multipart upload {upload_id}: {e}")
            
    def upload_multiple_files(self, file_mappings: List[tuple],
                            metadata: Optional[Dict[str, str]] = None) -> List[Future]:
        """
        Upload multiple files concurrently.
        
        Args:
            file_mappings: List of (local_path, s3_key) tuples
            metadata: Optional metadata to attach to all objects
            
        Returns:
            List of Future objects for upload operations
        """
        futures = []
        
        for local_path, s3_key in file_mappings:
            future = self.executor.submit(
                self.upload_file, local_path, s3_key, metadata=metadata
            )
            futures.append(future)
            
        return futures
        
    def wait_for_uploads(self, futures: List[Future], timeout: Optional[int] = None) -> Dict[str, bool]:
        """
        Wait for multiple uploads to complete.
        
        Args:
            futures: List of Future objects from upload operations
            timeout: Maximum time to wait for completion
            
        Returns:
            Dictionary mapping future to completion status
        """
        results = {}
        
        try:
            for future in as_completed(futures, timeout=timeout):
                results[future] = future.result()
        except Exception as e:
            self.logger.error(f"Error waiting for uploads: {e}")
            
        return results
        
    def shutdown(self) -> None:
        """Shutdown the uploader and close thread pool."""
        self.executor.shutdown(wait=True)
        self.logger.info("S3 uploader shutdown complete")
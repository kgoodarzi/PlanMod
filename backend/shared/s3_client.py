"""
S3 client utilities for PlanMod.

Provides high-level operations for S3 storage.
"""

import io
import json
from pathlib import Path
from typing import Any, Optional, Union

import boto3
from botocore.exceptions import ClientError

from backend.shared.config import get_settings
from backend.shared.models import S3Reference


class S3Client:
    """
    High-level S3 client for PlanMod operations.
    """
    
    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize S3 client.
        
        Args:
            settings: Optional settings override
        """
        self.settings = settings or get_settings()
        self._client: Optional[Any] = None
    
    @property
    def client(self) -> Any:
        """Get or create boto3 S3 client."""
        if self._client is None:
            config = self.settings.get_boto3_config()
            
            if self.settings.aws.profile and not config.get("aws_access_key_id"):
                session = boto3.Session(profile_name=self.settings.aws.profile)
                self._client = session.client("s3", **config)
            else:
                self._client = boto3.client("s3", **config)
        
        return self._client
    
    @property
    def bucket_name(self) -> str:
        """Get the configured bucket name."""
        return self.settings.bucket_name
    
    # =========================================================================
    # Upload Operations
    # =========================================================================
    
    def upload_file(
        self,
        local_path: Union[str, Path],
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> S3Reference:
        """
        Upload a local file to S3.
        
        Args:
            local_path: Path to local file
            key: S3 object key
            content_type: Optional MIME type
            metadata: Optional metadata dict
            
        Returns:
            S3Reference to uploaded file
        """
        extra_args: dict[str, Any] = {}
        
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata
        
        self.client.upload_file(
            str(local_path),
            self.bucket_name,
            key,
            ExtraArgs=extra_args if extra_args else None,
        )
        
        return S3Reference(bucket=self.bucket_name, key=key)
    
    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
    ) -> S3Reference:
        """
        Upload bytes data to S3.
        
        Args:
            data: Bytes to upload
            key: S3 object key
            content_type: Optional MIME type
            metadata: Optional metadata dict
            
        Returns:
            S3Reference to uploaded file
        """
        extra_args: dict[str, Any] = {}
        
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata
        
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=key,
            Body=data,
            **extra_args,
        )
        
        return S3Reference(bucket=self.bucket_name, key=key)
    
    def upload_json(
        self,
        data: Any,
        key: str,
        metadata: Optional[dict[str, str]] = None,
    ) -> S3Reference:
        """
        Upload JSON data to S3.
        
        Args:
            data: JSON-serializable data
            key: S3 object key
            metadata: Optional metadata dict
            
        Returns:
            S3Reference to uploaded file
        """
        json_bytes = json.dumps(data, default=str, indent=2).encode("utf-8")
        return self.upload_bytes(
            json_bytes,
            key,
            content_type="application/json",
            metadata=metadata,
        )
    
    # =========================================================================
    # Download Operations
    # =========================================================================
    
    def download_file(
        self,
        key: str,
        local_path: Union[str, Path],
    ) -> Path:
        """
        Download file from S3 to local path.
        
        Args:
            key: S3 object key
            local_path: Local destination path
            
        Returns:
            Path to downloaded file
        """
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.client.download_file(self.bucket_name, key, str(local_path))
        
        return local_path
    
    def download_bytes(self, key: str) -> bytes:
        """
        Download file from S3 as bytes.
        
        Args:
            key: S3 object key
            
        Returns:
            File contents as bytes
        """
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        return response["Body"].read()
    
    def download_json(self, key: str) -> Any:
        """
        Download and parse JSON file from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            Parsed JSON data
        """
        data = self.download_bytes(key)
        return json.loads(data.decode("utf-8"))
    
    def get_file_stream(self, key: str) -> io.BytesIO:
        """
        Get file from S3 as a BytesIO stream.
        
        Args:
            key: S3 object key
            
        Returns:
            BytesIO stream with file contents
        """
        data = self.download_bytes(key)
        return io.BytesIO(data)
    
    # =========================================================================
    # URL Operations
    # =========================================================================
    
    def generate_presigned_upload_url(
        self,
        key: str,
        content_type: Optional[str] = None,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a pre-signed URL for uploading.
        
        Args:
            key: S3 object key
            content_type: Expected content type
            expires_in: URL expiration in seconds
            
        Returns:
            Pre-signed upload URL
        """
        params: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key,
        }
        
        if content_type:
            params["ContentType"] = content_type
        
        return self.client.generate_presigned_url(
            "put_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    
    def generate_presigned_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """
        Generate a pre-signed URL for downloading.
        
        Args:
            key: S3 object key
            expires_in: URL expiration in seconds
            filename: Optional filename for Content-Disposition
            
        Returns:
            Pre-signed download URL
        """
        params: dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": key,
        }
        
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
        
        return self.client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in,
        )
    
    # =========================================================================
    # Utility Operations
    # =========================================================================
    
    def exists(self, key: str) -> bool:
        """
        Check if an object exists in S3.
        
        Args:
            key: S3 object key
            
        Returns:
            True if object exists
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise
    
    def delete(self, key: str) -> bool:
        """
        Delete an object from S3.
        
        Args:
            key: S3 object key
            
        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        List objects with a given prefix.
        
        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return
            
        Returns:
            List of object metadata dicts
        """
        response = self.client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix=prefix,
            MaxKeys=max_keys,
        )
        
        return response.get("Contents", [])
    
    def copy(
        self,
        source_key: str,
        dest_key: str,
        source_bucket: Optional[str] = None,
    ) -> S3Reference:
        """
        Copy an object within S3.
        
        Args:
            source_key: Source object key
            dest_key: Destination object key
            source_bucket: Source bucket (defaults to current bucket)
            
        Returns:
            S3Reference to copied object
        """
        source_bucket = source_bucket or self.bucket_name
        
        self.client.copy_object(
            Bucket=self.bucket_name,
            Key=dest_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
        )
        
        return S3Reference(bucket=self.bucket_name, key=dest_key)
    
    # =========================================================================
    # Key Generation
    # =========================================================================
    
    @staticmethod
    def generate_upload_key(job_id: str, filename: str) -> str:
        """Generate S3 key for uploaded file."""
        return f"uploads/{job_id}/{filename}"
    
    @staticmethod
    def generate_temp_key(job_id: str, filename: str) -> str:
        """Generate S3 key for temporary file."""
        return f"temp/{job_id}/{filename}"
    
    @staticmethod
    def generate_output_key(job_id: str, filename: str) -> str:
        """Generate S3 key for output file."""
        return f"outputs/{job_id}/{filename}"


# Singleton instance
_s3_client: Optional[S3Client] = None


def get_s3_client() -> S3Client:
    """Get or create singleton S3 client."""
    global _s3_client
    if _s3_client is None:
        _s3_client = S3Client()
    return _s3_client



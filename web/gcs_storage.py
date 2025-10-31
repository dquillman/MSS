"""
Google Cloud Storage utilities for MSS.

Provides functions to read/write files to GCS instead of local disk.
This is required for Cloud Run where local disk is ephemeral.
"""

import os
from pathlib import Path
from typing import Optional, BinaryIO
from google.cloud import storage
from google.auth.exceptions import DefaultCredentialsError


class GCSStorage:
    """Wrapper for Google Cloud Storage operations."""
    
    def __init__(self, bucket_name: Optional[str] = None, region: Optional[str] = None):
        """
        Initialize GCS client.
        
        Args:
            bucket_name: GCS bucket name (defaults to GCS_BUCKET_NAME env var)
            region: Bucket region (defaults to GCS_BUCKET_REGION env var)
        """
        self.bucket_name = bucket_name or os.getenv('GCS_BUCKET_NAME')
        self.region = region or os.getenv('GCS_BUCKET_REGION', 'us-central1')
        self._client = None
        self._bucket = None
        
        if self.bucket_name:
            try:
                self._client = storage.Client()
                self._bucket = self._client.bucket(self.bucket_name)
            except DefaultCredentialsError:
                print("[WARN] GCS credentials not found. Falling back to local storage.")
                self._client = None
                self._bucket = None
    
    def is_enabled(self) -> bool:
        """Check if GCS is configured and available."""
        return self._client is not None and self._bucket is not None
    
    def upload_file(self, local_path: str, gcs_path: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file to GCS.
        
        Args:
            local_path: Local file path
            gcs_path: GCS object path (e.g., 'out/video.mp4')
            content_type: MIME type (auto-detected if not provided)
            
        Returns:
            GCS public URL or local path if GCS unavailable
        """
        if not self.is_enabled():
            # Fallback to local storage
            return local_path
        
        blob = self._bucket.blob(gcs_path)
        if content_type:
            blob.content_type = content_type
        blob.upload_from_filename(local_path)
        
        # Return public URL
        blob.make_public()
        return blob.public_url
    
    def upload_fileobj(self, file_obj: BinaryIO, gcs_path: str, content_type: Optional[str] = None) -> str:
        """
        Upload a file-like object to GCS.
        
        Args:
            file_obj: File-like object (opened in binary mode)
            gcs_path: GCS object path
            content_type: MIME type
            
        Returns:
            GCS public URL
        """
        if not self.is_enabled():
            raise RuntimeError("GCS not available")
        
        blob = self._bucket.blob(gcs_path)
        if content_type:
            blob.content_type = content_type
        blob.upload_from_file(file_obj)
        blob.make_public()
        return blob.public_url
    
    def download_file(self, gcs_path: str, local_path: str) -> str:
        """
        Download a file from GCS to local disk.
        
        Args:
            gcs_path: GCS object path
            local_path: Local destination path
            
        Returns:
            Local path
        """
        if not self.is_enabled():
            return local_path
        
        blob = self._bucket.blob(gcs_path)
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(local_path)
        return local_path
    
    def get_public_url(self, gcs_path: str) -> Optional[str]:
        """
        Get public URL for a GCS object.
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            Public URL or None if not found
        """
        if not self.is_enabled():
            return None
        
        blob = self._bucket.blob(gcs_path)
        if blob.exists():
            blob.make_public()
            return blob.public_url
        return None
    
    def delete_file(self, gcs_path: str) -> bool:
        """
        Delete a file from GCS.
        
        Args:
            gcs_path: GCS object path
            
        Returns:
            True if deleted, False otherwise
        """
        if not self.is_enabled():
            return False
        
        blob = self._bucket.blob(gcs_path)
        if blob.exists():
            blob.delete()
            return True
        return False


# Global GCS instance
_gcs_storage: Optional[GCSStorage] = None


def get_gcs_storage() -> GCSStorage:
    """Get or create global GCS storage instance."""
    global _gcs_storage
    if _gcs_storage is None:
        _gcs_storage = GCSStorage()
    return _gcs_storage


def ensure_gcs_path(local_path: Path, prefix: str = "out/") -> Path:
    """
    Ensure a file path works with both local and GCS storage.
    
    For Cloud Run, files should be written to GCS. For local dev, use local disk.
    
    Args:
        local_path: Local file path
        prefix: GCS prefix (default: "out/")
        
    Returns:
        Path that can be used for storage
    """
    gcs = get_gcs_storage()
    if gcs.is_enabled():
        # Return GCS path
        gcs_path = f"{prefix}{local_path.name}"
        return Path(gcs_path)  # This is a virtual path for GCS
    return local_path


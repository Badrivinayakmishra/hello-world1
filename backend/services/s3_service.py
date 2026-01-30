"""
AWS S3 Service
Handles file uploads, downloads, and management in S3 bucket
"""

import os
import boto3
from botocore.exceptions import ClientError
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta


class S3Service:
    """Service for managing files in AWS S3"""

    def __init__(self):
        """Initialize S3 client with credentials from environment"""
        self.access_key = os.getenv('AWS_ACCESS_KEY_ID')
        self.secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('AWS_S3_BUCKET')
        self.region = os.getenv('AWS_S3_REGION', 'us-east-2')

        if not all([self.access_key, self.secret_key, self.bucket_name]):
            raise ValueError(
                "AWS credentials not configured. Set AWS_ACCESS_KEY_ID, "
                "AWS_SECRET_ACCESS_KEY, and AWS_S3_BUCKET environment variables."
            )

        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        # Base URL for public S3 files
        self.base_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com"

    def upload_file(
        self,
        file_path: str,
        s3_key: str,
        content_type: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload a file to S3

        Args:
            file_path: Local path to file
            s3_key: S3 object key (path in bucket)
            content_type: MIME type (auto-detected if None)

        Returns:
            (public_url, error_message)
        """
        try:
            extra_args = {}

            # Auto-detect content type if not provided
            if content_type:
                extra_args['ContentType'] = content_type
            elif s3_key.endswith('.mp4'):
                extra_args['ContentType'] = 'video/mp4'
            elif s3_key.endswith('.pdf'):
                extra_args['ContentType'] = 'application/pdf'
            elif s3_key.endswith('.pptx'):
                extra_args['ContentType'] = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
            elif s3_key.endswith('.docx'):
                extra_args['ContentType'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            elif s3_key.endswith('.png'):
                extra_args['ContentType'] = 'image/png'
            elif s3_key.endswith('.jpg') or s3_key.endswith('.jpeg'):
                extra_args['ContentType'] = 'image/jpeg'

            # Make file publicly readable
            extra_args['ACL'] = 'public-read'

            self.s3_client.upload_file(
                file_path,
                self.bucket_name,
                s3_key,
                ExtraArgs=extra_args
            )

            public_url = f"{self.base_url}/{s3_key}"
            print(f"[S3] Uploaded: {s3_key} -> {public_url}")
            return public_url, None

        except ClientError as e:
            error_msg = f"S3 upload failed: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return None, error_msg

    def upload_bytes(
        self,
        file_bytes: bytes,
        s3_key: str,
        content_type: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Upload bytes directly to S3

        Args:
            file_bytes: File content as bytes
            s3_key: S3 object key (path in bucket)
            content_type: MIME type

        Returns:
            (public_url, error_message)
        """
        try:
            extra_args = {}
            if content_type:
                extra_args['ContentType'] = content_type
            extra_args['ACL'] = 'public-read'

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_bytes,
                **extra_args
            )

            public_url = f"{self.base_url}/{s3_key}"
            print(f"[S3] Uploaded bytes: {s3_key} -> {public_url}")
            return public_url, None

        except ClientError as e:
            error_msg = f"S3 upload failed: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Upload error: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return None, error_msg

    def delete_file(self, s3_key: str) -> Tuple[bool, Optional[str]]:
        """
        Delete a file from S3

        Args:
            s3_key: S3 object key to delete

        Returns:
            (success, error_message)
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            print(f"[S3] Deleted: {s3_key}")
            return True, None

        except ClientError as e:
            error_msg = f"S3 delete failed: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Delete error: {str(e)}"
            print(f"[S3] Error: {error_msg}")
            return False, error_msg

    def file_exists(self, s3_key: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            s3_key: S3 object key to check

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.s3_client.head_object(
                Bucket=self.bucket_name,
                Key=s3_key
            )
            return True
        except ClientError:
            return False

    def get_presigned_url(
        self,
        s3_key: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate a presigned URL for temporary access

        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned URL or None
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            print(f"[S3] Error generating presigned URL: {e}")
            return None

    def get_public_url(self, s3_key: str) -> str:
        """
        Get public URL for a file

        Args:
            s3_key: S3 object key

        Returns:
            Public URL
        """
        return f"{self.base_url}/{s3_key}"

    def generate_s3_key(
        self,
        tenant_id: str,
        file_type: str,
        filename: str
    ) -> str:
        """
        Generate a consistent S3 key structure

        Args:
            tenant_id: Tenant ID
            file_type: Type of file (videos, documents, thumbnails, etc.)
            filename: Original filename

        Returns:
            S3 key in format: tenants/{tenant_id}/{file_type}/{filename}
        """
        # Clean filename - remove special characters
        clean_filename = "".join(c for c in filename if c.isalnum() or c in ('_', '-', '.'))

        # Add timestamp to avoid collisions
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(clean_filename)
        unique_filename = f"{name}_{timestamp}{ext}"

        return f"tenants/{tenant_id}/{file_type}/{unique_filename}"


# Singleton instance
_s3_service = None


def get_s3_service() -> S3Service:
    """Get or create S3 service singleton"""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service

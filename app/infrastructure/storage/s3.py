from __future__ import annotations

import boto3
from botocore.exceptions import ClientError
from django.conf import settings

from app.domain.exceptions import FileStorageError
from app.domain.ports import FileStorage


class S3FileStorage(FileStorage):
    def __init__(self):
        self.client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL or None,
            region_name=settings.AWS_S3_REGION_NAME or None,
        )
        self.bucket = settings.AWS_STORAGE_BUCKET_NAME

    def save_file(self, file_path: str, data: bytes) -> str:
        try:
            self.client.put_object(Bucket=self.bucket, Key=file_path, Body=data)
        except ClientError as e:
            raise FileStorageError(f"S3 upload failed: {e}")
        return file_path

    def read_file(self, file_path: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=file_path)
            return response["Body"].read()
        except ClientError as e:
            raise FileStorageError(f"S3 read failed: {e}")

    def delete_file(self, file_path: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=file_path)
        except ClientError as e:
            raise FileStorageError(f"S3 delete failed: {e}")

    def file_exists(self, file_path: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=file_path)
            return True
        except ClientError:
            return False

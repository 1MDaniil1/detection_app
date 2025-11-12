import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
import uuid 
import os
import logging

logger = logging.getLogger(__name__)

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'admin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'admin123')
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'images')

s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False 
)

def ensure_bucket_exists():
    """Создаёт bucket если не существует"""
    try:
        s3_client.head_bucket(Bucket=MINIO_BUCKET)
        logger.info(f"Bucket {MINIO_BUCKET} already exists")
    except ClientError:
        s3_client.create_bucket(Bucket=MINIO_BUCKET)
        logger.info(f"Bucket {MINIO_BUCKET} created")

ensure_bucket_exists()

async def upload_to_minio(file: UploadFile) -> str:
    """Загружает файл из UploadFile в MinIO"""
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"original_{uuid.uuid4()}.{file_extension}"
    
    try:
        file_content = await file.read()
        
        s3_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type
        )
        
        url = f"http://localhost:9000/{MINIO_BUCKET}/{unique_filename}"
        logger.info(f"Original file uploaded: {url}")
        return url
        
    except Exception as e:
        logger.error(f"MinIO upload failed: {str(e)}")
        raise ValueError(f"MinIO upload failed: {str(e)}")

def upload_bytes_to_minio(file_bytes: bytes, filename: str, content_type: str) -> str:
    """Загружает bytes в MinIO"""
    try:
        s3_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=filename,
            Body=file_bytes,
            ContentType=content_type
        )
        
        url = f"http://localhost:9000/{MINIO_BUCKET}/{filename}"
        logger.info(f"Processed image saved: {url}")
        return url
        
    except Exception as e:
        logger.error(f"MinIO bytes upload failed: {str(e)}")
        raise e
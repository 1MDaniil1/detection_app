import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from fastapi import UploadFile
import uuid 
import os

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'http://minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'admin')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'admin123')
MINIO_BUCKET = os.getenv('MINIO_BUCKET', 'images')

# Клиент S3 (MinIO-compatible)
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
    aws_session_token=None,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

# Создаем bucket при старте
try:
    s3_client.head_bucket(Bucket=MINIO_BUCKET)
    print(f"Bucket {MINIO_BUCKET} already exists")
except ClientError:
    s3_client.create_bucket(Bucket=MINIO_BUCKET)
    print(f"Bucket {MINIO_BUCKET} created")

async def upload_to_minio(file: UploadFile) -> str:
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"
    
    file_content = await file.read()
    try:
        s3_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=unique_filename,
            Body=file_content,
            ContentType=file.content_type
        )
        
        # Для фронтенда используем localhost, а не внутренний адрес
        url = f"http://localhost:9000/{MINIO_BUCKET}/{unique_filename}"
        
        # Сделаем файл публичным
        s3_client.put_object_acl(
            Bucket=MINIO_BUCKET,
            Key=unique_filename,
            ACL='public-read'
        )
        
        return url
    except Exception as e:
        raise ValueError(f"MinIO upload failed: {str(e)}")
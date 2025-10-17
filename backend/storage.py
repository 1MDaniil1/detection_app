import boto3
from botocore.exceptions import NoCredentialsError
from fastapi import UploadFile
import uuid 

MINIO_ENDPOINT = 'http://minio:9000' 
MINIO_ACCESS_KEY = 'admin'
MINIO_SECRET_KEY = 'admin123'
MINIO_BUCKET = 'images'

# Клиент S3 (MinIO-compatible)
s3_client = boto3.client(
    's3',
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY
)

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
        #presigned URL (для публичного доступа, expires in 1 hour)
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': MINIO_BUCKET, 'Key': unique_filename},
            ExpiresIn=3600
        )
        return url
    except NoCredentialsError:
        raise ValueError("MinIO credentials not found")
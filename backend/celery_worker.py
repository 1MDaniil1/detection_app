from celery import Celery
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from database import SessionLocal, Detection, get_db
from detection_model import detect_objects
import io
import os
import uuid
import boto3
from botocore.exceptions import NoCredentialsError
import redis
import json


# Celery configuration
celery = Celery(
    'worker',
    broker=os.getenv('REDIS_URL', 'redis://redis:6379/0'),
    backend=os.getenv('REDIS_URL', 'redis://redis:6379/0')
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_routes={
        'tasks.process_detection': {'queue': 'detection'}
    }
)

# MinIO client (синхронная версия для Celery)
minio_client = boto3.client(
    's3',
    endpoint_url=os.getenv('MINIO_ENDPOINT', 'http://minio:9000'),
    aws_access_key_id=os.getenv('MINIO_ACCESS_KEY', 'admin'),
    aws_secret_access_key=os.getenv('MINIO_SECRET_KEY', 'admin123'),
    aws_session_token=None,
    config=boto3.session.Config(signature_version='s3v4'),
    verify=False
)

def upload_to_minio_sync(file_content: bytes, filename: str, content_type: str) -> str:
    """Синхронная версия загрузки в MinIO для Celery"""
    try:
        file_extension = filename.split('.')[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        bucket_name = os.getenv('MINIO_BUCKET', 'images')
        
        # Создаем bucket если не существует
        try:
            minio_client.head_bucket(Bucket=bucket_name)
        except:
            minio_client.create_bucket(Bucket=bucket_name)
        
        minio_client.put_object(
            Bucket=bucket_name,
            Key=unique_filename,
            Body=file_content,
            ContentType=content_type
        )
        
        # Простой URL для MinIO (без ACL)
        return f"http://localhost:9000/{bucket_name}/{unique_filename}"
        
    except Exception as e:
        raise Exception(f"MinIO upload failed: {str(e)}")
    
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)

@celery.task(bind=True)
def process_detection_task(self, image_data: bytes, filename: str, content_type: str):
    task_id = self.request.id
    print(f"🎯 CELERY TASK STARTED: {task_id}")
    print(f"📧 Filename: {filename}")
    print(f"📦 Image data size: {len(image_data)} bytes")
    
    try:
        # 1. Обновляем статус в Redis
        import redis
        redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        redis_client.setex(f"task:{task_id}:status", 3600, "Starting detection...")
        print("✅ Redis status updated: Starting detection...")
        
        # 2. Пытаемся выполнить детекцию
        print("🔍 Attempting to call detect_objects...")
        bboxes, processed_img = detect_objects(image_data)
        print(f"✅ Detection completed, found {len(bboxes)} objects")
        
        # 3. Обновляем статус
        redis_client.setex(f"task:{task_id}:status", 3600, "Saving results...")
        print("✅ Redis status updated: Saving results...")
        
        # 4. Сохраняем обработанное изображение
        print("💾 Saving processed image...")
        img_byte_arr = io.BytesIO()
        processed_img.save(img_byte_arr, format='PNG')
        img_byte_arr.seek(0)
        processed_image_data = img_byte_arr.getvalue()
        
        # 5. Загружаем в MinIO
        print("☁️ Uploading to MinIO...")
        original_url = upload_to_minio_sync(image_data, filename, content_type)
        processed_url = upload_to_minio_sync(processed_image_data, f"processed_{filename}", "image/png")
        
        # 6. Сохраняем в базу
        print("💾 Saving to database...")
        db = SessionLocal()
        try:
            detection = Detection(
                image_name=filename,
                bounding_boxes=bboxes,
                storage_path=processed_url
            )
            db.add(detection)
            db.commit()
            db.refresh(detection)
            
            result = {
                "status": "success",
                "detection_id": detection.id,
                "bounding_boxes": bboxes,
                "original_image_url": original_url,
                "processed_image_url": processed_url,
                "veins_found": len(bboxes)
            }
            
            # 7. Финальный статус
            redis_client.setex(f"task:{task_id}:status", 3600, "completed")
            redis_client.setex(f"task:{task_id}:result", 3600, json.dumps(result))
            print(f"🎉 TASK COMPLETED SUCCESSFULLY: {task_id}")
            
            return result
            
        except Exception as e:
            db.rollback()
            print(f"❌ Database error: {str(e)}")
            raise e
        finally:
            db.close()
            
    except Exception as e:
        print(f"❌ CELERY TASK FAILED: {task_id}")
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()  # Это покажет полный стек вызовов
        
        # Обновляем статус ошибки
        try:
            redis_client.setex(f"task:{task_id}:status", 3600, "failed")
            redis_client.setex(f"task:{task_id}:error", 3600, str(e))
            print("✅ Error status saved to Redis")
        except:
            print("❌ Failed to save error status to Redis")
        
        return {
            "status": "error",
            "error": str(e)
        }
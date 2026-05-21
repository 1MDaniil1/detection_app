import io
import json
import os
import traceback
import uuid

import boto3
import redis
from celery import Celery

from database import Detection, SessionLocal
from detection_model import detect_objects

celery = Celery(
    "worker",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

minio_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
    aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "admin"),
    aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "admin123"),
    aws_session_token=None,
    config=boto3.session.Config(signature_version="s3v4"),
    verify=False,
)

MINIO_BUCKET = os.getenv("MINIO_BUCKET", "images")
MINIO_PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "http://127.0.0.1:9000")


def ensure_public_bucket(bucket_name: str) -> None:
    try:
        minio_client.head_bucket(Bucket=bucket_name)
    except Exception:
        minio_client.create_bucket(Bucket=bucket_name)

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
            }
        ],
    }
    minio_client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))


def upload_to_minio_sync(file_content: bytes, filename: str, content_type: str) -> str:
    try:
        file_extension = filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        ensure_public_bucket(MINIO_BUCKET)

        minio_client.put_object(
            Bucket=MINIO_BUCKET,
            Key=unique_filename,
            Body=file_content,
            ContentType=content_type,
        )

        return f"{MINIO_PUBLIC_ENDPOINT}/{MINIO_BUCKET}/{unique_filename}"
    except Exception as e:
        raise Exception(f"MinIO upload failed: {e}")


redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)


@celery.task(bind=True)
def process_detection_task(self, image_data: bytes, filename: str, content_type: str):
    task_id = self.request.id

    try:
        redis_client.setex(f"task:{task_id}:status", 3600, "Starting detection...")

        bboxes, processed_img = detect_objects(image_data)

        redis_client.setex(f"task:{task_id}:status", 3600, "Saving results...")

        img_byte_arr = io.BytesIO()
        processed_img.save(img_byte_arr, format="PNG")
        img_byte_arr.seek(0)
        processed_image_data = img_byte_arr.getvalue()

        original_url = upload_to_minio_sync(image_data, filename, content_type)
        processed_url = upload_to_minio_sync(
            processed_image_data,
            f"processed_{filename}",
            "image/png",
        )

        db = SessionLocal()
        try:
            detection = Detection(
                image_name=filename,
                bounding_boxes=bboxes,
                storage_path=processed_url,
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
                "veins_found": len(bboxes),
            }

            redis_client.setex(f"task:{task_id}:status", 3600, "completed")
            redis_client.setex(f"task:{task_id}:result", 3600, json.dumps(result))

            return result
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
    except Exception as e:
        traceback.print_exc()
        try:
            redis_client.setex(f"task:{task_id}:status", 3600, "failed")
            redis_client.setex(f"task:{task_id}:error", 3600, str(e))
        except Exception:
            pass

        return {"status": "error", "error": str(e)}

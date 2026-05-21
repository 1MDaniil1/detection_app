import json
import logging
import os

from celery import Celery
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import Detection, get_db

logger = logging.getLogger(__name__)

app = FastAPI(title="Vein Detection API", version="1.0.0")

celery_app = Celery(
    "api",
    broker=os.getenv("REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://redis:6379/0"),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Vein Detection API is running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "vein-detection-api"}


@app.post("/detect")
async def detect_async(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    try:
        image_bytes = await file.read()
        task = celery_app.send_task(
            "celery_worker.process_detection_task",
            kwargs={
                "image_data": image_bytes,
                "filename": file.filename,
                "content_type": file.content_type,
            },
        )

        return {
            "message": "Detection started in background",
            "task_id": task.id,
            "status_url": f"/detect/status/{task.id}",
        }
    except Exception as e:
        logger.error(f"Async detection error: {e}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {e}")


@app.get("/detect/status/{task_id}")
async def get_detection_status(task_id: str):
    try:
        import redis

        redis_client = redis.Redis(host="redis", port=6379, db=0, decode_responses=True)
        redis_status = redis_client.get(f"task:{task_id}:status")
        if not redis_status:
            return {"state": "PENDING", "status": "Waiting..."}

        if redis_status == "completed":
            result_json = redis_client.get(f"task:{task_id}:result")
            if not result_json:
                return {"state": "FAILURE", "status": "completed", "error": "Result not found"}

            return {
                "state": "SUCCESS",
                "status": "completed",
                "result": json.loads(result_json),
            }

        if redis_status == "failed":
            error = redis_client.get(f"task:{task_id}:error")
            return {
                "state": "FAILURE",
                "status": "failed",
                "error": error or "Detection task failed",
            }

        return {"state": "PROGRESS", "status": redis_status}
    except Exception as e:
        logger.error(f"Redis status read failed: {e}")
        return {"state": "PENDING", "status": "Waiting..."}


@app.get("/detections")
async def get_detections(db: Session = Depends(get_db)):
    return db.query(Detection).all()

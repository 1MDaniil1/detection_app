from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import io
from database import get_db, Detection
from detection_model import detect_objects
from storage import upload_to_minio
from celery_worker import process_detection_task
import uuid

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Detection API is running"}

# Синхронная версия (оставляем как запасной вариант)
@app.post("/detect")
async def detect(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        image_bytes = await file.read()
        bboxes, img = detect_objects(image_bytes)
        storage_url = await upload_to_minio(file)
        
        detection = Detection(
            image_name=file.filename,
            bounding_boxes=bboxes,
            storage_path=storage_url
        )
        db.add(detection)
        db.commit()
        db.refresh(detection)
        
        return {
            "message": "Detection successful",
            "detection_id": detection.id,
            "bounding_boxes": bboxes,
            "image_url": storage_url,
            "veins_found": len(bboxes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

# Асинхронная версия с Celery
@app.post("/detect-async")
async def detect_async(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        image_bytes = await file.read()
        
        # Запускаем задачу в Celery
        task = process_detection_task.delay(
            image_data=image_bytes,
            filename=file.filename,
            content_type=file.content_type
        )
        
        return {
            "message": "Detection started in background",
            "task_id": task.id,
            "status_url": f"/detect/status/{task.id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")

@app.get("/detect/status/{task_id}")
async def get_detection_status(task_id: str):
    from celery.result import AsyncResult
    task_result = AsyncResult(task_id)
    
    if task_result.state == 'PENDING':
        response = {
            'state': task_result.state,
            'status': 'Pending...'
        }
    elif task_result.state == 'PROGRESS':
        response = {
            'state': task_result.state,
            'status': task_result.info.get('status', '')
        }
    elif task_result.state == 'SUCCESS':
        response = {
            'state': task_result.state,
            'result': task_result.result
        }
    else:  # FAILURE
        response = {
            'state': task_result.state,
            'error': str(task_result.info)
        }
    
    return response

@app.get("/detections")
async def get_detections(db: Session = Depends(get_db)):
    detections = db.query(Detection).all()
    return detections
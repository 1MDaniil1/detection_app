from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import io
import uuid
import logging
from database import get_db, Detection
from detection_model import detect_objects
from storage import upload_to_minio, upload_bytes_to_minio
from celery_worker import process_detection_task
import json

# Настройка логирования
logger = logging.getLogger(__name__)

app = FastAPI(title="Vein Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Vein Detection API is running"}

@app.get("/health")
async def health_check():
    """Проверка здоровья сервиса"""
    return {
        "status": "healthy",
        "service": "vein-detection-api"
    } 

@app.post("/detect")
async def detect_async(file: UploadFile = File(...)):
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        image_bytes = await file.read()
        
        # Запуск фоновой задачи
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
        logger.error(f"Async detection error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")
    

@app.get("/detect/status/{task_id}")
async def get_detection_status(task_id: str):
    print(f"🔍 Frontend запрашивает статус задачи: {task_id}")
    
    try:
        import redis
        redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)
        redis_status = redis_client.get(f"task:{task_id}:status")
        if redis_status:
            print(f"Статус из Redis: {redis_status}")
            if redis_status == "completed":
                result_json = redis_client.get(f"task:{task_id}:result")
                if result_json:
                    result = json.loads(result_json)
                    print(f"✅ Задача завершена, возвращаем результат")
                    return {
                        "state": "SUCCESS",
                        "status": "completed", 
                        "result": result 
                    }
                else:
                    print(f"❌ Статус completed, но результат не найден")
                    return {"state": "FAILURE", "status": "completed", "error": "Result not found"}
            else:
                return {"state": "PROGRESS", "status": redis_status}
    except Exception as e:
        print(f"❌ Ошибка Redis: {e}")
    '''
    from celery.result import AsyncResult
    task_result = AsyncResult(task_id)
    print(f"Статус из Celery: {task_result.state}")
    return {"state": task_result.state, "status": "Waiting..."}
    '''


@app.get("/detections")
async def get_detections(db: Session = Depends(get_db)):
    """Получение всех детекций"""
    detections = db.query(Detection).all()
    return detections
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import io
from database import get_db, Detection
from detection_model import detect_objects
from storage import upload_to_minio  # Новый импорт

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/detect")
async def detect(file: UploadFile = File(...), db: Session = Depends(get_db)):
    image_bytes = await file.read()
    bboxes, img = detect_objects(image_bytes)
    
    storage_url = await upload_to_minio(file) 
    
    detection = Detection(image_name=file.filename, bounding_boxes=bboxes, storage_path=storage_url)
    db.add(detection)
    db.commit()
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    return StreamingResponse(img_byte_arr, media_type="image/png")
from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import time
import os
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://postgres:postgres@postgres:5432/mydatabase")

def create_engine_with_retry():
    """Создаёт engine с повторными попытками подключения"""
    for i in range(10):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect() as conn:
                logger.info("✅ Database connection successful")
            return engine
        except Exception as e:
            if i < 9:
                logger.warning(f"Database connection failed, retrying... ({i+1}/10)")
                time.sleep(2)
            else:
                logger.error("❌ Database connection failed after 10 attempts")
                raise e

engine = create_engine_with_retry()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    image_name = Column(String, index=True)
    bounding_boxes = Column(JSON)
    storage_path = Column(String)

def init_db():
    """Инициализация таблиц БД"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.warning(f"Database table creation note: {e}")

# Создаём таблицы при импорте
init_db()

def get_db():
    """Dependency для получения сессии БД"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
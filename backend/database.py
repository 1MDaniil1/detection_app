import logging
import os
import time

from sqlalchemy import JSON, Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/mydatabase")


def create_engine_with_retry():
    for i in range(10):
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect():
                logger.info("Database connection successful")
            return engine
        except Exception as e:
            if i < 9:
                logger.warning(f"Database connection failed, retrying... ({i + 1}/10)")
                time.sleep(2)
            else:
                logger.error("Database connection failed after 10 attempts")
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
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.warning(f"Database table creation note: {e}")


init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

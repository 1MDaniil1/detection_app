from database import engine, Base
from sqlalchemy import text

try:

    with engine.connect() as conn:
        result = conn.execute(text("SELECT version()"))
        print("✅ PostgreSQL подключен:", result.scalar())
        
    Base.metadata.create_all(bind=engine)
    print("✅ Таблицы созданы")
    
    # Проверяем таблицы
    with engine.connect() as conn:
        result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
        tables = [row[0] for row in result]
        print("✅ Таблицы в базе:", tables)
        
except Exception as e:
    print("❌ Ошибка:", e)
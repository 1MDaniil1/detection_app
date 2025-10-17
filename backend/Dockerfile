# Используем более легкий базовый образ
FROM python:3.10-slim-bullseye

WORKDIR /app

# Устанавливаем только необходимые системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Копируем только requirements сначала для лучшего кэширования
COPY requirements.txt .

# Устанавливаем Python зависимости с очисткой кэша
RUN pip install --no-cache-dir -r requirements.txt

# Копируем только необходимые файлы
COPY *.py ./
COPY model/ ./model/

# Удаляем ненужные файлы
RUN find . -name "*.pyc" -delete && \
    find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
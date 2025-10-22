FROM python:3.10-slim-bullseye

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc g++ libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev \
    && rm -rf /var/lib/apt/lists/* && apt-get clean

COPY requirements-base.txt .
RUN pip install --timeout 300 -r requirements-base.txt

COPY requirements.txt .
RUN pip install --timeout 300 -r requirements.txt

COPY *.py ./
COPY model/ ./model/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
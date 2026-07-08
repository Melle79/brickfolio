FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

ENV DB_PATH=/data/brickfolio.db \
    FRONTEND_DIR=/app/frontend \
    PYTHONUNBUFFERED=1

VOLUME /data
EXPOSE 8300

WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300"]

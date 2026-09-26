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
# Verbindungen länger offen halten als der Zwischenserver davor (cloudflared:
# 90 s). Mit uvicorns 5 s schloss der Server eine ruhende Verbindung, während
# der Tunnel gerade eine Anfrage darüber schickte – „EOF“, beim Nutzer ein
# 502 mitten im laufenden Betrieb (gesehen am 26.09.2026 bei trades/sync).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8300", "--timeout-keep-alive", "120"]

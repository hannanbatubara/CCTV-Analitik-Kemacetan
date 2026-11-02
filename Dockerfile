FROM python:3.12-slim

# libgl1/libglib2.0-0: dibutuhkan OpenCV; tzdata: timestamp WIB
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=Asia/Jakarta \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    PYTHONUNBUFFERED=1

WORKDIR /app

# torch versi CPU saja (jauh lebih kecil); inferensi memakai OpenVINO
RUN pip install --no-cache-dir torch==2.15.0 torchvision==0.29.2 --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py *.yaml ./
COPY data ./data
# model TIDAK ikut image: di-mount sebagai volume (lihat docker-compose.yml)

CMD ["python", "worker.py"]

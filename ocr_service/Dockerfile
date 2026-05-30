FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# libgl1 + libglib2.0-0 are required by opencv-python (PaddleOCR dependency)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --default-timeout=120 --retries=10 -r /app/requirements.txt

# Pre-download PaddleOCR Arabic models so first request is fast.
# Falls back gracefully if network is unavailable during build.
RUN python -c "from paddleocr import PaddleOCR; PaddleOCR(lang='ar', use_angle_cls=False, show_log=False)" \
    || echo "PaddleOCR Arabic model pre-download skipped — will download on first request"

COPY app.py /app/app.py

EXPOSE 9000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9000", "--workers", "1"]

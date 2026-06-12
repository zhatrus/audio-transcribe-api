# CPU image (default). For GPU use Dockerfile.gpu / docker-compose.gpu.yml.
FROM python:3.11-slim

ARG DEBIAN_FRONTEND=noninteractive

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HOME=/home/app/.cache/huggingface \
    DATA_DIR=/data \
    OMP_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /home/app

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /home/app/app

RUN mkdir -p /data /home/app/.cache/huggingface
VOLUME ["/home/app/.cache/huggingface", "/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
except Exception:
    raise SystemExit(1)
PY

CMD ["python", "-m", "app.main"]

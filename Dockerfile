ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive
ARG PIP_EXTRA_INDEX_URL=
ARG PIP_INDEX_URL=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_DISABLE_TELEMETRY=1 \
    OMP_NUM_THREADS=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    python3-dev \
    build-essential \
    git \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /home/app

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /home/app/app

VOLUME ["/home/app/.cache/huggingface", "/tmp/audio-transcribe-api"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5)
except Exception:
    raise SystemExit(1)
PY

CMD ["python", "-m", "app.main"]

ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg python3-dev build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /home/app
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY app /home/app/app
EXPOSE 8000
CMD ["python", "-m", "app.main"]

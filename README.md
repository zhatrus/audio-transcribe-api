# Audio Transcribe API

Self-hosted transcription API with speaker diarization.
Supports Ukrainian, Russian, English and auto-detection.

## Features

- Transcription via faster-whisper (CTranslate2)
- Speaker diarization via pyannote.audio 3.1
- Optimized for NVIDIA GPU (CUDA) or CPU
- Handles files up to 3 hours
- Simple FastAPI REST interface

## Quick start

```bash
cp .env.example .env   # edit HF_TOKEN, device, model size
make build
make up
```

## API

- `GET /health` — health check
- `POST /transcribe` — multipart form:
  - `file` — audio/video
  - `language` — `auto|uk|ru|en`
  - `diarize` — `true|false`
  - `min_speakers` — optional
  - `max_speakers` — optional

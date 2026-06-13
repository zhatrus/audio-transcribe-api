# Audio Transcribe API

Self-hosted, **asynchronous** transcription API with optional speaker diarization.
Supports Ukrainian, Russian, English and auto-detection.

## How it works

1. `POST /transcribe` — upload a file, get a `job_id` back **immediately**.
2. `GET /jobs/{job_id}` — poll for the result (`queued` → `processing` → `done`/`error`).
3. Results auto-delete: hard TTL from completion, plus a shorter TTL after the
   first time the result was fetched. You can also delete manually.

The uploaded audio is removed as soon as processing finishes — only the JSON
result stays in the cache. The model is loaded once and unloaded after a
configurable idle period.

## Features

- Transcription via faster-whisper (CTranslate2)
- Speaker diarization via pyannote.audio 3.1 (optional, needs `HF_TOKEN`)
- NVIDIA GPU (CUDA) or CPU
- Async job queue — long files never block the request
- Persistent job store (survives restarts), auto-cleanup by TTL
- Optional API-key auth

## Requirements

- Docker + Docker Compose
- For GPU: NVIDIA driver + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- A Hugging Face token (`HF_TOKEN`) only if you use diarization. Accept the
  model terms for `pyannote/speaker-diarization-3.1` on huggingface.co.

## Quick start

```bash
make env            # create .env from template, then edit it
# edit .env: set HF_TOKEN (for diarization), API_KEY (recommended), DEVICE

# CPU:
make cpu            # build + run the CPU variant

# GPU:
make gpu            # build + run the GPU variant
```

Check it is alive:

```bash
make health         # -> {"status":"ok"}
```

## Common commands

| Action | Command |
|---|---|
| Create `.env` | `make env` |
| Build image | `make build` (CPU) / `make COMPOSE_FILE=docker-compose.gpu.yml build` |
| Start | `make up` / `make cpu` / `make gpu` |
| Stop | `make down` |
| Restart | `make restart` |
| **Update after code changes** | `make update` (rebuild + recreate) |
| Logs | `make logs` |
| Status | `make ps` |
| Shell into container | `make shell` |
| Remove everything (volumes + image) | `make clean` |

For the GPU variant, prefix the compose file, e.g.:

```bash
make COMPOSE_FILE=docker-compose.gpu.yml update
```

## Configuration (`.env`)

| Variable | Default | Description |
|---|---|---|
| `DEVICE` | `cpu` | `cpu` / `gpu` / `cuda` / `auto` (gpu falls back to cpu if no CUDA) |
| `MODEL_SIZE` | `medium` | `tiny`/`base`/`small`/`medium`/`large-v3` |
| `COMPUTE_TYPE` | auto | empty = `float16` on GPU, `int8` on CPU |
| `MODEL_IDLE_TIMEOUT_MIN` | `30` | unload model after N idle minutes (`0` = never) |
| `LANGUAGE` | `auto` | default language hint |
| `HF_TOKEN` | — | required only for diarization |
| `DATA_DIR` | `/data` | base dir for uploads + cached results |
| `RESULT_TTL_HOURS` | `24` | hard auto-delete of any finished job |
| `DELIVERED_TTL_HOURS` | `6` | delete N hours after first result fetch |
| `CLEANUP_INTERVAL_MIN` | `10` | how often cleanup runs |
| `MAX_UPLOAD_MB` | `1024` | reject larger uploads (`0` = unlimited) |
| `API_KEY` | — | if set, requests need header `X-API-Key` |
| `WEBHOOK_URL` | — | if set, finished jobs are POSTed here as JSON |
| `WEBHOOK_TIMEOUT_SEC` | `15` | webhook request timeout |
| `PORT` | `8000` | host port |
| `WORKERS` | `1` | keep at 1 (single background worker) |

## API

All endpoints except `/health` require `X-API-Key: <API_KEY>` **if** `API_KEY` is set.

### `GET /health`
```json
{ "status": "ok" }
```

### `POST /transcribe` (multipart/form-data)
Fields: `file` (audio/video), `language` (`auto|uk|ru|en`), `diarize` (`true|false`),
`min_speakers`, `max_speakers` (optional), `subtitles` (`true|false` — adds an
`srt` field), `webhook_url` (optional — overrides `WEBHOOK_URL`).

Notes:
- Diarization is **best-effort**: if it fails, the job still returns the
  transcription with `speakers: null` and a `diarization_error` field (no hard
  failure). Audio is normalized to mono 16 kHz before diarization to avoid the
  pyannote tensor-size error on video/stereo inputs.
- With `subtitles=true`, the result includes `srt` (SRT built from segments;
  prefixed with `[SPEAKER_xx]` when diarization succeeded).

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "X-API-Key: $API_KEY" \
  -F "file=@meeting.mp3" \
  -F "language=uk" \
  -F "diarize=true"
```
Response (immediate):
```json
{ "job_id": "a1b2c3...", "status": "queued" }
```

### `GET /jobs/{job_id}`
```bash
curl http://localhost:8000/jobs/a1b2c3 -H "X-API-Key: $API_KEY"
```
While processing:
```json
{ "id": "a1b2c3", "status": "processing", ... }
```
On success (`status: "done"`) the `result` object holds `text`, `segments`,
`language`, `duration`, and `speakers` (if diarized). The first fetch sets
`delivered_at` and starts the post-delivery TTL.

On failure: `status: "error"` with an `error` message.

### `DELETE /jobs/{job_id}`
Delete one job and its cached result.

### `DELETE /jobs`
Delete all jobs.

### Webhook (no polling)
If `WEBHOOK_URL` is set (or a `webhook_url` field is sent with the upload), the
service POSTs the finished job to that URL as JSON when it reaches `done` or
`error` — the same body as `GET /jobs/{id}`. Ideal for long recordings where
polling would be wasteful. The request is retried once on failure.

## n8n flow

1. **HTTP Request** → `POST /transcribe` (multipart, send the binary file) → store `job_id`.
2. **Wait / loop** → `GET /jobs/{job_id}`; branch on `status`:
   - `queued` / `processing` → wait and poll again,
   - `error` → handle error,
   - `done` → use `result`.
3. Optionally `DELETE /jobs/{job_id}` after consuming the result (otherwise the
   TTL cleans it up automatically).

## Local development (without Docker)

```bash
py -3 -m venv .venv && . .venv/Scripts/activate   # Windows
pip install -r app/requirements.txt
set DATA_DIR=./_data
python -m app.main
```

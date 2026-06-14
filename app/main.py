"""Audio Transcription API — async job-based interface.

Flow:
  1. POST /transcribe  -> uploads file, returns {job_id, status} immediately.
  2. GET  /jobs/{id}   -> queued | processing | error | done (+ result).
  3. DELETE /jobs/{id} -> remove one job; DELETE /jobs -> remove all.

Finished jobs are auto-deleted by a background cleanup loop (hard TTL from
completion, shorter TTL after the first result fetch).
"""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from . import stt, store, worker
from .auth import require_api_key
from .config import get_settings
from .model_manager import evict_idle
from .utils import new_job_id, save_upload

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "info").upper(),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app.main")


async def _maintenance_loop() -> None:
    interval = max(60, get_settings().cleanup_interval_min * 60)
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.get_running_loop().run_in_executor(None, store.cleanup_expired)
            evict_idle()
        except Exception:  # noqa: BLE001
            logger.exception("Maintenance loop iteration failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.ensure_dirs()
    logger.info(
        "Starting: model=%s device=%s compute=%s cache=%s",
        s.model_size,
        s.device,
        s.compute_type,
        s.cache_dir,
    )

    # Warm the model in a thread so config errors surface early without blocking.
    async def _warm():
        try:
            from .stt import preload

            await asyncio.get_running_loop().run_in_executor(None, preload)
            logger.info("Model preloaded")
        except Exception:  # noqa: BLE001
            logger.exception("Model preload failed (will retry on first request)")

    worker.requeue_pending()
    tasks = [
        asyncio.create_task(worker.worker_loop()),
        asyncio.create_task(_maintenance_loop()),
        asyncio.create_task(_warm()),
    ]
    try:
        yield
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Audio Transcription API", version="2.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Surface unexpected errors as JSON instead of a bare 500 body."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/v1/audio/transcriptions", dependencies=[Depends(require_api_key)])
async def openai_transcriptions(
    file: UploadFile = File(...),
    model: str = Form("whisper-1"),  # noqa: ARG001 — accepted for compatibility, ignored
    language: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    job_id = new_job_id()
    upload_path = await save_upload(file, job_id)
    try:
        lang = None if language in (None, "auto") else language
        result = await asyncio.get_running_loop().run_in_executor(
            None, stt.transcribe, upload_path, lang
        )
    finally:
        upload_path.unlink(missing_ok=True)

    return {"text": result["text"]}


@app.post("/transcribe", dependencies=[Depends(require_api_key)])
async def transcribe_endpoint(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    diarize: bool = Form(False),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
    subtitles: bool = Form(False),
    webhook_url: str | None = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    job_id = new_job_id()
    upload_path = await save_upload(file, job_id)

    params = {
        "language": language,
        "diarize": diarize,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
        "subtitles": subtitles,
        "webhook_url": webhook_url or None,
    }
    store.create_job(file.filename, params, upload_path, job_id=job_id)
    worker.enqueue(job_id)

    logger.info("Queued job %s (%s)", job_id, file.filename)
    return {"job_id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job_endpoint(job_id: str):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Record the fetch; first fetch of a finished job starts the delivery TTL.
    if job.get("status") in {"done", "error"}:
        job = store.mark_fetched(job_id) or job

    return store.public_view(job)


@app.delete("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def delete_job_endpoint(job_id: str):
    if not store.delete_job(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": job_id}


@app.delete("/jobs", dependencies=[Depends(require_api_key)])
def delete_all_endpoint():
    removed = store.delete_all()
    return {"deleted_count": removed}


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host=s.host,
        port=s.port,
        workers=s.workers,
        log_level=s.log_level,
    )

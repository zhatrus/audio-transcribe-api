"""Single background worker that processes the transcription queue sequentially.

Jobs are processed one at a time to keep GPU/CPU memory predictable. The heavy,
synchronous transcription runs in a thread executor so the event loop (and the
health endpoint) stays responsive.
"""
import asyncio
import logging
import time
from pathlib import Path

from . import store
from .diarization import run_diarization
from .stt import transcribe

logger = logging.getLogger("app.worker")

_queue: "asyncio.Queue[str]" = asyncio.Queue()


def enqueue(job_id: str) -> None:
    _queue.put_nowait(job_id)


def _process(job: dict) -> dict:
    """Runs in a thread; returns the transcription result dict."""
    path = Path(job["upload_path"])
    params = job.get("params", {})
    language = params.get("language")
    lang = None if not language or language == "auto" else language

    transcription = transcribe(path, language=lang)
    speakers = None
    if params.get("diarize"):
        speakers = run_diarization(
            path,
            min_speakers=params.get("min_speakers"),
            max_speakers=params.get("max_speakers"),
        )

    return {
        "file": job.get("filename"),
        "language": transcription["language"],
        "duration": transcription["duration"],
        "text": transcription["text"],
        "segments": transcription["segments"],
        "speakers": speakers,
    }


async def _run_one(job_id: str) -> None:
    job = store.get_job(job_id)
    if job is None:
        return  # deleted before we got to it
    if job.get("status") != "queued":
        return  # already handled (e.g. after a restart re-enqueue)

    store.update_job(job_id, status="processing", started_at=time.time())
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _process, job)
        store.update_job(
            job_id,
            status="done",
            finished_at=time.time(),
            result=result,
            error=None,
        )
        logger.info("Job %s done", job_id)
    except Exception as exc:  # noqa: BLE001 - surface any model/IO failure to client
        logger.exception("Job %s failed", job_id)
        store.update_job(
            job_id,
            status="error",
            finished_at=time.time(),
            error=str(exc),
        )
    finally:
        # The uploaded audio is never kept around once processing is over.
        fresh = store.get_job(job_id)
        if fresh and fresh.get("upload_path"):
            try:
                Path(fresh["upload_path"]).unlink(missing_ok=True)
            except OSError:
                pass
            store.update_job(job_id, upload_path=None)


async def worker_loop() -> None:
    logger.info("Transcription worker started")
    while True:
        job_id = await _queue.get()
        try:
            await _run_one(job_id)
        finally:
            _queue.task_done()


def requeue_pending() -> int:
    """Re-enqueue jobs left queued/processing after a restart."""
    count = 0
    for job in store.list_jobs():
        if job.get("status") in {"queued", "processing"}:
            if job.get("upload_path") and Path(job["upload_path"]).exists():
                store.update_job(job["id"], status="queued")
                enqueue(job["id"])
                count += 1
            else:
                store.update_job(
                    job["id"],
                    status="error",
                    finished_at=time.time(),
                    error="Worker restarted before processing and upload was lost",
                )
    if count:
        logger.info("Re-enqueued %d pending job(s) after restart", count)
    return count

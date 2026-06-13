"""Single background worker that processes the transcription queue sequentially.

Jobs are processed one at a time to keep GPU/CPU memory predictable. The heavy,
synchronous transcription runs in a thread executor so the event loop (and the
health endpoint) stays responsive.
"""
import asyncio
import json
import logging
import time
import urllib.request
from pathlib import Path

from . import store
from .config import get_settings
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
    diarization_error = None
    if params.get("diarize"):
        try:
            speakers = run_diarization(
                path,
                min_speakers=params.get("min_speakers"),
                max_speakers=params.get("max_speakers"),
            )
        except Exception as exc:  # noqa: BLE001 - fall back to transcription-only
            diarization_error = str(exc)
            logger.warning(
                "Diarization failed for job %s, returning transcription only: %s",
                job.get("id"), exc,
            )

    result = {
        "file": job.get("filename"),
        "language": transcription["language"],
        "duration": transcription["duration"],
        "text": transcription["text"],
        "segments": transcription["segments"],
        "speakers": speakers,
    }
    if diarization_error:
        result["diarization_error"] = diarization_error
    if params.get("subtitles"):
        from .formatting import build_srt

        result["srt"] = build_srt(transcription["segments"], speakers)
    return result


def _post_webhook(url: str, payload: dict, timeout: int) -> int:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST", headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return getattr(resp, "status", resp.getcode())


async def _notify_webhook(job: dict) -> None:
    """POST the finished job to its webhook (per-job param overrides env default)."""
    url = (job.get("params") or {}).get("webhook_url") or get_settings().webhook_url
    if not url:
        return
    payload = store.public_view(job)
    timeout = get_settings().webhook_timeout_sec
    loop = asyncio.get_running_loop()
    for attempt in (1, 2):
        try:
            status = await loop.run_in_executor(None, _post_webhook, url, payload, timeout)
            logger.info("Webhook delivered job %s -> HTTP %s", job["id"], status)
            # A successful push counts as delivery -> starts the post-delivery TTL.
            if job.get("delivered_at") is None:
                store.update_job(job["id"], delivered_at=time.time())
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Webhook attempt %d failed for job %s (%s): %s",
                attempt, job["id"], url, exc,
            )
            if attempt == 1:
                await asyncio.sleep(2)
    logger.error("Webhook giving up for job %s", job["id"])


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

    # Notify the webhook (if any) with the final job state.
    final = store.get_job(job_id)
    if final is not None:
        await _notify_webhook(final)


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

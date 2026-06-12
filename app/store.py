"""Persistent job store backed by one JSON file per job in the cache directory.

A job record looks like::

    {
        "id": "...",
        "status": "queued|processing|done|error",
        "filename": "meeting.mp3",
        "params": {...},
        "created_at": 0.0,
        "started_at": null,
        "finished_at": null,
        "delivered_at": null,
        "fetch_count": 0,
        "error": null,
        "result": {...},
        "upload_path": "/tmp/.../uploads/<id>.bin"   # internal, stripped from API
    }

Timestamps are epoch seconds (UTC). Records survive process restarts.
"""
import json
import logging
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

from .config import get_settings

logger = logging.getLogger("app.store")

_lock = threading.Lock()

# Fields that must never be exposed through the API.
_PRIVATE_FIELDS = {"upload_path"}


def _cache_dir() -> Path:
    d = get_settings().cache_dir
    d.mkdir(parents=True, exist_ok=True)
    return d


def _job_path(job_id: str) -> Path:
    return _cache_dir() / f"{job_id}.json"


def _atomic_write(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def create_job(filename: str, params: dict, upload_path: Path, job_id: str | None = None) -> dict:
    job_id = job_id or uuid.uuid4().hex
    job = {
        "id": job_id,
        "status": "queued",
        "filename": filename,
        "params": params,
        "created_at": time.time(),
        "started_at": None,
        "finished_at": None,
        "delivered_at": None,
        "fetch_count": 0,
        "error": None,
        "result": None,
        "upload_path": str(upload_path),
    }
    with _lock:
        _atomic_write(_job_path(job_id), job)
    return job


def get_job(job_id: str) -> Optional[dict]:
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_job(job: dict) -> None:
    with _lock:
        _atomic_write(_job_path(job["id"]), job)


def update_job(job_id: str, **fields) -> Optional[dict]:
    with _lock:
        job = get_job(job_id)
        if job is None:
            return None
        job.update(fields)
        _atomic_write(_job_path(job_id), job)
        return job


def mark_fetched(job_id: str) -> Optional[dict]:
    """Record a result fetch; set delivered_at on the first one."""
    with _lock:
        job = get_job(job_id)
        if job is None:
            return None
        job["fetch_count"] = job.get("fetch_count", 0) + 1
        if job["status"] in {"done", "error"} and job.get("delivered_at") is None:
            job["delivered_at"] = time.time()
        _atomic_write(_job_path(job_id), job)
        return job


def list_jobs() -> list[dict]:
    jobs = []
    for path in _cache_dir().glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                jobs.append(json.load(f))
        except (json.JSONDecodeError, OSError):
            continue
    jobs.sort(key=lambda j: j.get("created_at", 0), reverse=True)
    return jobs


def _remove_upload(job: dict) -> None:
    upload = job.get("upload_path")
    if upload:
        try:
            Path(upload).unlink(missing_ok=True)
        except OSError:
            pass


def delete_job(job_id: str) -> bool:
    with _lock:
        job = get_job(job_id)
        if job is None:
            return False
        _remove_upload(job)
        try:
            _job_path(job_id).unlink(missing_ok=True)
        except OSError:
            pass
        return True


def delete_all() -> int:
    count = 0
    with _lock:
        for path in list(_cache_dir().glob("*.json")):
            try:
                with path.open("r", encoding="utf-8") as f:
                    _remove_upload(json.load(f))
            except (json.JSONDecodeError, OSError):
                pass
            try:
                path.unlink(missing_ok=True)
                count += 1
            except OSError:
                pass
    return count


def public_view(job: dict) -> dict:
    """Strip internal fields before returning a job over the API."""
    return {k: v for k, v in job.items() if k not in _PRIVATE_FIELDS}


def cleanup_expired() -> int:
    """Delete finished jobs past their hard TTL or post-delivery TTL."""
    s = get_settings()
    hard_ttl = s.result_ttl_hours * 3600
    delivered_ttl = s.delivered_ttl_hours * 3600
    now = time.time()
    removed = 0

    for job in list_jobs():
        status = job.get("status")
        if status not in {"done", "error"}:
            continue
        finished = job.get("finished_at") or job.get("created_at") or 0
        delivered = job.get("delivered_at")

        expired = False
        if hard_ttl > 0 and now - finished > hard_ttl:
            expired = True
        elif delivered is not None and delivered_ttl > 0 and now - delivered > delivered_ttl:
            expired = True

        if expired and delete_job(job["id"]):
            removed += 1

    if removed:
        logger.info("Cleanup removed %d expired job(s)", removed)
    return removed

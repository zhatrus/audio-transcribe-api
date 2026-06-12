"""Helpers for safely persisting uploads to a temporary file."""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile

from .config import get_settings

_CHUNK = 1024 * 1024  # 1 MiB


def _suffix(filename: str | None) -> str:
    if not filename:
        return ""
    suffix = Path(filename).suffix
    # Guard against absurdly long or path-like suffixes.
    return suffix[:16] if len(suffix) <= 16 else ""


async def save_upload(file: UploadFile, job_id: str) -> Path:
    """Stream an upload to a UUID-named temp file. Returns its path.

    Enforces ``MAX_UPLOAD_MB`` and never trusts the client-provided filename for
    the on-disk path (avoids traversal and collisions).
    """
    s = get_settings()
    s.upload_dir.mkdir(parents=True, exist_ok=True)
    dest = s.upload_dir / f"{job_id}{_suffix(file.filename)}"
    max_bytes = s.max_upload_bytes

    written = 0
    try:
        with dest.open("wb") as buffer:
            while True:
                chunk = await file.read(_CHUNK)
                if not chunk:
                    break
                written += len(chunk)
                if max_bytes and written > max_bytes:
                    buffer.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds limit of {s.max_upload_mb} MB",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise

    if written == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Empty file")

    return dest


def new_job_id() -> str:
    return uuid.uuid4().hex

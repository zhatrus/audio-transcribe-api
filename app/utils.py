import os
from pathlib import Path
import shutil
from fastapi import UploadFile

UPLOAD_DIR = Path("/tmp/audio-transcribe-api")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile) -> Path:
    if not file.filename:
        raise ValueError("Empty filename")
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return dest

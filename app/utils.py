from pathlib import Path
import shutil
from fastapi import UploadFile

UPLOAD_DIR = Path("/tmp/audio-transcribe-api")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def save_upload(file: UploadFile) -> Path:
    dest = UPLOAD_DIR / file.filename
    with dest.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return dest

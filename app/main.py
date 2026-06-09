import os
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from app.stt import transcribe
from app.diarization import run_diarization

app = FastAPI(title="Audio Transcription API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    language: str = Form("auto"),
    diarize: bool = Form(False),
    min_speakers: int | None = Form(None),
    max_speakers: int | None = Form(None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    from app.utils import save_upload
    path = await save_upload(file)

    try:
        lang = None if language == "auto" else language
        transcription = transcribe(path, language=lang)
        speakers = None

        if diarize:
            speakers = run_diarization(
                path,
                min_speakers=min_speakers,
                max_speakers=max_speakers,
            )

        return JSONResponse(
            {
                "file": file.filename,
                "language": transcription["language"],
                "duration": transcription["duration"],
                "text": transcription["text"],
                "segments": transcription["segments"],
                "speakers": speakers,
            }
        )
    finally:
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        workers=int(os.getenv("WORKERS", "1")),
        log_level=os.getenv("LOG_LEVEL", "info"),
    )

import os
from faster_whisper import WhisperModel
from .utils import UPLOAD_DIR


def get_model():
    model_size = os.getenv("MODEL_SIZE", "medium")
    device = os.getenv("DEVICE", "cpu")
    compute_type = "float16" if device == "gpu" else "int8"
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
    )
    return model


def transcribe(path, language=None):
    model = get_model()
    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
    )

    result = {
        "language": info.language,
        "duration": info.duration,
        "text": "",
        "segments": [],
    }

    for seg in segments:
        result["text"] += seg.text + " "
        result["segments"].append(
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "probability": seg.probability,
            }
        )

    result["text"] = result["text"].strip()
    return result

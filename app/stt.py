"""Speech-to-text via faster-whisper with a cached, idle-evicted model."""
import logging

from faster_whisper import WhisperModel

from .config import get_settings
from .model_manager import LazyModel, register

logger = logging.getLogger("app.stt")


def _load_model() -> WhisperModel:
    s = get_settings()
    logger.info(
        "Init WhisperModel size=%s device=%s compute_type=%s",
        s.model_size,
        s.device,
        s.compute_type,
    )
    return WhisperModel(s.model_size, device=s.device, compute_type=s.compute_type)


_model = register(
    LazyModel(
        "faster-whisper",
        _load_model,
        idle_timeout_sec=get_settings().model_idle_timeout_min * 60,
    )
)


def preload() -> None:
    """Eagerly load the model (used at startup to surface config errors early)."""
    _model.get()


def transcribe(path, language=None) -> dict:
    model: WhisperModel = _model.get()  # type: ignore[assignment]
    segments, info = model.transcribe(
        str(path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
    )

    out = {
        "language": info.language,
        "duration": info.duration,
        "text": "",
        "segments": [],
    }
    parts: list[str] = []
    for s in segments:
        text = s.text.strip()
        parts.append(text)
        out["segments"].append(
            {
                "start": s.start,
                "end": s.end,
                "text": text,
                "probability": getattr(s, "avg_logprob", None),
            }
        )
    out["text"] = " ".join(parts).strip()
    return out

import os
import torch
from faster_whisper import WhisperModel
from .utils import UPLOAD_DIR


def _detect_device():
    env = os.getenv("DEVICE", "cpu").strip().lower()
    if env == "gpu" and torch.cuda.is_available():
        return "cuda"
    if env == "cpu":
        return "cpu"
    if env == "cuda" and torch.cuda.is_available():
        return "cuda"
    return "cpu"


def get_model():
    model_size = os.getenv("MODEL_SIZE", "medium")
    device = _detect_device()
    compute_type = "float16" if device == "cuda" else "int8"
    model = WhisperModel(
        model_size,
        device=device,
        compute_type=compute_type,
    )
    return model


from faster_whisper import WhisperModel
from pyannote.audio import Pipeline
import torch
from .utils import UPLOAD_DIR


def _model():
    size = _env("MODEL_SIZE", "medium")
    device = _env("DEVICE", "cpu")
    ctype = "float16" if device == "gpu" else "int8"
    return WhisperModel(size, device=device, compute_type=ctype)


def _pipeline():
    token = _env("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN is required for diarization")
    device = _env("DEVICE", "cpu")
    torch_device = torch.device("cuda" if device == "gpu" else "cpu")
    p = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=token)
    p.to(torch_device)
    return p


def _env(name, default=None):
    v = os.environ.get(name, default)
    if v is None:
        raise RuntimeError(f"Missing env: {name}")
    return v


def transcribe(path, language=None):
    m = _model()
    segs, info = m.transcribe(
        str(path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
    )
    out = {"language": info.language, "duration": info.duration, "text": "", "segments": []}
    for s in segs:
        out["text"] += s.text + " "
        out["segments"].append({"start": s.start, "end": s.end, "text": s.text.strip(), "probability": s.probability})
    out["text"] = out["text"].strip()
    return out


def diarize(path, min_speakers=None, max_speakers=None):
    p = _pipeline()
    d = p(str(path), min_speakers=min_speakers, max_speakers=max_speakers)
    turns = []
    for turn, _, speaker in d.itertracks(yield_label=True):
        turns.append({"start": turn.start, "end": turn.end, "speaker": speaker})
    return turns

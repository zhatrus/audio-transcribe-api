"""Speaker diarization via pyannote.audio with a cached, idle-evicted pipeline."""
import logging

import torch
from pyannote.audio import Pipeline

from .config import get_settings
from .model_manager import LazyModel, register

logger = logging.getLogger("app.diarization")


def _load_pipeline() -> Pipeline:
    s = get_settings()
    if not s.hf_token:
        raise RuntimeError("HF_TOKEN is required for diarization")
    logger.info("Init pyannote pipeline on device=%s", s.device)
    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=s.hf_token,
    )
    if pipeline is None:
        # from_pretrained returns None (not raises) when the token lacks access.
        raise RuntimeError(
            "Failed to load pyannote pipeline. Check HF_TOKEN and accept the model "
            "conditions at https://hf.co/pyannote/speaker-diarization-3.1 and "
            "https://hf.co/pyannote/segmentation-3.0"
        )
    pipeline.to(torch.device(s.device))
    return pipeline


_pipeline = register(
    LazyModel(
        "pyannote-diarization",
        _load_pipeline,
        idle_timeout_sec=get_settings().model_idle_timeout_min * 60,
    )
)


def run_diarization(path, min_speakers=None, max_speakers=None) -> list[dict]:
    pipeline: Pipeline = _pipeline.get()  # type: ignore[assignment]
    diarization = pipeline(
        str(path),
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )
    turns: list[dict] = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append({"start": turn.start, "end": turn.end, "speaker": speaker})
    return turns

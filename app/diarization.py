from pyannote.audio import Pipeline
import torch
from .utils import UPLOAD_DIR


def get_pipeline():
    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise RuntimeError("HF_TOKEN is required for diarization")

    device = os.getenv("DEVICE", "cpu")
    torch_device = torch.device("cuda" if device == "gpu" else "cpu")

    pipeline = Pipeline.from_pretrained(
        "pyannote/speaker-diarization-3.1",
        use_auth_token=hf_token,
    )
    pipeline.to(torch_device)
    return pipeline


def run_diarization(path, min_speakers=None, max_speakers=None):
    pipeline = get_pipeline()
    diarization = pipeline(
        str(path),
        min_speakers=min_speakers,
        max_speakers=max_speakers,
    )

    turns = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        turns.append(
            {
                "start": turn.start,
                "end": turn.end,
                "speaker": speaker,
            }
        )
    return turns

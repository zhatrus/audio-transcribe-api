"""Centralized configuration loaded from environment variables."""
import os
from functools import lru_cache
from pathlib import Path


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def resolve_device(raw: str | None = None) -> str:
    """Map user-facing DEVICE values to a valid faster-whisper/torch device.

    Accepts cpu / gpu / cuda / auto and returns either "cuda" or "cpu".
    """
    value = (raw if raw is not None else os.getenv("DEVICE", "cpu")).strip().lower()
    wants_gpu = value in {"gpu", "cuda", "auto"}
    if wants_gpu:
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        # auto silently falls back; explicit gpu/cuda also falls back to cpu
        return "cpu"
    return "cpu"


def resolve_compute_type(device: str) -> str:
    raw = os.getenv("COMPUTE_TYPE", "").strip()
    if raw:
        return raw
    return "float16" if device == "cuda" else "int8"


class Settings:
    def __init__(self) -> None:
        # Models
        self.model_size = os.getenv("MODEL_SIZE", "medium")
        self.device = resolve_device()
        self.compute_type = resolve_compute_type(self.device)
        self.hf_token = os.getenv("HF_TOKEN") or None
        self.default_language = os.getenv("LANGUAGE", "auto")

        # Keep the loaded model in RAM/VRAM for this many minutes of inactivity
        # before evicting it. 0 disables eviction (model stays loaded forever).
        self.model_idle_timeout_min = _get_int("MODEL_IDLE_TIMEOUT_MIN", 30)

        # Storage
        base = Path(os.getenv("DATA_DIR", "/tmp/audio-transcribe-api"))
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", str(base / "uploads")))
        self.cache_dir = Path(os.getenv("CACHE_DIR", str(base / "cache")))

        # Result lifecycle (hours)
        self.result_ttl_hours = _get_int("RESULT_TTL_HOURS", 24)
        self.delivered_ttl_hours = _get_int("DELIVERED_TTL_HOURS", 6)
        self.cleanup_interval_min = _get_int("CLEANUP_INTERVAL_MIN", 10)

        # Limits / security
        self.max_upload_mb = _get_int("MAX_UPLOAD_MB", 1024)
        self.api_key = os.getenv("API_KEY") or None

        # Optional default webhook: POSTed the job (result/error) on completion.
        # A per-request `webhook_url` form field overrides this.
        self.webhook_url = os.getenv("WEBHOOK_URL") or None
        self.webhook_timeout_sec = _get_int("WEBHOOK_TIMEOUT_SEC", 15)

        # Server
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = _get_int("PORT", 8000)
        self.workers = _get_int("WORKERS", 1)
        self.log_level = os.getenv("LOG_LEVEL", "info")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024 if self.max_upload_mb > 0 else 0

    def ensure_dirs(self) -> None:
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

# Changelog

## 2026-06-13
- Optional webhook callback: finished jobs (done/error) are POSTed as JSON to
  `WEBHOOK_URL` or a per-request `webhook_url` field — avoids polling for long
  recordings. Retried once on failure.
- Diarization: normalize audio to mono 16 kHz (ffmpeg) before pyannote to fix
  the "Sizes of tensors must match" error on video/stereo inputs; make it
  best-effort — on failure the job still returns the transcription plus a
  `diarization_error` field.
- Optional `subtitles=true` form field adds an `srt` field (with speaker labels
  when diarization is available).

## 2026-06-12
- Rework to an asynchronous job-based API: `POST /transcribe` returns a `job_id`
  immediately; results are polled via `GET /jobs/{id}`.
- Fix 500 errors: removed duplicated/broken code in `stt.py`, correct
  `gpu`→`cuda` device mapping on the real code path, use `avg_logprob` instead
  of a non-existent `Segment.probability`.
- Load the model once (cached singleton) instead of per request; unload after
  `MODEL_IDLE_TIMEOUT_MIN` idle minutes.
- Run heavy transcription in a thread executor so the event loop / health check
  stays responsive; process jobs sequentially via a single background worker.
- Persistent JSON job store with double-TTL auto-cleanup (hard + post-delivery).
- Safe upload handling (UUID names, size limit), optional `X-API-Key` auth.
- Self-contained CPU/GPU Dockerfiles + coherent compose files; data volume.
- `DELETE /jobs/{id}` and `DELETE /jobs` for manual cleanup.

## 2026-06-09
- Init repo transcription API with diarization.

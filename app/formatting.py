"""Build subtitle/output formats from transcription segments."""


def _ts(seconds: float | None) -> str:
    ms = int(round((seconds or 0.0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _speaker_for(seg: dict, speakers: list[dict]) -> str | None:
    """Pick the speaker whose turn overlaps this segment the most."""
    best, best_overlap = None, 0.0
    for sp in speakers:
        overlap = min(seg["end"], sp["end"]) - max(seg["start"], sp["start"])
        if overlap > best_overlap:
            best, best_overlap = sp.get("speaker"), overlap
    return best


def build_srt(segments: list[dict], speakers: list[dict] | None = None) -> str:
    """SRT subtitles from Whisper segments, optionally prefixed with speaker."""
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        text = (seg.get("text") or "").strip()
        if speakers:
            sp = _speaker_for(seg, speakers)
            if sp:
                text = f"[{sp}] {text}"
        lines.append(str(i))
        lines.append(f"{_ts(seg.get('start'))} --> {_ts(seg.get('end'))}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()

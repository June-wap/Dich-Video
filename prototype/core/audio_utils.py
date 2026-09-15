"""Audio utilities: WAV write, MP3 export and conservative boundary DSP."""
from __future__ import annotations

import logging
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger("prototype")


@dataclass(frozen=True)
class PausePolicy:
    """Deterministic pauses selected within the CP0.2E starting ranges."""

    comma_ms: int = 150
    semicolon_ms: int = 240
    colon_ms: int = 260
    period_ms: int = 350
    question_ms: int = 450
    exclamation_ms: int = 400
    paragraph_ms: int = 650
    neutral_ms: int = 260


@dataclass(frozen=True)
class BoundaryDSPConfig:
    """Central configuration for safe, deliberately light boundary processing."""

    pause_policy: PausePolicy = field(default_factory=PausePolicy)
    silence_threshold_dbfs: float = -48.0
    silence_probe_ms: int = 5
    preserve_silence_ms: int = 35
    max_trim_ms: int = 250
    edge_fade_ms: int = 3
    crossfade_ms: int = 0
    target_dbfs: float | None = None
    max_gain_db: float = 1.5

    def __post_init__(self) -> None:
        if self.silence_probe_ms <= 0 or self.preserve_silence_ms < 0:
            raise ValueError("Invalid silence trim configuration")
        if self.max_trim_ms < 0 or not 0 <= self.edge_fade_ms <= 20:
            raise ValueError("Invalid boundary fade/trim configuration")
        if not 0 <= self.crossfade_ms <= 20 or self.max_gain_db < 0:
            raise ValueError("Crossfade must be 0–20 ms and gain must be non-negative")


def boundary_kind(text: str, is_paragraph_end: bool = False) -> str:
    """Classify a chunk boundary without changing its text."""

    if is_paragraph_end:
        return "paragraph"
    terminal = text.rstrip()[-1:] if isinstance(text, str) else ""
    return {
        ",": "comma", "，": "comma",
        ";": "semicolon", "；": "semicolon",
        ":": "colon", "：": "colon",
        ".": "period", "。": "period", "…": "period",
        "?": "question", "？": "question",
        "!": "exclamation", "！": "exclamation",
    }.get(terminal, "neutral")


def select_pause_ms(
    text: str,
    is_paragraph_end: bool = False,
    policy: PausePolicy | None = None,
) -> tuple[str, int]:
    """Return the semantic boundary label and configured pause duration."""

    policy = policy or PausePolicy()
    kind = boundary_kind(text, is_paragraph_end)
    return kind, int(getattr(policy, f"{kind}_ms"))


def _trim_segment_safely(segment, config: BoundaryDSPConfig):
    """Trim only confidently silent edges, with a cap and retained padding."""

    if len(segment) == 0:
        raise ValueError("Empty audio segment")
    step = config.silence_probe_ms

    def silent(part) -> bool:
        return part.dBFS == float("-inf") or part.dBFS <= config.silence_threshold_dbfs

    leading = 0
    while leading < len(segment) and silent(segment[leading:leading + step]):
        leading += step
    trailing = 0
    while trailing < len(segment) and silent(segment[len(segment) - trailing - step:len(segment) - trailing]):
        trailing += step

    trim_leading = min(config.max_trim_ms, max(0, leading - config.preserve_silence_ms))
    trim_trailing = min(config.max_trim_ms, max(0, trailing - config.preserve_silence_ms))
    end = max(trim_leading + 1, len(segment) - trim_trailing)
    trimmed = segment[trim_leading:end]
    if len(trimmed) == 0:
        raise ValueError("Boundary trim removed entire segment")
    return trimmed, trim_leading, trim_trailing


def write_wav(path: str | Path, samples: np.ndarray, sample_rate: int) -> Path:
    """Write float32 samples to a 16-bit mono WAV file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not np.asarray(samples).size or not np.isfinite(samples).all():
        raise ValueError("GENERATION_FAILED: empty or nonfinite audio")
    pcm = (np.clip(samples, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    logger.info("WAV written: %s (%d samples, %d Hz)", path.name, len(pcm), sample_rate)
    return path


def wav_duration(path: str | Path) -> float:
    """Return duration of a WAV file in seconds."""
    with wave.open(str(path), "rb") as wf:
        return wf.getnframes() / wf.getframerate()


def wav_sample_rate(path: str | Path) -> int:
    """Return sample rate of a WAV file."""
    with wave.open(str(path), "rb") as wf:
        return wf.getframerate()


def export_mp3(wav_path: str | Path, mp3_path: str | Path = None) -> Path | None:
    """Convert WAV to MP3 using pydub + ffmpeg. Returns path or None on failure."""
    wav_path = Path(wav_path)
    if mp3_path is None:
        mp3_path = wav_path.with_suffix(".mp3")
    else:
        mp3_path = Path(mp3_path)
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_wav(str(wav_path))
        audio.export(str(mp3_path), format="mp3", bitrate="192k")
        logger.info("MP3 exported: %s", mp3_path.name)
        return mp3_path
    except Exception as e:
        logger.error("MP3 export failed for %s: %s", wav_path.name, e)
        return None


def merge_segments(
    wav_paths: list[str | Path],
    output_path: str | Path,
    pause_ms: int = 500,
    target_sr: int = None,
    pauses_ms: list[float] | None = None,
    boundary_labels: list[str] | None = None,
    boundary_config: BoundaryDSPConfig | None = None,
    diagnostics_out: list[dict] | None = None,
) -> Path:
    """Merge multiple WAV files with pauses between them.

    All segments are resampled to a common sample rate if needed.
    """
    from pydub import AudioSegment

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not wav_paths:
        raise ValueError("No segments to merge")

    config = boundary_config
    segments = []
    for p in wav_paths:
        seg = AudioSegment.from_wav(str(p))
        segments.append(seg)

    if target_sr is None:
        target_sr = segments[0].frame_rate

    boundary_count = max(0, len(segments) - 1)
    if pauses_ms is not None and (
        len(pauses_ms) not in (boundary_count, len(segments))
        or any(not np.isfinite(p) or p < 0 or p > 10000 for p in pauses_ms)
    ):
        raise ValueError("Pause must be 0–10000 ms per boundary")
    if boundary_labels is not None and len(boundary_labels) != boundary_count:
        raise ValueError("Boundary labels must match inter-segment boundaries")

    diagnostics = diagnostics_out if diagnostics_out is not None else []
    merged = AudioSegment.empty()
    previous_pause = 0
    for i, seg in enumerate(segments):
        if seg.frame_rate != target_sr:
            seg = seg.set_frame_rate(target_sr)
        if seg.channels != 1:
            seg = seg.set_channels(1)

        trim_leading = trim_trailing = 0
        gain_db = 0.0
        if config is not None:
            seg, trim_leading, trim_trailing = _trim_segment_safely(seg, config)
            if config.target_dbfs is not None and seg.dBFS != float("-inf"):
                gain_db = max(-config.max_gain_db, min(config.max_gain_db, config.target_dbfs - seg.dBFS))
                seg = seg.apply_gain(gain_db)
            fade = min(config.edge_fade_ms, len(seg) // 2)
            if fade:
                seg = seg.fade_in(fade).fade_out(fade)

        if i and config is not None and config.crossfade_ms and previous_pause == 0:
            merged = merged.append(seg, crossfade=min(config.crossfade_ms, len(seg), len(merged)))
        else:
            merged += seg

        pause_after = 0
        if i < boundary_count:
            pause_after = pauses_ms[i] if pauses_ms is not None else pause_ms
            if pause_after:
                merged += AudioSegment.silent(duration=pause_after, frame_rate=target_sr)
        previous_pause = pause_after

        diagnostic = {
            "segment_index": i,
            "trim_leading_ms": trim_leading,
            "trim_trailing_ms": trim_trailing,
            "edge_fade_ms": config.edge_fade_ms if config is not None else 0,
            "gain_db": round(gain_db, 3),
            "boundary_after": boundary_labels[i] if boundary_labels is not None and i < boundary_count else None,
            "pause_after_ms": pause_after,
        }
        diagnostics.append(diagnostic)
        logger.info(
            "BOUNDARY_DSP segment=%d trim_leading_ms=%d trim_trailing_ms=%d "
            "fade_ms=%d gain_db=%.3f boundary=%s pause_ms=%s",
            i,
            trim_leading,
            trim_trailing,
            diagnostic["edge_fade_ms"],
            gain_db,
            diagnostic["boundary_after"],
            pause_after,
        )

    merged.export(str(output_path), format="wav")
    logger.info("Merged %d segments -> %s (%.1fs)", len(segments), output_path.name,
                len(merged) / 1000)
    return output_path

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from core.audio_utils import (
    BoundaryDSPConfig,
    PausePolicy,
    merge_segments,
    select_pause_ms,
)


@pytest.mark.parametrize(
    ("text", "kind", "low", "high"),
    [
        ("Một phần,", "comma", 120, 180),
        ("Một phần;", "semicolon", 200, 280),
        ("Một phần:", "colon", 220, 300),
        ("Một câu.", "period", 300, 400),
        ("Một câu?", "question", 400, 500),
        ("Một câu!", "exclamation", 350, 450),
    ],
)
def test_pause_selection_uses_punctuation_policy(text, kind, low, high):
    actual_kind, duration = select_pause_ms(text)
    assert actual_kind == kind
    assert low <= duration <= high


def test_paragraph_pause_overrides_punctuation():
    kind, duration = select_pause_ms("Kết thúc.", is_paragraph_end=True)
    assert kind == "paragraph"
    assert 550 <= duration <= 750


def test_pause_policy_is_not_universal_fixed_pause():
    durations = {
        select_pause_ms(text)[1]
        for text in ("a,", "b;", "c:", "d.", "e?", "f!")
    }
    assert len(durations) == 6


def _write(path: Path, samples: np.ndarray, rate: int = 24000) -> Path:
    sf.write(path, samples.astype(np.float32), rate)
    return path


def test_merge_applies_safe_trim_and_preserves_order(tmp_path):
    rate = 24000
    silence = np.zeros(rate // 10, dtype=np.float32)
    first = np.concatenate([silence, np.full(rate // 10, 0.12), silence])
    second = np.concatenate([silence, np.full(rate // 10, -0.18), silence])
    paths = [_write(tmp_path / "a.wav", first), _write(tmp_path / "b.wav", second)]
    output = tmp_path / "merged.wav"
    diagnostics = []
    config = BoundaryDSPConfig(max_trim_ms=60, preserve_silence_ms=25)

    merge_segments(
        paths,
        output,
        target_sr=24000,
        pauses_ms=[350],
        boundary_labels=["period"],
        boundary_config=config,
        diagnostics_out=diagnostics,
    )

    audio, sample_rate = sf.read(output, dtype="float32")
    assert sample_rate == 24000
    assert audio.ndim == 1 and np.isfinite(audio).all()
    assert diagnostics[0]["trim_leading_ms"] == 60
    assert diagnostics[0]["trim_trailing_ms"] == 60
    assert diagnostics[0]["pause_after_ms"] == 350
    assert diagnostics[0]["boundary_after"] == "period"
    assert diagnostics[1]["pause_after_ms"] == 0
    nonzero = audio[np.abs(audio) > 0.03]
    assert nonzero[0] > 0
    assert nonzero[-1] < 0


def test_short_chunks_remain_valid_and_finite(tmp_path):
    rate = 24000
    tiny = np.full(rate // 200, 0.1, dtype=np.float32)
    paths = [_write(tmp_path / "tiny1.wav", tiny), _write(tmp_path / "tiny2.wav", tiny)]
    output = tmp_path / "tiny_merged.wav"

    merge_segments(
        paths,
        output,
        target_sr=24000,
        pauses_ms=[120],
        boundary_labels=["comma"],
        boundary_config=BoundaryDSPConfig(edge_fade_ms=3),
    )

    audio, sample_rate = sf.read(output, dtype="float32")
    assert sample_rate == 24000
    assert audio.size > 0 and audio.ndim == 1
    assert np.isfinite(audio).all()
    assert abs(audio[0]) < 1e-4
    assert abs(audio[-1]) < 0.003
    assert np.max(np.abs(np.diff(audio))) < 0.11


def test_optional_loudness_gain_is_bounded():
    config = BoundaryDSPConfig(target_dbfs=-20.0, max_gain_db=1.25)
    assert config.max_gain_db == 1.25


def test_crossfade_is_disabled_by_default():
    assert BoundaryDSPConfig().crossfade_ms == 0

"""Tests for authoritative FFmpeg resolution, MP3 export fail-closed semantics,

and voice-profile decode integration with stripped PATH.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import shutil
import struct
import subprocess
import wave

import numpy as np
import pytest
import soundfile as sf

from backend.core.ffmpeg_resolver import (
    is_packaged_production,
    require_ffmpeg_path,
    resolve_ffmpeg_path,
)
from backend.core.audio_utils import export_mp3, write_wav


def _create_sine_wav(path: Path, duration_sec: float = 1.0, sample_rate: int = 24000) -> Path:
    """Create a real PCM16 mono WAV file."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False, dtype=np.float32)
    samples = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    return write_wav(path, samples, sample_rate)


def test_explicit_ffmpeg_path_precedence(tmp_path):
    fake_ffmpeg = tmp_path / "ffmpeg.exe"
    fake_ffmpeg.write_text("fake binary")
    env = {"LOCAL_AI_FFMPEG_PATH": str(fake_ffmpeg), "PATH": ""}
    resolved = resolve_ffmpeg_path(env)
    assert resolved == fake_ffmpeg.resolve()


def test_explicit_nonexistent_ffmpeg_fails_closed(tmp_path):
    missing_ffmpeg = tmp_path / "nonexistent" / "ffmpeg.exe"
    env = {"LOCAL_AI_FFMPEG_PATH": str(missing_ffmpeg), "PATH": ""}
    resolved = resolve_ffmpeg_path(env)
    assert resolved is None


def test_packaged_production_detection(tmp_path):
    # Explicit env flag
    assert is_packaged_production({"LOCAL_AI_PRODUCTION": "1"}) is True
    assert is_packaged_production({"LOCAL_AI_PACKAGED": "true"}) is True
    assert is_packaged_production({"LOCAL_AI_PRODUCTION": "0"}) is False


def test_packaged_production_resolves_bundled_ffmpeg_with_stripped_path(tmp_path, monkeypatch):
    # Simulate packaged resources layout: <root>/resources/backend/core/ffmpeg_resolver.py
    # and <root>/resources/bin/ffmpeg.exe
    app_root = tmp_path / "Voca Basic"
    resources = app_root / "resources"
    backend = resources / "backend"
    core = backend / "core"
    core.mkdir(parents=True)
    bin_dir = resources / "bin"
    bin_dir.mkdir(parents=True)
    bundled_ffmpeg = bin_dir / "ffmpeg.exe"
    bundled_ffmpeg.write_text("mock ffmpeg")

    # Point __file__ resolution anchor to simulated packaged file
    fake_file = core / "ffmpeg_resolver.py"
    fake_file.write_text("")
    monkeypatch.setattr("backend.core.ffmpeg_resolver.__file__", str(fake_file))

    env = {"LOCAL_AI_PRODUCTION": "1", "PATH": ""}
    resolved = resolve_ffmpeg_path(env)
    assert resolved == bundled_ffmpeg.resolve()


def test_packaged_production_fails_closed_when_bundled_missing(tmp_path, monkeypatch):
    # In packaged production, even if an ffmpeg exists on PATH, it must NOT be used
    fake_path_dir = tmp_path / "system_bin"
    fake_path_dir.mkdir()
    path_ffmpeg = fake_path_dir / "ffmpeg.exe"
    path_ffmpeg.write_text("path binary")

    # Empty resources folder without bin/ffmpeg.exe
    resources = tmp_path / "resources"
    backend = resources / "backend" / "core"
    backend.mkdir(parents=True)
    fake_file = backend / "ffmpeg_resolver.py"
    fake_file.write_text("")
    monkeypatch.setattr("backend.core.ffmpeg_resolver.__file__", str(fake_file))

    env = {"LOCAL_AI_PRODUCTION": "1", "PATH": str(fake_path_dir)}
    resolved = resolve_ffmpeg_path(env)
    assert resolved is None

    with pytest.raises(FileNotFoundError, match="BUNDLED_FFMPEG_MISSING"):
        require_ffmpeg_path(env)


def test_development_fallback_to_path_when_not_production(tmp_path, monkeypatch):
    fake_path_dir = tmp_path / "dev_path_bin"
    fake_path_dir.mkdir()
    path_ffmpeg = fake_path_dir / "ffmpeg.exe"
    path_ffmpeg.write_text("dev binary")

    # Empty fake repo dir without release/bin/ffmpeg.exe
    dev_core = tmp_path / "repo" / "backend" / "core"
    dev_core.mkdir(parents=True)
    fake_file = dev_core / "ffmpeg_resolver.py"
    fake_file.write_text("")
    monkeypatch.setattr("backend.core.ffmpeg_resolver.__file__", str(fake_file))

    env = {"LOCAL_AI_PRODUCTION": "0", "PATH": str(fake_path_dir)}
    resolved = resolve_ffmpeg_path(env)
    assert resolved == path_ffmpeg.resolve()


def test_export_mp3_real_conversion_with_stripped_path(tmp_path, monkeypatch):
    """Verify that a real WAV -> MP3 conversion succeeds with PATH completely stripped."""
    staged_ffmpeg = Path("release/bin/ffmpeg.exe").resolve()
    if not staged_ffmpeg.is_file():
        pytest.skip("Staged release/bin/ffmpeg.exe not present for real conversion test")

    # Strip PATH completely so ffmpeg CANNOT be found on PATH
    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    # Pass explicit bundled path as if packaged production launched it
    monkeypatch.setenv("LOCAL_AI_FFMPEG_PATH", str(staged_ffmpeg))
    monkeypatch.setenv("LOCAL_AI_PRODUCTION", "1")

    wav_path = tmp_path / "test_tone.wav"
    _create_sine_wav(wav_path, duration_sec=1.5, sample_rate=24000)
    assert wav_path.is_file() and wav_path.stat().st_size > 0

    mp3_path = tmp_path / "test_tone.mp3"
    exported = export_mp3(wav_path, mp3_path)

    assert exported is not None
    assert exported == mp3_path
    assert mp3_path.is_file()
    assert mp3_path.stat().st_size > 0
    # Confirm WAV was retained
    assert wav_path.is_file() and wav_path.stat().st_size > 0

    # Verify MP3 is a valid decodable audio file using soundfile or ffmpeg
    info = sf.info(str(mp3_path))
    assert info.format == "MP3"
    assert info.channels == 1
    assert 1.4 <= info.duration <= 1.6


def test_export_mp3_missing_ffmpeg_fails_closed_and_keeps_wav(tmp_path, monkeypatch):
    """When FFmpeg is unavailable, export_mp3 fails closed, produces NO 0-byte MP3, and retains WAV."""
    wav_path = tmp_path / "valid.wav"
    _create_sine_wav(wav_path, duration_sec=1.0)
    mp3_path = tmp_path / "output.mp3"

    # Mock resolver to return None
    monkeypatch.setattr("backend.core.ffmpeg_resolver.resolve_ffmpeg_path", lambda environ=None: None)

    exported = export_mp3(wav_path, mp3_path)
    assert exported is None
    # Verify no 0-byte MP3 was created or left on disk
    assert not mp3_path.exists()
    # Verify the original WAV file is fully preserved
    assert wav_path.is_file()
    assert wav_path.stat().st_size > 0


def test_voice_profile_validation_uses_resolved_ffmpeg(tmp_path, monkeypatch):
    """_validate_reference_audio invokes the resolved FFmpeg binary."""
    from backend.services.voice_profile_service import VoiceProfileService

    staged_ffmpeg = Path("release/bin/ffmpeg.exe").resolve()
    if not staged_ffmpeg.is_file():
        pytest.skip("Staged release/bin/ffmpeg.exe not present for real validation test")

    monkeypatch.setenv("PATH", "C:\\Windows\\System32")
    monkeypatch.setenv("LOCAL_AI_FFMPEG_PATH", str(staged_ffmpeg))

    # Create 4.0 second mono WAV reference
    ref_wav = tmp_path / "reference.wav"
    _create_sine_wav(ref_wav, duration_sec=4.0, sample_rate=24000)

    # Initialize service instance directly
    service = VoiceProfileService.__new__(VoiceProfileService)

    duration, rate, channels = service._validate_reference_audio(ref_wav)
    assert 3.9 <= duration <= 4.1
    assert rate == 24000
    assert channels == 1


def test_voice_profile_fallback_when_ffmpeg_missing(tmp_path, monkeypatch):
    """When FFmpeg is missing, WAV/FLAC still pass signature check, but non-WAV/FLAC fails with ValueError."""
    from backend.services.voice_profile_service import VoiceProfileService

    monkeypatch.setattr("backend.services.voice_profile_service.resolve_ffmpeg_path", lambda: None)

    service = VoiceProfileService.__new__(VoiceProfileService)

    # 1. Real WAV passes fallback
    ref_wav = tmp_path / "ref_fallback.wav"
    _create_sine_wav(ref_wav, duration_sec=3.5, sample_rate=24000)
    dur, rate, ch = service._validate_reference_audio(ref_wav)
    assert 3.4 <= dur <= 3.6

    # 2. Fake MP3/compressed file without RIFF/fLaC signature is rejected as INVALID_REFERENCE_AUDIO
    from backend.errors import ApplicationError, ErrorCode
    fake_mp3 = tmp_path / "fake.mp3"
    fake_mp3.write_bytes(b"\xFF\xFB\x90\x64" + b"\x00" * 1000)
    with pytest.raises(ApplicationError) as exc_info:
        service._validate_reference_audio(fake_mp3)
    assert exc_info.value.code == ErrorCode.INVALID_REFERENCE_AUDIO

import io
from pathlib import Path
import subprocess
import tempfile
import uuid
import wave

import numpy as np
import pytest
import soundfile as sf

from backend.config import Settings
from backend.tests.provider_fakes import TEST_PROVIDER_ID
from backend.errors import ApplicationError, ErrorCode
from backend.schemas.voices import CloneTestRequest
from backend.services.provider_service import ProviderService
from backend.services.voice_profile_service import VoiceProfileService
from backend.tests.provider_fakes import FakeCloneProvider


def make_wav_bytes(duration: float = 5.0, sample_rate: int = 24000, channels: int = 1) -> bytes:
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Sine wave
    sig = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    if channels == 2:
        sig = np.column_stack((sig, sig))
    buf = io.BytesIO()
    sf.write(buf, sig, sample_rate, format="WAV", subtype="PCM_16")
    return buf.getvalue()


@pytest.fixture
def service_env():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # database_path must be isolated per test like output_dir is: without
        # it, Repository falls back to Settings.app_data_dir's real,
        # persistent %LOCALAPPDATA%\Voca Basic\data\metadata.sqlite3 (see
        # backend/persistence.py), so voice profiles created by every test
        # run - not just this one - accumulate in the same database (this was
        # the actual cause of test_profile_retrieval_and_listing expecting 1
        # profile and getting dozens).
        settings = Settings(output_dir=Path(tmp_dir), database_path=Path(tmp_dir) / "metadata.sqlite3")
        provider = FakeCloneProvider()
        providers = ProviderService()
        providers.register(provider, device="cuda:0", available=True)
        providers.select_primary(TEST_PROVIDER_ID)
        vps = VoiceProfileService(settings, providers)
        yield vps, provider, providers, Path(tmp_dir)


def test_create_profile_valid(service_env):
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    transcript = "Đây là văn bản phát âm chuẩn để tạo giọng mẫu."

    resp = vps.create_profile(
        audio_bytes=wav_bytes,
        filename="ref.wav",
        transcript=transcript,
        name="My Clone Voice",
    )

    assert resp.ok is True
    data = resp.data
    assert uuid.UUID(data.profile_id)  # Safe UUID
    assert data.name == "My Clone Voice"
    assert data.provider == TEST_PROVIDER_ID
    assert data.status == "ready"
    assert data.reference is not None
    assert round(data.reference.duration_seconds, 1) == 5.0
    assert data.reference.sample_rate == 24000
    assert data.reference.channels == 1
    assert provider.create_profile_calls == 1


def test_invalid_audio_rejected(service_env):
    vps, _, _, _ = service_env
    transcript = "Văn bản mẫu."

    # Empty audio
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(b"", "empty.wav", transcript)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_AUDIO

    # Corrupt audio
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(b"not an audio file at all", "bad.wav", transcript)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_AUDIO

    # Too short audio (< 3.0s)
    short_bytes = make_wav_bytes(duration=1.5)
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(short_bytes, "short.wav", transcript)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_AUDIO

    # Too long audio (> 60.0s)
    long_bytes = make_wav_bytes(duration=65.0)
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(long_bytes, "long.wav", transcript)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_AUDIO

    # Corrupt audio *labeled* .mp3 - a genuinely undecodable file must still
    # be rejected under the FFmpeg-first decode order (regression guard for
    # the fix below: FFmpeg-first must not accidentally *widen* what's
    # accepted, only correctly decode real compressed containers).
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(b"not an audio file at all", "bad.mp3", transcript)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_AUDIO


def test_create_profile_accepts_real_mp3(service_env, tmp_path):
    """A genuinely MP3-encoded reference file must be accepted end to end.

    Regression test for the INVALID_REFERENCE_AUDIO bug: create_profile()'s
    own pre-validation (_validate_reference_audio) used to try libsndfile
    before FFmpeg, preserving the established decode order.
    """
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    wav_path = tmp_path / "ref_source.wav"
    wav_path.write_bytes(wav_bytes)
    mp3_path = tmp_path / "ref.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), "-c:a", "libmp3lame", str(mp3_path)],
        check=True, capture_output=True, timeout=30,
    )
    transcript = "Đây là văn bản phát âm chuẩn để tạo giọng mẫu."

    resp = vps.create_profile(
        audio_bytes=mp3_path.read_bytes(),
        filename="ref.mp3",
        transcript=transcript,
    )

    assert resp.ok is True
    assert round(resp.data.reference.duration_seconds, 0) == 5.0
    assert provider.create_profile_calls == 1


def test_create_profile_accepts_aac_disguised_as_mp3(service_env, tmp_path):
    """A routine real-world case: a phone voice recorder exports AAC audio
    but the file still has a `.mp3` extension. FFmpeg's container detection
    must decode this correctly instead of handing it to a decoder keyed off
    the (wrong) file extension - mirrors
    a generic provider fake's reference-audio test, which proves
    the service's own pre-validation gate (the actual site of the reported
    bug - a failure here surfaces as INVALID_REFERENCE_AUDIO before the
    provider is ever reached) does too.
    """
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    wav_path = tmp_path / "ref_source.wav"
    wav_path.write_bytes(wav_bytes)
    disguised_path = tmp_path / "reference.mp3"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(wav_path), "-c:a", "aac", "-f", "ipod", str(disguised_path)],
        check=True, capture_output=True, timeout=30,
    )
    transcript = "Đây là văn bản phát âm chuẩn để tạo giọng mẫu."

    resp = vps.create_profile(
        audio_bytes=disguised_path.read_bytes(),
        filename="reference.mp3",
        transcript=transcript,
    )

    assert resp.ok is True
    assert round(resp.data.reference.duration_seconds, 0) == 5.0


def test_oversized_audio_rejected(service_env):
    vps, _, _, _ = service_env
    oversized = b"0" * (15 * 1024 * 1024 + 1)
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(oversized, "big.wav", "Transcript")
    assert exc.value.code == ErrorCode.REFERENCE_AUDIO_TOO_LARGE


def test_invalid_transcript_rejected(service_env):
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)

    for bad_transcript in ["", "   ", "\n\t ", None]:
        with pytest.raises(ApplicationError) as exc:
            vps.create_profile(wav_bytes, "ref.wav", bad_transcript)
        assert exc.value.code == ErrorCode.INVALID_REFERENCE_TRANSCRIPT

    # Transcript too long (> 2000 chars)
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(wav_bytes, "ref.wav", "A" * 2001)
    assert exc.value.code == ErrorCode.INVALID_REFERENCE_TRANSCRIPT


def test_profile_retrieval_and_listing(service_env):
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Hôm nay trời đẹp.", "Voice A")
    pid = resp.data.profile_id

    # Get profile
    get_resp = vps.get_profile(pid)
    assert get_resp.ok is True
    assert get_resp.data.profile_id == pid
    assert get_resp.data.name == "Voice A"

    # List profiles
    list_resp = vps.list_profiles()
    assert list_resp.ok is True
    assert len(list_resp.data) == 1
    assert list_resp.data[0].profile_id == pid

    # Nonexistent profile
    with pytest.raises(ApplicationError) as exc:
        vps.get_profile(str(uuid.uuid4()))
    assert exc.value.code == ErrorCode.VOICE_PROFILE_NOT_FOUND


def test_delete_profile(service_env):
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Hôm nay trời đẹp.", "Voice A")
    pid = resp.data.profile_id

    assert pid in vps._records
    # Delete
    vps.delete_profile(pid)
    assert pid not in vps._records

    # Subsequent delete raises 404
    with pytest.raises(ApplicationError) as exc:
        vps.delete_profile(pid)
    assert exc.value.code == ErrorCode.VOICE_PROFILE_NOT_FOUND

    # Post-delete get raises 404
    with pytest.raises(ApplicationError) as exc:
        vps.get_profile(pid)
    assert exc.value.code == ErrorCode.VOICE_PROFILE_NOT_FOUND

    # Deletion did not unload the model
    assert provider.is_loaded() is True


def test_synthesize_clone_and_profile_reuse(service_env):
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản phát âm mẫu.", "Voice A")
    pid = resp.data.profile_id

    assert provider.create_profile_calls == 1
    assert provider.synthesize_cloned_calls == 0

    # Generation 1
    req1 = CloneTestRequest(text="Câu kiểm tra thứ nhất.", language="vi", speed=1.0, format="wav")
    res1 = vps.synthesize_clone(pid, req1)
    assert res1.ok is True
    assert res1.data.profile_id == pid
    assert provider.create_profile_calls == 1
    assert provider.synthesize_cloned_calls == 1

    # Generation 2
    req2 = CloneTestRequest(text="Câu kiểm tra thứ hai.", language="vi", speed=1.0, format="wav")
    res2 = vps.synthesize_clone(pid, req2)
    assert res2.ok is True
    assert res2.data.profile_id == pid
    assert provider.create_profile_calls == 1
    assert provider.synthesize_cloned_calls == 2

    # Generation 3
    req3 = CloneTestRequest(text="Câu kiểm tra thứ ba.", language="vi", speed=1.0, format="wav")
    res3 = vps.synthesize_clone(pid, req3)
    assert res3.ok is True
    assert res3.data.profile_id == pid
    assert provider.create_profile_calls == 1
    assert provider.synthesize_cloned_calls == 3

    # Verify record use_count
    rec = vps.get_profile_record(pid)
    assert rec.use_count == 3
    assert rec.creation_count == 1


def test_clone_input_validation(service_env):
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    # Empty text
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="", language="vi"))
    assert exc.value.code == ErrorCode.INVALID_TEXT

    # Text too long
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="A" * 2001, language="vi"))
    assert exc.value.code == ErrorCode.TEXT_TOO_LONG

    # A VieNeu profile cannot be used for a Chatterbox output language.
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="Hello", language="de"))
    assert exc.value.code == ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH

    # Speed not 1.0
    for bad_speed in [0.5, 1.5, 2.0, "fast", None]:
        with pytest.raises(ApplicationError) as exc:
            vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language="vi", speed=bad_speed))
        assert exc.value.code == ErrorCode.INVALID_SPEED

    # Invalid format
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language="vi", format="flac"))
    assert exc.value.code == ErrorCode.INVALID_FORMAT


@pytest.mark.parametrize("alias", ["vi", "VI", "vi-VN", "vi_VN", "Vi-vn"])
def test_clone_accepts_vietnamese_language_aliases(service_env, alias):
    """CP3 Section 6: vi/VI/vi-VN/vi_VN must all normalize to 'vi'."""
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    res = vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language=alias))
    assert res.ok is True
    assert res.data.language == "vi"


@pytest.mark.parametrize("other_language", ["en", "fr", "ja", "zh", "es", "pt", "it", "hi"])
def test_vieneu_clone_rejects_non_vietnamese_languages(service_env, other_language):
    """CP5: a persisted VieNeu profile cannot cross into Chatterbox output."""
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="Hello", language=other_language))
    assert exc.value.code == ErrorCode.VOICE_PROFILE_PROVIDER_MISMATCH


def test_deleted_profile_cannot_synthesize(service_env):
    vps, _, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    vps.delete_profile(pid)
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language="vi"))
    assert exc.value.code == ErrorCode.VOICE_PROFILE_NOT_FOUND


def test_clone_mp3_export(service_env):
    vps, _, _, out_dir = service_env
    wav_bytes = make_wav_bytes(duration=5.0)
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    res = vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language="vi", format="mp3"))
    assert res.ok is True
    assert res.data.format == "mp3"
    assert res.data.audio_url.endswith(".mp3")
    mp3_file = out_dir / f"{res.data.generation_id}.mp3"
    assert mp3_file.is_file()
    assert mp3_file.stat().st_size > 0


def test_provider_failures_normalized(service_env):
    vps, provider, _, _ = service_env
    wav_bytes = make_wav_bytes(duration=5.0)

    # Fail profile creation
    provider.fail_create_profile = True
    with pytest.raises(ApplicationError) as exc:
        vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    assert exc.value.code == ErrorCode.VOICE_PROFILE_CREATION_FAILED
    provider.fail_create_profile = False

    # Create successful profile
    resp = vps.create_profile(wav_bytes, "ref.wav", "Văn bản mẫu.")
    pid = resp.data.profile_id

    # Fail synthesis
    provider.fail_synthesize_cloned = True
    with pytest.raises(ApplicationError) as exc:
        vps.synthesize_clone(pid, CloneTestRequest(text="Xin chào", language="vi"))
    assert exc.value.code == ErrorCode.CLONE_GENERATION_FAILED

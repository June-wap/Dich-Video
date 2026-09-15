from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from core.long_text import ChunkingConfig
from core.tts_manager import TTSManager
from providers.base import TTSProvider, VoiceInfo, SynthResult


class FakeProvider(TTSProvider):
    """
    Provider giả để test CP0.2D orchestration.

    Không load model thật.
    Không dùng GPU.
    """

    def __init__(self):
        self.calls = []
        self.fail_once_text = None
        self.fail_always_text = None
        self.call_count_by_text = {}

    def provider_name(self):
        return "fake"

    def list_languages(self):
        return ["vi"]

    def list_voices(self, language):
        if language != "vi":
            return []

        return [
            VoiceInfo(
                id="fake-voice",
                name="Fake Voice",
                gender="neutral",
            )
        ]

    def health_check(self):
        return {
            "provider": "fake",
            "status": "OK",
        }

    def synthesize(
        self,
        text,
        language,
        voice_id,
        output_path,
        speed=1.0,
        **options,
    ):
        self.calls.append(text)

        count = self.call_count_by_text.get(
            text,
            0,
        ) + 1

        self.call_count_by_text[text] = count

        if text == self.fail_always_text:
            return SynthResult(
                status="FAIL",
                language=language,
                voice=voice_id,
                provider="fake",
                error="forced permanent failure",
            )

        if (
            text == self.fail_once_text
            and count == 1
        ):
            return SynthResult(
                status="FAIL",
                language=language,
                voice=voice_id,
                provider="fake",
                error="forced transient failure",
            )

        output_path = Path(output_path)

        # Generate deterministic tiny WAV.
        sample_rate = 24000

        # Mỗi text có amplitude khác nhau để kiểm tra thứ tự merge.
        amplitude = min(
            0.05 + len(text) / 10000.0,
            0.2,
        )

        samples = np.full(
            sample_rate // 20,
            amplitude,
            dtype=np.float32,
        )

        sf.write(
            output_path,
            samples,
            sample_rate,
        )

        return SynthResult(
            status="PASS",
            language=language,
            voice=voice_id,
            provider="fake",
            wav_path=str(output_path),
            gen_time=0.01,
            duration=len(samples) / sample_rate,
            rtf=0.2,
        )


@pytest.fixture
def manager(tmp_path):
    root = tmp_path

    (root / "prototype" / "outputs").mkdir(
        parents=True,
        exist_ok=True,
    )

    (root / "prototype" / "temp").mkdir(
        parents=True,
        exist_ok=True,
    )

    mgr = TTSManager(root)

    provider = FakeProvider()

    mgr.register_provider(provider)

    return mgr, provider


def make_text():
    return (
        "Đây là câu thứ nhất. "
        "Đây là câu thứ hai. "
        "Đây là câu thứ ba."
    )


def test_long_text_generates_all_chunks_in_order(manager):
    mgr, provider = manager

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"
    assert result["chunk_count"] == 3
    assert result["completed_chunks"] == 3

    assert provider.calls == [
        "Đây là câu thứ nhất.",
        "Đây là câu thứ hai.",
        "Đây là câu thứ ba.",
    ]

    assert result["wav_path"] is not None

    final_path = Path(
        result["wav_path"]
    )

    assert final_path.exists()


def test_long_text_retries_only_failed_chunk(manager):
    mgr, provider = manager

    provider.fail_once_text = (
        "Đây là câu thứ hai."
    )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        max_retries=2,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    assert provider.call_count_by_text[
        "Đây là câu thứ nhất."
    ] == 1

    assert provider.call_count_by_text[
        "Đây là câu thứ hai."
    ] == 2

    assert provider.call_count_by_text[
        "Đây là câu thứ ba."
    ] == 1


def test_long_text_retry_is_bounded(manager):
    mgr, provider = manager

    provider.fail_always_text = (
        "Đây là câu thứ hai."
    )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        max_retries=2,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "FAILED"

    # initial try + 2 retries
    assert provider.call_count_by_text[
        "Đây là câu thứ hai."
    ] == 3

    # chunk 3 must never run
    assert (
        "Đây là câu thứ ba."
        not in provider.call_count_by_text
    )

    assert result["wav_path"] is None


def test_failed_job_does_not_publish_final_wav(manager):
    mgr, provider = manager

    provider.fail_always_text = (
        "Đây là câu thứ hai."
    )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        filename="must_not_exist.wav",
        max_retries=0,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "FAILED"
    assert result["wav_path"] is None

    expected = (
        mgr.output_dir
        / "must_not_exist.wav"
    )

    assert not expected.exists()


def test_cancel_between_chunks(manager):
    mgr, provider = manager

    state = {
        "checks": 0,
    }

    def is_cancelled():
        state["checks"] += 1

        # first chunk allowed,
        # cancel before second chunk
        return state["checks"] >= 2

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        is_cancelled=is_cancelled,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "CANCELLED"
    assert result["completed_chunks"] == 1

    assert provider.calls == [
        "Đây là câu thứ nhất."
    ]

    assert result["wav_path"] is None


def test_progress_callback_receives_expected_stages(manager):
    mgr, _ = manager

    events = []

    def on_progress(payload):
        events.append(payload["stage"])

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        on_progress=on_progress,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    assert events[0] == "CHUNKING_COMPLETE"

    assert events.count(
        "GENERATING"
    ) == 3

    assert events.count(
        "CHUNK_COMPLETED"
    ) == 3

    assert "MERGING" in events

    assert events[-1] == "COMPLETED"


def test_progress_callback_failure_does_not_break_job(manager):
    mgr, _ = manager

    def broken_callback(payload):
        raise RuntimeError(
            "callback crash"
        )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        on_progress=broken_callback,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"


def test_temp_directory_is_removed_by_default(manager):
    mgr, _ = manager

    before = set(
        mgr.temp_dir.glob("long_*")
    )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    after = set(
        mgr.temp_dir.glob("long_*")
    )

    assert after == before


def test_keep_temp_preserves_job_directory(manager):
    mgr, _ = manager

    before = set(
        mgr.temp_dir.glob("long_*")
    )

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        keep_temp=True,
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    after = set(
        mgr.temp_dir.glob("long_*")
    )

    created = after - before

    assert len(created) == 1


def test_invalid_language_fails_before_provider_call(manager):
    mgr, provider = manager

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="xx",
        voice_id="fake-voice",
    )

    assert result["status"] == "FAILED"
    assert (
        result["error"]
        == "LANGUAGE_NOT_SUPPORTED"
    )

    assert provider.calls == []


def test_invalid_voice_fails_before_generation(manager):
    mgr, provider = manager

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="missing",
    )

    assert result["status"] == "FAILED"

    assert "VOICE_NOT_FOUND" in result["error"]

    assert provider.calls == []


def test_empty_text_fails(manager):
    mgr, provider = manager

    result = mgr.synthesize_long_text(
        text="",
        language="vi",
        voice_id="fake-voice",
    )

    assert result["status"] == "FAILED"

    assert "INVALID_TEXT" in result["error"]

    assert provider.calls == []


def test_output_is_24000_hz(manager):
    mgr, _ = manager

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    info = sf.info(
        result["wav_path"]
    )

    assert info.samplerate == 24000


def test_chunk_metadata_reports_completion(manager):
    mgr, _ = manager

    result = mgr.synthesize_long_text(
        text=make_text(),
        language="vi",
        voice_id="fake-voice",
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"

    assert len(
        result["chunks"]
    ) == 3

    assert all(
        chunk["status"] == "COMPLETED"
        for chunk in result["chunks"]
    )

    assert all(
        chunk["attempts"] == 1
        for chunk in result["chunks"]
    )


def test_long_text_reports_paragraph_boundary_diagnostics(manager):
    mgr, _provider = manager
    result = mgr.synthesize_long_text(
        text="Đây là đoạn thứ nhất.\n\nĐây là đoạn thứ hai?",
        language="vi",
        voice_id="fake-voice",
        chunk_config=ChunkingConfig(
            target_chars=500,
            max_chars=500,
            max_sentences_per_chunk=1,
        ),
    )

    assert result["status"] == "COMPLETED"
    assert result["chunk_count"] == 2
    assert result["boundary_diagnostics"][0]["boundary_after"] == "paragraph"
    assert 550 <= result["boundary_diagnostics"][0]["pause_after_ms"] <= 750
    audio, rate = sf.read(result["wav_path"])
    assert rate == 24000 and audio.ndim == 1
    assert np.isfinite(audio).all()

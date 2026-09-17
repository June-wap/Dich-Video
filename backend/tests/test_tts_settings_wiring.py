"""Task 2/4/5: Settings > Audio/Performance/Advanced tabs actually reach the
Short TTS pipeline (output_format was already real before this session -
retry_count, num_steps and output_dir were not). Goes through the real
create_app() lifecycle (like test_long_form.py's harness) rather than
constructing TTSService by hand, so AppSettingsService is wired in exactly
as it is at real backend startup.
"""
import time

import pytest
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.tests.provider_fakes import FakeCloneProvider, FakePiperProvider, registry


def payload(**overrides):
    base = {"text": "Xin chào, đây là bài kiểm tra.", "language": "vi", "format": "wav"}
    base.update(overrides)
    return base


def wait_http(client, job_id, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/tts/jobs/{job_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in {"COMPLETED", "FAILED"}:
            return body
        time.sleep(0.005)
    pytest.fail("Job did not terminate in time")


@pytest.fixture
def harness(tmp_path):
    settings = Settings(output_dir=tmp_path / "outputs", database_path=tmp_path / "app.sqlite3")
    provider = FakeCloneProvider()
    providers = registry(provider)
    app = create_app(settings, provider_service_factory=lambda _: providers)
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, provider, app.state.app_settings_service, settings


def test_num_steps_setting_reaches_the_provider(harness):
    client, provider, app_settings, _ = harness
    client.post("/api/settings/app", json={"num_steps": 32})
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    assert provider.last_synthesize_options.get("num_step") == 32


def test_default_num_steps_is_not_forced_onto_the_provider_call(harness):
    """No Settings save at all -> resolve_num_steps() returns None, so the
    provider call still receives num_step=None (never having saved Settings
    must be indistinguishable from this field not existing at all - the real
    OmniVoiceProvider then falls back to its own per-mode default, 16 for
    normal TTS / 24 for voice cloning - see resolve_num_steps()'s docstring
    in app_settings_service.py for why a flat 16 would be wrong for cloning)."""
    client, provider, _, _ = harness
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    assert provider.last_synthesize_options.get("num_step") is None


def test_default_retry_count_means_single_attempt_when_nothing_saved(harness):
    """No Settings save at all -> resolve_retry_count() returns 1 (today's
    exact legacy behavior: one attempt, no retry loop), not the schema's
    newer retry_count=2 default - see resolve_retry_count()'s docstring."""
    client, provider, _, _ = harness
    provider.fail_synthesize_count = 1
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 500
    assert provider.synthesize_calls == 1


def test_silence_trim_setting_reaches_the_provider(harness):
    client, provider, _, _ = harness
    client.post("/api/settings/app", json={"silence_trim": True})
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    assert provider.last_synthesize_options.get("trim_silence") is True


def test_default_silence_trim_is_false_when_nothing_saved(harness):
    client, provider, _, _ = harness
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    assert provider.last_synthesize_options.get("trim_silence") is False


def test_retry_count_retries_on_transient_failure_then_succeeds(harness):
    client, provider, _, _ = harness
    client.post("/api/settings/app", json={"retry_count": 2})
    provider.fail_synthesize_count = 1  # fails once, then a normal call succeeds
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert provider.synthesize_calls == 2  # 1 failed attempt + 1 successful retry


def test_retry_count_one_means_no_retry_matching_prior_behavior(harness):
    client, provider, _, _ = harness
    client.post("/api/settings/app", json={"retry_count": 1})
    provider.fail_synthesize_count = 1
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 500
    assert provider.synthesize_calls == 1


def test_output_directory_setting_changes_where_new_jobs_write(harness, tmp_path):
    client, _, _, settings = harness
    custom_dir = tmp_path / "customer_chosen_folder"
    client.post("/api/settings/app", json={"output_dir": str(custom_dir)})
    response = client.post("/api/tts", json=payload())
    assert response.status_code == 200
    gen_id = response.json()["data"]["generation_id"]
    assert (custom_dir / f"{gen_id}.wav").is_file()
    assert not (settings.output_dir / f"{gen_id}.wav").exists()


# ---------------------------------------------------------------------------
# Regression: num_step/silence_trim must never reach PiperProvider, which
# rejects ANY unrecognized keyword option outright. TTSService routes six
# languages to Piper (see PiperProvider.LANGUAGES) - before this test existed,
# nothing exercised that route at all, so an earlier version of this same
# num_steps/retry_count wiring silently broke every Piper-language job with
# INVALID_OPTIONS (num_step landing in Piper's **options). See TTSService._run()'s
# `is_piper`/`primary_only_options` handling.
# ---------------------------------------------------------------------------

class _FakeConfiguredTranslationService:
    """Piper languages are always non-Vietnamese, so TTSService._run() always
    calls translate() first (see its `if language != "vi"` branch) - this
    stub skips the real Gemini SDK/network call entirely (echoes the text
    unchanged) so the Piper-routing regression test below isn't coupled to
    translation working, only to num_step/trim_silence never reaching Piper.
    """

    def is_configured(self):
        return True

    def translate(self, text, target_language):
        return text


@pytest.fixture
def piper_harness(tmp_path):
    settings = Settings(output_dir=tmp_path / "outputs", database_path=tmp_path / "app.sqlite3")
    omnivoice_provider = FakeCloneProvider()
    piper_provider = FakePiperProvider()
    # Pass this exact instance through so the test can assert on it below -
    # registry(with_piper=True) alone would construct and register a
    # different, un-asserted FakePiperProvider (see registry()'s docstring
    # comment in provider_fakes.py).
    providers = registry(omnivoice_provider, piper_provider=piper_provider)
    app = create_app(settings, provider_service_factory=lambda _: providers,
                     translation_service_factory=lambda _: _FakeConfiguredTranslationService())
    with TestClient(app, base_url="http://127.0.0.1") as client:
        yield client, piper_provider


def test_piper_language_job_succeeds_even_with_num_steps_and_silence_trim_saved(piper_harness):
    client, piper_provider = piper_harness
    client.post("/api/settings/app", json={"num_steps": 32, "silence_trim": True})
    # voice_id must be explicit None here, not omitted: TTSRequest's schema
    # default is "omnivoice_auto" (correct for the common vi/OmniVoice case
    # payload() is normally used for), but the real frontend always submits
    # an explicit voice_id (falling back to null, never omitting the field -
    # see useTtsJobRunner.ts's `voice_id: payload.voiceId || null`), which
    # lets validate_request() apply its own per-provider default
    # (PiperProvider.AUTO_VOICE_ID for a Piper language). Omitting the key
    # here would instead let pydantic fill in the OmniVoice-specific schema
    # default, which is not a valid Piper voice id and would wrongly fail
    # with VOICE_NOT_FOUND before ever reaching the code this test guards.
    response = client.post("/api/tts", json=payload(language="it", voice_id=None))
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert piper_provider.synthesize_calls == 1
    # Piper never receives the OmniVoice-only kwargs at all - not even as
    # False/None - matching its exact pre-existing calling convention.
    assert piper_provider.last_synthesize_options == {}


def test_audio_still_served_after_output_directory_changes_again(harness, tmp_path):
    """A file generated under directory A must still be servable at its
    original audio_url even after Settings > Audio > Output Directory is
    changed to point at directory B for future jobs - see
    TTSService.resolve_audio_path()."""
    client, _, _, _ = harness
    first_dir = tmp_path / "first"
    client.post("/api/settings/app", json={"output_dir": str(first_dir)})
    first = client.post("/api/tts", json=payload())
    audio_url = first.json()["data"]["audio_url"]

    second_dir = tmp_path / "second"
    client.post("/api/settings/app", json={"output_dir": str(second_dir)})

    replay = client.get(audio_url)
    assert replay.status_code == 200

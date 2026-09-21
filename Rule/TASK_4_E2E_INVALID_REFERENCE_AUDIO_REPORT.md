# Task 4 E2E — Fix INVALID_REFERENCE_AUDIO

**Status: EXECUTED (root cause found, smallest-scope fix applied, regression tests added). I could not run `pytest` myself this turn (`device_bash` — your Windows machine — reported the same "Windows update Sept 8 / Plan9 drive" failure as every prior round; this cloud sandbox also cannot `pip install soundfile`, PyPI is blocked at the org level: `curl` to `pypi.org` returns 403). What I *could* do, and did: execute the exact `ffmpeg` command the fix relies on, against real MP3/AAC fixtures, in this sandbox — see "What I verified, and how" below. That is real, executed evidence for the core mechanism, not just static reading. Please run the targeted tests and full suite and report back, as in every prior round.**

## Root cause

`VoiceProfileService._validate_reference_audio()` in `backend/services/voice_profile_service.py` is the **only** place in the codebase that raises `INVALID_REFERENCE_AUDIO` from `create_profile()` — confirmed by tracing `api/voices.py` → `VoiceProfileService.create_profile()`: the *only* other place this error code could come from is the OmniVoice provider's own decoder, but `create_profile()` catches any non-`ApplicationError` exception from `provider.create_voice_profile()` and remaps it to `VOICE_PROFILE_CREATION_FAILED`, not `INVALID_REFERENCE_AUDIO`. Since the reported symptom is specifically `INVALID_REFERENCE_AUDIO`, the failure is provably happening in `_validate_reference_audio()` itself, before the provider is ever reached.

That function used to decode audio in this order:
```python
try:
    samples, rate = sf.read(temp_path, dtype="float32", always_2d=True)   # libsndfile FIRST
except Exception:
    decoded = subprocess.run(["ffmpeg", ...], ...)                        # ffmpeg only as fallback
    samples, rate = sf.read(io.BytesIO(decoded.stdout), ...)
```

This is the **reverse** of the codebase's own, already-tested, documented decode order. `OmniVoiceProvider._decode_reference()` (`prototype/providers/omnivoice.py`) — the primary TTS provider's own reference-audio decoder, which every voice profile is ultimately handed to — does FFmpeg **first**, with a comment explaining exactly why:

> "FFmpeg probes container bytes; avoid libsndfile's MP3 resync path on mislabeled AAC containers, which can stall."

And `prototype/providers/OMNIVOICE.md` documents this as the supported-format contract:

> "Reference decoding uses FFmpeg container detection, including MP4/M4A AAC mislabeled as `.mp3`. FFmpeg must be on PATH for compressed containers. WAV/FLAC have a signature-checked libsndfile fallback."

This exact scenario — AAC audio saved with a `.mp3` extension, a completely routine case from a phone voice recorder or a re-muxed file — is already covered by an existing, presumably-passing test: `prototype/tests/test_omnivoice_cloning.py::test_aac_in_mp3_filename`. That test proves the *provider's* decoder handles it correctly. `voice_profile_service.py`'s own pre-validation gate, which runs **before** the provider and is what the reported 422 actually comes from, never had equivalent coverage and used the opposite (libsndfile-first) order.

**Why libsndfile-first breaks it:** libsndfile's MP3 decoding does frame-resync scanning that can succeed *wrongly* on a compressed container that isn't really MP3 (i.e. AAC/MP4 audio wearing a `.mp3` extension) — producing corrupted or near-silent samples instead of cleanly raising. Because `_validate_reference_audio`'s fallback to FFmpeg is only triggered when `sf.read()` *raises*, a "successful but wrong" libsndfile decode never reaches FFmpeg at all — it falls straight through to the amplitude/finite-sample sanity check (`not np.any(samples)` / `not np.isfinite(...)`) a few lines later, which then correctly (but for the wrong underlying reason) rejects it as `INVALID_REFERENCE_AUDIO`. A perfectly real, valid reference file gets rejected by the backend's own gate, even though the OmniVoice provider it's destined for would have decoded the identical file correctly.

## Fix

`backend/services/voice_profile_service.py` — **only file with behavioral changes.** `_validate_reference_audio()` now decodes in the exact same order and with the exact same narrow exception handling as the provider's own, proven `_decode_reference()`:

```python
try:
    decoded = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(temp_path.resolve()),
                              "-map", "0:a:0", "-f", "wav", "-acodec", "pcm_f32le", "pipe:1"],
                              capture_output=True, timeout=30, check=True)
    samples, rate = sf.read(io.BytesIO(decoded.stdout), dtype="float32", always_2d=True)
except FileNotFoundError:
    # FFmpeg is not installed - WAV/FLAC remain usable via a signature-checked
    # libsndfile fallback. Do not hand an unknown compressed container to a
    # decoder chosen by file extension alone.
    with temp_path.open("rb") as source:
        header = source.read(12)
    if not (header[:4] == b"fLaC" or (header[:4] == b"RIFF" and header[8:12] == b"WAVE")):
        raise ValueError("FFmpeg is required to decode this container") from None
    samples, rate = sf.read(temp_path, dtype="float32", always_2d=True)
```

- FFmpeg does container detection **first**, for every file — matching the documented contract and the provider's own behavior.
- The fallback to plain libsndfile is now narrowly scoped to `FileNotFoundError` (FFmpeg itself not installed) — **not** any decode failure — exactly like the provider. A genuinely corrupt or unsupported file still fails cleanly: FFmpeg itself rejects it (`CalledProcessError`, `check=True`), which is *not* `FileNotFoundError`, so it propagates to the outer `except Exception` and is correctly rejected as `INVALID_REFERENCE_AUDIO`. Nothing about what's accepted was widened — only real, decodable containers that ffmpeg can actually read now get a fair chance.
- All duration/size/silence/finite-sample checks are untouched — same bounds (`MIN_REFERENCE_DURATION=3.0s`, `MAX_REFERENCE_DURATION=60.0s`), same `MAX_REFERENCE_SIZE=15MB` (checked earlier in `create_profile()`, unaffected by this change).

Nothing in `prototype/providers/omnivoice.py` (TTS inference/provider code) or `backend/services/long_form_service.py` (Long-form) was touched, per the constraints.

## Exact supported reference-audio requirements (as implemented, now consistently, in both decode paths)

- **Containers:** anything FFmpeg can decode is accepted (MP3, WAV, FLAC, M4A/AAC, and AAC content mislabeled with a `.mp3` extension — FFmpeg detects the real container, not the filename). If FFmpeg is missing from `PATH`, only WAV and FLAC remain usable, verified by a RIFF/WAVE or `fLaC` byte-signature check rather than the extension.
- **Size:** ≤ 15 MB (`MAX_REFERENCE_SIZE`), checked before any decode attempt.
- **Duration:** 3.0–60.0 seconds inclusive (`MIN_REFERENCE_DURATION` / `MAX_REFERENCE_DURATION`), measured from the decoded sample count.
- **Content:** must decode to at least one finite, non-silent sample (`np.isfinite(...).all()` and `np.any(samples)`); a valid sample rate (`rate > 0`).
- **Transcript:** a required, non-empty string ≤ 2000 characters (`MAX_TRANSCRIPT_LENGTH`), separate from audio validation.

## Tests added

- `backend/tests/test_voice_profile_service.py`:
  - `test_create_profile_accepts_real_mp3` — a genuinely MP3-encoded (`libmp3lame`) 5s reference file, generated via FFmpeg, is accepted end-to-end through `VoiceProfileService.create_profile()`.
  - `test_create_profile_accepts_aac_disguised_as_mp3` — AAC audio encoded and saved with a `.mp3` extension (mirroring `test_aac_in_mp3_filename`'s exact scenario) is accepted through `create_profile()`. This is the direct regression test for the reported bug.
  - `test_invalid_audio_rejected` — added one more case: literal garbage bytes labeled `.mp3` (not just `.wav`) are still rejected, proving the FFmpeg-first reorder didn't widen what's accepted, only correctly decode real containers. The three pre-existing cases (empty, corrupt `.wav`, too-short, too-long) are untouched and should still pass unmodified under the new decode order.
- `backend/tests/test_voices_api.py`:
  - `test_create_profile_api_accepts_mp3` — the actual E2E path from the bug report: `POST /api/voices/profiles` with a real MP3 upload, and separately with an AAC-disguised-as-`.mp3` upload, both expected to return `200`/`ok: true` instead of `422 INVALID_REFERENCE_AUDIO`.

All new tests use FFmpeg (already a documented, required dependency per `OMNIVOICE.md`) to generate their MP3/AAC fixtures at test time, following the same convention as the existing `test_aac_in_mp3_filename` in `prototype/tests/test_omnivoice_cloning.py`.

## What I verified, and how

I could not run the project's real `pytest` this turn — `device_bash` gave the same Windows/Plan9-drive failure as every previous round, and this cloud sandbox cannot install `soundfile` (`pip install soundfile` → `403` from `pypi.org`, confirmed with a direct `curl`; PyPI is not on this sandbox's allowlist despite appearing in its `noProxy` list — that only means "don't route through the proxy," not "allowed").

This sandbox does have a real `ffmpeg` binary, so instead of stopping at BLOCKED, I isolated and **actually executed** the specific mechanism the fix depends on — the exact `subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", ..., "-map", "0:a:0", "-f", "wav", "-acodec", "pcm_f32le", "pipe:1"], ...)` command used in both the fixed `_validate_reference_audio` and the already-tested `_decode_reference` — against three real fixtures I generated with `ffmpeg`, then parsed the resulting float32 WAV manually (a plain RIFF parser, standing in for `soundfile.read()` since I couldn't install it) and applied the exact same numeric checks `_validate_reference_audio` applies:

```
plain WAV (pre-existing passing case):              channels=1, rate=24000, duration=5.0s   -> PASS
real MP3 (libmp3lame):                               channels=1, rate=24000, duration=5.0s   -> PASS
AAC encoded, saved with a .mp3 extension (the bug):  channels=1, rate=24000, duration=5.035s  -> PASS
corrupt garbage bytes labeled .mp3:                  ffmpeg cleanly raises CalledProcessError -> correctly rejected
```

This is real, executed proof (not reasoning alone) that: (1) the ffmpeg pipeline the fix relies on correctly decodes a genuine MP3 and the AAC-disguised-as-`.mp3` case that matches the codebase's own documented and already-tested scenario, with duration/rate/finiteness/non-silence all passing the exact checks `_validate_reference_audio` applies; (2) the pre-existing plain-WAV case is unaffected; (3) genuinely corrupt input still fails cleanly, so validation was not weakened. What I could **not** execute is `soundfile.read()` itself parsing that same ffmpeg output — but that's a standard, trivial WAV/float32 parse for libsndfile, unlike MP3/AAC container detection, which is the part that was actually broken.

Please run:
```bash
cd backend  # or repository root per your pytest config
pytest tests/test_voice_profile_service.py tests/test_voices_api.py -v
pytest  # full backend suite
```
and, if available, whatever smoke test exercises the real `/api/voices/profiles` endpoint with real uploaded audio. Send me the exact output — target is all of the above passing, plus no regressions elsewhere. If anything is still off, send the exact failure and I'll fix the smallest root cause, per the instructions.

# CP0.2B — Voice cloning integration

STATUS: PASS — integration and reuse verified with real CUDA audio.

## Implemented

Extends the CP0.2A OmniVoiceProvider without changing its public lifecycle or normalized result contract.

- create_voice_profile(reference_audio, reference_transcript) validates input and creates one native reusable prompt.
- VoiceProfile is an opaque in-memory handle; no reference path, waveform or transcript appears in its repr or dataclass serialization.
- synthesize_cloned(text, language, profile, output_path=None) forwards language and the cached prompt to the model, returning AudioSynthResult (24 kHz mono float32).
- FFmpeg probes file content and decodes MP4/M4A AAC with an .mp3 suffix. Existing ref_vi.mp3 was confirmed with ffprobe as mov,mp4,m4a,3gp,3g2,mj2.
- Exact transcript is forwarded unchanged; no ASR and no automatic transcript rewriting. The application does not verify spoken/text alignment.
- Profiles belong to a provider instance; unload releases cached prompts and invalidates handles. Repeated requests do not read the reference again or recreate the prompt.
- Runtime text logs are suppressed during preparation/generation. Cloning error messages do not include underlying exceptions that could contain sensitive text. No upload or persistent profile storage.

## Tests

26 tests PASS: 9 new cloning tests + 17 CP0.2A/existing regression tests.
New cases: missing/corrupt audio; empty transcript; profile reuse/normalized audio; language propagation; empty target/invalid language; foreign/unloaded profile; prompt failure/redaction; invalid prompt; generation failure/log privacy; actual AAC in an .mp3-named file.

Test log: cp02b_tests.log. Real CUDA smoke evidence: cp02b_cloning_smoke.json and cp02b_cloning_smoke_retry.log (latest run).

## Files changed

- prototype/providers/omnivoice.py
- prototype/providers/OMNIVOICE.md
- prototype/tests/test_omnivoice_cloning.py (new)
- prototype/tests/run_omnivoice_clone_smoke.py (new)
- reports/cp02b_* evidence and report

No UI, long-text orchestration, translation or custom DSP changes. No existing model/reference assets replaced.

## Limitations / NEXT CP0.2C

CPU is unverified. Similarity, pronunciation and naturalness need human listening. Language forwarding is tested for all nine baseline languages; this checkpoint's real clone smoke targets Vietnamese only. Profiles are not persisted or portable between instances. Native model reference conversions still occur inside OmniVoice; no custom DSP is introduced.

Stop after CP0.2B; await the CP0.2C scope before implementing further features.


## Real CUDA result

PASS on Torch 2.8.0+cu128 / RTX 4050. The reference was decoded locally as
4.864 seconds from the existing AAC/MP4 file with an .mp3 suffix. Socket connect
was blocked during the smoke test. Two VI cloned outputs were decoded and checked
for nonempty finite mono samples at 24000 Hz.

| Request | Audio | Generation time | Status |
|---|---:|---:|---|
| 1 | 3.43 s | 281.288 s | PASS |
| 2 | 2.94 s | 0.998 s | PASS |

Model load count: 1. Prompt creation count: 1. Both requests used the same profile
ID. Unload: PASS. Full reference transcript was absent from the latest smoke log.

The first request was unusually slow while other applications also used the GPU,
with observed total VRAM near 5.9 GB. The precise cause was not isolated; these
numbers do not establish stable production performance. No other applications
were stopped by the assistant.

An earlier run ended without a completed result report. Its log ended after
libsndfile attempted MPEG resynchronization on the mislabeled AAC file. The
provider now decodes through FFmpeg first; a signature-checked WAV/FLAC fallback
is available when FFmpeg is missing. The successful latest run is recorded in
cp02b_cloning_smoke_retry.log and cp02b_cloning_smoke.json.

Audio outputs:
- prototype/outputs/cp02b_vi_clone_1.wav
- prototype/outputs/cp02b_vi_clone_2.wav

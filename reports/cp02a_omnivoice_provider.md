# CP0.2A — OmniVoice Provider Skeleton

Status: PASS (short TTS integration and lifecycle). Previous prototype task stopped at user request.

## Implemented

- Optional ManagedTTSProvider lifecycle contract; existing providers unchanged.
- OmniVoiceProvider: load, is_loaded, capabilities, synthesize, unload.
- One model instance reused under a lock; concurrent requests cannot duplicate load.
- AudioSynthResult: float32 mono PCM, native 24000 Hz, duration, provider_id, language, generation_time and metadata. Compatible with existing SynthResult and TTSManager.
- Strict language propagation to runtime, no language-agnostic fallback for invalid input.
- Local cached model loading; no automatic CPU fallback or model downloads.
- CPU explicitly unverified; production_ready=false.

## Tests

12 provider tests PASS: abstraction/capabilities, load/reuse/unload/reload, all nine language arguments, empty/invalid input, normalized result/logging, load retry, generation failure recovery, native sample rate, invalid PCM, concurrent reuse, existing manager routing, CUDA cache release.
5 existing regression tests PASS. Total 17 PASS.

Real CUDA smoke: PASS, Python 3.12.10, Torch 2.8.0+cu128, NVIDIA GeForce RTX 4050 Laptop GPU. Local offline environment flags enabled.

| Request | Language | Audio duration | Generation time | Load count | Output |
|---|---|---:|---:|---:|---|
| 1 | vi | 3.46 s | 8.367 s | 1 | prototype/outputs/cp02a_vi_1.wav |
| 2 | vi | 3.01 s | 4.928 s | 1 | prototype/outputs/cp02a_vi_2.wav |

Both files decoded successfully, 24000 Hz, mono, non-silent. Unload PASS. Timings are observations from this run, not performance guarantees.

## Files changed in CP0.2A

- Modified: prototype/providers/base.py
- Added: prototype/providers/omnivoice.py
- Added: prototype/providers/OMNIVOICE.md
- Added: prototype/tests/test_omnivoice_provider.py
- Added: prototype/tests/run_omnivoice_smoke.py
- Evidence: reports/cp02a_provider_tests.log, cp02a_omnivoice_smoke.log, cp02a_omnivoice_smoke.json, this report, two WAV outputs.

No UI, business logic, external model/repository or old checkpoint artifacts changed during CP0.2A. Earlier prototype edits remain in place; they were not reverted or continued.

## Limitations / next

Nine verified languages refer to existing external/OmniVoice/benchmark_results.json (9/9 PASS). This checkpoint adds real Vietnamese provider smoke and verifies language forwarding with unit tests; it does not repeat the entire baseline benchmark. Human audio quality, CPU, long text, cloning, DSP and production readiness are not verified or implemented here.

No further implementation started. Usage and exact commands: prototype/providers/OMNIVOICE.md.

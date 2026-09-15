# CP0.2A — OmniVoice provider

Current runtime authority: [CP0.3B-0 backend runtime](../../docs/backend_runtime.md).
Use `external/OmniVoice/.venv312` for all current backend/test commands; older
checkpoint commands below are historical evidence, not alternative runtimes.

Original CP0.2A scope: short TTS and lifecycle. CP0.2B adds reusable cloning profiles. Reuses `TTSProvider`, `SynthResult` and
`TTSManager`. No UI or business module imports the OmniVoice runtime.

`ManagedTTSProvider` adds the optional lifecycle contract without changing the
requirements on existing providers. `AudioSynthResult` exposes float32 PCM in
`audio`, along with `sample_rate`, `duration`, `provider_id`, `language`,
`generation_time` and `metadata`. It retains existing `gen_time`/`provider` fields
for compatibility. PCM is excluded from dataclass log serialization.

Run from the repository root using the existing verified environment:

```powershell
external\OmniVoice\.venv312\Scripts\python.exe -m unittest discover -s prototype\tests -p test_omnivoice_provider.py -v
external\OmniVoice\.venv312\Scripts\python.exe -u prototype\tests\run_omnivoice_smoke.py
```

Usage (with `prototype` on Python's module search path):

```python
from providers.base import ManagedTTSProvider
from providers.omnivoice import OmniVoiceProvider

provider: ManagedTTSProvider = OmniVoiceProvider(device="cuda:0")
try:
    provider.load()  # optional; synthesize also loads lazily
    result = provider.synthesize("Xin chào!", "vi")
    if result.status == "PASS":
        print(result.audio.shape, result.sample_rate, result.generation_time)
    else:
        print(result.error)
finally:
    provider.unload()
```

An existing manager can use `manager.register_provider(provider)` and route
requests with voice ID `omnivoice_auto`. No UI wiring is part of CP0.2A.

The model loads once per provider instance; load, generate and unload are
serialized with a lock. Unload releases the model reference and unused CUDA
allocator cache; it does not destroy the process-wide CUDA context. A later
request may reload explicitly or lazily.

Default model: `k2-fsa/OmniVoice`, resolved from local Hugging Face cache only.
An explicit local snapshot path is also accepted. The snapshot must include
`audio_tokenizer/`. No automatic download or CPU fallback is performed.

Native 24000 Hz is required. Output must be finite, nonempty, mono float32.
No resampling or DSP is added. `output_path` optionally writes PCM16 WAV.
Standard TTS uses auto voice; cloned TTS uses an explicit VoiceProfile. Both use default speed and 16 generation steps.

Capabilities list nine baseline-verified languages: vi, en, zh, ja, es, pt, it,
fr, hi. Evidence is the existing `external/OmniVoice/benchmark_results.json`.
This checkpoint reruns two Vietnamese requests through the new adapter; it
does not rerun the previous nine-language benchmark or certify audio quality.
CPU is unverified and requires explicit `allow_unverified_cpu=True` for
experimental use. No production readiness claim is made.

`load()` raises `OmniVoiceError(MODEL_LOAD_FAILED)`; `synthesize()` follows the
existing FAIL-result convention with an error code in metadata. Empty text,
unsupported languages, unsupported options, load/generation/export errors
have distinct messages. Failed input validation never loads the model.

Out of scope: long-text support, translation, DSP, production UI,
database and installer. Existing CP0 assets are not modified.


## CP0.2B — reusable voice cloning

```python
provider = OmniVoiceProvider()
try:
    profile = provider.create_voice_profile("reference.mp3", "Exact spoken reference transcript.")
    first = provider.synthesize_cloned("Xin chào!", "vi", profile)
    second = provider.synthesize_cloned("Hello!", "en", profile)
finally:
    provider.unload()
```

Reference decoding uses FFmpeg container detection,
including MP4/M4A AAC mislabeled as `.mp3`. FFmpeg must be on PATH for compressed containers. WAV/FLAC have a signature-checked libsndfile fallback. Missing, corrupt, empty/nonfinite or silent audio is rejected before
model loading. The exact transcript is mandatory, forwarded unchanged with
`preprocess_prompt=False`; no automatic transcription is invoked. This validates
presence, not whether a human transcript is factually accurate.

A VoiceProfile is an opaque in-memory handle. The provider owns its encoded
prompt and reuses that same prompt without rereading audio or re-encoding it.
Handles are specific to their provider instance and become invalid on unload.
They are not portable or persisted. No raw reference waveform or transcript is
included in the handle, repr, synthesis metadata or logs. Runtime text debug logs
are suppressed during prompt preparation/generation, and cloning exceptions are
sanitized. No upload is performed; smoke tests also block socket connections.

`create_voice_profile()` raises coded OmniVoiceError on invalid input/prompt.
`synthesize_cloned()` returns the same AudioSynthResult contract as CP0.2A,
including FAIL/error_code for invalid profiles, language, text or generation.
No additional DSP is implemented; OmniVoice's native reference preprocessing
still performs the conversions required by its tokenizer.

Run CP0.2B checks from the repository root:

```powershell
external\OmniVoice\.venv312\Scripts\python.exe -m unittest discover -s prototype\tests -p "test_*.py"
external\OmniVoice\.venv312\Scripts\python.exe -u prototype\tests\run_omnivoice_clone_smoke.py
```

Real smoke reuses the existing reference audio and transcript from the prior
OmniVoice cloning baseline. Only Vietnamese cloning is tested with real inference
in CP0.2B; other target-language arguments are verified in unit tests. Human
similarity/naturalness scoring and CPU remain unverified.
## CP0.2C — deterministic language handling

Canonical metadata lives in `core/languages.py`; `text_utils.LANGUAGE_NAMES`
remains a compatible export. IDs accepted by both normal and cloned synthesis
are exactly: `vi,en,zh,ja,es,pt,it,fr,hi`. Names, aliases, region codes, whitespace,
uppercase IDs and `None` are rejected; they are never silently mapped or passed
into OmniVoice's language-agnostic fallback.

`language_status(id)` returns:
- `VERIFIED`: one of the nine CUDA normal short-TTS baseline languages.
- `EXPERIMENTAL-UPSTREAM`: present in the pinned upstream ID snapshot but not
  benchmarked locally. Exposed separately in capabilities, disabled for synthesis.
- `UNSUPPORTED`: unknown or malformed ID.

The upstream snapshot in `core/omnivoice_upstream_languages.json` records its
local source and SHA256; it is metadata, not a runtime import or a production
verification claim. Updates to upstream do not silently expand accepted input.

Both synthesis modes return `metadata.diagnostics`: provider, language, language
status, device, actual model dtype when known, audio dtype, generation time,
duration, RTF, mode and status. A missing runtime dtype is null, not an invented
CPU/GPU result. Audio remains float32, independently of float16 model weights.
Nine-language VERIFIED refers to the existing normal-TTS benchmark; real cloned
verification remains Vietnamese only. Production readiness is still false.

```powershell
.cp0\venv\Scripts\python.exe -m unittest discover -s prototype\tests -p "test_*.py"
external\OmniVoice\.venv312\Scripts\python.exe -u prototype\tests\run_omnivoice_language_smoke.py
```

The targeted smoke generates EN normal and VI cloned speech only. It does not
repeat the nine-language benchmark. Reports: `reports/cp02c_tests.log`,
`reports/cp02c_smoke.json`, `reports/cp02c_smoke.log`.

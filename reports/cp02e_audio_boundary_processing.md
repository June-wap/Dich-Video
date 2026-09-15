# CP0.2E — Audio Boundary Processing

STATUS:
PASS_WITH_LIMITATIONS

IMPLEMENTED:
- Centralized punctuation and paragraph pause policy in `PausePolicy`.
- Default pauses use values inside the requested starting ranges: comma 150 ms, semicolon 240 ms, colon 260 ms, period 350 ms, question 450 ms, exclamation 400 ms and paragraph 650 ms.
- Preserved `TextChunk.is_paragraph_end` through pause selection and boundary diagnostics.
- Added conservative leading/trailing silence trim with a -48 dBFS threshold, 5 ms probes, 35 ms retained edge padding and a 250 ms maximum trim per edge.
- Added 3 ms edge fades to reduce click/pop. Optional crossfade is limited to 20 ms, only applies when the boundary pause is zero, and remains disabled by default to avoid overlapping speech.
- Loudness adjustment is disabled by default. When explicitly enabled, gain is capped at ±1.5 dB.
- Forced merged output to 24000 Hz mono.
- Added per-segment diagnostics for trim, fade, gain, boundary kind and inserted pause. Logs contain metadata only.
- Reused the CP0.2D chunker and normal OmniVoice lifecycle without redesign.

TESTS:
- CP0.2E targeted boundary and manager tests: 27/27 PASS.
- Full CP0.2A–E regression: 92/92 PASS.
- Covered punctuation pause selection, paragraph priority, non-universal pauses, trim cap/padding, order, short chunks, edge fades, click/pop discontinuity bound, sample rate, mono output, finite samples and valid WAV decoding.
- Live CUDA smoke: PASS for technical validation. Three Vietnamese chunks completed in order with model `load_count=1`.
- Live output: 24000 Hz mono, 9.845 seconds; generation time 16.389 seconds; RTF 1.6647.
- Live diagnostics: chunk-edge trims were 140/195 ms, 115/130 ms and 150/175 ms; the two sentence boundaries received 350 ms period pauses; gain remained 0 dB and crossfade remained disabled.

LIVE LISTENING — SUBJECTIVE:
- The processed Vietnamese file was generated successfully at `prototype/outputs/cp02d_long_vi.wav` for human listening.
- No subjective listening verdict is claimed: this execution environment can generate and inspect audio data but cannot perceive playback. Automated waveform checks are recorded separately and are not treated as a listening PASS.
- Human review should focus on whether 350 ms sentence pauses feel natural, whether retained breaths sound intact, and whether either join is audible. Findings can then tune the centralized policy without changing the chunker.

FILES CHANGED:
- `prototype/core/audio_utils.py`
- `prototype/core/tts_manager.py`
- `prototype/tests/test_audio_boundary.py`
- `prototype/tests/test_long_text_manager.py`
- `reports/cp02e_audio_boundary_processing.md`
- Updated live evidence: `reports/cp02d_omnivoice_long_text_smoke.json`
- Updated live outputs: `prototype/outputs/cp02d_long_vi.wav`, `prototype/outputs/cp02d_long_vi.mp3`

LIMITATIONS:
- Subjective listening requires human playback and remains pending.
- Live inference covered Vietnamese CUDA normal TTS only.
- CPU remains unverified.
- DSP uses conservative fixed configuration defaults; language- or voice-specific tuning is not included.
- pydub emits the existing Python 3.13 `audioop` deprecation warning; Python 3.12 is unaffected.

NEXT:
CP0.2F after human listening feedback is recorded, or with the current conservative defaults accepted as the CP0.2E baseline.

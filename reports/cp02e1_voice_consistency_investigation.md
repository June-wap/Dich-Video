# CP0.2E.1 — Voice Consistency & Robotic Diagnostic

## STATUS

PASS_WITH_LISTENING_REQUIRED. Human listening confirms voice drift between generated chunks. Automated evidence independently confirms non-deterministic OmniVoice generation and shows that DSP fade and merge do not explain whole-chunk voice changes. The subjective robotic quality of the raw and `num_step` alternatives still requires human A/B listening and is not presented as an automated quality verdict.

## ENVIRONMENT

- Python 3.12.10; interpreter `external/OmniVoice/.venv312/Scripts/python.exe`.
- Torch 2.8.0+cu128; NVIDIA GeForce RTX 4050 Laptop GPU; CUDA FP16.
- OmniVoice normal TTS, language `vi`, 24000 Hz mono.

## EXISTING EVIDENCE REUSED

- Reused all 24 valid artifacts already generated in `reports/cp02e1_listening/`.
- Reused the completed raw/processed, chunk-size, `num_step` and repeatability measurements.
- No GPU inference was rerun for the report/schema update, and no WAV was overwritten.

## TESTS EXECUTED

- Test A: three repeated generations of identical text/settings.
- Test B: one set of five raw chunks routed through pause-only and current CP0.2E processing.
- Test C: runtime-derived A/B/C chunk plans over the same long text.
- Test D: `num_step` 16/24/32 over the same representative text.
- Test E: provider/model lifecycle observation across the entire controlled session.

## TEST CONFIG

- Python 3.12.10; Torch 2.8.0+cu128; NVIDIA GeForce RTX 4050 Laptop GPU.
- One `OmniVoiceProvider`, one loaded model, CUDA FP16 inference, language `vi`, 24000 Hz mono.
- Same 359-character Vietnamese text for raw/processed and all chunk-size variants.
- Crossfade disabled and gain disabled in every comparison.
- CUDA synchronization was performed before and after timed inference.
- Provider default remained unchanged at `num_step=16`.
- Underlying `generate()` accepts `num_step` through keyword arguments. Its inspected signature has no declared `seed`, `generator`, or `random_seed` parameter. It has `**kwargs`, but unsupported seed behavior was not invented or tested.

Chunk plans:

- A — one sentence per chunk: 5 chunks, 66/74/67/76/74 characters.
- B — maximum two sentences per chunk: 3 chunks, 141/144/74 characters.
- C — target 250–350 characters: 2 chunks, 286/74 characters.

## RAW VS PROCESSED RESULT

- `raw_merge.wav`: 22.690 s, RMS 0.092104, peak 0.5.
- `trim_merge.wav`: 21.035 s, RMS 0.095658, peak 0.5.
- Trim removed 1.655 s of detected edge silence across five chunks. Individual leading/trailing trims were 125–190 ms and remained below the configured 250 ms cap.
- `trim_fade_merge.wav` and `processed_merge.wav` are byte-identical. This is expected because current CP0.2E is trim + 3 ms fade with gain and crossfade disabled.
- Comparing trim-only with trim + fade: only 324 samples changed; maximum absolute difference was 0.002228 and mean absolute difference was 0.000000281.
- Raw merge only concatenates provider WAV data with semantic pauses. It does not alter the speech samples.

Conclusion: `DSP_FADE_ARTIFACT` and `MERGE_BOUNDARY_ARTIFACT` are not supported as explanations for voice identity changing across whole chunks. Trim changes boundary timing and could affect perceived breath/cadence, but the evidence does not show it changing voice identity. Human comparison of raw versus trim remains the correct check for any boundary-specific robotic impression.

## CHUNK SIZE RESULT

- A: 5 independent generations, output 21.035 s.
- B: 3 independent generations, output 20.775 s.
- C: 2 independent generations, output 20.895 s.
- Larger chunks deterministically reduce the number of fresh generation starts and prosody resets from five to three or two.
- RMS and spectral centroid vary between plans because each plan triggers new stochastic generations over different text spans. Those metrics cannot establish subjective voice quality.

Conclusion: `CHUNK_TOO_SHORT` is a supported contributing factor for transition frequency and prosody resets. Human A/B files are provided to decide whether B or C sounds best before changing chunk defaults.

## NUM_STEP RESULT

Same 141-character representative text and same loaded model:

| num_step | Duration | Generation | RTF | RMS | Spectral centroid |
|---:|---:|---:|---:|---:|---:|
| 16 | 8.170 s | 1.827 s | 0.2236 | 0.104001 | 2542.83 Hz |
| 24 | 8.180 s | 2.810 s | 0.3435 | 0.119716 | 1653.93 Hz |
| 32 | 8.190 s | 3.207 s | 0.3916 | 0.106515 | 2382.28 Hz |

`num_step` materially changes the generated waveform and costs more inference time, but the objective metrics are not monotonic and cannot label one output less robotic. `INFERENCE_QUALITY_SETTING` remains a candidate requiring human A/B listening. The production default was not changed.

## REPEATABILITY RESULT

The same 141-character chunk was generated three times:

| Run | Duration | Generation | RTF | RMS | Spectral centroid |
|---:|---:|---:|---:|---:|---:|
| 1 | 8.160 s | 1.621 s | 0.1987 | 0.107389 | 2298.51 Hz |
| 2 | 8.190 s | 2.064 s | 0.2520 | 0.111747 | 2209.67 Hz |
| 3 | 8.110 s | 2.515 s | 0.3101 | 0.104481 | 2252.55 Hz |

- Duration spread: 80 ms, under 1% of mean duration.
- RMS spread: about 6.8% from minimum to maximum.
- Time-normalized pairwise waveform correlations were -0.0415, -0.0080 and 0.0013, showing that repeated output is not waveform-deterministic.
- No explicit seed control is declared by the inspected API, so no unsupported parameter was supplied.

Conclusion: `NON_DETERMINISTIC_GENERATION` is confirmed.

## MODEL LIFECYCLE

- `load_count=1` after all raw, chunk-size, `num_step` and repeatability generations.
- The same provider/model instance was reused throughout.

## ROOT CAUSE CLASSIFICATION

- `NON_DETERMINISTIC_GENERATION` — CONFIRMED. Identical text/settings produce substantially different waveforms.
- `GENERATION_VOICE_DRIFT` — CONFIRMED BY HUMAN LISTENING. The provider starts a new stochastic generation for every chunk with no stable voice/seed control exposed; automated waveform evidence supports non-determinism but is not used as the speaker-identity proof.
- `CHUNK_TOO_SHORT` — CONTRIBUTING. One-sentence chunks maximize independent starts and prosody resets; B/C reduce boundaries from five to three/two.
- `INFERENCE_QUALITY_SETTING` — CANDIDATE. Step count changes output materially, but listening is required to select quality.
- `DSP_TRIM_ARTIFACT` — POSSIBLE ONLY FOR BREATH/CADENCE AT EDGES; not supported as the source of whole-chunk voice drift.
- `DSP_FADE_ARTIFACT` — NOT SUPPORTED. The 3 ms fade has tiny, edge-local impact.
- `MERGE_BOUNDARY_ARTIFACT` — NOT SUPPORTED AS VOICE-DRIFT SOURCE. Raw merge leaves speech samples unchanged.
- `GENERATION_ROBOTIC_ARTIFACT` — UNRESOLVED SUBJECTIVELY until raw chunks and step variants are heard by a person.

## AUDIO VALIDATION

- Diagnostic runner: PASS.
- All generated WAV files: decodable, finite, 24000 Hz mono.
- Chunk order: preserved.
- Provider/model reuse: PASS, one load.
- Crossfade: OFF.
- Gain: OFF.
- Existing full CP0.2A–E regression: 92/92 PASS.

## AUTOMATED TESTS

- Post-diagnostic targeted regression required by this checkpoint: 83/83 PASS (provider, languages, long-text, manager and audio boundary).
- Existing full CP0.2A–E regression including cloning: 92/92 PASS.
- Diagnostic runner compiled and completed with status PASS.
- No production tests or defaults were modified for this investigation.

## HUMAN LISTENING REQUIRED

- Human finding recorded: `GENERATION_VOICE_DRIFT = CONFIRMED`.
- `listening_checklist.md` is intentionally blank for subjective ratings.
- Further human comparison is required for robotic quality and selection among chunk plans or `num_step` values.
- Waveform difference, RMS and spectral metrics were not treated as proof of speaker identity change.

## FILES CREATED

Directory: `reports/cp02e1_listening/`

- Raw provider: `raw_chunk_01.wav` through `raw_chunk_05.wav`, `raw_merge.wav`.
- DSP isolation: `trim_merge.wav`, `trim_fade_merge.wav`, `processed_merge.wav`.
- Chunk size: `chunk_size_A_1_sentence.wav`, `chunk_size_B_2_sentences.wav`, `chunk_size_C_250_350_chars.wav` plus B/C individual chunks.
- Inference steps: `num_step_16.wav`, `num_step_24.wav`, `num_step_32.wav`.
- Repeatability: `repeat_1.wav`, `repeat_2.wav`, `repeat_3.wav`.
- Machine-readable evidence: `diagnostics.json`.
- Reproducible runner: `prototype/tests/run_cp02e1_voice_diagnostic.py`.
- Canonical runner: `prototype/tests/run_cp02e1_voice_consistency.py`.
- Listening worksheet: `reports/cp02e1_listening/listening_checklist.md`.

## FILES CHANGED

- `reports/cp02e1_listening/diagnostics.json` was extended with the required top-level checkpoint schema using existing measurements.
- `reports/cp02e1_voice_consistency_investigation.md` was aligned to the required report headings.
- No production code was changed by CP0.2E.1.

## LIMITATIONS

- Voice identity and robotic quality are perceptual properties; RMS, duration, spectral centroid and waveform correlation cannot replace human listening.
- Different chunk plans necessarily generate different text spans, so their acoustic summary metrics are descriptive rather than a quality score.
- The API has generic `**kwargs`; only explicitly observed `num_step` support was exercised. Seed behavior was not assumed.
- No production setting was modified.

## RECOMMENDATION

1. Listen in this order: raw chunks/raw merge versus processed merge; then chunk-size A/B/C; then `num_step` 16/24/32; finally repeat 1/2/3.
2. If raw chunks already change voice, prioritize a supported deterministic generation/voice-conditioning mechanism upstream. Do not try to solve identity drift with DSP.
3. Prefer chunk plan B or C if listening confirms better continuity; this reduces stochastic resets without redesigning the chunker.
4. Change `num_step` only after listening identifies a repeatable improvement. The current measurements do not justify a default change.
5. Keep crossfade and gain off. Retain conservative trim unless raw-versus-trim listening identifies lost breaths or clipped phonemes.
6. Stop at CP0.2E.1. Do not begin CP0.2F until these listening files are reviewed.

## NEXT

CP0.2E.2 is not ready for automatic implementation. It becomes ready only after the human listening checklist identifies the preferred chunk plan and whether any `num_step` variant consistently reduces robotic artifacts.

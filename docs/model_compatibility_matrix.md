# Model compatibility matrix

CP0 baseline + CP0.1 closure, 2026-09-11. Investigation evidence, not production approval.

## Vocabulary

VERIFIED = directly exercised, within the stated test boundary. NOT_VERIFIED = no live evidence.
FAILED = attempted operation failed. BLOCKED = prerequisites unavailable. NOT_APPLICABLE = feature absent.
Valid PCM does not establish pronunciation, naturalness or speaker similarity.

## Language coverage at CP0.1

Piper catalogue revision: `1162a9173d0ce503555aed757976b7a9912eae4c`.

| Language | Model | Standard TTS | Fixed voices | Cloning | CPU | GPU | Offline | Windows | Production |
|---|---|---|---|---|---|---|---|---|---|
| VI | VieNeu v3 Turbo (clone); Sherpa vi_VN-vais1000-medium (standard) | VERIFIED (PCM only) | VERIFIED (sid=0 Sherpa; preset VieNeu) | VERIFIED (VieNeu v3 Turbo, 3/3 ref lengths PASS) | VERIFIED | NOT_VERIFIED | VERIFIED (Python network guard) | VERIFIED | PENDING (VieNeu weights license) |
| JA | ja_JA-hi_fi_captain-medium via ORT-direct + pyopenjtalk (MIT) | VERIFIED (3/3 sentences PASS) | VERIFIED (female=0, male=1) | NOT_APPLICABLE | VERIFIED | NOT_VERIFIED | VERIFIED (Python network guard) | VERIFIED | REJECTED (CC-BY-NC-SA dataset) |
| EN | en_US-lessac-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| ZH | zh_CN-huayan-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| ES | es_ES-davefx-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| PT | pt_BR-faber-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| IT | it_IT-riccardo-x_low | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| FR | fr_FR-siwis-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | PENDING |
| HI | hi_IN-pratham-medium | NOT_VERIFIED | NOT_VERIFIED | NOT_APPLICABLE | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | REJECTED (CC-BY-NC-SA) |

Original Piper weights downloads for all nine models FAILED with HTTPS/CDN timeouts. No Japanese inference failure occurred in CP0: it never reached model loading. Do not misreport the download failure as a phonemizer/runtime failure.

## Concrete runtime and candidate revisions

| Candidate | Revision/runtime | Declared scope | Actual verification |
|---|---|---|---|
| NGHI | 46d160da32041f7e176607203b958069265df7da; lock: onnxruntime-web 1.22.0, phonemizer 1.2.2, sherpa-onnx 1.12.25 | Browser TTS; Vietnamese text processing | Source inspected; browser not run |
| Piper Python | piper-tts 1.8.0; onnxruntime 1.30.0 | Fixed voice inference, CPU and optional CUDA | Package install/import verified; original weights unavailable |
| Sherpa CPU POC | sherpa-onnx and sherpa-onnx-core 1.12.26 | Converted Piper VAIS1000 + bundled espeak-ng-data | VI generation verified, 4 threads; not identical to NGHI browser runtime |
| Coqui | dbf1a08a0d4e47fdad6172e433eeb34bc6b13b4e | Framework, capabilities depend on model | Not installed; original project Python constraints differ from current environment |
| XTTS-v2 | 6c2b0d75eae4b7047358e3b6bd9325f857d43f77 | EN ZH JA ES PT IT FR HI among targets; VI absent from model card | NOT_VERIFIED; weights CPML noncommercial, excluded |
| VieNeu v3 Turbo | model 8b7e9cffb4b41918cb638b9f62f0a751184d14a6; SDK vieneu 3.6.4 Apache-2.0 | VI/EN; fixed voices and clone; ONNX CPU | VERIFIED: clone 3/3 PASS, offline PASS, 48 kHz, ~2.9 GB RSS |
| VieNeu v3 Nano | model aba295eb96a6fa6003ebe417cc1f2802a7adc1dc | VI preview; CPU/ONNX | NOT_VERIFIED |
| JA ORT-Direct | pyopenjtalk 0.4.1-post9 (MIT) + onnxruntime 1.30.0 (MIT) | Japanese Piper model direct inference, GPL-free | VERIFIED: 3/3 PASS, offline PASS, 22050 Hz, 1.6 s load |
| Kokoro 82M | f3ff3571791e39611d31c381e3a41a3af07b4987 | Multilingual fixed voices; potential Japanese/Hindi alternative | NOT_VERIFIED; not selected as production configuration |

## Measured performance and boundaries

See [raw benchmark](../reports/evidence/cp0/sherpa_vi_benchmark.json) and [environment](../reports/evidence/cp0/environment.json).
VI cold model load: 1.686 s. First synthesis: 0.734 s / 3.889 s audio, RTF 0.189.
Two warm short runs: RTF approximately 0.105 and 0.096. PCM mono 22050 Hz, 16-bit.
125 repeated-sentence segments / 10250 characters: 48.555 s processing for 493.923 s audio.
Peak process working set: 523214848 bytes. This includes POC bookkeeping and validation, not just model memory.
No GPU inference/VRAM benchmark. No subjective listening. The repeated-text test is not a natural audiobook evaluation.

For unexecuted candidates: cold/warm time, RTF, RAM, VRAM, crash rate and long-text stability are NOT_VERIFIED, not zero.
Declared file sizes (not runtime memory): XTTS model.pth 1867929118 bytes; VieNeu Turbo main model.safetensors 261835312 bytes, ONNX shared fp32 data 415319040 bytes; additional graphs/codec/tokenizer/voices are required. Never treat these single files as complete offline-pack sizes.

## Evidence

- [Piper pinned catalogue](https://huggingface.co/rhasspy/piper-voices/blob/1162a9173d0ce503555aed757976b7a9912eae4c/voices.json)
- [NGHI pinned inference](https://github.com/nghimestudio/nghitts/blob/46d160da32041f7e176607203b958069265df7da/src/lib/piper-tts.js)
- [VieNeu Turbo](https://huggingface.co/pnnbao-ump/VieNeu-TTS-v3-Turbo/tree/8b7e9cffb4b41918cb638b9f62f0a751184d14a6)
- [Evidence receipts](../reports/evidence/cp0/sources.json), [additional receipts](../reports/evidence/cp0/sources_extra.json), [final receipts](../reports/evidence/cp0/sources_final.json)

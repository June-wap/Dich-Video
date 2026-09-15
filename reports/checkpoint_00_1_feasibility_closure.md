# Checkpoint 00.1 - Feasibility Closure Report

Date: 2026-09-11. Implementer evidence report; not reviewer approval.

## 1. Repository State

Not yet a git repository. CP0 artifacts and .cp0/ infrastructure from prior checkpoint.

## 2. Instructions Read

checkpoint_00_1.txt, RULES.txt, checkpoint_00.txt, model_compatibility_matrix.md, model_license_matrix.md, checkpoint_00_feasibility_report.md.

## 3. CP0 Baseline

VI standard TTS: VERIFIED (Sherpa-ONNX 1.12.26 + VAIS1000). JA: NOT_VERIFIED at CP0 (download failed). Cloning: NOT_VERIFIED. 8/9 benchmarked via Piper runtime.

## 4. Environment

Python 3.12.14, onnxruntime 1.30.0 (MIT), pyopenjtalk-plus 0.4.1-post9 (MIT), vieneu 3.6.4 (Apache-2.0), piper-tts 1.8.0 (GPL-3.0, CP0 testing only). Windows x64.

## 5. Voice Cloning Investigation

VieNeu v3 Turbo. SDK vieneu 3.6.4 (Apache-2.0). HF model pnnbao-ump/VieNeu-TTS-v3-Turbo. ONNX CPU, 48 kHz. API: Vieneu("v3turbo"), encode_reference(), infer(text, ref_audio).

## 6. Voice Cloning Live POC

Script: scripts/cp0_1_vieneu_poc.py. Evidence: vieneu_cloning_poc.json. Preset: 2.88s RTF=0.82 PASS. Clone 5s/10s/30s: all PASS (RTF 1.25-2.81). Offline (network blocked): PASS 1.12s. Load: 8.6s. RSS: ~2.9GB.

## 7. Voice Cloning Quality Results

NOT_VERIFIED (requires human listening). All 7 outputs valid PCM, non-silent (RMS 0.10-0.12). Audio in .cp0/audio/vieneu_cloning_poc/ for manual 1-5 scale review.

## 8. Japanese Failure Reproduction

CP0: download failed, no runtime test. Post-CP0: Piper+pyopenjtalk 3/3 PASS. Sherpa path: metadata patched, failed on multi-char phoneme tokens. Classification: runtime incompatibility.

## 9. Japanese Resolution / Alternative

ORT-Direct (GPL-free): pyopenjtalk (MIT) + IPA mapping + phoneme_id_map + onnxruntime (MIT). Script: cp0_1_ja_ort_direct.py. Evidence: ja_ort_direct_poc.json. Basic 1.43s PASS. Weather 1.64s PASS. Long 7.87s PASS. Offline 1.61s PASS. Model SHA256: 5eafa161. 22050 Hz, 2 speakers. Zero GPL imports.

## 10. License Closure

Runtime: onnxruntime (MIT) APPROVED, pyopenjtalk-plus (MIT) APPROVED, vieneu SDK (Apache-2.0) APPROVED. Piper-tts (GPL-3.0) EXCLUDED. Models: JA CC-BY-NC-SA REJECTED. HI CC-BY-NC-SA REJECTED. Others PENDING.

## 11. espeak-ng Analysis

Source GPL-3.0. Data bundled in piper (373 files/18.2MB) and Sherpa (355 files/17.16MB). No separate permissive license. JA/VI not affected. 7 espeak-dependent languages need GPL compliance or alternative. Treatment: ALTERNATIVE_REQUIRED.

## 12. Compatibility Matrix Changes

JA Standard TTS VERIFIED (ORT-direct). VI Cloning VERIFIED (VieNeu). Updated docs/model_compatibility_matrix.md and docs/model_license_matrix.md.

## 13. Tests Added/Changed

cp0_1_vieneu_poc.py (5-phase clone POC), cp0_1_ja_ort_direct.py (GPL-free JA), cp0_1_ja_sherpa.py (Sherpa JA failure), cp0_1_patch_ja_metadata.py.

## 14. Test Results

VieNeu Cloning: PASS (3/3 clone, offline). JA ORT-direct: PASS (3/3, offline). JA Sherpa: FAILED (token incompatibility).

## 15. Evidence Created

vieneu_cloning_poc.json, ja_ort_direct_poc.json, 7 clone WAVs, 4 JA WAVs.

## 16. Security/Privacy Review

No secrets. No external API in production path. Offline confirmed after model cache.

## 17. Known Limitations

1. Clone quality not subjectively evaluated. 2. JA model NC-licensed needs replacement. 3. espeak-ng GPL affects 7 languages. 4. Most model weights PENDING. 5. No GPU test.

## 18. Remaining Blockers

JA commercial model (HIGH), HI commercial model (HIGH), espeak-ng GPL (MEDIUM), VieNeu weights license (MEDIUM), remaining PENDING licenses (MEDIUM).

## 19. Files Changed

New: cp0_1_vieneu_poc.py, cp0_1_ja_ort_direct.py, cp0_1_ja_sherpa.py, cp0_1_patch_ja_metadata.py, checkpoint_00_1_feasibility_closure.md. Updated: model_compatibility_matrix.md, model_license_matrix.md.

## 20. Git Diff Summary

No git repository. All new files or edits to CP0 documents.

## 21. Final Status

| Area | Status | Evidence |
|---|---|---|
| Voice Cloning | PASS | VieNeu v3 Turbo 3/3 clone PASS, offline PASS |
| Japanese TTS | ALTERNATIVE_PASS | ORT-direct+pyopenjtalk 3/3 PASS, offline PASS |
| 9-Language Coverage | PARTIAL | JA+VI proven; 7 need espeak resolution |
| Commercial Model Set | PARTIAL | JA,HI REJECTED; others PENDING |
| espeak-ng Treatment | ALTERNATIVE_REQUIRED | GPL data affects 7 languages |
| CP0.1 Final | PASS_WITH_LIMITATIONS | Core gaps closed; license gaps documented |

Next: CP1. Preconditions: source JA/HI commercial models, espeak-ng strategy, confirm VieNeu weights license.

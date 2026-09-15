# Checkpoint 00 — feasibility report

Date: 2026-09-11. Implementer evidence report; not reviewer approval.

## 1. Repository State

NOT A GIT REPOSITORY. Initially only Rule/ existed, with 18 instruction files. No application, tests, dependency manifest or build existed. No Git initialization or commit performed.

## 2. Instructions Read

Read Rule/AGENTS.md (empty), Rule/RULES.txt (v1.0), Rule/checkpoint_00.txt. No Rule.md, root AGENTS.md or Master Prompt.md was present. Latest user instruction requests CP0.1; this report first preserves the completed CP0 baseline.

## 3. Baseline

No pre-existing test/build suite. System Python 3.14.7. Created isolated .cp0/venv with available Python 3.12.14; did not modify system Python. Initial network socket access restricted; explicitly escalated public research/download/install commands. WMI initially denied; psutil provided RAM/core measurements.

## 4. Files Inspected

Instructions, upstream NGHI README/LICENSE/package lock/inference source, Piper model catalogue/cards, Coqui and XTTS metadata/license, VieNeu source/model cards and dataset metadata, Kokoro card/voices, Sherpa release assets and license, installed runtime APIs. See reports/evidence/cp0/sources*.json for exact receipts.

## 5. Findings

- VI standard TTS demonstrated with Sherpa-ONNX 1.12.26 and converted Piper VAIS1000.
- Original Piper weights for nine languages could not be downloaded through Hugging Face's redirected CDN (timeouts). Japanese did NOT reach inference; no Japanese runtime failure was established.
- NGHI TTS source uses ONNX Runtime Web and a phonemizer; it is not simply a Python Piper wrapper. Lock versions: onnxruntime-web 1.22.0, phonemizer 1.2.2, sherpa-onnx 1.12.25. Browser UI was not run.
- Python wheel for Sherpa 1.12.25 was unavailable for this environment; 1.12.26 succeeded. This is a different tested configuration from NGHI.
- XTTS standard model card does not include VI; CPML model/output noncommercial terms exclude it from this proposed commercial set.
- Japanese Hi-Fi Captain, Hindi Pratham and Vietnamese Vivos cards specify NC dataset terms; excluded absent separate rights. Huayan dataset licence is explicitly unknown.
- VieNeu v3 Turbo is the primary VI clone candidate for further investigation, not approved. Dataset and preset rights need evidence. Nano is experimental and its documentation includes inconsistent/stale clone descriptions.

## 6. Implementation

Only CP0 research/POC scripts and reports. No production UI/API/database/providers/job engine.
Added explicit metadata collectors, pinned model downloader, Piper harness and successful Sherpa CPU harness. Large artifacts and generated audio isolated under ignored .cp0/.

## 7. Tests Added/Changed

Six evidence tests: silence rejection, truncated WAV rejection, artifact hash mismatch, path escape, generated WAV hashes, source receipt integrity.
Real model POC: six short cases plus 125 sequential repetitions (10250 characters). Raw numeric text and manually expanded numeric text both produced PCM; correctness of how numbers are spoken remains NOT_VERIFIED.

## 8. Test Results

Commands:
```powershell
.\.cp0\venv\Scripts\python.exe scripts/cp0_sherpa_poc.py
.\.cp0\venv\Scripts\python.exe -m unittest discover -s tests -v
.\.cp0\venv\Scripts\python.exe -m compileall -q scripts tests
.\.cp0\venv\Scripts\python.exe -m pip check
```
POC exit 0; six tests PASS; compileall exit 0; pip check: no broken requirements.
Piper download attempts FAILED on all nine selected voices; no false synthesis success recorded.
Sherpa archive downloaded from official GitHub release, SHA256 matched `fa1367710767d36ed5cf13b4a449e20c35ffd12791c2e47c2e64142bfa55551a`.

Hardware: Windows 11 build 26200; 8 physical / 12 logical CPU cores; RAM 16886784000 bytes; NVIDIA RTX 4050 Laptop 6141 MiB, driver 591.59. GPU inference NOT_VERIFIED.

Measured VI: 1.686 s model load; 0.734 s first synthesis / 3.889 s output (RTF 0.189); warm RTF 0.105 and 0.096. Long repetition test 48.555 s / 493.923 s audio. Peak working set 523214848 bytes (whole POC process). These timings exclude downloads and are not a minimum-spec hardware guarantee. Exact values in sherpa_vi_benchmark.json.

## 9. Manual Verification

Inspected PCM metadata and code, not subjective listening. Pronunciation/naturalness/speaker similarity: NOT_VERIFIED. Voice cloning 5/10/30-second trials: BLOCKED, no reference audio with user-confirmed rights supplied. Asked user for a local reference path and consent; no such response received during CP0. No personal voice downloaded or cloned.

## 10. Security/Privacy Review

Only public source/model metadata downloaded. No private scripts/audio uploaded. POC text is artificial. Inference uses explicit local paths, Python socket deny guard and restricted execution. Full OS firewall/native network audit and clean-machine offline test NOT_VERIFIED. Safe archive extraction used Python data filter. No telemetry added to project.

## 11. License Impact

See docs/model_license_matrix.md. No production model approved. espeak data exists inside model archive and cannot be ignored because wrapper code is Apache-2.0. Research installation is not production redistribution approval.

## 12. Known Limitations

No human listening panel, clone trial, GPU trial, clean-Windows packaging, full 9-language live coverage or commercial rights closure. Long test repeats one sentence rather than a natural script. Original Hugging Face weights could not be fetched. Source/API metadata and model-card support claims remain separate from live tests. Candidate RAM/VRAM/RTF not measured are explicitly unknown.

## 13. Files Changed

.gitignore; scripts/cp0_collect.py, cp0_collect_extra.py, cp0_collect_final.py, cp0_download_piper.py, cp0_benchmark.py, cp0_sherpa_poc.py; tests/test_cp0_evidence.py; docs/model_compatibility_matrix.md; docs/model_license_matrix.md; this report; reports/evidence/cp0/. Local runtime, model and audio in .cp0/ are not source deliverables. Original Rule files unchanged by the implementer.

## 14. Git Diff Summary

NOT A GIT REPOSITORY; no git diff/branch/commit available. Inspected new script paths and binary locations. .gitignore excludes .cp0 and audio/model formats. No secrets intentionally collected or written.

## 15. Final Status

**BLOCKED**.

| Gate | Evidence result |
|---|---|
| Standard TTS path | Demonstrated, VI PCM generation on CPU |
| Vietnamese feasibility | Engineering generation demonstrated; listening pending |
| Multilingual gaps known | Catalogue/cards inspected; other eight not synthesized |
| Voice cloning | BLOCKED: no live authorized-reference trial or quality evaluation |
| Licenses documented | Matrices written; production approvals unresolved |
| No unsupported production-ready claim | Satisfied; no model set approved |

CP0 cannot be PASS under its explicit mandatory cloning gate. Next action is user-requested CP0.1 closure, not CP1. Preserve raw results rather than upgrading this status on the basis of README claims.

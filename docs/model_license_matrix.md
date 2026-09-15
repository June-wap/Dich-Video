# Model and dependency license review

CP0 baseline, 2026-09-11. Review states: PENDING / APPROVED / REJECTED.
No combined runtime + voice package is approved for production in this audit.
REJECTED means excluded from this proposed commercial catalogue under the evidence reviewed, not a universal legal conclusion about all possible separately licensed uses.
PENDING and REJECTED artifacts are excluded. Approval belongs to the project reviewer.

## Artifact evidence

| Component | Source / revision | Artifact/hash | Code/model license | Dataset / voice / phonemizer | Redistribution and attribution | Review status / missing evidence |
|---|---|---|---|---|---|---|
| NGHI source | nghimestudio/nghitts @ 46d160da32041f7e176607203b958069265df7da | Source receipt hashes in sources.json / sources_extra.json | Apache-2.0 source | Voice rights separate; celebrity dataset examples in README; phonemizer bundled tgz not fully audited | Preserve license/notices; audit transitive packages | PENDING: source license exists, exact voice rights and tgz provenance unresolved |
| Piper Python | piper-tts 1.8.0 | Installed runtime; complete binary hash inventory not yet recorded | GPL-3.0-or-later | espeak dependency must be audited separately | Distribution requires applicable GPL compliance and source/notices; process boundary not an automatic exemption | PENDING: no production distribution compliance plan |
| ONNX Runtime | 1.30.0 | Installed wheel version in runtime_freeze.txt | MIT | No grant of model/voice rights | Preserve copyright/license | PENDING: exact production binary bill of materials not approved |
| Sherpa runtime | 1.12.26 | sherpa-onnx + sherpa-onnx-core | Apache-2.0 project source | Linked/bundled phonemizer must be independently audited | Apache notices plus applicable third-party terms | PENDING: espeak native relationship requires CP0.1 closure |
| Converted VAIS1000 | k2-fsa/sherpa-onnx tts-models release | archive SHA256 fa1367710767d36ed5cf13b4a449e20c35ffd12791c2e47c2e64142bfa55551a; every extracted file in sherpa_vi_benchmark.json | Model distribution rights not fully established from card alone | Dataset CC-BY-4.0; fine-tuned from Lessac; espeak-ng-data included | Attribution, upstream lineage and bundled phonemizer compliance required | PENDING: weights/voice/base-model terms and complete redistribution treatment |
| Piper Lessac EN | rhasspy/piper-voices @ 1162a9173d0ce503555aed757976b7a9912eae4c | en_US-lessac-medium; weights not downloaded, hash unknown | No separate conclusion | Custom dataset license link | Must review linked Lessac conditions | PENDING |
| Piper Huayan ZH | same catalogue revision | zh_CN-huayan-medium; hash unknown | No separate conclusion | Model card: dataset license Unknown | Cannot assume commercial rights | PENDING |
| Piper Hi-Fi Captain JA | same catalogue revision | ja_JA-hi_fi_captain-medium; hash unknown | No separate conclusion | Dataset CC-BY-NC-SA-4.0; LibriTTS-R base | No evidence of separate commercial grant | REJECTED for proposed production catalogue |
| Piper Davefx ES | same catalogue revision | es_ES-davefx-medium; hash unknown | No separate conclusion | Dataset CC0; Lessac fine-tune | Check upstream base/weights conditions | PENDING |
| Piper Faber PT | same catalogue revision | pt_BR-faber-medium; hash unknown | No separate conclusion | Dataset CC0; Lessac fine-tune | Check upstream base/weights conditions | PENDING |
| Piper Riccardo IT | same catalogue revision | it_IT-riccardo-x_low; hash unknown | No separate conclusion | M-AILABS external license link | Linked terms not closed | PENDING |
| Piper Siwis FR | same catalogue revision | fr_FR-siwis-medium; hash unknown | No separate conclusion | Dataset CC-BY-4.0; Lessac fine-tune | Attribution and upstream conditions | PENDING |
| Piper Pratham HI | same catalogue revision | hi_IN-pratham-medium; hash unknown | No separate conclusion | Dataset CC-BY-NC-SA-4.0 | No evidence of separate commercial grant | REJECTED for proposed production catalogue |
| Piper Vivos VI | same catalogue revision | vi_VN-vivos-x_low; hash unknown | No separate conclusion | Dataset CC-BY-NC-SA-4.0 | No evidence of separate commercial grant | REJECTED for proposed production catalogue |
| Coqui framework | coqui-ai/TTS @ dbf1a08a0d4e47fdad6172e433eeb34bc6b13b4e | LICENSE snapshot hash in sources_extra.json | MPL-2.0 source | Does not license XTTS weights | Preserve notices and meet file-level source obligations when applicable | PENDING: no concrete production distribution selected |
| XTTS-v2 | coqui/XTTS-v2 @ 6c2b0d75eae4b7047358e3b6bd9325f857d43f77 | model.pth not downloaded; LICENSE snapshot in evidence | CPML 1.0.0 limits model and outputs to noncommercial use | No separate commercial grant supplied | Published CPML terms incompatible with intended commercial use without another grant | REJECTED |
| VieNeu v3 Turbo | pnnbao-ump/VieNeu-TTS-v3-Turbo @ 8b7e9cffb4b41918cb638b9f62f0a751184d14a6; SDK vieneu 3.6.4 | Models cached locally after HF download | SDK Apache-2.0; model card Apache-2.0 | Clone verified; dataset/voice rights need explicit confirmation from model author | Preserve notices; clarify weights commercial rights | PENDING: SDK approved, model weights license confirmation needed |
| pyopenjtalk-plus | 0.4.1-post9 | pip installed wheel | MIT (package); New BSD (OpenJTalk C library) | Japanese morphological analysis and phonemization | Preserve license notices | APPROVED for production |
| espeak-ng data | Bundled in piper-tts and Sherpa archives | 355–373 files, 17–18 MB compiled dictionary data | GPL-3.0 (no separate permissive license found) | Required by EN, ZH, ES, PT, IT, FR, HI phonemization | GPL compliance or alternative phonemizer needed | ALTERNATIVE_REQUIRED for commercial distribution |
| VieNeu v3 Nano / v1 | Nano aba295eb96a6fa6003ebe417cc1f2802a7adc1dc; v1 7cbfde99a613d07630f390cc623ecfb2a070d0c1 | Weights not downloaded | Model cards Apache-2.0 | 1000h dataset metadata CC-BY-NC-4.0, gated; do not infer weights are automatically prohibited or approved | Clarify separate rights held by model issuer | PENDING |
| Kokoro 82M | hexgrad/Kokoro-82M @ f3ff3571791e39611d31c381e3a41a3af07b4987 | Weights not downloaded | Model card Apache-2.0 | Per-voice/tokenizer dependencies require review | Preserve notices; check exact Japanese runtime and voice | PENDING |
| espeak-ng | Source COPYING fetched; exact bundled build not established | Data inventory in sherpa_vi_benchmark.json | GPL-3.0 source evidence | Data bundled inside downloaded VAIS1000 archive | Need exact source/version mapping, license notices and distribution obligations | PENDING |

## Evidence and limitations

Model cards are saved individually under `reports/evidence/cp0/*_MODEL_CARD.txt`.
Source URLs, content SHA256, fetch failures and timestamps: `sources.json`, `sources_extra.json`, `sources_final.json`.
SHA256 of a downloaded source document is not the weights hash. Unknown weights hashes stay unknown.
Upstream mutable branches were recorded with snapshot receipts; where pinned source URLs are used they include exact commits. CP0 did not prove every mutable snapshot matches a separately queried head commit byte-for-byte.

- [XTTS license](https://huggingface.co/coqui/XTTS-v2/blob/6c2b0d75eae4b7047358e3b6bd9325f857d43f77/LICENSE.txt)
- [Piper licence](https://github.com/OHF-Voice/piper1-gpl/blob/v1.8.0/COPYING)
- [Sherpa licence](https://github.com/k2-fsa/sherpa-onnx/blob/v1.12.26/LICENSE)
- [NGHI](https://github.com/nghimestudio/nghitts/tree/46d160da32041f7e176607203b958069265df7da)
- [VieNeu 1000h metadata](https://huggingface.co/api/datasets/pnnbao-ump/VieNeu-TTS-1000h)

No model is production-ready merely because its WAV was generated successfully.

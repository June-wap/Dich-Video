# Cây thư mục toàn diện — Voca Basic

> Cập nhật theo workspace hiện tại. Các thư mục dependency/cache lớn được biểu diễn theo cấu trúc thay vì liệt kê từng package/file sinh tự động.

```text
Tool Dich Cho Khach/
├── .cp0/                         # Dữ liệu checkpoint cũ
├── .git/                         # Git metadata
├── .pytest_cache/                # Pytest cache (generated)
├── .runtime/                     # Runtime state (generated)
├── .vendor-vieneu/               # Official VieNeu source checkout cho CP2
│   ├── .github/
│   ├── docker/
│   ├── docs/
│   ├── examples/
│   ├── vieneu/                   # Official VieNeu runtime package
│   ├── vieneu_utils/             # Official utilities
│   ├── LICENSE
│   ├── pyproject.toml
│   ├── README.md
│   └── uv.lock
├── .venv312/                     # Python 3.12 virtual environment (local)
│   ├── Include/
│   ├── Lib/
│   │   └── site-packages/
│   ├── Scripts/
│   └── pyvenv.cfg
├── backend/                      # FastAPI backend
│   ├── api/
│   │   ├── app_settings.py
│   │   ├── audio.py
│   │   ├── auth.py
│   │   ├── health.py
│   │   ├── long_form.py
│   │   ├── providers.py
│   │   ├── router.py
│   │   ├── settings.py
│   │   ├── system.py
│   │   ├── tts.py
│   │   ├── tts_jobs.py
│   │   └── voices.py
│   ├── dependencies/
│   ├── errors/
│   │   ├── __init__.py
│   │   └── handlers.py
│   ├── schemas/
│   │   ├── app_settings.py
│   │   ├── common.py
│   │   ├── long_form.py
│   │   ├── providers.py
│   │   ├── settings.py
│   │   ├── system.py
│   │   ├── tts.py
│   │   └── voices.py
│   ├── services/
│   │   ├── app_settings_service.py
│   │   ├── execution.py
│   │   ├── long_form_service.py
│   │   ├── provider_service.py
│   │   ├── system_service.py
│   │   ├── translation_service.py
│   │   ├── tts_service.py
│   │   ├── vieneu_adapter.py
│   │   └── voice_profile_service.py
│   ├── tests/
│   │   ├── provider_fakes.py
│   │   ├── test_backend.py
│   │   ├── test_provider_service.py
│   │   ├── test_tts_jobs.py
│   │   ├── test_tts_service.py
│   │   ├── test_voices_api.py
│   │   └── ...
│   ├── config.py
│   ├── logging_config.py
│   ├── main.py
│   └── persistence.py
├── Claude outputs/               # Artifact/phân tích do công cụ khác tạo
├── codex-with-chatgpt/           # Integration/workflow support
├── desktop/                      # Electron main process
│   ├── icon.png
│   ├── main.cjs
│   └── preload.cjs
├── docs/                         # Tài liệu dự án/phát hành
│   └── windows_release.md
├── external/                     # Khu vực external dependency/artifact
├── frontend/                     # React + TypeScript + Vite frontend
│   ├── dist/                     # Production build output (generated)
│   ├── node_modules/             # Frontend dependencies (generated)
│   ├── public/
│   │   ├── favicon.ico
│   │   ├── logo-128.png
│   │   └── logo.png
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── AppShell/
│   │   │   ├── AudioPlayer/
│   │   │   ├── Button/
│   │   │   ├── Sidebar/
│   │   │   └── ...
│   │   ├── context/
│   │   ├── data/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── i18n/
│   │   ├── pages/
│   │   ├── services/
│   │   ├── styles/
│   │   ├── test/
│   │   ├── types/
│   │   ├── utils/
│   │   ├── App.tsx
│   │   ├── index.css
│   │   └── main.tsx
│   ├── index.html
│   └── vite.config.ts
├── logs/                         # Runtime logs
├── long_audio_stability_results/ # Long-audio benchmark output
├── node_modules/                 # Root Electron dependencies (generated)
├── prototype/                    # Legacy/generic TTS core & assets
│   ├── core/
│   │   ├── audio_utils.py
│   │   ├── hardware.py
│   │   ├── languages.py
│   │   ├── long_text.py
│   │   ├── text_utils.py
│   │   └── tts_manager.py
│   ├── logs/
│   ├── models/                   # Legacy model/token assets
│   ├── outputs/                  # Generated audio/results
│   ├── providers/
│   │   ├── base.py
│   │   ├── ort_japanese.py
│   │   ├── piper.py
│   │   ├── sherpa_piper.py
│   │   └── voice_clone.py
│   ├── temp/
│   ├── tests/
│   ├── voices/
│   ├── app.py
│   ├── README.md
│   └── requirements.txt
├── release/                      # Packaging resources/artifacts
│   ├── evaluation-python/        # Evaluated portable Python runtime
│   ├── icon.ico
│   ├── icon.png
│   ├── runtime-manifest.json
│   ├── stage-runtime.log
│   ├── THIRD_PARTY_NOTICES.md
│   └── Voca Basic - Huong dan su dung.docx
├── reports/                      # Historical reports/evidence/benchmark logs
├── Rule/                         # Checkpoint rule and verification reports
├── scripts/                      # Local launch/stage/package scripts
│   ├── assert_release_not_running.ps1
│   ├── run_app.py
│   ├── run_app_silent.vbs
│   ├── run_backend.ps1
│   └── stage_release_runtime.ps1
├── tests/                        # Repository-level tests
├── .gitignore
├── constraints-backend.txt
├── long_audio_stability_test_vi.txt
├── package-lock.json
├── package.json
├── pnpm-lock.yaml
├── PROJECT_TREE.md               # File này
└── requirements-backend.txt
```

## Phân loại nhanh

| Nhóm | Thư mục/file |
|---|---|
| Production source | `backend/`, `frontend/src/`, `desktop/`, `scripts/` |
| TTS legacy/support | `prototype/` |
| Official vendor source | `.vendor-vieneu/` |
| Packaging | `release/`, `package.json` |
| Dependencies/generated | `node_modules/`, `frontend/node_modules/`, `.venv312/`, `frontend/dist/` |
| Runtime/generated data | `.runtime/`, `logs/`, `prototype/outputs/`, `.pytest_cache/` |
| Historical/evidence | `reports/`, `Rule/`, `Claude outputs/` |

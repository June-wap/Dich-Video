# Windows installer release runbook

The application is hosted by Electron. Its renderer is served only from
`127.0.0.1:5173`; Electron starts the FastAPI child process on
`127.0.0.1:8000`, waits for `/api/health`, and terminates that process when
the application exits. The renderer has sandboxing/context isolation and no
Node integration.

## User data

All customer data is under Electron's per-user `%LOCALAPPDATA%` application
directory, in `backend-data/`: `audio/` contains generated speech and reference
audio, `data/metadata.sqlite3` contains profiles/jobs/settings, and `runtime/`
contains the fresh local session token. The **Dữ liệu** menu can copy the whole
directory as a backup or erase it after an explicit confirmation. Uninstalling
the program does not erase customer data; the user controls that separately.

## Release gate

`npm run package:win` first runs `scripts/stage_release_runtime.ps1`. It refuses
to stage anything unless all three environment variables are supplied:

- `LOCAL_VOICE_PYTHON_RUNTIME`: audited portable Python runtime, including all
  application dependencies (not the current source-machine virtualenv).
- `LOCAL_VOICE_FFMPEG_DIRECTORY`: reviewed FFmpeg directory containing
  `ffmpeg.exe`.
- `LOCAL_VOICE_APPROVED_MODELS_DIRECTORY`: reviewed model artifact root.

It also refuses an empty/unapproved `release/model-manifest.json`, validates
every listed SHA-256 before copying, and packages the manifest plus notices.
This intentional block is required because the present license audit has not
approved a distributable model/voice combination.

## Windows clean-machine acceptance checklist

1. Run the NSIS installer as a standard user; launch the app; confirm backend
   reaches healthy status and FFmpeg/GPU diagnostics are truthful.
2. Test both an NVIDIA CUDA machine and a CPU-only machine; record the model
   load result and runtime/quality limits rather than treating CPU as certified.
3. Upload WAV, MP3 and M4A/AAC reference audio; clone a voice; generate short
   and long-form audio; restart during a job and confirm recovery is marked.
4. Back up, restore manually by copying the data folder, then erase through
   the menu; confirm generated audio, profiles, SQLite and token are removed.
5. Uninstall the app and verify program files are removed while user data is
   retained until the user explicitly erases it.

## Portable release (no Windows shortcut)

When distributing a single executable is preferable to an installed application,
run `npm run package:portable`. The artifact is written to
`release/portable-dist/` and does not create a Desktop or Start Menu shortcut.
It uses a separate output directory, so a running development or unpacked copy
cannot partially overwrite this portable build. The same staged runtime and
model-license checks apply as for the NSIS installer.

For a repeatable local packaging test using the runtime already staged by a
previous approved release build, use `npm run package:portable:staged`.

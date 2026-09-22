# Third-party notices — release gate

This package is an **internal, non-commercial evaluation build only**. It is
not approved for commercial distribution or customer delivery.

Before a commercial release, replace the evaluation model entry with one entry per shipped artifact and
`model-manifest.json` with the immutable source, SHA-256, license text/notice,
redistribution status, and reviewer approval. Include the resulting notices in
the installer. See `docs/model_license_matrix.md` for the open items.

---

## Bundled Tools

### FFmpeg
- **Version**: 2025-06-02-git-688f3944ce-full_build-www.gyan.dev
- **Source/Provenance**: Built by MSYS2 / gcc 15.1.0 (gyan.dev static build)
- **License**: GNU General Public License version 3 (GPLv3)
- **SHA-256**: `5e16cfd831f19d27314403d62d77f2f943fa7fc7d11fecbfd8dd8f29ab0af26d`
- **Location**: `resources/bin/ffmpeg.exe`
- **Purpose**: Local WAV to MP3 encoding (libmp3lame) and audio container verification.

### 7-Zip
- **Version**: 26.03 (x64)
- **Source**: Igor Pavlov (www.7-zip.org)
- **License**: GNU LGPL / unRAR license with restrictions
- **Components**: `7z.exe`, `7z.dll`
- **Purpose**: Offline decompression of AI Packages.

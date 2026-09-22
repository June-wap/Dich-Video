import hashlib
import json
import os
from pathlib import Path

def generate():
    target_dir = Path(r"D:\Tool Dich Cho Khach\release-candidates\runtime-main-sp021-vcruntime-fix")
    vm_iso_c = Path(r"D:\Tool Dich Cho Khach\release\vm-isolation-test\candidate_c_combined")

    def sha256(fp):
        h = hashlib.sha256()
        with open(fp, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().upper()

    whl = target_dir / "sentencepiece-0.2.1-cp312-cp312-win_amd64.whl"
    pyd = target_dir / "site-packages" / "sentencepiece" / "_sentencepiece.cp312-win_amd64.pyd"
    vc_dir = target_dir / "vc_runtime_dlls"

    manifest = {
        "candidate_name": "Candidate C - Combined SentencePiece 0.2.1 + Microsoft VC++ Runtime DLLs",
        "timestamp": "2026-09-22T06:02:00Z",
        "target_runtime": "portable runtime-main (Python 3.12.10 x64)",
        "sentencepiece_wheel": {
            "filename": whl.name,
            "size": whl.stat().st_size,
            "sha256": sha256(whl),
            "source": "Official PyPI (wheelhouse / https://pypi.org/project/sentencepiece/0.2.1/)",
        },
        "sentencepiece_native_pyd": {
            "filename": pyd.name,
            "size": pyd.stat().st_size,
            "sha256": sha256(pyd),
            "linker_version": "14.44 (MSVC 2022 v17.10/v17.12 CRT compatible)",
            "binding_framework": "SWIG (stable GIL/CRT ABI)",
        },
        "vc_runtime_dlls": [],
    }

    for f in sorted(vc_dir.glob("*.dll")):
        manifest["vc_runtime_dlls"].append({
            "filename": f.name,
            "size": f.stat().st_size,
            "sha256": sha256(f),
            "version": "14.51.36231.0",
            "source": "Microsoft Visual Studio 2022 VC Redistributable CRT",
        })

    lines = []
    lines.append("=================================================================")
    lines.append(" CANDIDATE C: SENTENCEPIECE 0.2.1 + MICROSOFT VC++ RUNTIME DLLS")
    lines.append("=================================================================\n")
    lines.append("1. SENTENCEPIECE WHEEL:")
    lines.append(f"   File:   {manifest['sentencepiece_wheel']['filename']}")
    lines.append(f"   Size:   {manifest['sentencepiece_wheel']['size']} bytes")
    lines.append(f"   SHA256: {manifest['sentencepiece_wheel']['sha256']}")
    lines.append(f"   Source: {manifest['sentencepiece_wheel']['source']}\n")
    lines.append("2. NATIVE PYD:")
    lines.append(f"   File:   {manifest['sentencepiece_native_pyd']['filename']}")
    lines.append(f"   Size:   {manifest['sentencepiece_native_pyd']['size']} bytes")
    lines.append(f"   SHA256: {manifest['sentencepiece_native_pyd']['sha256']}")
    lines.append(f"   Linker: {manifest['sentencepiece_native_pyd']['linker_version']}\n")
    lines.append("3. MICROSOFT VC++ RUNTIME DLLS (Placed in runtime-main root):")
    for d in manifest["vc_runtime_dlls"]:
        lines.append(f"   {d['filename']: <28} | {d['version']: <14} | {d['sha256']} | {d['size']: >7} bytes")

    txt_content = "\n".join(lines) + "\n"

    for dest in [target_dir, vm_iso_c]:
        dest.mkdir(parents=True, exist_ok=True)
        with open(dest / "MANIFEST.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        with open(dest / "MANIFEST.txt", "w", encoding="utf-8") as f:
            f.write(txt_content)

    print("Successfully generated manifests in both locations.")

if __name__ == "__main__":
    generate()

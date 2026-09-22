import argparse
import datetime
import hashlib
import json
import struct
import sys
import ctypes
from ctypes import wintypes
from pathlib import Path


def _get_file_version(path: Path) -> str:
    try:
        ver_dll = ctypes.WinDLL("version", use_last_error=True)
        file_path = str(path)
        size = ver_dll.GetFileVersionInfoSizeW(file_path, None)
        if size == 0:
            return "N/A"
        buffer = ctypes.create_string_buffer(size)
        if not ver_dll.GetFileVersionInfoW(file_path, 0, size, buffer):
            return "N/A"
        pointer = ctypes.c_void_p()
        length = wintypes.UINT()
        if not ver_dll.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length)):
            return "N/A"
        raw = ctypes.string_at(pointer.value, length.value)
        if len(raw) >= 16:
            ms, ls = struct.unpack_from("<II", raw, 8)
            return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
    except Exception:
        pass
    return "unknown"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest().upper()


def _read_dist_metadata_version(candidate_root: Path, package: str) -> str | None:
    site_packages = candidate_root / "Lib" / "site-packages"
    if not site_packages.is_dir():
        site_packages = candidate_root / "site-packages"
    for metadata in site_packages.glob(f"{package}-*.dist-info/METADATA"):
        for line in metadata.read_text(encoding="utf-8").splitlines():
            if line.startswith("Version: "):
                return line.split(": ", 1)[1]
    return None


def generate(candidate_root: Path, output_json: Path, output_txt: Path) -> None:
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    sentencepiece_version = _read_dist_metadata_version(candidate_root, "sentencepiece")

    # Locate artifacts in candidate root
    wheels = list(candidate_root.glob("*.whl"))
    whl = wheels[0] if wheels else None

    # Locate PYD
    pyd = None
    for p in candidate_root.rglob("*.pyd"):
        if p.name.startswith("_sentencepiece"):
            pyd = p
            break

    # Locate VC runtime DLLs
    vc_dir = candidate_root / "vc_runtime_dlls"
    if not vc_dir.is_dir():
        vc_dir = candidate_root  # Fallback if placed at root

    manifest = {
        "candidate_name": f"Candidate - Generated from {candidate_root.name}",
        "timestamp": timestamp,
        "target_runtime": "portable runtime-main (Python 3.12 x64)",
        "sentencepiece_version": sentencepiece_version,
        "sentencepiece_wheel": None,
        "sentencepiece_native_pyd": None,
        "vc_runtime_dlls": [],
    }

    if whl:
        manifest["sentencepiece_wheel"] = {
            "filename": whl.name,
            "size": whl.stat().st_size,
            "sha256": _sha256(whl),
            "source": f"Local wheel: {whl.name}",
        }

    if pyd:
        manifest["sentencepiece_native_pyd"] = {
            "filename": pyd.name,
            "size": pyd.stat().st_size,
            "sha256": _sha256(pyd),
            "linker_version": "Unknown (extracted)",
            "binding_framework": "unknown/not_measured",
        }

    for f in sorted(vc_dir.glob("*.dll")):
        if f.name.lower() == "python3.dll" or f.name.lower() == "python312.dll":
            continue
        manifest["vc_runtime_dlls"].append({
            "filename": f.name,
            "size": f.stat().st_size,
            "sha256": _sha256(f),
            "actual_file_version": _get_file_version(f),
            "source_path": str(f.resolve()),
            "source_provenance": "measured from candidate artifact",
        })

    lines = []
    lines.append("=================================================================")
    lines.append(f" {manifest['candidate_name'].upper()}")
    lines.append(f" Timestamp: {timestamp}")
    lines.append("=================================================================\n")

    if manifest["sentencepiece_wheel"]:
        lines.append("1. SENTENCEPIECE WHEEL:")
        lines.append(f"   File:   {manifest['sentencepiece_wheel']['filename']}")
        lines.append(f"   Size:   {manifest['sentencepiece_wheel']['size']} bytes")
        lines.append(f"   SHA256: {manifest['sentencepiece_wheel']['sha256']}")
        lines.append(f"   Source: {manifest['sentencepiece_wheel']['source']}\n")

    if manifest["sentencepiece_native_pyd"]:
        lines.append("2. NATIVE PYD:")
        lines.append(f"   File:   {manifest['sentencepiece_native_pyd']['filename']}")
        lines.append(f"   Size:   {manifest['sentencepiece_native_pyd']['size']} bytes")
        lines.append(f"   SHA256: {manifest['sentencepiece_native_pyd']['sha256']}")
        lines.append(f"   Linker: {manifest['sentencepiece_native_pyd']['linker_version']}\n")

    if manifest["vc_runtime_dlls"]:
        lines.append("3. MICROSOFT VC++ RUNTIME DLLS:")
        for d in manifest["vc_runtime_dlls"]:
            lines.append(f"   {d['filename']: <28} | {d['actual_file_version']: <14} | {d['sha256']} | {d['size']: >7} bytes")

    output_json.parent.mkdir(parents=True, exist_ok=True)
    with output_json.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    output_txt.parent.mkdir(parents=True, exist_ok=True)
    with output_txt.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Successfully generated manifests at:\n  {output_json}\n  {output_txt}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate manifest from candidate artifacts.")
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="Output MANIFEST.json path")
    parser.add_argument("--output-txt", type=Path, default=None, help="Optional text manifest path")
    args = parser.parse_args()

    output_json = args.output.resolve()
    output_txt = (args.output_txt or output_json.with_suffix(".txt")).resolve()
    generate(args.candidate_root.resolve(), output_json, output_txt)

if __name__ == "__main__":
    main()

"""Construct CP8.2 self-contained onedir Python runtimes from audited inputs."""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import re
import shutil
import struct
import sys
from ctypes import wintypes
from pathlib import Path


EXCLUDED_TOP_LEVEL = {
    "pip", "pip-25.3.dist-info",
    "wheel", "wheel-0.45.1.dist-info",
    "pytest", "_pytest",
}
MAIN_EXCLUDED_PREFIXES = ("piper", "onnxruntime", "gradio", "webview", "clr", "pythonnet", "llama_cpp")


def _ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name == "__pycache__" or name in {"tests", "test"}}
    if Path(directory).name == "site-packages":
        ignored |= {name for name in names if name in EXCLUDED_TOP_LEVEL}
    return ignored


VC_RUNTIME_DLLS_REQUIRED = {
    "vcruntime140.dll",
    "vcruntime140_1.dll",
    "msvcp140.dll",
    "msvcp140_1.dll",
    "msvcp140_2.dll",
    "msvcp140_atomic_wait.dll",
    "msvcp140_codecvt_ids.dll",
    "concrt140.dll",
    "vccorlib140.dll",
}
VC_RUNTIME_DLLS_OPTIONAL = {
    "vcruntime140_threads.dll",  # Only exists in newer Visual Studio redist (14.4x+)
}


def _get_pe_arch(path: Path) -> str:
    """Return architecture of a PE file: x64, x86, arm64, or INVALID."""
    try:
        with path.open("rb") as f:
            dos_hdr = f.read(64)
            if len(dos_hdr) < 64 or dos_hdr[:2] != b"MZ":
                return "INVALID"
            pe_offset = struct.unpack("<I", dos_hdr[0x3C:0x40])[0]
            f.seek(pe_offset)
            pe_hdr = f.read(24)
            if len(pe_hdr) < 24 or pe_hdr[:4] != b"PE\x00\x00":
                return "INVALID"
            machine = struct.unpack("<H", pe_hdr[4:6])[0]
            if machine == 0x8664:
                return "x64"
            if machine == 0x014C:
                return "x86"
            if machine == 0xAA64:
                return "arm64"
            return f"unknown(0x{machine:x})"
    except Exception:
        return "ERROR"


def _get_file_version(path: Path) -> str:
    """Get Win32 file version of a DLL using ctypes."""
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


def _resolve_vc_redist_dir(explicit_dir: Path | None, base_python: Path) -> Path:
    """Resolve VC redist source. System32 is intentionally not a release fallback."""
    if explicit_dir is not None:
        candidate = explicit_dir.resolve()
        if not candidate.is_dir():
            raise RuntimeError(f"FAIL CLOSED: --vc-redist-dir is not a directory: {candidate}")
        cand_str = str(candidate).lower()
        if "system32" in cand_str or "syswow64" in cand_str:
            raise RuntimeError(f"FAIL CLOSED: System32/SysWOW64 is forbidden as VC redist source: {candidate}")
        return candidate

    vs_redist_roots = [
        Path(r"C:\Program Files\Microsoft Visual Studio"),
        Path(r"C:\Program Files (x86)\Microsoft Visual Studio"),
    ]
    for vs_root in vs_redist_roots:
        if vs_root.exists():
            crt_dirs = [
                d.resolve() for d in vs_root.glob("**/x64/Microsoft.VC14*.CRT")
                if "onecore" not in str(d).lower()
            ]
            if crt_dirs:
                return sorted(crt_dirs, reverse=True)[0]

    base_python = base_python.resolve()
    if (base_python / "vcruntime140.dll").is_file():
        return base_python

    raise RuntimeError(
        "FAIL CLOSED: Could not deterministically resolve VC Redist source directory. "
        "Provide --vc-redist-dir explicitly. System32 is not accepted as a release fallback."
    )


def _find_and_verify_vc_redist_dlls(vc_source_dir: Path) -> dict[str, dict]:
    """Find allowlisted VC DLLs and measure actual version/hash/provenance."""
    found: dict[str, dict] = {}
    for dll_name in sorted(VC_RUNTIME_DLLS_REQUIRED | VC_RUNTIME_DLLS_OPTIONAL):
        dll_path = vc_source_dir / dll_name
        if not dll_path.is_file():
            if dll_name in VC_RUNTIME_DLLS_REQUIRED:
                raise RuntimeError(f"FAIL CLOSED: required VC runtime DLL missing: {dll_name} in {vc_source_dir}")
            continue

        arch = _get_pe_arch(dll_path)
        if arch != "x64":
            raise RuntimeError(f"FAIL CLOSED: {dll_name} architecture is {arch}; expected x64")

        file_version = _get_file_version(dll_path)
        if file_version in {"N/A", "unknown", "ERROR"}:
            raise RuntimeError(f"FAIL CLOSED: unable to read Windows file version for {dll_name}")

        found[dll_name] = {
            "path": dll_path,
            "filename": dll_name,
            "size_bytes": dll_path.stat().st_size,
            "sha256": _sha256(dll_path),
            "file_version": file_version,
            "architecture": arch,
            "source_path": str(dll_path),
            "source_provenance": "explicit --vc-redist-dir or deterministic Visual Studio/Base-Python redist resolution",
            "hash_allowlist_status": "PENDING_VALIDATION",
        }
    return found


def _copy_base(base: Path, target: Path, vc_dlls: dict[str, dict]) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in ("python.exe", "pythonw.exe", "python3.dll", "python312.dll"):
        shutil.copy2(base / name, target / name)

    for dll_name, dll_info in vc_dlls.items():
        shutil.copy2(dll_info["path"], target / dll_name)

    for name in ("DLLs", "Lib", "tcl"):
        source = base / name
        if source.exists():
            shutil.copytree(source, target / name, ignore=_ignore, dirs_exist_ok=True)
    shutil.rmtree(target / "Lib" / "site-packages", ignore_errors=True)


def _copy_site_packages(venv: Path, target: Path, *, main: bool) -> None:
    source = venv / "Lib" / "site-packages"
    destination = target / "Lib" / "site-packages"
    destination.mkdir(parents=True, exist_ok=True)
    for entry in source.iterdir():
        lowered = entry.name.lower()
        if entry.name in EXCLUDED_TOP_LEVEL or (main and lowered.startswith(MAIN_EXCLUDED_PREFIXES)):
            continue
        copied = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, copied, ignore=_ignore, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, copied)


def _copy_backend(source: Path, target: Path) -> None:
    shutil.copytree(
        source / "backend", target / "app" / "backend",
        ignore=lambda _path, names: {name for name in names if name in {"tests", "__pycache__"}},
        dirs_exist_ok=True,
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _cuda_build(version_file: Path) -> str:
    """Read Torch's generated CUDA assignment without importing Torch/DLLs."""
    match = re.search(
        r"^\s*cuda(?:\s*:\s*[^=]+)?\s*=\s*(['\"])([^'\"]+)\1\s*$",
        version_file.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if not match:
        raise RuntimeError(f"Unable to determine CUDA build from {version_file}")
    return match.group(2)


def _manifest(runtime: Path, output: Path, vc_metadata: list[dict]) -> None:
    files = []
    for path in sorted(item for item in runtime.rglob("*") if item.is_file()):
        files.append({"relative_path": path.relative_to(runtime).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    site = runtime / "Lib" / "site-packages"
    def version(name: str) -> str:
        metadata = next(site.glob(f"{name.replace('-', '_')}-*.dist-info/METADATA"))
        return next(line.split(": ", 1)[1] for line in metadata.read_text(encoding="utf-8").splitlines() if line.startswith("Version: "))
    torch_version = version("torch")
    torchao_metadata = list(site.glob("torchao-*.dist-info/METADATA"))
    payload = {
        "python_architecture": "64bit",
        "python_version": "3.12.10",
        "torch_version": torch_version,
        "torchaudio_version": version("torchaudio"),
        "cuda_build": _cuda_build(site / "torch" / "version.py"),
        "vc_runtime_dlls": vc_metadata,
        "files": files,
    }
    sp_metadata = list(site.glob("sentencepiece-*.dist-info/METADATA"))
    if sp_metadata:
        payload["sentencepiece_version"] = version("sentencepiece")
        sp_pyd = site / "sentencepiece" / "_sentencepiece.cp312-win_amd64.pyd"
        if sp_pyd.is_file():
            payload["sentencepiece_native_pyd_sha256"] = _sha256(sp_pyd)
    if torchao_metadata:
        payload["torchao_version"] = version("torchao")
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


LOCKED_SP_VERSION = "0.2.1"
LOCKED_SP_PYD_SHA256 = "f1069eaa45cfa5d6d81f7b46876b80860fe9147d28d84c7057ed952e84b064e5"


def _verify_main_runtime(runtime: Path) -> None:
    site = runtime / "Lib" / "site-packages"
    sp_dir = site / "sentencepiece"
    sp_pyd = sp_dir / "_sentencepiece.cp312-win_amd64.pyd"
    if not sp_pyd.is_file():
        raise RuntimeError(f"FAIL CLOSED: _sentencepiece.cp312-win_amd64.pyd missing in {sp_dir}")
    actual_hash = _sha256(sp_pyd).lower()
    if actual_hash != LOCKED_SP_PYD_SHA256:
        raise RuntimeError(
            f"FAIL CLOSED: SentencePiece native pyd hash mismatch!\n"
            f"Expected: {LOCKED_SP_PYD_SHA256}\n"
            f"Actual:   {actual_hash}"
        )
    if (site / "sentencepiece-0.2.2.dist-info").exists():
        raise RuntimeError("FAIL CLOSED: sentencepiece-0.2.2.dist-info residue found in staged runtime!")


def build(base: Path, venv: Path, project: Path, target: Path, vc_dlls: dict[str, dict], *, main: bool) -> None:
    # Windows can retain transient handles on a previous interrupted Torch
    # copy.  Copying the same audited inputs over that staging tree is
    # deterministic and avoids touching either source virtual environment.
    target.mkdir(parents=True, exist_ok=True)
    _copy_base(base, target, vc_dlls)
    _copy_site_packages(venv, target, main=main)
    _copy_backend(project, target)
    if main:
        _verify_main_runtime(target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-python", required=True, type=Path)
    parser.add_argument("--main-venv", required=True, type=Path)
    parser.add_argument("--chatterbox-venv", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
    parser.add_argument(
        "--vc-redist-dir",
        type=Path,
        default=None,
        help="Explicit source directory for VC++ Redistributable DLLs (x64).",
    )
    parser.add_argument(
        "--runtime",
        choices=("main", "chatterbox", "all"),
        default="all",
        help="Select which runtime to stage. Default: all.",
    )

    args = parser.parse_args()
    base = args.base_python.resolve()
    destination = args.destination.resolve()
    main_runtime = destination / "runtime-main"
    chatter_runtime = destination / "runtime-chatterbox"

    vc_source = _resolve_vc_redist_dir(args.vc_redist_dir, base)
    vc_dlls = _find_and_verify_vc_redist_dlls(vc_source)
    vc_metadata = []
    for info in vc_dlls.values():
        entry = dict(info)
        del entry["path"]
        vc_metadata.append(entry)

    if args.runtime in ("main", "all"):
        build(
            base,
            args.main_venv.resolve(),
            args.project.resolve(),
            main_runtime,
            vc_dlls,
            main=True,
        )
        _manifest(main_runtime, destination / "runtime-main-manifest.json", vc_metadata)

    if args.runtime in ("chatterbox", "all"):
        build(
            base,
            args.chatterbox_venv.resolve(),
            args.project.resolve(),
            chatter_runtime,
            vc_dlls,
            main=False,
        )
        _manifest(chatter_runtime, destination / "runtime-chatterbox-manifest.json", vc_metadata)


if __name__ == "__main__":
    main()

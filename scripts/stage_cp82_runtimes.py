"""Construct CP8.2 self-contained onedir Python runtimes from audited inputs."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
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


def _copy_base(base: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in ("python.exe", "pythonw.exe", "python3.dll", "python312.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        shutil.copy2(base / name, target / name)
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


def _manifest(runtime: Path, output: Path) -> None:
    files = []
    for path in sorted(item for item in runtime.rglob("*") if item.is_file()):
        files.append({"relative_path": path.relative_to(runtime).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)})
    site = runtime / "Lib" / "site-packages"
    def version(name: str) -> str:
        metadata = next(site.glob(f"{name.replace('-', '_')}-*.dist-info/METADATA"))
        return next(line.split(": ", 1)[1] for line in metadata.read_text(encoding="utf-8").splitlines() if line.startswith("Version: "))
    torch_version = version("torch")
    torchao_metadata = list(site.glob("torchao-*.dist-info/METADATA"))
    payload = {"python_architecture": "64bit", "python_version": "3.12.10", "torch_version": torch_version, "torchaudio_version": version("torchaudio"), "cuda_build": _cuda_build(site / "torch" / "version.py"), "files": files}
    if torchao_metadata:
        payload["torchao_version"] = version("torchao")
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build(base: Path, venv: Path, project: Path, target: Path, *, main: bool) -> None:
    # Windows can retain transient handles on a previous interrupted Torch
    # copy.  Copying the same audited inputs over that staging tree is
    # deterministic and avoids touching either source virtual environment.
    target.mkdir(parents=True, exist_ok=True)
    _copy_base(base, target)
    _copy_site_packages(venv, target, main=main)
    _copy_backend(project, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-python", required=True, type=Path)
    parser.add_argument("--main-venv", required=True, type=Path)
    parser.add_argument("--chatterbox-venv", required=True, type=Path)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--destination", required=True, type=Path)
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

    if args.runtime in ("main", "all"):
        build(
            base,
            args.main_venv.resolve(),
            args.project.resolve(),
            main_runtime,
            main=True,
        )
        _manifest(main_runtime, destination / "runtime-main-manifest.json")

    if args.runtime in ("chatterbox", "all"):
        build(
            base,
            args.chatterbox_venv.resolve(),
            args.project.resolve(),
            chatter_runtime,
            main=False,
        )
        _manifest(chatter_runtime, destination / "runtime-chatterbox-manifest.json")


if __name__ == "__main__":
    main()

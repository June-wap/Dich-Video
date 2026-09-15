"""CP0.3B-0 read-only runtime checks; no installs, downloads or model inference.

Run with the official interpreter from the project root. Optionally save JSON
evidence in a .txt file with --output.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata as metadata
import json
import platform
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL = ROOT / "external/OmniVoice/.venv312/Scripts/python.exe"
PACKAGES = (
    "pip", "pytest", "torch", "torchaudio", "numpy", "soundfile",
    "librosa", "pydub", "transformers", "accelerate", "gradio",
    "fastapi", "uvicorn", "pydantic", "psutil", "tensorboardX", "webdataset",
)
CORE = {
    "core.tts_manager": "TTSManager",
    "providers.omnivoice": "OmniVoiceProvider",
    "core.long_text": "build_chunks",
    "core.audio_utils": "merge_segments",
    "core.hardware": "get_hardware_info",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    evidence = {
        "checkpoint": "CP0.3B-0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backend_python": platform.python_version(),
        "backend_sys_executable": sys.executable,
        "base_executable": getattr(sys, "_base_executable", None),
        "architecture": platform.machine(),
        "official_interpreter": Path(sys.executable).resolve() == OFFICIAL.resolve(),
        "packages": {}, "core_imports": {}, "errors": [],
    }
    if sys.version_info[:2] != (3, 12):
        evidence["errors"].append("Backend requires Python 3.12.x")
    if not evidence["official_interpreter"]:
        evidence["errors"].append("Use external/OmniVoice/.venv312/Scripts/python.exe")
    sys.path.insert(0, str(ROOT / "prototype"))
    for name in PACKAGES:
        try:
            importlib.import_module(name)
            evidence["packages"][name] = {"version": metadata.version(name), "import": "PASS"}
        except Exception as exc:
            evidence["packages"][name] = {"import": "FAIL", "error": str(exc)}
            evidence["errors"].append(f"Import failed: {name}")
    for module, attribute in CORE.items():
        try:
            getattr(importlib.import_module(module), attribute)
            evidence["core_imports"][f"{module}.{attribute}"] = "PASS"
        except Exception as exc:
            evidence["core_imports"][module] = str(exc)
            evidence["errors"].append(f"Core import failed: {module}")
    # Verify the checked-in direct dependency contract against this interpreter.
    evidence["dependency_pins"] = {}
    for filename in ("requirements-backend.txt", "constraints-backend.txt"):
        for line in (ROOT / filename).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            name, expected = line.split("==", 1)
            try:
                actual = metadata.version(name)
            except metadata.PackageNotFoundError:
                actual = None
            evidence["dependency_pins"][name] = {"expected": expected, "actual": actual}
            if actual != expected:
                evidence["errors"].append(f"Dependency pin mismatch: {name}")
    try:
        omnivoice = importlib.import_module("omnivoice")
        source = Path(omnivoice.__file__).resolve()
        evidence["omnivoice"] = {"import": "PASS", "path": str(source),
                                 "version": metadata.version("omnivoice"),
                                 "local_source": source.is_relative_to(ROOT / "external/OmniVoice/omnivoice")}
        if not evidence["omnivoice"]["local_source"]:
            evidence["errors"].append("OmniVoice must resolve to the local source checkout")
    except Exception as exc:
        evidence["omnivoice"] = {"import": "FAIL", "error": str(exc)}
        evidence["errors"].append("OmniVoice import failed")
    try:
        import torch
        available = torch.cuda.is_available()
        evidence["cuda"] = {"torch": torch.__version__, "build": torch.version.cuda,
                            "available": available}
        if available:
            evidence["cuda"].update(gpu=torch.cuda.get_device_name(0),
                                   vram_gb=round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2))
            # Exercise a real CUDA kernel without loading any speech model.
            value = (torch.ones(4, device="cuda:0") * 2).sum().item()
            evidence["cuda"]["kernel_check"] = "PASS" if value == 8 else "FAIL"
        if (not available or "RTX 4050" not in evidence["cuda"].get("gpu", "")
                or torch.__version__ != "2.8.0+cu128" or torch.version.cuda != "12.8"
                or evidence["cuda"].get("kernel_check") != "PASS"):
            evidence["errors"].append("CUDA baseline mismatch")
    except Exception as exc:
        evidence["errors"].append(f"CUDA check failed: {exc}")
    for command in ("ffmpeg", "ffprobe"):
        try:
            proc = subprocess.run([command, "-version"], capture_output=True, text=True,
                                  timeout=20, check=True)
            evidence[command] = {"path": shutil.which(command), "version": proc.stdout.splitlines()[0]}
        except Exception as exc:
            evidence["errors"].append(f"{command}: {exc}")
    for label, command in (
        ("global_python", ["python", "--version"]),
        ("python_launcher", ["py", "-0p"]),
        ("pip_check", [sys.executable, "-m", "pip", "check"]),
        ("pip_cli", [sys.executable, "-m", "pip", "--version"]),
        ("pytest_cli", [sys.executable, "-m", "pytest", "--version"]),
    ):
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=60)
            evidence[label] = {"exit_code": proc.returncode, "output": (proc.stdout + proc.stderr).strip()}
            if label in ("pip_check", "pip_cli", "pytest_cli") and proc.returncode:
                evidence["errors"].append(f"{label} failed")
        except Exception as exc:
            evidence[label] = {"error": str(exc)}
            if label in ("pip_check", "pip_cli", "pytest_cli"):
                evidence["errors"].append(f"{label} failed")
    evidence["source_sha256"] = {
        str(path.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (ROOT / "external/OmniVoice/pyproject.toml",
                     ROOT / "external/OmniVoice/omnivoice/models/omnivoice.py")
    }
    evidence["status"] = "PASS" if not evidence["errors"] else "FAIL"
    serialized = json.dumps(evidence, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

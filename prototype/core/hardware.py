"""Hardware detection: CPU, RAM, GPU, CUDA."""
import os
import platform
import sys


def get_hardware_info() -> dict:
    """Return system hardware and runtime info."""
    import psutil

    info = {
        "os": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": sys.version.split()[0],
        "cpu": platform.processor() or "unknown",
        "cpu_cores_physical": psutil.cpu_count(logical=False),
        "cpu_cores_logical": psutil.cpu_count(logical=True),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
        "ram_available_gb": round(psutil.virtual_memory().available / (1024 ** 3), 1),
        "cuda_available": False,
        "gpu_name": None,
        "vram_total_gb": None,
        "vram_used_gb": None,
    }

    # CUDA / GPU detection
    try:
        import onnxruntime as ort
        providers = ort.get_available_providers()
        info["ort_providers"] = providers
        if "CUDAExecutionProvider" in providers:
            info["cuda_available"] = True
    except Exception:
        info["ort_providers"] = []

    # Try to get GPU info via a lightweight approach
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 3:
                info["gpu_name"] = parts[0].strip()
                info["vram_total_gb"] = round(int(parts[1].strip()) / 1024, 1)
                info["vram_used_gb"] = round(int(parts[2].strip()) / 1024, 1)
    except Exception:
        pass

    return info


def get_runtime_versions() -> dict:
    """Return installed TTS runtime versions."""
    versions = {}
    for pkg, mod in [
        ("onnxruntime", "onnxruntime"),
        ("sherpa-onnx", "sherpa_onnx"),
        ("vieneu", "vieneu"),
        ("soundfile", "soundfile"),
        ("pydub", "pydub"),
        ("gradio", "gradio"),
        ("pyopenjtalk-plus", "pyopenjtalk"),
        ("numpy", "numpy"),
    ]:
        try:
            import importlib
            m = importlib.import_module(mod)
            v = getattr(m, "__version__", None)
            if v is None:
                import importlib.metadata
                v = importlib.metadata.version(pkg)
            versions[pkg] = v
        except Exception:
            versions[pkg] = "not installed"
    return versions

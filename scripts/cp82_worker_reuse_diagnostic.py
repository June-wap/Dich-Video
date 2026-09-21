"""Deterministic, fail-loud CP8.2 portable Chatterbox worker diagnostic."""
from __future__ import annotations

import os
import json
import sys
import time
import traceback
import wave
from pathlib import Path

def validate_wav(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    with wave.open(str(path), "rb") as item:
        return item.getnchannels() == 1 and item.getframerate() == 24_000 and item.getnframes() > 0


def diagnostic(provider, text: str, output: Path, label: str):
    started = time.perf_counter()
    result = provider.synthesize(text, "en", output_path=output)
    elapsed = time.perf_counter() - started
    process = provider._process
    pid = process.pid if process is not None else None
    print(f"REQUEST_{label}_STATUS={result.status}")
    print(f"REQUEST_{label}_ERROR={result.error}")
    print(f"REQUEST_{label}_TIME={elapsed:.3f}")
    print(f"WORKER_PID_AFTER_REQUEST_{label}={pid}")
    print(f"RESULT_{label}={result}")
    print(f"WAV_{label}_VALID={'YES' if validate_wav(output) else 'NO'}")
    return result, pid


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    runtime_app = Path(sys.executable).resolve().parent / "app"
    sys.path.insert(0, str(runtime_app))
    from backend.services.chatterbox_worker_provider import ChatterboxWorkerProvider
    chatterbox = Path(os.environ["LOCAL_AI_CHATTERBOX_PYTHON"]).resolve()
    worker_root = chatterbox.parent / "app"
    output = root / ".runtime" / "cp82" / "gates"
    output.mkdir(parents=True, exist_ok=True)
    evidence = {"parent_exe": str(Path(sys.executable).resolve()), "worker_exe": str(chatterbox), "hf_home": os.environ.get("HF_HOME"), "hf_hub_cache": os.environ.get("HF_HUB_CACHE")}
    print(f"PARENT_EXE={Path(sys.executable).resolve()}")
    print(f"CHATTERBOX_PYTHON={chatterbox}")
    print(f"HF_HOME={os.environ.get('HF_HOME')}")
    print(f"HF_HUB_CACHE={os.environ.get('HF_HUB_CACHE')}")
    provider = ChatterboxWorkerProvider(chatterbox, worker_root)
    try:
        provider.load()
        process = provider._process
        if process is None:
            raise RuntimeError("WorkerProvider.load() returned without _process")
        print(f"WORKER_PID_1={process.pid}")
        evidence["worker_pid_1"] = process.pid
        first, pid_one = diagnostic(provider, "Hello, this is portable worker request one.", output / "worker-one.wav", "1")
        evidence.update({"request_1_status": first.status, "request_1_error": first.error, "worker_pid_after_request_1": pid_one, "wav_1_valid": validate_wav(output / "worker-one.wav")})
        if first.status != "PASS":
            print(f"WORKER_EXIT_CODE={process.poll()}")
            print(f"WORKER_STDERR={provider._stderr_tail()}")
            evidence.update({"worker_exit_code": process.poll(), "worker_stderr": provider._stderr_tail()})
            (output / "worker-reuse-report.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
            return 1
        second, pid_two = diagnostic(provider, "Hello, this is portable worker request two.", output / "worker-two.wav", "2")
        print(f"WORKER_PID_2={pid_two}")
        print(f"SAME_WORKER={'YES' if pid_one == pid_two and pid_one is not None else 'NO'}")
        print(f"WORKER_EXIT_CODE={process.poll()}")
        print(f"WORKER_STDERR={provider._stderr_tail()}")
        evidence.update({"request_2_status": second.status, "request_2_error": second.error, "worker_pid_2": pid_two, "wav_2_valid": validate_wav(output / "worker-two.wav"), "same_worker": pid_one == pid_two and pid_one is not None, "worker_exit_code": process.poll(), "worker_stderr": provider._stderr_tail()})
        (output / "worker-reuse-report.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return 0 if second.status == "PASS" and validate_wav(output / "worker-one.wav") and validate_wav(output / "worker-two.wav") and pid_one == pid_two else 1
    except Exception:
        traceback.print_exc()
        process = provider._process
        print(f"WORKER_EXIT_CODE={process.poll() if process is not None else None}")
        print(f"WORKER_STDERR={provider._stderr_tail()}")
        evidence.update({"exception": traceback.format_exc(), "worker_exit_code": process.poll() if process is not None else None, "worker_stderr": provider._stderr_tail()})
        (output / "worker-reuse-report.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
        return 1
    finally:
        provider.unload()


if __name__ == "__main__":
    raise SystemExit(main())

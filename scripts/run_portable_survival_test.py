"""Portable Backend Survival Test for runtime-main-combined-test.

Validates:
1. Spawns <PORTABLE_COPY_PATH>\\python.exe -m backend.main
2. Captures and manages exact owned child PID.
3. Polls http://127.0.0.1:8000/api/health until ready.
4. Executes real Vietnamese TTS synthesis request:
   POST /api/tts (text="Xin chào, đây là bài kiểm tra backend survival test.")
5. Verifies API response: HTTP 200, valid JSON, valid audio URL.
6. Downloads audio, validates WAV format, canonical sample rate (24000), channels=1, duration > 0.
7. Confirms backend process is STILL ALIVE (proc.poll() is None).
8. Safely terminates ONLY the owned PID/process tree without broad taskkill.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path


def run_survival_test(portable_python: Path, project_root: Path, output_wav: Path, chatterbox_python: Path | None = None) -> bool:
    print("=================================================================")
    print("           PORTABLE BACKEND SURVIVAL & REAL TTS TEST             ")
    print(f" Python Executable: {portable_python}")
    print(f" Project Root:      {project_root}")
    print("=================================================================")

    if not portable_python.is_file():
        print(f"[FAIL] Portable python not found: {portable_python}", file=sys.stderr)
        return False
    if not (project_root / "backend").is_dir():
        print(f"[FAIL] Project root does not contain backend/: {project_root}", file=sys.stderr)
        return False

    env = os.environ.copy()
    env["PYTHONPATH"] = str(project_root)
    if not chatterbox_python or not chatterbox_python.is_file():
        candidates = [
            project_root / ".venv-chatterbox" / "Scripts" / "python.exe",
            portable_python.parent.parent / "runtime-chatterbox" / "python.exe",
            portable_python.parent / "runtime-chatterbox" / "python.exe",
        ]
        for c in candidates:
            if c.is_file():
                chatterbox_python = c
                break

    if chatterbox_python and chatterbox_python.is_file():
        env["LOCAL_AI_CHATTERBOX_PYTHON"] = str(chatterbox_python)
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    # Ensure local token is disabled or matched if required
    env["LOCAL_AI_REQUIRE_TOKEN"] = "0"

    cmd = [str(portable_python), "-m", "backend.main"]
    print(f"\n[1/5] Launching backend process: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=str(project_root),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    backend_pid = proc.pid
    print(f"  Backend spawned successfully. Owned PID: {backend_pid}")

    try:
        # Step 2: Poll /api/health
        print("\n[2/5] Polling /api/health endpoint...")
        health_url = "http://127.0.0.1:8000/api/health"
        is_ready = False
        t0 = time.time()
        while time.time() - t0 < 60:
            if proc.poll() is not None:
                stdout, stderr = proc.communicate()
                print(f"[FAIL] Backend process {backend_pid} exited unexpectedly with code {proc.returncode}!", file=sys.stderr)
                print(f"--- STDOUT ---\n{stdout}")
                print(f"--- STDERR ---\n{stderr}")
                return False
            try:
                with urllib.request.urlopen(health_url, timeout=2) as resp:
                    if resp.status == 200:
                        body = json.loads(resp.read().decode("utf-8"))
                        print(f"  [OK] /api/health responded HTTP 200: {body}")
                        is_ready = True
                        break
            except Exception:
                time.sleep(1)

        if not is_ready:
            print(f"[FAIL] Timeout waiting for /api/health after 60s!", file=sys.stderr)
            return False

        # Step 3: Real Vietnamese TTS request
        print("\n[3/5] Sending real Vietnamese TTS request to /api/tts...")
        tts_url = "http://127.0.0.1:8000/api/tts"
        tts_payload = {
            "text": "Xin chào, đây là bài kiểm tra backend survival test bằng VieNeu.",
            "language": "vi",
            "voice_id": "vieneu_default",
            "speed": 1.0,
            "format": "wav",
        }
        req_data = json.dumps(tts_payload).encode("utf-8")
        req = urllib.request.Request(
            tts_url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        t_synth = time.time()
        with urllib.request.urlopen(req, timeout=180) as resp:
            status_code = resp.status
            resp_body = json.loads(resp.read().decode("utf-8"))
        elapsed_synth = time.time() - t_synth

        print(f"  [OK] /api/tts responded HTTP {status_code} in {elapsed_synth:.2f}s")
        print(f"  Response: {resp_body}")

        if status_code != 200 or not resp_body.get("ok"):
            print(f"[FAIL] TTS request returned non-OK status: {resp_body}", file=sys.stderr)
            return False

        audio_url = resp_body["data"]["audio_url"]
        full_audio_url = f"http://127.0.0.1:8000{audio_url}"

        # Step 4: Download and validate WAV
        print(f"\n[4/5] Downloading generated audio from {full_audio_url}...")
        test_wav = output_wav.resolve()
        test_wav.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(full_audio_url, timeout=30) as audio_resp:
            test_wav.write_bytes(audio_resp.read())

        wav_size = test_wav.stat().st_size
        print(f"  Downloaded {wav_size} bytes to {test_wav}")
        if wav_size <= 44:
            print(f"[FAIL] Audio file too small: {wav_size} bytes", file=sys.stderr)
            return False

        with wave.open(str(test_wav), "rb") as wf:
            sr = wf.getframerate()
            ch = wf.getnchannels()
            frames = wf.getnframes()
            dur = frames / float(sr)
            print(f"  [OK] Valid WAV: sr={sr}, channels={ch}, frames={frames}, duration={dur:.2f}s")
            if sr != 24000:
                print(f"[FAIL] Sample rate expected 24000, got {sr}", file=sys.stderr)
                return False
            if ch != 1:
                print(f"[FAIL] Channels expected 1, got {ch}", file=sys.stderr)
                return False
            if dur <= 0:
                print(f"[FAIL] Duration <= 0", file=sys.stderr)
                return False

        # Step 5: Verify backend STILL ALIVE after inference
        print("\n[5/5] Checking if backend process is STILL ALIVE after VieNeu inference...")
        if proc.poll() is not None:
            print(f"[FAIL] Backend process {backend_pid} died after synthesis! Returncode: {proc.returncode}", file=sys.stderr)
            return False

        print(f"  >>> SUCCESS: Backend PID {backend_pid} is ALIVE and HEALTHY! <<<")

        # Second health check
        with urllib.request.urlopen(health_url, timeout=5) as resp:
            assert resp.status == 200
        print("  [OK] Post-synthesis /api/health confirmed 200 OK.")

        return True

    finally:
        # Safe termination of EXACT owned PID
        print(f"\n[Cleanup] Terminating owned backend PID {backend_pid} gracefully...")
        try:
            # On Windows, taskkill /PID /T terminates the specific tree of backend_pid only
            subprocess.run(
                ["taskkill", "/PID", str(backend_pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
            proc.wait(timeout=5)
            print(f"  [OK] Owned process tree for PID {backend_pid} cleanly terminated.")
        except Exception as exc:
            print(f"  [WARN] Exception during cleanup: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-python", type=Path, required=True, help="Path to portable runtime python.exe")
    parser.add_argument("--project-root", type=Path, required=True, help="Path to project root containing backend/")
    parser.add_argument("--output-wav", type=Path, required=True, help="Path to save the generated test audio")
    parser.add_argument("--chatterbox-python", type=Path, default=None, help="Optional path to Chatterbox python.exe")

    args = parser.parse_args()

    ok = run_survival_test(
        portable_python=args.runtime_python.resolve(),
        project_root=args.project_root.resolve(),
        output_wav=args.output_wav.resolve(),
        chatterbox_python=args.chatterbox_python.resolve() if args.chatterbox_python else None
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

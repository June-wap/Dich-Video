"""Automated fail-closed preflight and release gate for portable runtime-main on Windows x64.

Enforces strict verification across six sequential native child processes:
- Gate A1: import sentencepiece._sentencepiece; print("NATIVE_SENTENCEPIECE_OK")
- Gate A2: import sentencepiece; print(sentencepiece.__version__) -> must be 0.2.1
- Gate B:  Torch CPU tensor matrix multiplication (no NaN, exit 0)
- Gate C:  from backend.services.vieneu_adapter import VieNeuAdapter (exit 0)
- Gate D:  VieNeuAdapter(device="cpu").load() (offline, model weights loaded, exit 0)
- Gate E:  Real VieNeu WAV generation ("Xin chào, đây là bài kiểm tra Voca Basic.")
           Validates: file exists, size > 44 bytes, readable WAV, channels=1, frames>0,
           duration>0, sample_rate==24000 (canonical VieNeu sample rate).

Requirements:
- Strict explicit argument --runtime-python <path> (NO automatic fallback to .venv312).
- Every native gate runs in an isolated CHILD PROCESS.
- Captures: stdout, stderr, timeout, raw signed exit code, unsigned exit code, hex code.
- Explicitly flags 0xC0000005 (3221225477 / -1073741819) as native crash and FAILS CLOSED.
- Injects read-only Win32 diagnostic logging loaded path and version of CRT modules.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
import struct
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

ACCESS_VIOLATION_CODES = {
    3221225477,           # Unsigned 32-bit Windows 0xC0000005
    -1073741819,          # Signed 32-bit equivalent of 0xC0000005
    0xC0000005,
}

CANONICAL_VIENEU_SAMPLE_RATE = 24000
VIENEU_TEST_SENTENCE = "Xin chào, đây là bài kiểm tra Voca Basic."

DIAGNOSTIC_SNIPPET = r'''
import ctypes
from ctypes import wintypes
import struct

def _dump_loaded_crt_modules():
    try:
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        ver_dll = ctypes.WinDLL('version', use_last_error=True)

        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.EnumProcessModules.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        psapi.EnumProcessModules.restype = wintypes.BOOL
        psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
        psapi.GetModuleFileNameExW.restype = wintypes.DWORD

        def _get_ver(fp):
            try:
                sz = ver_dll.GetFileVersionInfoSizeW(fp, None)
                if sz == 0: return "N/A"
                buf = ctypes.create_string_buffer(sz)
                if not ver_dll.GetFileVersionInfoW(fp, 0, sz, buf): return "N/A"
                pVal = ctypes.c_void_p()
                uLen = wintypes.UINT()
                if not ver_dll.VerQueryValueW(buf, "\\", ctypes.byref(pVal), ctypes.byref(uLen)): return "N/A"
                raw = ctypes.string_at(pVal.value, uLen.value)
                if len(raw) >= 16:
                    ms, ls = struct.unpack_from("<II", raw, 8)
                    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
            except Exception:
                pass
            return "unknown"

        hProc = k32.GetCurrentProcess()
        cbNeed = wintypes.DWORD()
        hMods = (wintypes.HMODULE * 1024)()
        if psapi.EnumProcessModules(hProc, hMods, ctypes.sizeof(hMods), ctypes.byref(cbNeed)):
            cnt = cbNeed.value // ctypes.sizeof(wintypes.HMODULE)
            for i in range(cnt):
                mName = (ctypes.c_wchar * 1024)()
                if psapi.GetModuleFileNameExW(hProc, hMods[i], mName, len(mName)):
                    val = mName.value
                    low = val.lower()
                    if any(k in low for k in ("msvcp140", "vcruntime140", "_sentencepiece")):
                        print(f"  [DIAGNOSTIC] Loaded: {val} (Version: {_get_ver(val)})")
    except Exception as e:
        print(f"  [DIAGNOSTIC] Error: {e}")
'''


def _run_single_gate(
    gate_name: str,
    python_exe: Path,
    child_script: str,
    extra_args: list[str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 60,
    env: dict[str, str] | None = None,
) -> tuple[bool, dict]:
    print(f"\n[{gate_name}] Spawning isolated child process...")
    print(f"  Target:     {python_exe}")
    print(f"  Timeout:    {timeout_sec}s")

    cmd = [str(python_exe), "-c", child_script]
    if extra_args:
        cmd.extend(extra_args)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    t0 = time.time()
    result_meta = {
        "gate": gate_name,
        "raw_signed_exit_code": None,
        "unsigned_exit_code": None,
        "hex_exit_code": None,
        "elapsed_sec": 0.0,
        "stdout": "",
        "stderr": "",
        "is_access_violation": False,
        "timed_out": False,
    }

    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=merged_env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.time() - t0
        retcode = proc.returncode
        u_retcode = retcode & 0xFFFFFFFF
        hex_code = f"0x{u_retcode:08X}"
        is_av = (u_retcode == 0xC0000005) or (retcode in ACCESS_VIOLATION_CODES)

        result_meta.update({
            "raw_signed_exit_code": retcode,
            "unsigned_exit_code": u_retcode,
            "hex_exit_code": hex_code,
            "elapsed_sec": round(elapsed, 2),
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "is_access_violation": is_av,
        })

        print(f"  Exit Code:  Signed={retcode}, Unsigned={u_retcode}, Hex={hex_code} ({elapsed:.2f}s)")

        if proc.stdout.strip():
            print("  --- STDOUT ---")
            for line in proc.stdout.strip().splitlines():
                print(f"    {line}")
        if proc.stderr.strip():
            print("  --- STDERR ---")
            for line in proc.stderr.strip().splitlines():
                print(f"    {line}")

        if is_av:
            print(f"  >>> FATAL: {gate_name} NATIVE CRASH 0xC0000005 (Access Violation) detected! FAIL CLOSED. <<<")
            return False, result_meta

        if retcode != 0:
            print(f"  >>> FAILED: {gate_name} exited with non-zero code {retcode} ({hex_code})! FAIL CLOSED. <<<")
            return False, result_meta

        print(f"[{gate_name}] PASS")
        return True, result_meta

    except subprocess.TimeoutExpired as exc:
        elapsed = time.time() - t0
        result_meta.update({
            "timed_out": True,
            "elapsed_sec": round(elapsed, 2),
            "stdout": exc.stdout if isinstance(exc.stdout, str) else "",
            "stderr": exc.stderr if isinstance(exc.stderr, str) else "",
        })
        print(f"  >>> FAILED: {gate_name} TIMED OUT after {elapsed:.2f}s! FAIL CLOSED. <<<")
        return False, result_meta

    except Exception as exc:
        elapsed = time.time() - t0
        result_meta.update({
            "elapsed_sec": round(elapsed, 2),
            "stderr": str(exc),
        })
        print(f"  >>> FAILED: {gate_name} unexpected exception: {exc} <<<")
        return False, result_meta


def run_gates(
    python_exe: Path,
    project_root: Path,
    selected_gates: list[str],
    output_dir: Path,
    expected_sp_version: str = "0.2.1",
    timeout_load: int = 180,
    timeout_synth: int = 180,
) -> bool:
    print("=================================================================")
    print("      PORTABLE RUNTIME-MAIN PREFLIGHT & RELEASE GATE            ")
    print(f" Target Python:       {python_exe}")
    print(f" Project Root:        {project_root}")
    print(f" Expected SP Version: {expected_sp_version}")
    print(f" Selected Gates:      {', '.join(selected_gates)}")
    print("=================================================================")

    if not python_exe.is_file():
        print(f"FATAL: Target Python executable not found: {python_exe}")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    base_env = {
        "PYTHONPATH": str(project_root),
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
    }

    # Gate A1: Native SentencePiece import
    code_a1 = f"""{DIAGNOSTIC_SNIPPET}
import sys
import sentencepiece._sentencepiece
print("NATIVE_SENTENCEPIECE_OK")
_dump_loaded_crt_modules()
"""

    # Gate A2: SentencePiece package import & exact version check
    code_a2 = f"""{DIAGNOSTIC_SNIPPET}
import sys
import sentencepiece as sp
ver = getattr(sp, '__version__', 'unknown')
print(f"SENTENCEPIECE_VERSION={{ver}}")
expected = "{expected_sp_version}"
if expected and ver != expected:
    print(f"ERROR: Expected sentencepiece=={{expected}}, but got {{ver}}", file=sys.stderr)
    sys.exit(9)
p = sp.SentencePieceProcessor()
print("SENTENCEPIECE_PROCESSOR_OK")
_dump_loaded_crt_modules()
"""

    # Gate B: Torch CPU operation
    code_b = f"""{DIAGNOSTIC_SNIPPET}
import sys
import torch
x = torch.randn(1024, 1024, dtype=torch.float32)
y = torch.matmul(x, x)
assert y.shape == (1024, 1024)
assert not torch.isnan(y).any()
print(f"TORCH_CPU_OK torch_version={{torch.__version__}}")
_dump_loaded_crt_modules()
"""

    # Gate C: VieNeuAdapter import
    code_c = f"""{DIAGNOSTIC_SNIPPET}
import sys
from backend.services.vieneu_adapter import VieNeuAdapter
assert VieNeuAdapter.PROVIDER_ID == "vieneu"
print("VIENEU_ADAPTER_IMPORT_OK")
_dump_loaded_crt_modules()
"""

    # Gate D: VieNeuAdapter(device="cpu").load()
    code_d = f"""{DIAGNOSTIC_SNIPPET}
import sys
import os
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from backend.services.vieneu_adapter import VieNeuAdapter
adapter = VieNeuAdapter(device="cpu")
adapter.load()
assert adapter.is_loaded()
print("VIENEU_LOAD_OK")
_dump_loaded_crt_modules()
"""

    # Gate E: Real VieNeu WAV generation and canonical validation
    target_wav = output_dir / f"gate_e_vieneu_{int(time.time())}.wav"
    canonical_sr = CANONICAL_VIENEU_SAMPLE_RATE
    test_sentence = VIENEU_TEST_SENTENCE

    code_e = f"""{DIAGNOSTIC_SNIPPET}
import sys
import os
import wave
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
from backend.services.vieneu_adapter import VieNeuAdapter
adapter = VieNeuAdapter(device="cpu")
adapter.load()
target = r"{target_wav}"
text = "{test_sentence}"
res = adapter.synthesize(
    text=text,
    language="vi",
    voice="vieneu_default",
    output_path=target,
)
if res.status != "PASS":
    print(f"GATE_E_FAIL synthesis status={{res.status}} error={{res.error}}", file=sys.stderr)
    sys.exit(2)
if not os.path.isfile(target):
    print(f"GATE_E_FAIL WAV file missing: {{target}}", file=sys.stderr)
    sys.exit(3)
size = os.path.getsize(target)
if size <= 44:
    print(f"GATE_E_FAIL WAV size <= 44 bytes header (size={{size}})", file=sys.stderr)
    sys.exit(4)
with wave.open(target, "rb") as wf:
    sr = wf.getframerate()
    ch = wf.getnchannels()
    frames = wf.getnframes()
    duration = frames / float(sr)
    if sr != {canonical_sr}:
        print(f"GATE_E_FAIL Canonical sample rate mismatch: expected {canonical_sr}, got {{sr}}", file=sys.stderr)
        sys.exit(5)
    if ch != 1:
        print(f"GATE_E_FAIL Channels mismatch: expected 1, got {{ch}}", file=sys.stderr)
        sys.exit(6)
    if frames <= 0 or duration <= 0:
        print(f"GATE_E_FAIL Invalid audio frames={{frames}} duration={{duration}}", file=sys.stderr)
        sys.exit(7)
    print(f"GATE_E_PASS valid_canonical_wav size={{size}} sr={{sr}} channels={{ch}} frames={{frames}} duration={{duration:.2f}}s")
_dump_loaded_crt_modules()
"""

    gate_definitions = [
        ("GATE_A1", code_a1, 30),
        ("GATE_A2", code_a2, 30),
        ("GATE_B", code_b, 60),
        ("GATE_C", code_c, 60),
        ("GATE_D", code_d, timeout_load),
        ("GATE_E", code_e, timeout_synth),
    ]

    for tag, code, timeout_val in gate_definitions:
        clean_tag = tag.replace("GATE_", "")
        if selected_gates != ["ALL"] and clean_tag not in selected_gates and tag not in selected_gates:
            continue

        ok, meta = _run_single_gate(
            gate_name=tag,
            python_exe=python_exe,
            child_script=code,
            cwd=project_root,
            timeout_sec=timeout_val,
            env=base_env,
        )
        if not ok:
            print(f"\n>>> PREFLIGHT FAILED AT {tag}! RELEASE GATE FAILS CLOSED. <<<")
            return False

    print("\n=================================================================")
    print(" ALL SELECTED GATES PASSED 100%! [VALIDATION SUCCESS]           ")
    print("=================================================================")
    return True


def _find_backend_root(explicit_root: Path | None, py_exe: Path) -> Path:
    candidates = []
    if explicit_root and explicit_root.is_dir():
        candidates.append(explicit_root)
    candidates.extend([
        Path(__file__).resolve().parent.parent,
        Path.cwd(),
        Path.cwd() / "resources",
        py_exe.parent.parent.parent / "resources",
        py_exe.parent.parent / "resources",
        py_exe.parent / "resources",
        py_exe.parent,
        Path(r"D:\Tool Dich Cho Khach"),
    ])
    for c in candidates:
        if (c / "backend").is_dir():
            return c.resolve()
    return (explicit_root or Path(__file__).resolve().parent.parent).resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runtime-python",
        type=Path,
        required=True,
        help="REQUIRED: Path to portable runtime-main python.exe (NO FALLBACK to .venv312)",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=None,
        help="Project root directory containing backend/ (default: auto-detected)",
    )
    parser.add_argument(
        "--gates",
        type=str,
        default="ALL",
        help="Comma-separated gates: A1,A2,B,C,D,E or ALL (default: ALL)",
    )
    parser.add_argument(
        "--expected-sp-version",
        type=str,
        default="0.2.1",
        help="Expected sentencepiece version in Gate A2 (default: 0.2.1)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(tempfile.gettempdir()) / "voca_release_gates",
        help="Output directory for generated test audio",
    )
    parser.add_argument(
        "--timeout-load",
        type=int,
        default=300,
        help="Timeout in seconds for Gate D (default: 300s)",
    )
    parser.add_argument(
        "--timeout-synth",
        type=int,
        default=300,
        help="Timeout in seconds for Gate E (default: 300s)",
    )

    args = parser.parse_args()
    target_python = args.runtime_python.resolve()

    if not target_python.is_file():
        print(f"FATAL: --runtime-python must point to an existing python.exe: {target_python}", file=sys.stderr)
        sys.exit(1)

    resolved_root = _find_backend_root(args.project_root, target_python)
    selected = [g.strip().upper() for g in args.gates.split(",") if g.strip()]
    success = run_gates(
        python_exe=target_python,
        project_root=resolved_root,
        selected_gates=selected,
        output_dir=args.output_dir.resolve(),
        expected_sp_version=args.expected_sp_version,
        timeout_load=args.timeout_load,
        timeout_synth=args.timeout_synth,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

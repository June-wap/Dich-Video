"""Independent automated verification script for CP0.3B-3.
Tests against the live running backend on http://127.0.0.1:8000.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, ProxyHandler
import numpy as np
import soundfile as sf

sys.stdout.reconfigure(line_buffering=True)
BASE_URL = "http://127.0.0.1:8000"
REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports" / "cp03b3_verification"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

opener = build_opener(ProxyHandler({}))


def http_get(path: str, headers: dict | None = None) -> tuple[int, dict, bytes]:
    req_headers = {"Origin": "http://localhost:5173"}
    if headers:
        req_headers.update(headers)
    req = Request(f"{BASE_URL}{path}", headers=req_headers)
    try:
        with opener.open(req, timeout=120) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def http_post(path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict, bytes]:
    req_headers = {"Content-Type": "application/json", "Origin": "http://localhost:5173"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    req = Request(f"{BASE_URL}{path}", data=body, headers=req_headers, method="POST")
    try:
        with opener.open(req, timeout=180) as resp:
            return resp.status, dict(resp.headers), resp.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read()


def wait_for_health(timeout: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            status, _, body = http_get("/api/health")
            if status == 200:
                data = json.loads(body.decode("utf-8"))
                if data.get("status") == "ok":
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def validate_wav_file(file_path: Path) -> dict:
    data, sr = sf.read(str(file_path), dtype="float32")
    channels = 1 if data.ndim == 1 else data.shape[1]
    duration = len(data) / sr if sr > 0 else 0.0
    finite = bool(np.isfinite(data).all())
    has_nan = bool(np.isnan(data).any())
    has_inf = bool(np.isinf(data).any())

    return {
        "file_exists": file_path.is_file(),
        "file_size": file_path.stat().st_size,
        "sample_rate": sr,
        "channels": channels,
        "duration": round(duration, 3),
        "finite": finite,
        "has_nan": has_nan,
        "has_inf": has_inf,
        "valid": bool(sr == 24000 and channels == 1 and duration > 0 and finite and not has_nan and not has_inf),
    }


def main():
    print("=== CP0.3B-3 INDEPENDENT AUTOMATED VERIFICATION ===")
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "FAIL",
    }

    # 1. Wait for health
    print("[1] Waiting for /api/health...")
    if not wait_for_health():
        results["error"] = "Backend failed to become healthy within timeout"
        print("FAIL: Backend not reachable")
        sys.exit(1)
    print("  /api/health is 200 OK")

    # 2. System status
    status_code, _, body = http_get("/api/system/status")
    results["system_status"] = {
        "status_code": status_code,
        "body": json.loads(body.decode("utf-8")),
    }
    print(f"  /api/system/status: HTTP {status_code}")

    # 3. Provider status before inference
    status_code, _, body = http_get("/api/providers/status")
    prov_data = json.loads(body.decode("utf-8"))
    results["provider_before"] = {
        "status_code": status_code,
        "body": prov_data,
    }
    omnivoice_before = next((p for p in prov_data.get("providers", []) if p["id"] == "omnivoice"), None)
    print("  Provider before inference:", omnivoice_before)

    if not omnivoice_before or omnivoice_before.get("state") != "NOT_LOADED" or omnivoice_before.get("loaded") is not False:
        results["error"] = "EAGER_MODEL_LOAD: Provider state was not NOT_LOADED at startup"
        print(f"FAIL: {results['error']}")
        with open(REPORTS_DIR / "verification.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        sys.exit(1)

    # 4. Request 1 (Cold inference)
    req1_payload = {
        "text": "Xin chào. Đây là bài kiểm tra hệ thống tổng hợp giọng nói bằng OmniVoice.",
        "language": "vi",
        "voice_id": "omnivoice_auto",
        "speed": 1.0,
        "format": "wav",
    }
    print("[2] Sending Request 1 (Cold)...")
    t0 = time.perf_counter()
    status_code, _, body = http_post("/api/tts", req1_payload)
    t1 = time.perf_counter()
    cold_wall_time = t1 - t0
    resp1 = json.loads(body.decode("utf-8"))
    results["request_1"] = {
        "status_code": status_code,
        "wall_time_seconds": round(cold_wall_time, 3),
        "response": resp1,
    }
    print(f"  Request 1 status: {status_code} in {cold_wall_time:.2f}s")
    if status_code != 200 or not resp1.get("ok"):
        results["error"] = f"Request 1 failed: {resp1}"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    req1_data = resp1["data"]
    gen1_id = req1_data["generation_id"]
    audio1_url = req1_data["audio_url"]

    # Retrieve WAV 1
    wav1_status, wav1_headers, wav1_bytes = http_get(audio1_url)
    wav1_path = REPORTS_DIR / "listening_01.wav"
    wav1_path.write_bytes(wav1_bytes)
    wav1_metrics = validate_wav_file(wav1_path)
    wav1_metrics["media_type"] = wav1_headers.get("content-type")
    results["wav_1_metrics"] = wav1_metrics
    print(f"  WAV 1 metrics: {wav1_metrics}")

    if not wav1_metrics["valid"] or wav1_headers.get("content-type") != "audio/wav":
        results["error"] = f"WAV 1 validation failed: {wav1_metrics}"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    # 5. Provider status after Request 1
    status_code, _, body = http_get("/api/providers/status")
    prov_data1 = json.loads(body.decode("utf-8"))
    results["provider_after_1"] = {
        "status_code": status_code,
        "body": prov_data1,
    }
    omnivoice_after1 = next((p for p in prov_data1.get("providers", []) if p["id"] == "omnivoice"), None)
    print("  Provider after Request 1:", omnivoice_after1)
    if not omnivoice_after1 or omnivoice_after1.get("state") != "READY" or omnivoice_after1.get("loaded") is not True:
        results["error"] = "Provider state was not READY after Request 1"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    # 6. Request 2 (Warm inference / Model reuse)
    req2_payload = {
        "text": "Hệ thống đang thực hiện yêu cầu thứ hai để xác minh mô hình được tái sử dụng.",
        "language": "vi",
        "voice_id": "omnivoice_auto",
        "speed": 1.0,
        "format": "wav",
    }
    print("[3] Sending Request 2 (Warm)...")
    t0 = time.perf_counter()
    status_code, _, body = http_post("/api/tts", req2_payload)
    t1 = time.perf_counter()
    warm_wall_time = t1 - t0
    resp2 = json.loads(body.decode("utf-8"))
    results["request_2"] = {
        "status_code": status_code,
        "wall_time_seconds": round(warm_wall_time, 3),
        "response": resp2,
    }
    print(f"  Request 2 status: {status_code} in {warm_wall_time:.2f}s")
    if status_code != 200 or not resp2.get("ok"):
        results["error"] = f"Request 2 failed: {resp2}"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    req2_data = resp2["data"]
    gen2_id = req2_data["generation_id"]
    audio2_url = req2_data["audio_url"]

    # Retrieve WAV 2
    wav2_status, wav2_headers, wav2_bytes = http_get(audio2_url)
    wav2_path = REPORTS_DIR / "listening_02.wav"
    wav2_path.write_bytes(wav2_bytes)
    wav2_metrics = validate_wav_file(wav2_path)
    wav2_metrics["media_type"] = wav2_headers.get("content-type")
    results["wav_2_metrics"] = wav2_metrics
    print(f"  WAV 2 metrics: {wav2_metrics}")

    if not wav2_metrics["valid"] or wav2_headers.get("content-type") != "audio/wav":
        results["error"] = f"WAV 2 validation failed: {wav2_metrics}"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    # 7. Provider status after Request 2
    status_code, _, body = http_get("/api/providers/status")
    prov_data2 = json.loads(body.decode("utf-8"))
    results["provider_after_2"] = {
        "status_code": status_code,
        "body": prov_data2,
    }
    omnivoice_after2 = next((p for p in prov_data2.get("providers", []) if p["id"] == "omnivoice"), None)
    print("  Provider after Request 2:", omnivoice_after2)
    if not omnivoice_after2 or omnivoice_after2.get("state") != "READY" or omnivoice_after2.get("loaded") is not True:
        results["error"] = "Provider state was not READY after Request 2"
        print(f"FAIL: {results['error']}")
        sys.exit(1)

    # Model reuse check: warm inference time vs cold inference time
    results["performance"] = {
        "cold_wall_time_seconds": round(cold_wall_time, 3),
        "warm_wall_time_seconds": round(warm_wall_time, 3),
        "speedup_factor": round(cold_wall_time / warm_wall_time, 2) if warm_wall_time > 0 else 0,
        "audio_1_duration": req1_data["duration_seconds"],
        "audio_2_duration": req2_data["duration_seconds"],
        "warm_rtf": round(warm_wall_time / req2_data["duration_seconds"], 3) if req2_data["duration_seconds"] > 0 else 0,
    }
    print(f"  Performance: Cold={cold_wall_time:.2f}s, Warm={warm_wall_time:.2f}s (Warm RTF={results['performance']['warm_rtf']})")

    # 8. MP3 Test
    print("[4] Testing MP3 export...")
    mp3_payload = {
        "text": "Đây là bài kiểm tra định dạng âm thanh nén MP3 của hệ thống.",
        "language": "vi",
        "voice_id": "omnivoice_auto",
        "speed": 1.0,
        "format": "mp3",
    }
    status_code, _, body = http_post("/api/tts", mp3_payload)
    resp_mp3 = json.loads(body.decode("utf-8"))
    results["mp3_test"] = {
        "status_code": status_code,
        "response": resp_mp3,
    }
    if status_code == 200 and resp_mp3.get("ok"):
        mp3_url = resp_mp3["data"]["audio_url"]
        mp3_status, mp3_headers, mp3_bytes = http_get(mp3_url)
        mp3_path = REPORTS_DIR / "listening_mp3.mp3"
        mp3_path.write_bytes(mp3_bytes)
        
        # Read MP3 with soundfile
        mp3_data, mp3_sr = sf.read(str(mp3_path), dtype="float32")
        mp3_dur = len(mp3_data) / mp3_sr if mp3_sr > 0 else 0.0
        results["mp3_test"]["file_size"] = len(mp3_bytes)
        results["mp3_test"]["media_type"] = mp3_headers.get("content-type")
        results["mp3_test"]["sample_rate"] = mp3_sr
        results["mp3_test"]["duration"] = round(mp3_dur, 3)
        results["mp3_test"]["valid"] = bool(mp3_headers.get("content-type") == "audio/mpeg" and len(mp3_bytes) > 0 and mp3_dur > 0)
        print(f"  MP3 metrics: size={len(mp3_bytes)}, dur={mp3_dur:.2f}s, valid={results['mp3_test']['valid']}")
    else:
        results["mp3_test"]["valid"] = False
        print("FAIL: MP3 export request failed")

    # 9. Input Validation Tests
    print("[5] Running Input Validation Tests...")
    val_cases = [
        ("empty_text", {"text": "", "language": "vi", "voice_id": "omnivoice_auto", "speed": 1.0, "format": "wav"}, 422, "INVALID_TEXT"),
        ("whitespace_text", {"text": "   \n\t  ", "language": "vi", "voice_id": "omnivoice_auto", "speed": 1.0, "format": "wav"}, 422, "INVALID_TEXT"),
        ("oversized_text", {"text": "A" * 2001, "language": "vi", "voice_id": "omnivoice_auto", "speed": 1.0, "format": "wav"}, 422, "TEXT_TOO_LONG"),
        ("unsupported_language", {"text": "Hallo", "language": "de", "voice_id": "omnivoice_auto", "speed": 1.0, "format": "wav"}, 422, "LANGUAGE_NOT_SUPPORTED"),
        ("invalid_voice", {"text": "Xin chào", "language": "vi", "voice_id": "nonexistent_voice", "speed": 1.0, "format": "wav"}, 422, "VOICE_NOT_FOUND"),
        ("speed_too_low", {"text": "Xin chào", "language": "vi", "voice_id": "omnivoice_auto", "speed": 0.4, "format": "wav"}, 422, "INVALID_SPEED"),
        ("speed_too_high", {"text": "Xin chào", "language": "vi", "voice_id": "omnivoice_auto", "speed": 2.1, "format": "wav"}, 422, "INVALID_SPEED"),
        ("speed_not_one", {"text": "Xin chào", "language": "vi", "voice_id": "omnivoice_auto", "speed": 1.5, "format": "wav"}, 422, "INVALID_SPEED"),
        ("invalid_format", {"text": "Xin chào", "language": "vi", "voice_id": "omnivoice_auto", "speed": 1.0, "format": "ogg"}, 422, "INVALID_FORMAT"),
    ]
    val_results = {}
    all_val_pass = True
    for name, payload, expected_status, expected_code in val_cases:
        status, _, body = http_post("/api/tts", payload)
        try:
            err_json = json.loads(body.decode("utf-8"))
            err_code = err_json.get("error", {}).get("code")
            has_traceback = "Traceback" in body.decode("utf-8")
        except Exception:
            err_code = None
            has_traceback = True
        case_pass = (status == expected_status and err_code == expected_code and not has_traceback)
        val_results[name] = {
            "status_code": status,
            "expected_status": expected_status,
            "error_code": err_code,
            "expected_code": expected_code,
            "has_traceback": has_traceback,
            "passed": case_pass,
        }
        if not case_pass:
            all_val_pass = False
            print(f"  FAIL: validation {name}: status={status}, code={err_code}")
        else:
            print(f"  PASS: validation {name} -> {expected_code}")

    results["input_validation"] = {
        "all_passed": all_val_pass,
        "cases": val_results,
    }

    # 10. Security Tests on Audio Endpoint
    print("[6] Running Audio Security Tests...")
    sec_cases = [
        ("nonexistent_uuid", "/api/audio/00000000-0000-0000-0000-000000000000.wav", 404, "ARTIFACT_NOT_FOUND"),
        ("path_traversal_relative", "/api/audio/../../secret.txt", 404, "ARTIFACT_NOT_FOUND"),
        ("path_traversal_parent_wav", "/api/audio/../reference.wav", 404, "ARTIFACT_NOT_FOUND"),
        ("absolute_windows_path", "/api/audio/C:/Windows/system32/calc.exe", 404, "ARTIFACT_NOT_FOUND"),
        ("unix_passwd", "/api/audio//etc/passwd", 404, "ARTIFACT_NOT_FOUND"),
        ("non_uuid_filename", "/api/audio/not-a-uuid.wav", 404, "ARTIFACT_NOT_FOUND"),
        ("exe_extension", "/api/audio/3b9b6972-2774-4c04-8bbd-fa078a76409a.exe", 404, "ARTIFACT_NOT_FOUND"),
    ]
    sec_results = {}
    all_sec_pass = True
    for name, path, expected_status, expected_code in sec_cases:
        status, _, body = http_get(path)
        try:
            err_json = json.loads(body.decode("utf-8"))
            err_code = err_json.get("error", {}).get("code")
            has_traceback = "Traceback" in body.decode("utf-8")
        except Exception:
            err_code = None
            has_traceback = True
        case_pass = (status == expected_status and (err_code == expected_code or status == 404) and not has_traceback)
        sec_results[name] = {
            "status_code": status,
            "expected_status": expected_status,
            "error_code": err_code,
            "has_traceback": has_traceback,
            "passed": case_pass,
        }
        if not case_pass:
            all_sec_pass = False
            print(f"  FAIL: security {name}: status={status}, code={err_code}")
        else:
            print(f"  PASS: security {name} -> status {status}")

    results["security"] = {
        "all_passed": all_sec_pass,
        "cases": sec_results,
    }

    # 11. Privacy Marker Test
    print("[7] Testing Request Privacy Marker...")
    privacy_marker = "CP03B3_PRIVACY_MARKER_92841"
    priv_payload = {
        "text": f"Xin chào {privacy_marker} bảo vệ thông tin khách hàng.",
        "language": "vi",
        "voice_id": "omnivoice_auto",
        "speed": 1.0,
        "format": "wav",
    }
    status, _, body = http_post("/api/tts", priv_payload)
    results["privacy_request"] = {
        "status_code": status,
        "marker": privacy_marker,
    }
    print(f"  Privacy request status: {status}")

    # Final overall automated status
    if all_val_pass and all_sec_pass and results["wav_1_metrics"]["valid"] and results["wav_2_metrics"]["valid"] and results["mp3_test"]["valid"]:
        results["status"] = "PASS_WITH_LISTENING_REQUIRED"
    else:
        results["status"] = "FAIL"

    out_file = REPORTS_DIR / "verification.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nVerification finished with status: {results['status']}")
    print(f"Saved evidence to: {out_file}")


if __name__ == "__main__":
    main()

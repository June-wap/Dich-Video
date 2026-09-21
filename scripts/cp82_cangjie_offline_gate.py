"""Direct CP8.2 Task 4B Chatterbox Chinese offline diagnostic gate.

Run this script with the staged runtime-chatterbox interpreter.  It imports
only the staged application tree, blocks socket connections defensively, and
writes evidence for the Cangjie compatibility path alongside the WAV output.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import wave
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
RUNTIME_APP = Path(sys.executable).resolve().parent / "app"
OUTPUT = PROJECT / ".runtime" / "cp82" / "gates" / "chatterbox-zh-portable-fixed.wav"
REPORT = PROJECT / ".runtime" / "cp82" / "gates" / "chatterbox-zh-portable-fixed-report.json"
REVISION = "5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18"
FILENAME = "Cangjie5_TC.json"
SHA256 = "7073fd9de919443ae88e0bd2449917a65fe54898a4413ed1edcc4b67f28bce8c"
SIZE = 1_920_163


def _deny_network(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
    raise AssertionError("NETWORK_ATTEMPT_BLOCKED_BY_CP82_GATE")


def main() -> int:
    report: dict[str, object] = {
        "parent_executable": str(Path(sys.executable).resolve()),
        "runtime_app": str(RUNTIME_APP),
        "network_used": False,
        "hf_token_used": bool(os.environ.get("HF_TOKEN")),
        "user_hf_cache_used": False,
    }
    original_connect = socket.socket.connect
    socket.socket.connect = _deny_network
    try:
        if not RUNTIME_APP.is_dir():
            raise RuntimeError(f"staged runtime app missing: {RUNTIME_APP}")
        sys.path.insert(0, str(RUNTIME_APP))
        from backend.services.chatterbox_adapter import ChatterboxAdapter
        from chatterbox.models.tokenizers.tokenizer import ChineseCangjieConverter

        original_loader = ChineseCangjieConverter._load_cangjie_mapping
        adapter = ChatterboxAdapter(device="cuda")
        adapter.load()
        restored = ChineseCangjieConverter._load_cangjie_mapping is original_loader
        converter = adapter._runtime.tokenizer.cangjie_converter
        mapping_count = len(converter.word2cj)
        mapping_loaded = mapping_count > 0 and bool(converter.word2cj.get("你"))
        cache = Path(os.environ["HF_HUB_CACHE"]).resolve()
        mapping_path = cache / "models--ResembleAI--chatterbox" / "snapshots" / REVISION / FILENAME
        mapping_resolved = mapping_path.resolve()
        digest = hashlib.sha256(mapping_resolved.read_bytes()).hexdigest()
        mapping_identity = (
            mapping_path.is_file()
            and mapping_resolved.stat().st_size == SIZE
            and digest == SHA256
        )
        result = adapter.synthesize(
            "你好，这是一个离线中文语音测试。",
            language="zh",
            output_path=OUTPUT,
            speed=1.0,
        )
        wav: dict[str, object] = {"exists": OUTPUT.is_file(), "size": OUTPUT.stat().st_size if OUTPUT.exists() else 0}
        if OUTPUT.is_file():
            with wave.open(str(OUTPUT), "rb") as source:
                frames = source.getnframes()
                rate = source.getframerate()
                wav.update({
                    "channels": source.getnchannels(),
                    "sample_rate": rate,
                    "frames": frames,
                    "duration": frames / rate if rate else 0,
                })
        wav_valid = bool(
            wav["exists"] and wav["size"] > 0 and wav.get("channels") == 1
            and wav.get("sample_rate") == 24000 and wav.get("frames", 0) > 0
            and wav.get("duration", 0) > 0
        )
        report.update({
            "cangjie_mapping_path": str(mapping_path),
            "cangjie_mapping_resolved_path": str(mapping_resolved),
            "cangjie_mapping_sha256": digest,
            "cangjie_mapping_identity_verified": mapping_identity,
            "cangjie_mapping_loaded": mapping_loaded,
            "cangjie_mapping_entry_count": mapping_count,
            "chinese_tokenizer_degraded": not mapping_loaded,
            "upstream_loader_restored": restored,
            "result_status": result.status,
            "result_error": result.error,
            "device": result.device,
            "model": result.model,
            "checkpoint": result.metadata.get("t3_checkpoint"),
            "wav": wav,
            "wav_valid": wav_valid,
        })
        required = (
            result.status == "PASS" and mapping_identity and mapping_loaded and restored
            and wav_valid and result.device == "cuda"
            and result.model == "ChatterboxMultilingual-v3"
            and result.metadata.get("t3_checkpoint") == "t3_mtl23ls_v3.safetensors"
        )
        report["gate_pass"] = required
        if not required:
            raise RuntimeError("CP82_CANGJIE_GATE_ASSERTION_FAILED")
        return 0
    except Exception as exc:
        report.update({"gate_pass": False, "error": repr(exc)})
        raise
    finally:
        socket.socket.connect = original_connect
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())

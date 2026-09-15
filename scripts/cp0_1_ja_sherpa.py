"""CP0.1 — Japanese TTS via Sherpa-ONNX using Piper ONNX model."""
import hashlib, json, os, socket, sys, time, wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def deny_network():
    _real = socket.socket.__init__
    def _guard(self, *a, **kw):
        raise OSError("Network blocked by CP0.1 guard")
    socket.socket.__init__ = _guard

def inspect_wav(path):
    with wave.open(str(path), 'rb') as w:
        frames = w.getnframes()
        rate = w.getframerate()
        channels = w.getnchannels()
        width = w.getsampwidth()
        duration = frames / rate
    return {"frames": frames, "rate": rate, "channels": channels,
            "sample_width": width, "duration_s": duration,
            "size_bytes": path.stat().st_size}

def main():
    deny_network()
    import sherpa_onnx, importlib.metadata

    model_dir = ROOT / '.cp0/models/piper/ja_JA-hi_fi_captain-medium'
    espeak_data = ROOT / '.cp0/models/sherpa/vits-piper-vi_VN-vais1000-medium/espeak-ng-data'
    output_dir = ROOT / '.cp0/audio/ja_JA-hi_fi_captain-medium-sherpa'
    # Use patched model with Sherpa-required metadata
    patched_model = model_dir / 'ja_JA-hi_fi_captain-medium_sherpa.onnx'
    if patched_model.exists():
        model_path_override = patched_model
    else:
        model_path_override = None
    output_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "task": "cp0_1_japanese_tts",
        "provider": "sherpa-onnx",
        "runtime_version": importlib.metadata.version("sherpa-onnx"),
        "model_id": "ja_JA-hi_fi_captain-medium",
        "model_source": "rhasspy/piper-voices",
        "device": "cpu",
        "network_guard": True,
        "runs": [],
        "errors": [],
    }

    # Hash model file
    model_path = model_path_override or (model_dir / "ja_JA-hi_fi_captain-medium.onnx")
    report["model_sha256"] = hashlib.sha256(model_path.read_bytes()).hexdigest()
    report["model_size_bytes"] = model_path.stat().st_size

    # Build tokens from model config
    config_path = model_dir / "ja_JA-hi_fi_captain-medium.onnx.json"
    with open(config_path) as f:
        model_config = json.load(f)

    # Try Sherpa with espeak-ng phonemizer
    # The model uses phoneme_type "japanese" but espeak voice "ja"
    # Sherpa may handle this via espeak-ng-data/ja_dict
    tokens_path = ROOT / '.cp0/models/sherpa/vits-piper-vi_VN-vais1000-medium/tokens.txt'

    # We need a tokens.txt for this model — generate from phoneme_id_map
    ja_tokens = output_dir / "tokens.txt"
    pmap = model_config["phoneme_id_map"]
    max_id = max(max(v) for v in pmap.values())
    token_list = [""] * (max_id + 1)
    for sym, ids in pmap.items():
        for i in ids:
            token_list[i] = sym
    with open(ja_tokens, "w", encoding="utf-8") as f:
        for idx, tok in enumerate(token_list):
            f.write(f"{tok} {idx}\n")

    report["tokens_generated"] = True
    report["num_tokens"] = len(token_list)

    try:
        config = sherpa_onnx.OfflineTtsConfig(
            model=sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(model_path),
                    tokens=str(ja_tokens),
                    data_dir=str(espeak_data),
                ),
                num_threads=4,
                provider="cpu",
                debug=False,
            )
        )
        if not config.validate():
            report["errors"].append("Sherpa config validation failed")
            report["status"] = "FAILED"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            sys.exit(1)

        begin = time.perf_counter()
        tts = sherpa_onnx.OfflineTts(config)
        report["model_load_s"] = round(time.perf_counter() - begin, 3)

        test_texts = [
            ("short", "こんにちは、これはテストです。"),
            ("medium", "日本語のテキスト読み上げシステムのテストを行っています。品質を確認してください。"),
            ("long", "人工知能による音声合成技術は、近年急速に進歩しています。このシステムは、ローカルで動作するオフラインの音声合成エンジンです。"),
        ]

        for name, text in test_texts:
            begin = time.perf_counter()
            audio = tts.generate(text, sid=0, speed=1.0)
            gen_s = time.perf_counter() - begin

            if audio.sample_rate == 0 or len(audio.samples) == 0:
                report["errors"].append(f"{name}: empty audio")
                continue

            wav_path = output_dir / f"{name}.wav"
            import numpy as np
            samples = np.array(audio.samples, dtype=np.float32)
            pcm16 = (samples * 32767).astype(np.int16)

            with wave.open(str(wav_path), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(audio.sample_rate)
                w.writeframes(pcm16.tobytes())

            info = inspect_wav(wav_path)
            sha = hashlib.sha256(wav_path.read_bytes()).hexdigest()
            rms = float(np.sqrt(np.mean(samples ** 2)))
            rtf = gen_s / info["duration_s"] if info["duration_s"] > 0 else None

            run = {
                "name": name,
                "text": text,
                "generation_s": round(gen_s, 3),
                "duration_s": round(info["duration_s"], 3),
                "rtf": round(rtf, 4) if rtf else None,
                "sample_rate": audio.sample_rate,
                "rms": round(rms, 4),
                "sha256": sha,
                "path": str(wav_path.relative_to(ROOT)),
            }
            report["runs"].append(run)

        report["status"] = "PASS" if len(report["runs"]) > 0 else "FAILED"

    except Exception as e:
        report["errors"].append(str(e))
        report["status"] = "FAILED"

    print(json.dumps(report, indent=2, ensure_ascii=False))

    # Save evidence
    evidence_path = ROOT / "reports/evidence/cp0_1/ja_sherpa_benchmark.json"
    with open(evidence_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    sys.exit(0 if report["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()

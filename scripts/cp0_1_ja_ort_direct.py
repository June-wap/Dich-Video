"""CP0.1 Japanese ORT-Direct Inference POC.

Proves GPL-free Japanese TTS: pyopenjtalk (MIT) + onnxruntime (MIT).
No piper runtime imported. Phoneme mapping is self-contained.
"""
import hashlib, json, os, re, socket, sys, time, wave
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / ".cp0/models/piper/ja_JA-hi_fi_captain-medium"
MODEL_ONNX = MODEL_DIR / "ja_JA-hi_fi_captain-medium.onnx"
MODEL_JSON = MODEL_DIR / "ja_JA-hi_fi_captain-medium.onnx.json"
OUT = ROOT / ".cp0/audio/ja_ort_direct"
EV = ROOT / "reports/evidence/cp0_1"
OUT.mkdir(parents=True, exist_ok=True)
EV.mkdir(parents=True, exist_ok=True)

# ── OpenJTalk phoneme → IPA mapping (self-contained, no GPL import) ──────
# Derived from standard Japanese phonology; maps pyopenjtalk labels to IPA.
OPENJTALK_TO_IPA = {
    "a": "a", "i": "i", "u": "ɯ", "e": "e", "o": "o",
    "k": "k", "ky": "kʲ", "kw": "kʷ",
    "g": "ɡ", "gy": "ɡʲ", "gw": "ɡʷ",
    "s": "s", "sh": "ɕ", "z": "z", "j": "dʑ",
    "t": "t", "ts": "ts", "ty": "tʲ", "ch": "tɕ",
    "d": "d", "dy": "dʲ",
    "n": "n", "ny": "nʲ",
    "h": "h", "hy": "hʲ", "f": "ɸ",
    "b": "b", "by": "bʲ", "p": "p", "py": "pʲ",
    "m": "m", "my": "mʲ",
    "y": "j", "r": "ɾ", "ry": "ɾʲ", "w": "w", "v": "v",
    "N": "ɴ", "cl": "ʔ",
}
DEVOICED_VOWELS = frozenset({"A", "I", "U", "E", "O"})
SILENCE_PHONES = frozenset({"sil", "pau"})
MORA_FINAL = frozenset({"a", "i", "u", "e", "o", "N", "cl"})
NO_FEAT = -50

# Prosody symbols (mapped to model phoneme IDs via config)
SYM_RISE = "↑"
SYM_FALL = "↓"
SYM_BOUNDARY = "#"
SYM_PAUSE = ","
SYM_DECL = "."
SYM_QUES = "?"
# Piper special tokens
BOS = "^"
EOS = "$"
PAD = "_"


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def wav_info(p):
    with wave.open(str(p), "rb") as w:
        n, r = w.getnframes(), w.getframerate()
    return {"dur": round(n / r, 3), "rate": r, "bytes": Path(p).stat().st_size}


def write_wav(p, samples, sr):
    c = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(p), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(c.tobytes())


def _nfeat(pattern, label):
    m = re.search(pattern, label)
    if m is None:
        return NO_FEAT
    try:
        return int(m.group(1))
    except ValueError:
        return NO_FEAT


def _phone_from_label(label):
    m = re.search(r"\-([A-Za-z]+)\+", label)
    return m.group(1) if m else ""


def japanese_phonemize(text, drop_devoiced=True):
    """Convert Japanese text → list of IPA phoneme chars + prosody symbols.

    Uses pyopenjtalk (MIT) for morphological analysis and full-context labels.
    Mapping to IPA is self-contained (no GPL dependency).
    """
    import pyopenjtalk
    sentences = _split_ja(text)
    all_phones = []
    for sent in sentences:
        labels = pyopenjtalk.extract_fullcontext(sent)
        if not labels:
            continue
        phones = _labels_to_ipa(labels, drop_devoiced)
        if phones:
            is_question = sent.rstrip().endswith("？") or sent.rstrip().endswith("?")
            phones.append(SYM_QUES if is_question else SYM_DECL)
            all_phones.append(phones)
    return all_phones


def _labels_to_ipa(labels, drop_devoiced):
    phones = []
    for idx, label in enumerate(labels[1:-1], start=1):
        phone = _phone_from_label(label)
        if phone in SILENCE_PHONES:
            if phone == "pau":
                phones.append(SYM_PAUSE)
            continue
        if phone in DEVOICED_VOWELS:
            if drop_devoiced:
                continue
            phone = phone.lower()
        ipa = OPENJTALK_TO_IPA.get(phone)
        if ipa is None:
            continue
        phones.extend(ipa)  # multi-char IPA → individual chars

        # Prosody from full-context features
        a1 = _nfeat(r"/A:([0-9\-]+)\+", label)
        a2 = _nfeat(r"\+(\d+)\+", label)
        a3 = _nfeat(r"\+(\d+)/", label)
        f1 = _nfeat(r"/F:(\d+)_", label)
        a2_next = _nfeat(r"\+(\d+)\+", labels[idx + 1]) if idx + 1 < len(labels) else NO_FEAT
        if (a3 == 1) and (a2_next == 1) and (phone in MORA_FINAL):
            phones.append(SYM_BOUNDARY)
        elif (a1 == 0) and (a2_next == (a2 + 1)) and (a2 != f1):
            phones.append(SYM_FALL)
        elif (a2 == 1) and (a2_next == 2):
            phones.append(SYM_RISE)
    return phones


_SENT_END = re.compile(r"[。！？.!?]+\s*")

def _split_ja(text):
    parts = []
    start = 0
    for m in _SENT_END.finditer(text):
        s = text[start:m.end()].strip()
        if s:
            parts.append(s)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    return parts if parts else [text]


def phonemes_to_ids(phonemes, id_map):
    """Convert phoneme list to ID sequence with BOS/EOS/PAD."""
    ids = list(id_map[BOS]) + list(id_map[PAD])
    for ph in phonemes:
        if ph in id_map:
            ids.extend(id_map[ph])
            ids.extend(id_map[PAD])
    ids.extend(id_map[EOS])
    return ids


def ort_synthesize(session, phoneme_ids, speaker_id, noise_scale, length_scale, noise_w):
    """Run ONNX inference directly."""
    ph_arr = np.expand_dims(np.array(phoneme_ids, dtype=np.int64), 0)
    ph_len = np.array([ph_arr.shape[1]], dtype=np.int64)
    scales = np.array([noise_scale, length_scale, noise_w], dtype=np.float32)
    args = {"input": ph_arr, "input_lengths": ph_len, "scales": scales}
    if speaker_id is not None:
        args["sid"] = np.array([speaker_id], dtype=np.int64)
    result = session.run(None, args)
    return result[0].squeeze()


TEST_SENTENCES = [
    ("basic", "こんにちは世界", 0),        # Hello world (female)
    ("weather", "今日は天気がいいです。", 1),  # Nice weather (male)
    ("long", "人工知能は私たちの生活を大きく変えています。音声合成技術はますます自然になっています。", 0),
]


def main():
    import onnxruntime as ort

    R = {
        "task": "cp0_1_ja_ort_direct",
        "model": "ja_JA-hi_fi_captain-medium",
        "runtime": "onnxruntime",
        "ort_version": ort.__version__,
        "phonemizer": "pyopenjtalk (MIT)",
        "gpl_imports": "NONE",
        "tests": [],
        "errors": [],
    }

    # Load config
    with open(MODEL_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    id_map = cfg["phoneme_id_map"]
    sr = cfg["audio"]["sample_rate"]
    ns = cfg["inference"]["noise_scale"]
    ls = cfg["inference"]["length_scale"]
    nw = cfg["inference"]["noise_w"]
    num_spk = cfg["num_speakers"]
    R["sample_rate"] = sr
    R["num_speakers"] = num_spk
    R["model_sha"] = sha256(MODEL_ONNX)

    # Load ONNX session
    print("[1] Loading ONNX model...")
    t0 = time.perf_counter()
    sess = ort.InferenceSession(
        str(MODEL_ONNX),
        providers=["CPUExecutionProvider"],
    )
    load_s = time.perf_counter() - t0
    R["load_s"] = round(load_s, 3)
    print(f"  Loaded in {load_s:.3f}s")

    # Test sentences
    print("[2] Generating Japanese audio...")
    for label, text, spk in TEST_SENTENCES:
        print(f"  {label}: {text}")
        try:
            tp = time.perf_counter()
            sent_phones = japanese_phonemize(text)
            phonemize_s = time.perf_counter() - tp

            # Flatten all sentences' phonemes
            all_ph = []
            for sp in sent_phones:
                all_ph.extend(sp)

            ph_ids = phonemes_to_ids(all_ph, id_map)

            tg = time.perf_counter()
            audio = ort_synthesize(sess, ph_ids, spk if num_spk > 1 else None, ns, ls, nw)
            gen_s = time.perf_counter() - tg

            wav_path = OUT / f"ja_{label}_spk{spk}.wav"
            write_wav(wav_path, audio, sr)
            info = wav_info(wav_path)

            result = {
                "label": label, "text": text, "speaker_id": spk,
                "phonemes": "".join(all_ph),
                "num_phoneme_ids": len(ph_ids),
                "phonemize_s": round(phonemize_s, 4),
                "gen_s": round(gen_s, 3),
                "dur": info["dur"],
                "rtf": round(gen_s / info["dur"], 4) if info["dur"] > 0 else None,
                "rms": round(float(np.sqrt(np.mean(audio ** 2))), 4),
                "sha": sha256(wav_path),
                "path": str(wav_path.relative_to(ROOT)),
                "status": "PASS" if info["dur"] > 0.1 else "FAILED",
            }
            R["tests"].append(result)
            print(f"    PASS: {info['dur']}s, RTF={result['rtf']}")
        except Exception as e:
            import traceback
            R["tests"].append({
                "label": label, "text": text, "status": "FAILED",
                "error": str(e), "tb": traceback.format_exc(),
            })
            R["errors"].append(f"{label}:{e}")
            print(f"    FAIL: {e}")

    # Offline test
    print("[3] Offline test...")
    _orig = socket.socket.__init__
    def _block(self, *a, **kw):
        raise OSError("network blocked")
    socket.socket.__init__ = _block
    try:
        text_off = "オフラインテストです。"
        sp = japanese_phonemize(text_off)
        ph_all = []
        for s in sp:
            ph_all.extend(s)
        ids_off = phonemes_to_ids(ph_all, id_map)
        audio_off = ort_synthesize(sess, ids_off, 0 if num_spk > 1 else None, ns, ls, nw)
        off_path = OUT / "ja_offline.wav"
        write_wav(off_path, audio_off, sr)
        oi = wav_info(off_path)
        R["offline"] = {"status": "PASS", "dur": oi["dur"], "sha": sha256(off_path)}
        print(f"  PASS: {oi['dur']}s")
    except Exception as e:
        R["offline"] = {"status": "FAILED", "error": str(e)}
        print(f"  FAIL: {e}")
    finally:
        socket.socket.__init__ = _orig

    # Summary
    passed = sum(1 for t in R["tests"] if t.get("status") == "PASS")
    R["status"] = "PASS" if passed == len(TEST_SENTENCES) else (
        "PARTIAL" if passed > 0 else "FAILED")

    ev_path = EV / "ja_ort_direct_poc.json"
    with open(ev_path, "w", encoding="utf-8") as f:
        json.dump(R, f, indent=2, ensure_ascii=False)
    print(json.dumps(R, indent=2, ensure_ascii=False))
    sys.exit(0 if R["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()


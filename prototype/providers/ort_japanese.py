from __future__ import annotations
import json, logging, re, time
from pathlib import Path
import numpy as np
from .base import TTSProvider, VoiceInfo, SynthResult

logger = logging.getLogger("prototype")

OPENJTALK_TO_IPA = {
    "a": "a", "i": "i", "u": "\u026f", "e": "e", "o": "o",
    "k": "k", "ky": "k\u02b2", "kw": "k\u02b7", "g": "\u0261", "gy": "\u0261\u02b2",
    "gw": "\u0261\u02b7", "s": "s", "sh": "\u0255", "z": "z", "j": "d\u0291",
    "t": "t", "ts": "ts", "ty": "t\u02b2", "ch": "t\u0255",
    "d": "d", "dy": "d\u02b2", "n": "n", "ny": "n\u02b2",
    "h": "h", "hy": "h\u02b2", "f": "\u0278",
    "b": "b", "by": "b\u02b2", "p": "p", "py": "p\u02b2",
    "m": "m", "my": "m\u02b2", "y": "j", "r": "\u027e", "ry": "\u027e\u02b2",
    "w": "w", "v": "v", "N": "\u0274", "cl": "\u0294",
}
SILENCE_PHONES = frozenset({"sil", "pau"})
DEVOICED_VOWELS = frozenset({"A", "I", "U", "E", "O"})
NO_FEAT = -50
SYM_RISE = "\u2191"; SYM_FALL = "\u2193"; SYM_BOUNDARY = "#"
SYM_PAUSE = ","; SYM_DECL = "."; SYM_QUES = "?"
BOS = "^"; EOS = "$"; PAD = "_"

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

def _split_ja(text):
    parts = re.split(r"(?<=[\u3002\uff01\uff1f\n])", text)
    return [p for p in parts if p.strip()]
MORA_FINAL = frozenset({"a", "i", "u", "e", "o", "N", "cl"})

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


def _ort_synthesize(sess, ph_ids, speaker_id, ns, ls, nw):
    x = np.array([ph_ids], dtype=np.int64)
    x_len = np.array([len(ph_ids)], dtype=np.int64)
    scales = np.array([ns, ls, nw], dtype=np.float32)
    feed = {"input": x, "input_lengths": x_len, "scales": scales}
    if speaker_id is not None:
        feed["sid"] = np.array([speaker_id], dtype=np.int64)
    audio = sess.run(None, feed)[0].squeeze()
    return audio.astype(np.float32)

class ORTJapaneseProvider(TTSProvider):
    def __init__(self, model_dir):
        self._model_dir = Path(model_dir)
        self._onnx = self._model_dir / "ja_JA-hi_fi_captain-medium.onnx"
        self._json = self._model_dir / "ja_JA-hi_fi_captain-medium.onnx.json"
        self._sess = None
        self._config = None
        self._id_map = None
        self._available = self._onnx.exists() and self._json.exists()
        if self._available:
            with open(self._json, "r", encoding="utf-8") as f:
                self._config = json.load(f)
            self._id_map = self._config.get("phoneme_id_map", {})

    def _get_session(self):
        if self._sess is not None:
            return self._sess
        import onnxruntime as ort
        t0 = time.perf_counter()
        self._sess = ort.InferenceSession(str(self._onnx), providers=["CPUExecutionProvider"])
        logger.info("JA ORT session loaded in %.2fs", time.perf_counter() - t0)
        return self._sess

    def provider_name(self):
        return "ORT-Direct Japanese (GPL-free)"

    def list_languages(self):
        return ["ja"] if self._available else []

    def list_voices(self, language):
        if language != "ja" or not self._available:
            return []
        spk_map = self._config.get("speaker_id_map", {})
        voices = []
        for name, sid in spk_map.items():
            voices.append(VoiceInfo(
                id=f"ja_{name}", name=f"JA {name.title()}", language="ja",
                gender=name, provider=self.provider_name(),
                model="ja_JA-hi_fi_captain-medium",
                sample_rate=self._config["audio"]["sample_rate"]))
        return voices
    def synthesize(self, text, language, voice, output_path, speed=1.0, **options):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = SynthResult(
            provider=self.provider_name(), model="ja_JA-hi_fi_captain-medium",
            language="ja", voice=voice, device="cpu")
        if not self._available:
            result.status = "FAIL"
            result.error = "MODEL_NOT_FOUND: JA model missing"
            return result
        if not text or not text.strip():
            result.status = "FAIL"
            result.error = "INVALID_TEXT: empty text"
            return result
        try:
            started = time.perf_counter()
            sess = self._get_session()
            result.load_time = time.perf_counter() - started
            cfg = self._config["inference"]
            ns, ls, nw = cfg["noise_scale"], cfg["length_scale"], cfg["noise_w"]
            ls = ls / speed if speed > 0 else ls
            spk_map = self._config.get("speaker_id_map", {})
            num_spk = self._config.get("num_speakers", 1)
            sid = options.get("speaker_id", 0)
            for name, _sid in spk_map.items():
                if voice and name in voice:
                    sid = _sid
                    break
            t0 = time.perf_counter()
            sent_phones = japanese_phonemize(text)
            all_ph = []
            for sp in sent_phones:
                all_ph.extend(sp)
            ph_ids = phonemes_to_ids(all_ph, self._id_map)
            audio = _ort_synthesize(sess, ph_ids, sid if num_spk > 1 else None, ns, ls, nw)
            gen_time = time.perf_counter() - t0
            sr = self._config["audio"]["sample_rate"]
            from core.audio_utils import write_wav
            write_wav(output_path, audio, sr)
            duration = len(audio) / sr
            result.wav_path = str(output_path)
            result.sample_rate = sr
            result.duration = round(duration, 3)
            result.gen_time = round(gen_time, 3)
            result.rtf = round(gen_time / duration, 4) if duration > 0 else 0
            result.status = "PASS"
        except Exception as e:
            result.status = "FAIL"
            result.error = f"GENERATION_FAILED: {e}"
            logger.exception("JA synthesis failed")
        return result

    def health_check(self):
        return {
            "provider": self.provider_name(),
            "model_path": str(self._onnx),
            "available": self._available,
            "status": "OK" if self._available else "MODEL_NOT_FOUND",
        }
from __future__ import annotations
import json, logging, time
from pathlib import Path
import numpy as np
from .base import TTSProvider, VoiceInfo, SynthResult

logger = logging.getLogger("prototype")

PIPER_MODELS = {
    "vi": "vi_VN-vais1000-medium", "en": "en_US-lessac-medium",
    "zh": "zh_CN-huayan-medium", "es": "es_ES-davefx-medium",
    "pt": "pt_BR-faber-medium", "it": "it_IT-riccardo-x_low",
    "fr": "fr_FR-siwis-medium", "hi": "hi_IN-pratham-medium",
}
VOICE_NAMES = {
    "vi": [("vi_vais1000", "VAIS1000 Female", "female")],
    "en": [("en_lessac", "Lessac", "neutral")],
    "zh": [("zh_huayan", "Huayan Female", "female")],
    "es": [("es_davefx", "DaveFX Male", "male")],
    "pt": [("pt_faber", "Faber Male", "male")],
    "it": [("it_riccardo", "Riccardo Male", "male")],
    "fr": [("fr_siwis", "Siwis Female", "female")],
    "hi": [("hi_pratham", "Pratham Male", "male")],
}

def _ensure_tokens_txt(model_dir, json_path):
    tokens_path = model_dir / "tokens.txt"
    if tokens_path.exists():
        return tokens_path
    with open(json_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    id_map = config.get("phoneme_id_map", {})
    if not id_map:
        raise ValueError(f"No phoneme_id_map in {json_path}")
    pairs = []
    for token, ids in id_map.items():
        for tid in ids:
            pairs.append((tid, token))
    pairs.sort(key=lambda x: x[0])
    with open(tokens_path, "w", encoding="utf-8") as f:
        for tid, token in pairs:
            f.write(f"{token} {tid}\n")
    logger.info("Generated tokens.txt for %s (%d tokens)", model_dir.name, len(pairs))
    return tokens_path
class SherpaPiperProvider(TTSProvider):
    def __init__(self, models_root, espeak_data_dir, num_threads=4):
        self._models_root = Path(models_root)
        self._espeak_data = Path(espeak_data_dir)
        self._engines = {}
        self._configs = {}
        self._available_languages = []
        self._num_threads = num_threads
        for lang, model_name in PIPER_MODELS.items():
            model_dir = self._models_root / model_name
            onnx_path = model_dir / f"{model_name}.onnx"
            json_path = model_dir / f"{model_name}.onnx.json"
            if onnx_path.exists() and json_path.exists():
                self._available_languages.append(lang)
                with open(json_path, "r", encoding="utf-8") as fh:
                    self._configs[lang] = json.load(fh)
        logger.info("SherpaPiper: %d languages: %s", len(self._available_languages), self._available_languages)

    def _get_engine(self, lang):
        if lang in self._engines:
            return self._engines[lang]
        import sherpa_onnx
        model_name = PIPER_MODELS[lang]
        model_dir = self._models_root / model_name
        onnx_path = model_dir / f"{model_name}.onnx"
        json_path = model_dir / f"{model_name}.onnx.json"
        # Adapt a local copy: raw Piper models lack mandatory Sherpa metadata.
        import onnx
        cfg = self._configs[lang]
        cache = self._models_root.parents[2] / "prototype" / "models" / model_name
        cache.mkdir(parents=True, exist_ok=True)
        adapted = cache / onnx_path.name
        if not adapted.exists():
            model = onnx.load(str(onnx_path))
            metadata = {p.key: p.value for p in model.metadata_props}
            metadata.update(model_type="vits", comment="piper", language=lang,
                            has_espeak="1", voice=cfg["espeak"]["voice"],
                            n_speakers=str(cfg.get("num_speakers", 1)),
                            sample_rate=str(cfg["audio"]["sample_rate"]))
            onnx.helper.set_model_props(model, metadata)
            onnx.save(model, str(adapted))
        onnx_path = adapted
        tokens_path = _ensure_tokens_txt(cache, json_path)
        vits_config = sherpa_onnx.OfflineTtsVitsModelConfig(
            model=str(onnx_path), tokens=str(tokens_path), data_dir=str(self._espeak_data))
        model_config = sherpa_onnx.OfflineTtsModelConfig(
            vits=vits_config, num_threads=self._num_threads, provider="cpu")
        tts_config = sherpa_onnx.OfflineTtsConfig(model=model_config)
        t0 = time.perf_counter()
        engine = sherpa_onnx.OfflineTts(tts_config)
        load_time = time.perf_counter() - t0
        self._engines[lang] = engine
        logger.info("Loaded Sherpa for %s in %.2fs (sr=%d)", lang, load_time, engine.sample_rate)
        return engine

    def provider_name(self):
        return "Sherpa-ONNX + Piper VITS"

    def list_languages(self):
        return list(self._available_languages)

    def list_voices(self, language):
        if language not in self._available_languages:
            return []
        voices = []
        for vid, vname, gender in VOICE_NAMES.get(language, []):
            cfg = self._configs.get(language, {})
            sr = cfg.get("audio", {}).get("sample_rate", 22050)
            voices.append(VoiceInfo(
                id=vid, name=vname, language=language, gender=gender,
                provider=self.provider_name(), model=PIPER_MODELS.get(language, ""), sample_rate=sr))
        return voices
    def synthesize(self, text, language, voice, output_path, speed=1.0, **options):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = SynthResult(
            provider=self.provider_name(), model=PIPER_MODELS.get(language, ""),
            language=language, voice=voice, device="cpu")
        if language not in self._available_languages:
            result.status = "FAIL"
            result.error = f"LANGUAGE_NOT_SUPPORTED: {language}"
            return result
        if not text or not text.strip():
            result.status = "FAIL"
            result.error = "INVALID_TEXT: empty text"
            return result
        try:
            started = time.perf_counter()
            engine = self._get_engine(language)
            result.load_time = time.perf_counter() - started
            sid = options.get("speaker_id", 0)
            t0 = time.perf_counter()
            audio = engine.generate(text, sid=sid, speed=speed)
            gen_time = time.perf_counter() - t0
            if audio.samples is None or len(audio.samples) == 0:
                result.status = "FAIL"
                result.error = "GENERATION_FAILED: empty audio"
                return result
            samples = np.array(audio.samples, dtype=np.float32)
            from core.audio_utils import write_wav
            write_wav(output_path, samples, audio.sample_rate)
            duration = len(audio.samples) / audio.sample_rate
            result.wav_path = str(output_path)
            result.sample_rate = audio.sample_rate
            result.duration = round(duration, 3)
            result.gen_time = round(gen_time, 3)
            result.rtf = round(gen_time / duration, 4) if duration > 0 else 0
            result.status = "PASS"
        except Exception as e:
            result.status = "FAIL"
            result.error = f"GENERATION_FAILED: {e}"
            logger.exception("Synthesis failed for %s/%s", language, voice)
        return result

    def health_check(self):
        return {
            "provider": self.provider_name(),
            "available_languages": self._available_languages,
            "models_root": str(self._models_root),
            "loaded_engines": list(self._engines.keys()),
            "status": "OK" if self._available_languages else "NO_MODELS",
        }
from __future__ import annotations
import logging, time
from pathlib import Path
import numpy as np
from .base import CloningProvider, VoiceInfo, SynthResult

logger = logging.getLogger("prototype")


class VieNeuCloneProvider(CloningProvider):
    def __init__(self):
        self._engine = None
        self._available = False
        self._sr = 48000
        try:
            from vieneu import Vieneu
            self._vieneu_cls = Vieneu
            self._available = True
        except ImportError:
            logger.warning("vieneu package not installed")

    def _get_engine(self):
        if self._engine is not None:
            return self._engine
        t0 = time.perf_counter()
        self._engine = self._vieneu_cls(mode="v3turbo")
        self._sr = self._engine.sample_rate
        logger.info("VieNeu loaded in %.2fs (sr=%d)", time.perf_counter() - t0, self._sr)
        return self._engine

    def provider_name(self):
        return "VieNeu v3 Turbo (Clone)"

    def list_languages(self):
        return ["vi"] if self._available else []

    def list_voices(self, language):
        if language != "vi" or not self._available:
            return []
        return [VoiceInfo(id="vieneu:" + name, name=name, language="vi",
                          gender=gender, provider=self.provider_name(),
                          model="VieNeu-TTS-v3-Turbo", sample_rate=self._sr)
                for name, gender in [("Minh Đức", "male"), ("Trúc Ly", "female")]]

    def synthesize(self, text, language, voice, output_path, speed=1.0, **options):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = SynthResult(
            provider=self.provider_name(), model="VieNeu-TTS-v3-Turbo",
            language=language, voice=voice, device="cpu")
        if not self._available:
            result.status = "FAIL"
            result.error = "MODEL_NOT_FOUND: vieneu not installed"
            return result
        try:
            started = time.perf_counter()
            eng = self._get_engine()
            if isinstance(result, SynthResult):
                result.load_time = time.perf_counter() - started
            t0 = time.perf_counter()
            wav = eng.infer(text=text, voice=voice.removeprefix("vieneu:"))
            gen_time = time.perf_counter() - t0
            from core.audio_utils import write_wav
            write_wav(output_path, wav, self._sr)
            duration = len(wav) / self._sr
            result.wav_path = str(output_path)
            result.sample_rate = self._sr
            result.duration = round(duration, 3)
            result.gen_time = round(gen_time, 3)
            result.rtf = round(gen_time / duration, 4) if duration > 0 else 0
            result.status = "PASS"
        except Exception as e:
            result.status = "FAIL"
            result.error = f"GENERATION_FAILED: {e}"
            logger.exception("VieNeu preset synthesis failed")
        return result
    def prepare_voice_profile(self, reference_audio, voice_name="clone"):
        result = {"voice_name": voice_name, "reference": str(reference_audio)}
        if not self._available:
            result["error"] = "vieneu not installed"
            return result
        try:
            started = time.perf_counter()
            eng = self._get_engine()
            if isinstance(result, SynthResult):
                result.load_time = time.perf_counter() - started
            t0 = time.perf_counter()
            spk_emb, ref_codes = eng.encode_reference(str(reference_audio))
            prep_time = time.perf_counter() - t0
            result["conditioning"] = {"speaker_emb": spk_emb, "codes": ref_codes}
            result["prep_time"] = round(prep_time, 3)
            result["spk_shape"] = list(spk_emb.shape) if spk_emb is not None else None
            result["status"] = "OK"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "FAIL"
            logger.exception("Voice profile preparation failed")
        return result

    def synthesize_with_profile(self, text, reference_audio, language, output_path, **options):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result = SynthResult(
            provider=self.provider_name(), model="VieNeu-TTS-v3-Turbo",
            language=language, voice="clone", device="cpu")
        if not self._available:
            result.status = "FAIL"
            result.error = "MODEL_NOT_FOUND: vieneu not installed"
            return result
        ref_path = str(reference_audio)
        if not Path(ref_path).exists():
            result.status = "FAIL"
            result.error = f"INVALID_REFERENCE_AUDIO: {ref_path} not found"
            return result
        try:
            started = time.perf_counter()
            eng = self._get_engine()
            if isinstance(result, SynthResult):
                result.load_time = time.perf_counter() - started
            t0 = time.perf_counter()
            profile = options.get("profile")
            if profile is None:
                profile = self.prepare_voice_profile(reference_audio)
            if profile.get("error"):
                raise ValueError(profile["error"])
            result.preparation_time = profile.get("prep_time", 0)
            t0 = time.perf_counter()
            wav = eng.infer(text=text, voice=profile["conditioning"])
            gen_time = time.perf_counter() - t0
            from core.audio_utils import write_wav
            write_wav(output_path, wav, self._sr)
            duration = len(wav) / self._sr
            result.wav_path = str(output_path)
            result.sample_rate = self._sr
            result.duration = round(duration, 3)
            result.gen_time = round(gen_time, 3)
            result.rtf = round(gen_time / duration, 4) if duration > 0 else 0
            result.status = "PASS"
        except Exception as e:
            result.status = "FAIL"
            result.error = f"GENERATION_FAILED: {e}"
            logger.exception("Voice cloning synthesis failed")
        return result

    def health_check(self):
        return {
            "provider": self.provider_name(),
            "available": self._available,
            "sample_rate": self._sr,
            "status": "OK" if self._available else "NOT_INSTALLED",
        }
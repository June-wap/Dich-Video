"""Pinned official VieNeu adapter for the approved Vietnamese 0.5B model."""
from __future__ import annotations

import os
from pathlib import Path
from threading import RLock

import torch

from backend.services.provider_base import AudioSynthResult, VoiceInfo


class VieNeuAdapter:
    PROVIDER_ID = "vieneu"

    MODEL_REPOSITORY = "pnnbao-ump/VieNeu-TTS"
    MODEL_REVISION = "7cbfde99a613d07630f390cc623ecfb2a070d0c1"

    CODEC_REPOSITORY = "neuphonic/distill-neucodec"
    CODEC_REVISION = "6f2b93b3fa2bc74740ba1bd10622e1ee37dbbe46"

    SOURCE_REVISION = "b116f820dc9ed8fae70a5570389928ecad233175"

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._runtime = None
        self._lock = RLock()

    def provider_name(self):
        return self.PROVIDER_ID

    def is_loaded(self):
        return self._runtime is not None

    def list_languages(self):
        return ["vi"]

    def list_voices(self, language):
        if language != "vi":
            return []

        return [
            VoiceInfo(
                id="vieneu_default",
                name="VieNeu Default",
                language="vi",
                provider=self.PROVIDER_ID,
                sample_rate=24000,
            )
        ]

    def capabilities(self):
        return {
            "verified_languages": ["vi"],
            "language_metadata": [],
            "experimental_languages_enabled": False,
            "production_ready": False,
        }

    @staticmethod
    def _load_pinned_neucodec(codec_cls, repository: str, revision: str):
        """Load the approved codec without HubMixin's unrelated config probe.

        ``DistillNeuCodec.from_pretrained`` first runs the generic Hugging
        Face ``ModelHubMixin`` loader.  That loader probes ``config.json``,
        which is not an artifact in the approved Neucodec revision.  Call the
        codec's own loader directly instead: it is the official implementation
        that fetches exactly ``pytorch_model.bin`` and ``meta.yaml``.

        Application-controlled Hugging Face cache paths continue to work via
        the standard hub configuration.  In either supported offline mode,
        make the no-network requirement explicit for this codec request.
        """
        offline = any(
            os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}
            for name in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")
        )
        return codec_cls._from_pretrained(
            model_id=repository,
            revision=revision,
            local_files_only=offline,
        )

    @classmethod
    def _ensure_offline_model_store(cls) -> Path | None:
        """Auto-resolve offline HuggingFace model store if not explicitly set."""
        hf_home = os.environ.get("HF_HOME")
        if hf_home:
            home_path = Path(hf_home)
            if (home_path / "hub").is_dir() or (home_path / "models--pnnbao-ump--VieNeu-TTS").is_dir():
                return home_path

        candidates: list[Path] = []
        try:
            exe_parent = Path(sys.executable).resolve().parent
            candidates.extend([
                exe_parent.parent / "ai-packages" / "models" / "huggingface",
                exe_parent.parent / "models" / "huggingface",
                exe_parent / "models" / "huggingface",
                exe_parent.parent / "release" / "AI-Packages" / "models" / "huggingface",
            ])
        except Exception:
            pass

        try:
            repo_root = Path(__file__).resolve().parent.parent.parent
            candidates.extend([
                repo_root / "ai-packages" / "models" / "huggingface",
                repo_root / "models" / "huggingface",
                repo_root / "release" / "AI-Packages" / "models" / "huggingface",
            ])
        except Exception:
            pass

        for cand in candidates:
            if cand.is_dir():
                hub = cand / "hub"
                if hub.is_dir() or (cand / "models--pnnbao-ump--VieNeu-TTS").is_dir():
                    os.environ["HF_HOME"] = str(cand)
                    os.environ["HF_HUB_CACHE"] = str(hub if hub.is_dir() else cand)
                    return cand

        return None

    def load(self):
        with self._lock:
            if self._runtime is not None:
                return self

            self._ensure_offline_model_store()

            from vieneu.core import VieNeuTTS
            from transformers import AutoModelForCausalLM, AutoTokenizer
            from neucodec import DistillNeuCodec

            model_repo = self.MODEL_REPOSITORY
            model_revision = self.MODEL_REVISION
            codec_repo = self.CODEC_REPOSITORY
            codec_revision = self.CODEC_REVISION

            class PinnedVieNeu(VieNeuTTS):
                
                def _load_backbone(
                    runtime_self,
                    backbone_repo,
                    backbone_device,
                    hf_token=None,
                ):
                    if backbone_repo != model_repo:
                        raise RuntimeError(
                            f"Unexpected VieNeu backbone: {backbone_repo}"
                        )

                    print(
                        "Loading pinned VieNeu backbone "
                        f"{model_repo}@{model_revision} "
                        f"on {backbone_device} ..."
                    )

                    runtime_self.tokenizer = AutoTokenizer.from_pretrained(
                        model_repo,
                        revision=model_revision,
                        token=hf_token,
                    )

                    runtime_self.backbone = (
                        AutoModelForCausalLM.from_pretrained(
                            model_repo,
                            revision=model_revision,
                            token=hf_token,
                        )
                        .to(torch.device(backbone_device))
                    )

                    runtime_self._is_quantized_model = False

                def _load_codec(
                    runtime_self,
                    codec_repo_arg,
                    codec_device,
                ):
                    if codec_repo_arg != codec_repo:
                        raise RuntimeError(
                            f"Unexpected VieNeu codec: {codec_repo_arg}"
                        )

                    print(
                        "Loading pinned NeuCodec "
                        f"{codec_repo}@{codec_revision} "
                        f"on {codec_device} ..."
                    )

                    runtime_self.codec = VieNeuAdapter._load_pinned_neucodec(
                        DistillNeuCodec,
                        codec_repo,
                        codec_revision,
                    )
                    runtime_self.codec.eval().to(codec_device)
                    runtime_self._is_onnx_codec = False

                def _load_voices(
                    runtime_self,
                    backbone_repo,
                    hf_token=None,
                    clear_existing=False,
                ):
                    if backbone_repo != model_repo:
                        raise RuntimeError(
                            f"Unexpected VieNeu voices repository: {backbone_repo}"
                        )

                    from huggingface_hub import hf_hub_download

                    print(
                        "Loading pinned VieNeu voices "
                        f"{model_repo}@{model_revision} ..."
                    )

                    voices_file = hf_hub_download(
                        repo_id=model_repo,
                        filename="voices.json",
                        revision=model_revision,
                        token=hf_token,
                        repo_type="model",
                    )

                    runtime_self._load_voices_from_file(
                        Path(voices_file),
                        clear_existing=clear_existing,
                    )

            self._runtime = PinnedVieNeu(
                backbone_repo=model_repo,
                backbone_device=self.device,
                codec_repo=codec_repo,
                codec_device=self.device,
            )

        return self

    def unload(self):
        with self._lock:
            if self._runtime is not None:
                self._runtime.close()
                self._runtime = None

    def synthesize(
        self,
        text,
        language,
        voice="vieneu_default",
        output_path=None,
        speed=1.0,
        **options,
    ):
        if (
            language != "vi"
            or voice != "vieneu_default"
            or speed != 1.0
            or output_path is None
        ):
            return AudioSynthResult(
                status="FAIL",
                error="INVALID_REQUEST",
                provider=self.PROVIDER_ID,
                language=language,
            )

        try:
            self.load()

            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            self._runtime.save(
                self._runtime.infer(text),
                str(target),
            )

            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError("invalid audio output")

            return AudioSynthResult(
                status="PASS",
                wav_path=str(target),
                sample_rate=24000,
                provider=self.PROVIDER_ID,
                language="vi",
                voice=voice,
            )

        except Exception as exc:
            return AudioSynthResult(
                status="FAIL",
                error=str(exc),
                provider=self.PROVIDER_ID,
                language="vi",
                voice=voice,
            )

    # ------------------------------------------------------------------
    # CP3: Vietnamese voice cloning
    # ------------------------------------------------------------------
    #
    # The pinned source (.vendor-vieneu/vieneu/core.py) defines `clone_voice()`
    # only on `FastVieNeuTTS` (the LMDeploy-batched backend). The pinned CPU/
    # Transformers backbone this adapter actually loads is the base
    # `VieNeuTTS` class (see `load()` above: `PinnedVieNeu(VieNeuTTS)`), which
    # does NOT expose `clone_voice()`. It does expose the official
    # `encode_reference(path) -> codes` call that `FastVieNeuTTS.clone_voice`
    # itself is built from verbatim:
    #
    #     def clone_voice(self, audio_path, text):
    #         ref_codes = self.encode_reference(audio_path)
    #         return {"codes": ref_codes, "text": text}
    #
    # create_voice_profile() below reproduces that exact structure against
    # the same pinned model/codec revisions already validated in CP2, using
    # only the real, official API present on the pinned class. The resulting
    # dict is the opaque provider-owned "profile" that infer(voice=...) below
    # accepts directly - no mocking, no alternate source/model/codec.

    def create_voice_profile(self, reference_audio, transcript):
        """Build a real VieNeu voice-clone profile from reference audio + transcript.

        Returns an in-memory dict `{"codes": <torch.Tensor>, "text": <str>}`.
        Never pickled/serialized by callers (see
        backend/services/voice_profile_service.py - provider_profile is
        deliberately excluded from persistence and rebuilt via this same
        method after restart).
        """
        if not isinstance(transcript, str) or not transcript.strip():
            raise ValueError("VieNeu voice cloning requires a non-empty reference transcript")

        audio_path = Path(reference_audio)
        if not audio_path.is_file():
            raise ValueError(f"Reference audio not found: {audio_path}")

        self.load()

        ref_codes = self._runtime.encode_reference(str(audio_path))
        return {"codes": ref_codes, "text": transcript.strip()}

    def synthesize_cloned(
        self,
        text,
        language,
        profile,
        output_path=None,
        **options,
    ):
        """Synthesize `text` conditioned on a real cloned voice `profile`.

        CP3 is Vietnamese-only: `language` must already be normalized to
        "vi" by the caller (VoiceProfileService/TTSService); this is a
        defense-in-depth check, mirroring synthesize()'s own strict gate.
        `profile` must be the dict produced by create_voice_profile() above -
        never a default/built-in voice is substituted.
        """
        if (
            language != "vi"
            or output_path is None
            or not isinstance(profile, dict)
            or "codes" not in profile
            or "text" not in profile
        ):
            return AudioSynthResult(
                status="FAIL",
                error="INVALID_REQUEST",
                provider=self.PROVIDER_ID,
                language=language,
            )

        try:
            self.load()

            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)

            self._runtime.save(
                self._runtime.infer(text, voice=profile),
                str(target),
            )

            if not target.is_file() or target.stat().st_size == 0:
                raise RuntimeError("invalid audio output")

            return AudioSynthResult(
                status="PASS",
                wav_path=str(target),
                sample_rate=24000,
                provider=self.PROVIDER_ID,
                language="vi",
            )

        except Exception as exc:
            return AudioSynthResult(
                status="FAIL",
                error=str(exc),
                provider=self.PROVIDER_ID,
                language="vi",
            )

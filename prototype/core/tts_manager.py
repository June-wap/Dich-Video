"""TTS Manager: orchestrates providers and routes requests."""

from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from core.audio_utils import (
    BoundaryDSPConfig,
    export_mp3,
    merge_segments,
    select_pause_ms,
)
from core.languages import VERIFIED_LANGUAGE_IDS
from core.long_text import (
    ChunkStatus,
    ChunkingConfig,
    TextChunk,
    build_chunks,
)
from core.text_utils import TEST_SENTENCES
from providers.base import (
    CloningProvider,
    SynthResult,
    TTSProvider,
    VoiceInfo,
)

logger = logging.getLogger("prototype")

ProgressCallback = Callable[[dict[str, Any]], None]
CancelCallback = Callable[[], bool]


class TTSManager:
    """Central manager for all TTS providers."""

    def __init__(self, project_root: Path, *, output_dir: Path | None = None,
                 temp_dir: Path | None = None):
        self.root = Path(project_root)

        self.output_dir = (
            self.root
            / "prototype"
            / "outputs"
        )

        self.temp_dir = (
            self.root
            / "prototype"
            / "temp"
        )

        self.output_dir = Path(output_dir) if output_dir is not None else self.output_dir
        self.temp_dir = Path(temp_dir) if temp_dir is not None else self.temp_dir
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.temp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._providers: list[TTSProvider] = []

        # Legacy cloning provider path.
        self._clone_provider: (
            CloningProvider | None
        ) = None

        self._lang_provider_map: dict[
            str,
            TTSProvider,
        ] = {}

    # ============================================================
    # PROVIDER REGISTRATION
    # ============================================================

    def register_provider(
        self,
        provider: TTSProvider,
    ) -> None:
        """Register a TTS provider."""

        if provider in self._providers:
            return

        self._providers.append(provider)

        for language in provider.list_languages():
            if (
                language
                not in self._lang_provider_map
            ):
                self._lang_provider_map[
                    language
                ] = provider

        if isinstance(
            provider,
            CloningProvider,
        ):
            self._clone_provider = provider

    # ============================================================
    # LANGUAGE / VOICE DISCOVERY
    # ============================================================

    def get_languages(self) -> list[str]:
        """Return available languages in canonical order."""

        languages = list(
            self._lang_provider_map.keys()
        )

        order = VERIFIED_LANGUAGE_IDS

        return sorted(
            languages,
            key=lambda language: (
                order.index(language)
                if language in order
                else 99
            ),
        )

    def get_voices(
        self,
        language: str,
    ) -> list[VoiceInfo]:
        """Return every voice available for a language."""

        voices: list[VoiceInfo] = []

        for provider in self._providers:
            try:
                voices.extend(
                    provider.list_voices(
                        language
                    )
                )

            except Exception:
                logger.exception(
                    "Provider failed while "
                    "listing voices: %s",
                    provider.provider_name(),
                )

        return voices

    def get_voice_display(
        self,
        language: str,
    ) -> list[tuple[str, str]]:
        """
        Return dropdown-friendly:

        [
            (display_name, voice_id),
            ...
        ]
        """

        voices = self.get_voices(
            language
        )

        return [
            (
                f"{voice.name} "
                f"({voice.gender})",
                voice.id,
            )
            for voice in voices
        ]

    def _find_provider_for_voice(
        self,
        language: str,
        voice_id: str,
    ) -> TTSProvider | None:
        """
        Find the provider that owns a specific voice.

        No fallback is performed.
        """

        for provider in self._providers:
            try:
                voices = provider.list_voices(
                    language
                )

            except Exception:
                logger.exception(
                    "Provider failed while "
                    "listing voices: %s",
                    provider.provider_name(),
                )

                continue

            if any(
                voice.id == voice_id
                for voice in voices
            ):
                return provider

        return None

    # ============================================================
    # SHORT TTS
    # ============================================================

    def synthesize(
        self,
        text,
        language,
        voice_id,
        speed=1.0,
        filename=None,
        **options,
    ) -> SynthResult:
        """Generate standard short-form TTS."""

        if (
            not isinstance(text, str)
            or not text.strip()
        ):
            return SynthResult(
                status="FAIL",
                error=(
                    "INVALID_TEXT: empty text"
                ),
            )

        if (
            not isinstance(
                speed,
                (int, float),
            )
            or not 0.5 <= speed <= 2
        ):
            return SynthResult(
                status="FAIL",
                error=(
                    "INVALID_TEXT: "
                    "speed must be 0.5–2"
                ),
            )

        if language not in self.get_languages():
            return SynthResult(
                status="FAIL",
                language=language,
                error=(
                    "LANGUAGE_NOT_SUPPORTED"
                ),
            )

        provider = (
            self._find_provider_for_voice(
                language,
                voice_id,
            )
        )

        if provider is None:
            return SynthResult(
                status="FAIL",
                language=language,
                error=(
                    "VOICE_NOT_FOUND: "
                    f"{language}/{voice_id}"
                ),
            )

        if filename is None:
            timestamp = int(
                time.time() * 1000
            )

            filename = (
                f"tts_{language}_"
                f"{timestamp}.wav"
            )

        out_path = (
            self.output_dir
            / Path(filename).name
        )

        try:
            result = provider.synthesize(
                text,
                language,
                voice_id,
                out_path,
                speed=speed,
                **options,
            )

        except Exception as exc:
            logger.exception(
                "Provider failed"
            )

            result = SynthResult(
                status="FAIL",
                language=language,
                voice=voice_id,
                provider=(
                    provider.provider_name()
                ),
                error=(
                    "GENERATION_FAILED: "
                    f"{exc}"
                ),
            )

        if (
            result.status == "PASS"
            and result.wav_path
        ):
            mp3 = export_mp3(
                result.wav_path
            )

            if mp3:
                result.mp3_path = str(
                    mp3
                )

        result.text_length = len(text)

        if (
            result.wav_path
            and not result.mp3_path
        ):
            result.export_error = (
                "EXPORT_FAILED: "
                "MP3 conversion failed; "
                "WAV retained"
            )

        self._log_result(
            result
        )

        return result

    # ============================================================
    # LONG TEXT — CP0.2D
    # ============================================================

    def synthesize_long_text(
        self,
        text: str,
        language: str,
        voice_id: str,
        *,
        speed: float = 1.0,
        filename: str | None = None,
        chunk_config: (
            ChunkingConfig | None
        ) = None,
        boundary_config: (
            BoundaryDSPConfig | None
        ) = None,
        max_retries: int = 2,
        on_progress: (
            ProgressCallback | None
        ) = None,
        is_cancelled: (
            CancelCallback | None
        ) = None,
        keep_temp: bool = False,
        chunk_synthesizer: Callable | None = None,
        audio_validator: Callable[[Path], Any] | None = None,
        export_mp3_enabled: bool = True,
        **options,
    ) -> dict[str, Any]:
        """
        Generate long-form speech using chunking.

        CP0.2D responsibilities:
        - chunk text
        - sequential generation
        - bounded retry
        - cancellation between chunks
        - progress reporting
        - ordered merge
        - safe failure handling

        Advanced pause/boundary DSP belongs to CP0.2E.
        """

        # --------------------------------------------------------
        # Validate input
        # --------------------------------------------------------

        if (
            not isinstance(text, str)
            or not text.strip()
        ):
            return self._long_text_failure(
                error=(
                    "INVALID_TEXT: empty text"
                ),
                language=language,
                voice_id=voice_id,
                text_length=0,
            )

        if language not in self.get_languages():
            return self._long_text_failure(
                error=(
                    "LANGUAGE_NOT_SUPPORTED"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        if (
            not isinstance(
                speed,
                (int, float),
            )
            or not 0.5 <= speed <= 2
        ):
            return self._long_text_failure(
                error=(
                    "INVALID_TEXT: "
                    "speed must be 0.5–2"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        if (
            not isinstance(
                max_retries,
                int,
            )
            or max_retries < 0
        ):
            return self._long_text_failure(
                error=(
                    "INVALID_RETRY_POLICY: "
                    "max_retries must be >= 0"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        provider = (
            self._find_provider_for_voice(
                language,
                voice_id,
            )
        )

        if provider is None:
            return self._long_text_failure(
                error=(
                    "VOICE_NOT_FOUND: "
                    f"{language}/{voice_id}"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        # --------------------------------------------------------
        # Chunk text
        # --------------------------------------------------------

        config = (
            chunk_config
            or ChunkingConfig()
        )

        try:
            chunks = build_chunks(
                text,
                config,
            )
            # Normalization may change whitespace, never source content/order.
            if "".join(text.split()) != "".join("".join(c.text.split()) for c in chunks):
                raise ValueError("TEXT_INTEGRITY_FAILED")
            if [c.index for c in chunks] != list(range(len(chunks))):
                raise ValueError("CHUNK_ORDER_FAILED")

        except Exception as exc:
            logger.error("Long-text chunking failed code=CHUNKING_FAILED")

            return self._long_text_failure(
                error=(
                    "CHUNKING_FAILED: "
                    f"{exc}"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        if not chunks:
            return self._long_text_failure(
                error=(
                    "INVALID_TEXT: "
                    "no synthesizable chunks"
                ),
                language=language,
                voice_id=voice_id,
                text_length=len(text),
            )

        # --------------------------------------------------------
        # Create isolated job workspace
        # --------------------------------------------------------

        job_id = uuid.uuid4().hex

        job_dir = (
            self.temp_dir
            / f"long_{job_id}"
        )

        job_dir.mkdir(
            parents=True,
            exist_ok=False,
        )

        if filename is None:
            timestamp = int(
                time.time() * 1000
            )

            filename = (
                f"long_{language}_"
                f"{timestamp}.wav"
            )

        final_path = (
            self.output_dir
            / Path(filename).name
        )

        if final_path.exists():
            final_path.unlink()

        segment_paths: list[Path] = []

        started_at = (
            time.perf_counter()
        )

        self._emit_progress(
            on_progress,
            {
                "job_id": job_id,
                "stage": (
                    "CHUNKING_COMPLETE"
                ),
                "current": 0,
                "total": len(chunks),
                "progress": 0.0,
            },
        )

        try:
            # ----------------------------------------------------
            # Generate chunks sequentially
            # ----------------------------------------------------

            for position, chunk in enumerate(
                chunks,
                start=1,
            ):

                # ----------------------------------------------
                # Cancel safely BETWEEN chunks
                # ----------------------------------------------

                if (
                    is_cancelled
                    is not None
                    and is_cancelled()
                ):
                    chunk.status = (
                        ChunkStatus.CANCELLED
                    )

                    self._emit_progress(
                        on_progress,
                        {
                            "job_id": job_id,
                            "stage": "CANCELLED",
                            "current": (
                                position - 1
                            ),
                            "total": (
                                len(chunks)
                            ),
                            "progress": (
                                (
                                    position
                                    - 1
                                )
                                / len(chunks)
                            ),
                        },
                    )

                    return (
                        self._build_long_text_result(
                            job_id=job_id,
                            status="CANCELLED",
                            language=language,
                            voice_id=voice_id,
                            provider=(
                                provider
                                .provider_name()
                            ),
                            text=text,
                            chunks=chunks,
                            wav_path=None,
                            mp3_path=None,
                            error=(
                                "Generation "
                                "cancelled"
                            ),
                            started_at=(
                                started_at
                            ),
                        )
                    )

                chunk.status = (
                    ChunkStatus.GENERATING
                )

                self._emit_progress(
                    on_progress,
                    {
                        "job_id": job_id,
                        "stage": (
                            "GENERATING"
                        ),
                        "chunk_index": (
                            chunk.index
                        ),
                        "current": position,
                        "total": len(chunks),
                        "progress": (
                            (
                                position - 1
                            )
                            / len(chunks)
                        ),
                    },
                )

                chunk_path = (
                    job_dir
                    / (
                        f"chunk_"
                        f"{chunk.index:04d}.wav"
                    )
                )

                success = False
                last_error: (
                    str | None
                ) = None

                # ----------------------------------------------
                # Retry current chunk only
                # ----------------------------------------------

                for attempt in range(
                    1,
                    max_retries + 2,
                ):
                    chunk.attempts = (
                        attempt
                    )

                    try:
                        if (
                            chunk_path
                            .exists()
                        ):
                            chunk_path.unlink()

                        result = (
                            (chunk_synthesizer or provider.synthesize)(
                                chunk.text,
                                language,
                                voice_id,
                                chunk_path,
                                speed=speed,
                                **options,
                            )
                        )

                        if (
                            result.status
                            != "PASS"
                        ):
                            raise RuntimeError(
                                result.error
                                or (
                                    "Provider "
                                    "returned "
                                    "non-PASS "
                                    "result"
                                )
                            )

                        if not result.wav_path:
                            raise RuntimeError(
                                "Provider "
                                "returned no "
                                "WAV path"
                            )

                        actual_path = Path(
                            result.wav_path
                        )

                        if (
                            not actual_path
                            .exists()
                        ):
                            raise RuntimeError(
                                "Generated WAV "
                                "does not exist"
                            )

                        if audio_validator is not None:
                            audio_validator(actual_path)

                        chunk.status = (
                            ChunkStatus.COMPLETED
                        )

                        chunk.error = None

                        segment_paths.append(
                            actual_path
                        )

                        success = True

                        break

                    except Exception as exc:
                        logger.error(
                            "Long-text chunk "
                            "failed "
                            "job=%s "
                            "chunk=%s "
                            "attempt=%s",
                            job_id,
                            chunk.index,
                            attempt,
                        )

                        last_error = "CHUNK_GENERATION_FAILED"

                        chunk.error = (
                            last_error
                        )

                # ----------------------------------------------
                # Failed after retries
                # ----------------------------------------------

                if not success:
                    chunk.status = (
                        ChunkStatus.FAILED
                    )

                    error = (
                        "CHUNK_FAILED: "
                        f"index="
                        f"{chunk.index} "
                        f"{last_error}"
                    )

                    self._emit_progress(
                        on_progress,
                        {
                            "job_id": job_id,
                            "stage": "FAILED",
                            "chunk_index": (
                                chunk.index
                            ),
                            "current": position,
                            "total": (
                                len(chunks)
                            ),
                            "progress": (
                                (
                                    position - 1
                                )
                                / len(chunks)
                            ),
                            "error": error,
                        },
                    )

                    return (
                        self._build_long_text_result(
                            job_id=job_id,
                            status="FAILED",
                            language=language,
                            voice_id=voice_id,
                            provider=(
                                provider
                                .provider_name()
                            ),
                            text=text,
                            chunks=chunks,
                            wav_path=None,
                            mp3_path=None,
                            error=error,
                            started_at=(
                                started_at
                            ),
                        )
                    )

                self._emit_progress(
                    on_progress,
                    {
                        "job_id": job_id,
                        "stage": (
                            "CHUNK_COMPLETED"
                        ),
                        "chunk_index": (
                            chunk.index
                        ),
                        "current": position,
                        "total": len(chunks),
                        "progress": (
                            position
                            / len(chunks)
                        ),
                    },
                )

            # ----------------------------------------------------
            # Sanity check
            # ----------------------------------------------------

            completed_count = sum(
                1
                for chunk in chunks
                if (
                    chunk.status
                    == ChunkStatus.COMPLETED
                )
            )

            if (
                completed_count
                != len(chunks)
            ):
                return (
                    self._build_long_text_result(
                        job_id=job_id,
                        status="FAILED",
                        language=language,
                        voice_id=voice_id,
                        provider=(
                            provider
                            .provider_name()
                        ),
                        text=text,
                        chunks=chunks,
                        wav_path=None,
                        mp3_path=None,
                        error=(
                            "INCOMPLETE_CHUNKS: "
                            f"{completed_count}/"
                            f"{len(chunks)}"
                        ),
                        started_at=(
                            started_at
                        ),
                    )
                )

            # ----------------------------------------------------
            # Merge
            # ----------------------------------------------------

            if is_cancelled is not None and is_cancelled():
                return self._build_long_text_result(
                    job_id=job_id, status="CANCELLED", language=language,
                    voice_id=voice_id, provider=provider.provider_name(), text=text,
                    chunks=chunks, wav_path=None, mp3_path=None,
                    error="Generation cancelled", started_at=started_at)

            self._emit_progress(
                on_progress,
                {
                    "job_id": job_id,
                    "stage": "MERGING",
                    "current": len(chunks),
                    "total": len(chunks),
                    "progress": 1.0,
                },
            )

            dsp_config = (
                boundary_config
                or BoundaryDSPConfig()
            )
            boundary_choices = [
                select_pause_ms(
                    chunk.text,
                    chunk.is_paragraph_end,
                    dsp_config.pause_policy,
                )
                for chunk in chunks[:-1]
            ]
            boundary_labels = [
                choice[0]
                for choice in boundary_choices
            ]
            pauses_ms = [
                choice[1]
                for choice in boundary_choices
            ]
            boundary_diagnostics: list[dict] = []

            merge_segments(
                segment_paths,
                final_path,
                target_sr=24000,
                pauses_ms=pauses_ms,
                boundary_labels=boundary_labels,
                boundary_config=dsp_config,
                diagnostics_out=(
                    boundary_diagnostics
                ),
            )

            if not final_path.exists():
                raise RuntimeError(
                    "Final merged WAV "
                    "was not created"
                )

            # ----------------------------------------------------
            # MP3 export
            # ----------------------------------------------------

            mp3_path: str | None = None

            if audio_validator is not None:
                audio_validator(final_path)

            try:
                exported = export_mp3(final_path) if export_mp3_enabled else None
            except Exception:
                logger.error("Long-text MP3 export failed; valid WAV retained")
                exported = None

            if exported:
                mp3_path = str(
                    exported
                )

            self._emit_progress(
                on_progress,
                {
                    "job_id": job_id,
                    "stage": "COMPLETED",
                    "current": len(chunks),
                    "total": len(chunks),
                    "progress": 1.0,
                },
            )

            return (
                self._build_long_text_result(
                    job_id=job_id,
                    status="COMPLETED",
                    language=language,
                    voice_id=voice_id,
                    provider=(
                        provider
                        .provider_name()
                    ),
                    text=text,
                    chunks=chunks,
                    wav_path=str(
                        final_path
                    ),
                    mp3_path=mp3_path,
                    error=None,
                    started_at=started_at,
                    boundary_diagnostics=(
                        boundary_diagnostics
                    ),
                )
            )

        except Exception as exc:
            logger.error(
                "Long-text generation "
                "failed job=%s",
                job_id,
            )

            # Never expose a partial final WAV
            # as successful.
            if final_path.exists():
                try:
                    final_path.unlink()

                except OSError:
                    logger.warning(
                        "Unable to remove "
                        "partial final WAV: %s",
                        final_path,
                    )

            return (
                self._build_long_text_result(
                    job_id=job_id,
                    status="FAILED",
                    language=language,
                    voice_id=voice_id,
                    provider=(
                        provider
                        .provider_name()
                    ),
                    text=text,
                    chunks=chunks,
                    wav_path=None,
                    mp3_path=None,
                    error=(
                        "LONG_TEXT_FAILED: "
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                    started_at=started_at,
                )
            )

        finally:
            if not keep_temp:
                shutil.rmtree(
                    job_dir,
                    ignore_errors=True,
                )

    # ============================================================
    # LONG TEXT HELPERS
    # ============================================================

    @staticmethod
    def _emit_progress(
        callback: (
            ProgressCallback | None
        ),
        payload: dict[str, Any],
    ) -> None:
        """
        Progress callback must never crash
        the synthesis job.
        """

        if callback is None:
            return

        try:
            callback(
                payload
            )

        except Exception:
            logger.exception(
                "Progress callback failed"
            )

    @staticmethod
    def _serialize_chunk(
        chunk: TextChunk,
    ) -> dict[str, Any]:
        """
        Serialize chunk metadata.

        Note:
        The returned result retains text for
        internal/debug use.

        Do not blindly log this object in
        production because it may contain
        customer text.
        """

        return {
            "index": chunk.index,
            "text": chunk.text,
            "paragraph_index": (
                chunk.paragraph_index
            ),
            "sentence_count": (
                chunk.sentence_count
            ),
            "is_paragraph_end": (
                chunk.is_paragraph_end
            ),
            "status": (
                chunk.status.value
            ),
            "attempts": (
                chunk.attempts
            ),
            "error": chunk.error,
        }

    def _build_long_text_result(
        self,
        *,
        job_id: str,
        status: str,
        language: str,
        voice_id: str,
        provider: str,
        text: str,
        chunks: list[TextChunk],
        wav_path: str | None,
        mp3_path: str | None,
        error: str | None,
        started_at: float,
        boundary_diagnostics: (
            list[dict] | None
        ) = None,
    ) -> dict[str, Any]:
        """Create normalized long-text result."""

        elapsed = (
            time.perf_counter()
            - started_at
        )

        result = {
            "job_id": job_id,
            "status": status,
            "provider": provider,
            "language": language,
            "voice": voice_id,
            "text_length": len(text),
            "chunk_count": len(chunks),
            "completed_chunks": sum(
                1
                for chunk in chunks
                if (
                    chunk.status
                    == ChunkStatus.COMPLETED
                )
            ),
            "elapsed_sec": round(
                elapsed,
                3,
            ),
            "wav_path": wav_path,
            "mp3_path": mp3_path,
            "error": error,
            "chunks": [
                self._serialize_chunk(
                    chunk
                )
                for chunk in chunks
            ],
            "boundary_diagnostics": (
                boundary_diagnostics
                or []
            ),
        }

        # Important:
        # Do not log full customer text.
        logger.info(
            (
                "LONG_TTS "
                "status=%s "
                "provider=%s "
                "lang=%s "
                "voice=%s "
                "text_length=%s "
                "chunks=%s "
                "completed=%s "
                "elapsed=%.3fs"
            ),
            status,
            provider,
            language,
            voice_id,
            len(text),
            len(chunks),
            result[
                "completed_chunks"
            ],
            elapsed,
        )

        return result

    @staticmethod
    def _long_text_failure(
        *,
        error: str,
        language: str | None,
        voice_id: str | None,
        text_length: int = 0,
    ) -> dict[str, Any]:
        """Create pre-generation failure result."""

        return {
            "job_id": None,
            "status": "FAILED",
            "provider": None,
            "language": language,
            "voice": voice_id,
            "text_length": (
                text_length
            ),
            "chunk_count": 0,
            "completed_chunks": 0,
            "elapsed_sec": 0.0,
            "wav_path": None,
            "mp3_path": None,
            "error": error,
            "chunks": [],
        }

    # ============================================================
    # LEGACY VOICE CLONING
    # ============================================================

    def synthesize_clone(
        self,
        text,
        reference_audio,
        language="vi",
        filename=None,
        **options,
    ) -> SynthResult:
        """
        Legacy cloning path.

        Voice cloning is currently handled
        through its newer provider API and is
        not forced through this legacy contract.
        """

        if (
            not isinstance(text, str)
            or not text.strip()
        ):
            return SynthResult(
                status="FAIL",
                error="INVALID_TEXT",
            )

        if language != "vi":
            return SynthResult(
                status="FAIL",
                error=(
                    "LANGUAGE_NOT_SUPPORTED"
                ),
            )

        if self._clone_provider is None:
            return SynthResult(
                status="FAIL",
                error=(
                    "No cloning provider "
                    "registered"
                ),
            )

        if filename is None:
            timestamp = int(
                time.time() * 1000
            )

            filename = (
                f"clone_{timestamp}.wav"
            )

        out_path = (
            self.output_dir
            / Path(filename).name
        )

        try:
            result = (
                self._clone_provider
                .synthesize_with_profile(
                    text,
                    reference_audio,
                    language,
                    out_path,
                    **options,
                )
            )

        except Exception as exc:
            logger.exception(
                "Clone provider failed"
            )

            return SynthResult(
                status="FAIL",
                language=language,
                error=(
                    "GENERATION_FAILED: "
                    f"{exc}"
                ),
            )

        if (
            result.status == "PASS"
            and result.wav_path
        ):
            mp3 = export_mp3(
                result.wav_path
            )

            if mp3:
                result.mp3_path = str(
                    mp3
                )

        result.text_length = len(text)

        if (
            result.wav_path
            and not result.mp3_path
        ):
            result.export_error = (
                "EXPORT_FAILED: "
                "MP3 conversion failed; "
                "WAV retained"
            )

        self._log_result(
            result
        )

        return result

    def prepare_clone_profile(
        self,
        reference_audio,
    ) -> dict:
        """Prepare legacy voice-clone profile."""

        if self._clone_provider is None:
            return {
                "error": (
                    "No cloning provider"
                )
            }

        return (
            self._clone_provider
            .prepare_voice_profile(
                reference_audio
            )
        )

    # ============================================================
    # CONVERSATION
    # ============================================================

    def merge_conversation(
        self,
        wav_paths,
        output_name="conversation.wav",
        pause_ms=500,
    ) -> str:
        """Merge conversation segments."""

        out_path = (
            self.output_dir
            / Path(output_name).name
        )

        merge_segments(
            wav_paths,
            out_path,
            pause_ms=pause_ms,
        )

        export_mp3(
            out_path
        )

        return str(
            out_path
        )

    # ============================================================
    # SELF TEST / HEALTH
    # ============================================================

    def run_self_test(
        self,
    ) -> list[dict]:
        """
        Synthesize one test sentence for
        every available voice/language.
        """

        results: list[dict] = []

        for language in self.get_languages():

            text = TEST_SENTENCES.get(
                language,
                "Test.",
            )

            voices = self.get_voices(
                language
            )

            for voice in voices:
                result = self.synthesize(
                    text,
                    language,
                    voice.id,
                )

                results.append(
                    asdict(result)
                )

        return results

    def get_all_health(
        self,
    ) -> list[dict]:
        """Return provider health information."""

        return [
            provider.health_check()
            for provider
            in self._providers
        ]

    # ============================================================
    # LOGGING
    # ============================================================

    def _log_result(
        self,
        result: SynthResult,
    ) -> None:
        """Log normalized short-TTS result."""

        logger.info(
            json.dumps(
                asdict(result),
                ensure_ascii=False,
            )
        )

        logger.info(
            (
                "TTS %s | "
                "lang=%s "
                "voice=%s | "
                "%.3fs gen, "
                "%.3fs dur, "
                "RTF=%.4f | %s"
            ),
            result.provider,
            result.language,
            result.voice,
            result.gen_time or 0.0,
            result.duration or 0.0,
            result.rtf or 0.0,
            result.status,
        )

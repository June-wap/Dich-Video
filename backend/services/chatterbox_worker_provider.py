"""Main-runtime bridge to the isolated local Chatterbox worker."""
from __future__ import annotations

from collections import deque
import json
import logging
from pathlib import Path
import subprocess
from threading import RLock, Thread

from backend.services.provider_base import AudioSynthResult, VoiceInfo
from backend.core.languages import CHATTERBOX_LANGUAGE_IDS
from backend.errors import ApplicationError, ErrorCode
from backend.services.capability_service import HardwareCapabilityService


# The provider consumes the app-scoped capability snapshot; it never probes
# the worker runtime itself.


logger = logging.getLogger(__name__)


class ChatterboxWorkerProvider:
    PROVIDER_ID = "chatterbox"
    DEFAULT_VOICE_ID = "chatterbox_default"
    LANGUAGES = CHATTERBOX_LANGUAGE_IDS

    def __init__(self, python_executable: Path, project_root: Path, *,
                 capability_service: HardwareCapabilityService | None = None):
        self._python = Path(python_executable)
        self._root = Path(project_root)
        self._process = None
        self._lock = RLock()
        self._stderr_lines: deque[str] = deque(maxlen=40)
        self._stderr_thread: Thread | None = None
        # This is the same app-scoped service used by /system/capabilities.
        # The provider only reads its cached snapshot and never probes itself.
        self._capability_service = capability_service

    def provider_name(self): return self.PROVIDER_ID
    def is_loaded(self): return self._process is not None and self._process.poll() is None
    def list_languages(self): return list(self.LANGUAGES)
    def capabilities(self): return {"verified_languages": list(self.LANGUAGES), "language_metadata": [], "experimental_languages_enabled": False, "production_ready": True}
    def list_voices(self, language):
        return [VoiceInfo(id=self.DEFAULT_VOICE_ID, name="Chatterbox Default", language=language, provider=self.PROVIDER_ID, sample_rate=24000)] if language in self.LANGUAGES else []
    def health_check(self): return {"provider": self.PROVIDER_ID, "loaded": self.is_loaded(), "device": "cuda"}

    def _drain_stderr(self, process) -> None:
        try:
            for line in process.stderr:
                self._stderr_lines.append(line.rstrip())
        except (OSError, ValueError):
            # A normal terminate()/pipe close can race the reader.
            pass

    def _start_stderr_drain(self, process) -> None:
        self._stderr_lines.clear()
        self._stderr_thread = Thread(target=self._drain_stderr, args=(process,), daemon=True)
        self._stderr_thread.start()

    def _stderr_tail(self) -> str:
        tail = " | ".join(line for line in self._stderr_lines if line)
        return tail[-2000:] if tail else "(no worker stderr captured)"

    def load(self):
        with self._lock:
            if self.is_loaded(): return self
            if not self._python.is_file(): raise RuntimeError("CHATTERBOX_RUNTIME_UNAVAILABLE")
            if self._capability_service is not None:
                capability = self._capability_service.snapshot().chatterbox
                if not capability.local_available:
                    logger.warning(
                        "chatterbox_admission_denied reason=%s runtime=%s",
                        capability.reason or "LOCAL_GPU_UNAVAILABLE",
                        self._python,
                    )
                    raise ApplicationError(ErrorCode.LOCAL_GPU_UNAVAILABLE)
            self._process = subprocess.Popen([str(self._python), "-m", "backend.services.chatterbox_worker"], cwd=str(self._root), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", bufsize=1, shell=False)
            self._start_stderr_drain(self._process)
        return self

    def unload(self):
        with self._lock:
            process = self._process
            self._process = None
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill()

    def _protocol_failure(self, reason, language, voice):
        self.unload()
        return self._fail(f"{reason}; stderr={self._stderr_tail()}", language, voice)

    def _request(self, payload, language, voice):
        with self._lock:
            self.load()
            process = self._process
            process.stdin.write(json.dumps(payload) + "\n")
            process.stdin.flush()
            raw_response = process.stdout.readline()
            if not raw_response:
                return self._protocol_failure(f"CHATTERBOX_WORKER_PROTOCOL_EOF exit_code={process.poll()}", language, voice)
            try:
                response = json.loads(raw_response)
            except json.JSONDecodeError:
                return self._protocol_failure(f"CHATTERBOX_WORKER_PROTOCOL_INVALID_JSON raw={raw_response.strip()[:300]!r}", language, voice)
        if response.get("status") != "PASS":
            return self._fail(response.get("error") or "GENERATION_FAILED", language, voice)
        logger.info("chatterbox_timing worker_pid=%s timings=%s", response.get("worker_pid"), response.get("metadata") or {})
        return AudioSynthResult(status="PASS", wav_path=response.get("wav_path"), sample_rate=response.get("sample_rate", 0), duration=response.get("duration", 0), gen_time=response.get("gen_time", 0), provider=self.PROVIDER_ID, language=language, voice=voice, device="cuda", metadata={**(response.get("metadata") or {}), "worker_pid": response.get("worker_pid")})

    def create_voice_profile(self, reference_audio, transcript=None):
        path = Path(reference_audio).resolve()
        if not path.is_file():
            raise ValueError("INVALID_REFERENCE_AUDIO")
        # V3 conditions are GPU-resident and cannot be persisted safely. The
        # worker caches them lazily when synthesize_cloned first uses this
        # durable path; transcript is not required by pinned upstream.
        return {"reference_audio": str(path)}

    def synthesize(self, text, language, voice=DEFAULT_VOICE_ID, output_path=None, speed=1.0, **options):
        if language not in self.LANGUAGES: return self._fail("LANGUAGE_NOT_SUPPORTED", language, voice)
        if voice != self.DEFAULT_VOICE_ID or output_path is None or speed != 1.0 or options: return self._fail("INVALID_REQUEST", language, voice)
        try:
            return self._request({"action":"synthesize", "text":text, "language":language, "voice":voice, "output_path":str(output_path), "speed":speed}, language, voice)
        except Exception as exc: return self._fail(str(exc), language, voice)

    def synthesize_cloned(self, text, language, profile, output_path, **options):
        if language not in self.LANGUAGES:
            return self._fail("LANGUAGE_NOT_SUPPORTED", language, "chatterbox_clone")
        if options:
            return self._fail("INVALID_REQUEST", language, "chatterbox_clone")
        try:
            return self._request({"action": "synthesize_clone", "text": text, "language": language,
                                  "profile": profile, "output_path": str(output_path)},
                                 language, "chatterbox_clone")
        except Exception as exc:
            return self._fail(str(exc), language, "chatterbox_clone")

    def _fail(self, error, language, voice): return AudioSynthResult(status="FAIL", error=error, provider=self.PROVIDER_ID, language=language, voice=voice, device="cuda")

"""Private JSON-lines worker run only by the isolated Chatterbox runtime.

File descriptor 1 is reserved for the parent/worker protocol.  Chatterbox and
its dependencies may print diagnostics while loading or generating, so their
ordinary stdout is redirected to stderr before the adapter is imported.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Callable, TextIO



def _isolate_protocol_stdout() -> TextIO:
    """Keep a duplicate of stdout for JSON, then direct other fd-1 output to stderr."""
    protocol_fd = os.dup(sys.stdout.fileno())
    protocol_stdout = os.fdopen(protocol_fd, "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    sys.stdout = sys.stderr
    return protocol_stdout


def _reply(protocol_stdout: TextIO, payload: dict) -> None:
    protocol_stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    protocol_stdout.flush()


def main(*, adapter_factory: Callable[..., object] | None = None,
         input_stream: TextIO | None = None,
         protocol_stdout: TextIO | None = None) -> int:
    """Serve requests; injectable streams/factory keep protocol tests model-free."""
    if protocol_stdout is None:
        protocol_stdout = _isolate_protocol_stdout()
    if adapter_factory is None:
        # Import after stdout isolation: import-time diagnostics cannot become
        # protocol messages.
        from backend.services.chatterbox_adapter import ChatterboxAdapter
        adapter_factory = ChatterboxAdapter

    adapter = adapter_factory(device="cuda")
    try:
        for line in input_stream or sys.stdin:
            try:
                request = json.loads(line)
                action = request.get("action")
                if action not in {"synthesize", "synthesize_clone"}:
                    raise ValueError("INVALID_WORKER_REQUEST")
                if action == "synthesize_clone":
                    result = adapter.synthesize_cloned(
                        request.get("text"), request.get("language"), request.get("profile"),
                        output_path=Path(request["output_path"]),
                    )
                else:
                    result = adapter.synthesize(
                        request.get("text"), request.get("language"),
                        voice=request.get("voice", adapter.DEFAULT_VOICE_ID),
                        output_path=Path(request["output_path"]), speed=request.get("speed", 1.0),
                    )
                _reply(protocol_stdout, {"status": result.status, "error": result.error, "wav_path": result.wav_path,
                        "sample_rate": result.sample_rate, "duration": result.duration,
                        "gen_time": result.gen_time, "provider": result.provider,
                        "language": result.language, "voice": result.voice,
                        # Keep the JSON protocol compatible with adapters used
                        # by diagnostics/tests that predate timing metadata.
                        "metadata": getattr(result, "metadata", None) or {},
                        "worker_pid": os.getpid()})
            except Exception as exc:
                _reply(protocol_stdout, {"status": "FAIL", "error": str(exc), "provider": "chatterbox"})
    finally:
        adapter.unload()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

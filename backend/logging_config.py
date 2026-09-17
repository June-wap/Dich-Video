"""Console-only backend logging; never attach duplicate handlers.

Also keeps a small in-memory ring buffer of the most recent formatted log
lines (see _RingBufferHandler/get_recent_logs), so Diagnostics > Open Logs
can show real backend output instead of a hardcoded sample transcript. Never
written to disk and capped at MAX_LOG_LINES - this is a live debugging aid,
not a persisted audit log.
"""
import collections
import logging
import threading

MAX_LOG_LINES = 500
_buffer: collections.deque[str] = collections.deque(maxlen=MAX_LOG_LINES)
_buffer_lock = threading.Lock()


class _RingBufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            line = self.format(record)
        except Exception:
            return
        with _buffer_lock:
            _buffer.append(line)


def get_recent_logs() -> list[str]:
    """Newest-last, like a log file tail. Safe to call from any thread/request."""
    with _buffer_lock:
        return list(_buffer)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("backend")
    logger.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    if not any(getattr(handler, "_local_ai_backend", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._local_ai_backend = True
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    if not any(getattr(handler, "_local_ai_backend_ring", False) for handler in logger.handlers):
        ring_handler = _RingBufferHandler()
        ring_handler._local_ai_backend_ring = True
        ring_handler.setFormatter(formatter)
        logger.addHandler(ring_handler)
    logger.propagate = False

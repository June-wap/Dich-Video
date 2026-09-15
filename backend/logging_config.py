"""Console-only backend logging; never attach duplicate handlers."""
import logging


def configure_logging(level: str) -> None:
    logger = logging.getLogger("backend")
    logger.setLevel(level)
    if not any(getattr(handler, "_local_ai_backend", False) for handler in logger.handlers):
        handler = logging.StreamHandler()
        handler._local_ai_backend = True
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
    logger.propagate = False

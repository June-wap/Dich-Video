"""Serialize application inference, including whole long-form jobs."""
from functools import wraps


def serialized_inference(method):
    @wraps(method)
    def execute(self, *args, **kwargs):
        with self._provider_service.inference_lock:
            return method(self, *args, **kwargs)
    return execute

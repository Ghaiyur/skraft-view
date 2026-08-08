import threading

_shutdown_callback = None
_lock = threading.Lock()


def register_shutdown_callback(callback) -> None:
    global _shutdown_callback
    with _lock:
        _shutdown_callback = callback


def request_shutdown() -> bool:
    with _lock:
        callback = _shutdown_callback
    if callback is None:
        return False
    callback()
    return True

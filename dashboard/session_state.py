import threading
import time

SESSION_TIMEOUT_SECONDS = 15
_sessions: dict[str, float] = {}
_lock = threading.Lock()


def _prune_locked(now: float) -> None:
    expired = [
        session_id
        for session_id, last_seen in _sessions.items()
        if now - last_seen > SESSION_TIMEOUT_SECONDS
    ]
    for session_id in expired:
        _sessions.pop(session_id, None)


def touch_session(session_id: str) -> dict[str, int]:
    now = time.time()
    with _lock:
        _prune_locked(now)
        _sessions[session_id] = now
        return {"active_sessions": len(_sessions)}


def close_session(session_id: str) -> dict[str, int]:
    with _lock:
        _sessions.pop(session_id, None)
        return {"active_sessions": len(_sessions)}


def should_shutdown() -> bool:
    # Keep the local server alive so temporary browser throttling or network
    # hiccups do not terminate the app out from under the user.
    return False

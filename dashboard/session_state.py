import threading
import time


SESSION_TIMEOUT_SECONDS = 15
_sessions: dict[str, float] = {}
_lock = threading.Lock()
_last_empty_at: float | None = None
_has_seen_session = False


def _prune_locked(now: float) -> None:
    expired = [
        session_id
        for session_id, last_seen in _sessions.items()
        if now - last_seen > SESSION_TIMEOUT_SECONDS
    ]
    for session_id in expired:
        _sessions.pop(session_id, None)


def touch_session(session_id: str) -> dict[str, int]:
    global _last_empty_at, _has_seen_session
    now = time.time()
    with _lock:
        _prune_locked(now)
        _sessions[session_id] = now
        _has_seen_session = True
        _last_empty_at = None
        return {"active_sessions": len(_sessions)}


def close_session(session_id: str) -> dict[str, int]:
    global _last_empty_at
    now = time.time()
    with _lock:
        _prune_locked(now)
        _sessions.pop(session_id, None)
        if not _sessions:
            _last_empty_at = now
        return {"active_sessions": len(_sessions)}


def should_shutdown() -> bool:
    global _last_empty_at
    now = time.time()
    with _lock:
        _prune_locked(now)
        if _sessions:
            _last_empty_at = None
            return False
        if not _has_seen_session:
            return False
        if _last_empty_at is None:
            _last_empty_at = now
            return False
        return now - _last_empty_at >= SESSION_TIMEOUT_SECONDS

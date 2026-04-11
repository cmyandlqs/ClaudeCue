#!/usr/bin/env python3
"""
Bootstrap hook entry for ccCue.

Reads hook payload from stdin, ensures notifier is running, then forwards event.
Always exits with code 0 to avoid blocking Claude Code workflow.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from hooks.notify_hook import MAX_STDIN_READ, map_hook_to_event, send_event  # noqa: E402

NOTIFIER_PORT = 19527
HEALTH_URL = f"http://127.0.0.1:{NOTIFIER_PORT}/health"
HEALTH_TIMEOUT = 0.3
STARTUP_WAIT_SECONDS = 2.0
POLL_INTERVAL = 0.2
SESSION_CACHE_MAX = 200


def _is_notifier_healthy() -> bool:
    try:
        req = urllib.request.Request(HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, Exception):
        return False


def _choose_pythonw() -> str:
    python_exe = Path(sys.executable)
    pythonw = python_exe.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return str(python_exe)


def _start_notifier_background() -> None:
    project_root = Path(__file__).resolve().parents[1]
    python_cmd = _choose_pythonw()

    kwargs = {
        "cwd": str(project_root),
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }

    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )

    subprocess.Popen([python_cmd, "-m", "notifier.main"], **kwargs)


def _ensure_notifier_running() -> None:
    if _is_notifier_healthy():
        return

    _start_notifier_background()

    deadline = time.time() + STARTUP_WAIT_SECONDS
    while time.time() < deadline:
        if _is_notifier_healthy():
            return
        time.sleep(POLL_INTERVAL)


def _runtime_state_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        root = Path(local_app_data) / "ccCue" / "runtime"
    else:
        root = PROJECT_ROOT / ".runtime"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _session_cache_path() -> Path:
    return _runtime_state_dir() / "seen_sessions.json"


def _load_seen_sessions() -> dict:
    path = _session_cache_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _save_seen_sessions(cache: dict) -> None:
    # Bound cache size to avoid unbounded growth
    if len(cache) > SESSION_CACHE_MAX:
        items = list(cache.items())[-SESSION_CACHE_MAX:]
        cache = dict(items)
    _session_cache_path().write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def _should_emit_startup_hint(session_id: str) -> bool:
    session_id = (session_id or "").strip()
    if not session_id:
        return False
    cache = _load_seen_sessions()
    if session_id in cache:
        return False
    cache[session_id] = int(time.time())
    _save_seen_sessions(cache)
    return True


def _build_startup_hint_event(session_id: str) -> dict:
    return {
        "event_type": "notification",
        "title": "ccCue Ready",
        "message": "ccCue connected. Notifications are active for this Claude session.",
        "severity": "info",
        "display": {"timeout_ms": 1800, "sticky": False, "play_sound": False},
        "session_id": session_id,
        "source": "cccue-bootstrap",
    }


def main() -> None:
    try:
        payload = sys.stdin.read(MAX_STDIN_READ)
        if not payload:
            sys.exit(0)

        hook_data = json.loads(payload)
        event = map_hook_to_event(hook_data)
        session_id = str(hook_data.get("session_id", "")).strip()

        _ensure_notifier_running()
        if _should_emit_startup_hint(session_id):
            send_event(_build_startup_hint_event(session_id))
        send_event(event)
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()

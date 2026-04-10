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

from hooks.notify_hook import MAX_STDIN_READ, map_hook_to_event, send_event

NOTIFIER_PORT = 19527
HEALTH_URL = f"http://127.0.0.1:{NOTIFIER_PORT}/health"
HEALTH_TIMEOUT = 0.3
STARTUP_WAIT_SECONDS = 2.0
POLL_INTERVAL = 0.2


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


def main() -> None:
    try:
        payload = sys.stdin.read(MAX_STDIN_READ)
        if not payload:
            sys.exit(0)

        hook_data = json.loads(payload)
        event = map_hook_to_event(hook_data)

        _ensure_notifier_running()
        send_event(event)
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()

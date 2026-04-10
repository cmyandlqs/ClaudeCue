#!/usr/bin/env python3
"""
Claude Code hook mapper and forwarder for ccCue notifier.

This module provides:
- map_hook_to_event: maps raw hook JSON to unified event payload.
- send_event: forwards event to local notifier HTTP endpoint.
- main: legacy direct hook entry point (no bootstrap).
"""
from __future__ import annotations

import ctypes
import json
import sys
import urllib.error
import urllib.request
from typing import Callable, Dict, Optional

NOTIFIER_PORT = 19527
NOTIFIER_URL = f"http://127.0.0.1:{NOTIFIER_PORT}/event"
REQUEST_TIMEOUT = 0.5
MAX_STDIN_READ = 1024 * 1024

TERMINAL_CLASS_HINTS = (
    "cascadia_hosting_window_class",
    "cascadiahost",
    "consolewindowclass",
)

TERMINAL_TITLE_HINTS = (
    "windows terminal",
    "powershell",
    "command prompt",
    "cmd",
    "claude",
)


def _get_foreground_window_handle() -> Optional[int]:
    """Get current foreground window handle on Windows."""
    try:
        user32 = ctypes.windll.user32
        hwnd = int(user32.GetForegroundWindow())
        if hwnd > 0:
            return hwnd
    except Exception:
        return None
    return None


def _get_window_pid(hwnd: int) -> Optional[int]:
    """Get process id for a window handle."""
    try:
        user32 = ctypes.windll.user32
        pid = ctypes.c_ulong(0)
        user32.GetWindowThreadProcessId(ctypes.c_void_p(hwnd), ctypes.byref(pid))
        if pid.value > 0:
            return int(pid.value)
    except Exception:
        return None
    return None


def _get_window_text(hwnd: int) -> str:
    """Get window title text."""
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd))
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(ctypes.c_void_p(hwnd), buf, length + 1)
        return buf.value or ""
    except Exception:
        return ""


def _get_class_name(hwnd: int) -> str:
    """Get window class name."""
    try:
        user32 = ctypes.windll.user32
        buf = ctypes.create_unicode_buffer(256)
        length = user32.GetClassNameW(ctypes.c_void_p(hwnd), buf, 256)
        if length > 0:
            return buf.value or ""
    except Exception:
        return ""
    return ""


def _looks_like_terminal_window(class_name: str, title: str) -> bool:
    """Heuristic check whether current foreground window is a terminal."""
    c_name = (class_name or "").strip().lower()
    title = (title or "").strip().lower()

    for hint in TERMINAL_CLASS_HINTS:
        if hint in c_name:
            return True

    for hint in TERMINAL_TITLE_HINTS:
        if hint in title:
            return True

    return False


def _mapper_notification(data: Dict) -> Dict:
    return {
        "event_type": "notification",
        "title": data.get("title", "Claude Code"),
        "message": data.get("message", ""),
        "severity": "info",
        "display": {"timeout_ms": 5000},
    }


def _mapper_stop(data: Dict) -> Dict:
    return {
        "event_type": "stop",
        "title": "Task Completed",
        "message": "Claude Code completed the task.",
        "severity": "info",
        "display": {"timeout_ms": 3000},
    }


def _mapper_stop_failure(data: Dict) -> Dict:
    return {
        "event_type": "notification",
        "title": "Task Failed",
        "message": "Claude Code task execution failed.",
        "severity": "error",
        "display": {"timeout_ms": 5000, "sticky": True},
    }


def _mapper_permission_request(data: Dict) -> Dict:
    tool_name = data.get("tool_name", "tool")
    return {
        "event_type": "permission_request",
        "title": "Permission Request",
        "message": f"Claude needs permission to use {tool_name}",
        "severity": "warning",
        "display": {"timeout_ms": 0, "sticky": True},
    }


def _mapper_permission_denied(data: Dict) -> Dict:
    tool_name = data.get("tool_name", "tool")
    return {
        "event_type": "notification",
        "title": "Permission Denied",
        "message": f"Tool execution denied: {tool_name}",
        "severity": "warning",
        "display": {"timeout_ms": 3000},
    }


def _mapper_pre_tool_use(data: Dict) -> Dict:
    tool_name = data.get("tool_name", "tool")
    return {
        "event_type": "notification",
        "title": "Running Tool",
        "message": f"Executing: {tool_name}",
        "severity": "info",
        "display": {"play_sound": False, "timeout_ms": 2000},
    }


def _mapper_post_tool_use_failure(data: Dict) -> Dict:
    tool_name = data.get("tool_name", "tool")
    error = data.get("error", "Unknown error")
    return {
        "event_type": "notification",
        "title": "Tool Failed",
        "message": f"{tool_name}: {error}",
        "severity": "error",
        "display": {"timeout_ms": 5000},
    }


def _mapper_task_created(data: Dict) -> Dict:
    subject = data.get("subject", "")
    return {
        "event_type": "notification",
        "title": "Task Created",
        "message": f"Created task: {subject}",
        "severity": "info",
        "display": {"play_sound": False, "timeout_ms": 2000},
    }


def _mapper_task_completed(data: Dict) -> Dict:
    subject = data.get("subject", "")
    return {
        "event_type": "notification",
        "title": "Task Completed",
        "message": f"Completed: {subject}",
        "severity": "info",
        "display": {"timeout_ms": 3000},
    }


def _mapper_elicitation(data: Dict) -> Dict:
    return {
        "event_type": "needs_input",
        "title": "Input Required",
        "message": data.get("message", "Claude Code needs your input."),
        "severity": "warning",
        "display": {"timeout_ms": 0, "sticky": True},
    }


def map_hook_to_event(hook_data: Dict) -> Dict:
    """Map Claude Code hook payload to unified event format."""
    event_name = hook_data.get("hook_event_name", "")
    session_id = hook_data.get("session_id", "")

    mappers: Dict[str, Callable[[Dict], Dict]] = {
        "Notification": _mapper_notification,
        "Stop": _mapper_stop,
        "StopFailure": _mapper_stop_failure,
        "PermissionRequest": _mapper_permission_request,
        "PermissionDenied": _mapper_permission_denied,
        "PreToolUse": _mapper_pre_tool_use,
        "PostToolUseFailure": _mapper_post_tool_use_failure,
        "TaskCreated": _mapper_task_created,
        "TaskCompleted": _mapper_task_completed,
        "Elicitation": _mapper_elicitation,
    }

    mapper = mappers.get(
        event_name,
        lambda _: {
            "event_type": "notification",
            "title": event_name,
            "message": f"Claude Code event: {event_name}",
            "severity": "info",
            "display": {"timeout_ms": 3000, "sticky": False, "play_sound": True},
        },
    )

    event = mapper(hook_data)
    event.update({"session_id": session_id, "source": "claude-hook"})

    hwnd_hint = _get_foreground_window_handle()
    if hwnd_hint:
        class_hint = _get_class_name(hwnd_hint)
        title_hint = _get_window_text(hwnd_hint)
        if _looks_like_terminal_window(class_hint, title_hint):
            event["terminal_hwnd_hint"] = hwnd_hint
            pid_hint = _get_window_pid(hwnd_hint)
            if pid_hint:
                event["terminal_pid_hint"] = pid_hint
            if title_hint:
                event["terminal_title_hint"] = title_hint
            event["terminal_class_hint"] = class_hint

    return event


def send_event(event: Dict) -> bool:
    """Send event to notifier service via HTTP POST."""
    try:
        data = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            NOTIFIER_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as response:
            return response.status == 200
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, Exception):
        return False


def main() -> None:
    """Legacy direct hook entry point (without bootstrap)."""
    try:
        input_data = sys.stdin.read(MAX_STDIN_READ)
        if not input_data:
            sys.exit(0)

        hook_data = json.loads(input_data)
        event = map_hook_to_event(hook_data)
        send_event(event)
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()

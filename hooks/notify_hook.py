#!/usr/bin/env python3
"""
Claude Code hook forwarder for ccCue notifier.

Reads hook events from stdin, maps them to unified event format,
and forwards them to the local notifier service via HTTP.
"""
import sys
import json
import urllib.request
import urllib.error
from typing import Dict, Callable, Optional

# Notifier service configuration
NOTIFIER_PORT = 19527
NOTIFIER_URL = f"http://127.0.0.1:{NOTIFIER_PORT}/event"
# Timeout in seconds - hooks should not block Claude
REQUEST_TIMEOUT = 0.5
# Maximum stdin read size (1 MB - more than enough for hook events)
MAX_STDIN_READ = 1024 * 1024


def map_hook_to_event(hook_data: Dict) -> Dict:
    """
    Map Claude Code hook payload to unified event format.

    Args:
        hook_data: Raw hook payload from Claude Code

    Returns:
        Unified event dictionary
    """
    event_name = hook_data.get("hook_event_name", "")
    session_id = hook_data.get("session_id", "")

    # Event-specific mappers
    mappers: Dict[str, Callable[[Dict], Dict]] = {
        "Notification": lambda d: {
            "event_type": "notification",
            "title": d.get("title", "Claude Code"),
            "message": d.get("message", ""),
            "severity": "info",
            "display": {
                "timeout_ms": 5000
            }
        },
        "Stop": lambda d: {
            "event_type": "stop",
            "title": "任务完成",
            "message": "Claude Code 已完成任务",
            "severity": "info",
            "display": {
                "timeout_ms": 3000
            }
        },
        "StopFailure": lambda d: {
            "event_type": "notification",
            "title": "任务失败",
            "message": "Claude Code 任务执行失败",
            "severity": "error",
            "display": {
                "timeout_ms": 5000,
                "sticky": True
            }
        },
        "PermissionRequest": lambda d: {
            "event_type": "permission_request",
            "title": "权限请求",
            "message": f"Claude 需要权限使用 {d.get('tool_name', 'tool')}",
            "severity": "warning",
            "display": {
                "timeout_ms": 0,  # Don't auto-close
                "sticky": True
            }
        },
        "PermissionDenied": lambda d: {
            "event_type": "notification",
            "title": "权限被拒绝",
            "message": f"工具调用被拒绝: {d.get('tool_name', 'tool')}",
            "severity": "warning",
            "display": {
                "timeout_ms": 3000
            }
        },
        "PreToolUse": lambda d: {
            "event_type": "notification",
            "title": "执行工具",
            "message": f"正在执行: {d.get('tool_name', 'tool')}",
            "severity": "info",
            "display": {
                "play_sound": False,  # Don't play sound for every tool
                "timeout_ms": 2000
            }
        },
        "PostToolUseFailure": lambda d: {
            "event_type": "notification",
            "title": "工具执行失败",
            "message": f"{d.get('tool_name', 'tool')}: {d.get('error', 'Unknown error')}",
            "severity": "error",
            "display": {
                "timeout_ms": 5000
            }
        },
        "TaskCreated": lambda d: {
            "event_type": "notification",
            "title": "任务创建",
            "message": f"已创建任务: {d.get('subject', '')}",
            "severity": "info",
            "display": {
                "play_sound": False,
                "timeout_ms": 2000
            }
        },
        "TaskCompleted": lambda d: {
            "event_type": "notification",
            "title": "任务完成",
            "message": f"已完成: {d.get('subject', '')}",
            "severity": "info",
            "display": {
                "timeout_ms": 3000
            }
        },
        "Elicitation": lambda d: {
            "event_type": "needs_input",
            "title": "需要输入",
            "message": d.get("message", "Claude Code 需要您的输入"),
            "severity": "warning",
            "display": {
                "timeout_ms": 0,
                "sticky": True
            }
        }
    }

    # Get mapper for this event type
    mapper = mappers.get(event_name, lambda d: {
        "event_type": "notification",
        "title": event_name,
        "message": f"Claude Code 事件: {event_name}",
        "severity": "info",
        "display": {
            "timeout_ms": 3000,
            "sticky": False,
            "play_sound": True
        }
    })

    # Build event
    event = mapper(hook_data)
    event.update({
        "session_id": session_id,
        "source": "claude-hook"
    })

    return event


def send_event(event: Dict) -> bool:
    """
    Send event to notifier service via HTTP POST.

    Args:
        event: Unified event dictionary

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        data = json.dumps(event).encode("utf-8")
        req = urllib.request.Request(
            NOTIFIER_URL,
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.status == 200

    except urllib.error.URLError:
        # Notifier not running - silent fail is OK
        return False
    except urllib.error.HTTPError:
        # Server error but notifier is running
        return False
    except (TimeoutError, OSError):
        # Network/timeout error
        return False
    except Exception:
        # Any other error - don't crash Claude
        return False


def main() -> None:
    """Main entry point for hook script."""
    try:
        # Read hook payload from stdin with size limit
        input_data = sys.stdin.read(MAX_STDIN_READ)
        if not input_data:
            # No input, nothing to do
            sys.exit(0)

        hook_data = json.loads(input_data)

        # Map to unified event format
        event = map_hook_to_event(hook_data)

        # Send to notifier (may fail silently)
        send_event(event)

        # Always exit 0 - don't block Claude
        sys.exit(0)

    except json.JSONDecodeError:
        # Invalid JSON - exit gracefully
        sys.exit(0)
    except Exception:
        # Any other error - don't crash Claude
        sys.exit(0)


if __name__ == "__main__":
    main()

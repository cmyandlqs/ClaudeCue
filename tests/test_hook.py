"""
Tests for the hook forwarding script.
"""
import json
import pytest
import sys
from io import StringIO

from hooks.notify_hook import map_hook_to_event


class TestHookMapper:
    """Test hook to event mapping function."""

    def test_all_supported_hook_types(self):
        """Test that all supported hook types produce valid events."""
        hook_types = [
            "Notification",
            "Stop",
            "StopFailure",
            "PermissionRequest",
            "PermissionDenied",
            "PreToolUse",
            "PostToolUseFailure",
            "TaskCreated",
            "TaskCompleted",
            "Elicitation"
        ]

        for hook_type in hook_types:
            hook_data = {
                "hook_event_name": hook_type,
                "session_id": "test-session"
            }

            event = map_hook_to_event(hook_data)

            # Verify required fields
            assert "event_type" in event
            assert "title" in event
            assert "message" in event
            assert "severity" in event
            assert "display" in event
            assert event["source"] == "claude-hook"
            assert event["session_id"] == "test-session"

    def test_notification_hook_fields(self):
        """Test Notification hook field mapping."""
        hook_data = {
            "hook_event_name": "Notification",
            "title": "Custom Title",
            "message": "Custom message",
            "session_id": "session-123"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "notification"
        assert event["title"] == "Custom Title"
        assert event["message"] == "Custom message"

    def test_stop_hook_message(self):
        """Test Stop hook produces appropriate message."""
        hook_data = {
            "hook_event_name": "Stop",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "stop"
        assert "任务" in event["title"] or "Task" in event["title"]
        assert event["display"]["timeout_ms"] == 3000

    def test_permission_request_sticky(self):
        """Test PermissionRequest produces sticky notification."""
        hook_data = {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "permission_request"
        assert event["display"]["sticky"] is True
        assert event["display"]["timeout_ms"] == 0  # No auto-close
        assert event["severity"] == "warning"

    def test_tool_use_includes_tool_name(self):
        """Test PreToolUse includes tool name in message."""
        hook_data = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Read",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "notification"
        assert "Read" in event["message"]
        assert event["display"]["play_sound"] is False  # Don't play for every tool

    def test_task_events_include_subject(self):
        """Test TaskCreated/TaskCompleted include subject."""
        hook_data = {
            "hook_event_name": "TaskCreated",
            "subject": "Build the project",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "notification"
        assert "Build the project" in event["message"]

    def test_elicitation_is_needs_input(self):
        """Test Elicitation maps to needs_input."""
        hook_data = {
            "hook_event_name": "Elicitation",
            "message": "Please enter your API key",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        assert event["event_type"] == "needs_input"
        assert "API key" in event["message"]
        assert event["display"]["sticky"] is True

    def test_display_config_defaults(self):
        """Test that display config has proper defaults."""
        hook_data = {
            "hook_event_name": "UnknownEvent",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)

        display = event["display"]
        assert "timeout_ms" in display
        assert "sticky" in display
        assert "play_sound" in display


class TestHookScript:
    """Integration tests for the hook script."""

    def test_main_exits_successfully(self):
        """Test that main() exits with code 0."""
        import subprocess

        # Test with valid JSON input
        result = subprocess.run(
            ["python", "hooks/notify_hook.py"],
            input='{"hook_event_name":"Stop","session_id":"test"}',
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should exit 0 even if notifier is not running
        assert result.returncode == 0

    def test_main_handles_invalid_json(self):
        """Test that main() handles invalid JSON gracefully."""
        import subprocess

        result = subprocess.run(
            ["python", "hooks/notify_hook.py"],
            input='not valid json',
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should exit 0, not crash
        assert result.returncode == 0

    def test_main_handles_empty_input(self):
        """Test that main() handles empty input."""
        import subprocess

        result = subprocess.run(
            ["python", "hooks/notify_hook.py"],
            input='',
            capture_output=True,
            text=True,
            timeout=5
        )

        # Should exit 0
        assert result.returncode == 0

"""
Tests for event mapping and event model.
"""
import json
from sys import path

# Add parent directory to path for imports
path.insert(0, ".")

from notifier.event_models import NotificationEvent, DisplayConfig


class TestNotificationEvent:
    """Test NotificationEvent dataclass."""

    def test_create_event(self):
        """Test creating a basic event."""
        event = NotificationEvent(
            event_type="notification",
            title="Test",
            message="Test message"
        )
        assert event.event_type == "notification"
        assert event.title == "Test"
        assert event.message == "Test message"
        assert event.severity == "info"

    def test_to_dict(self):
        """Test converting event to dictionary."""
        event = NotificationEvent(
            event_type="stop",
            title="Done",
            message="Task complete",
            severity="info"
        )
        data = event.to_dict()
        assert data["event_type"] == "stop"
        assert data["title"] == "Done"
        assert data["message"] == "Task complete"
        assert data["severity"] == "info"
        assert "display" in data

    def test_from_dict(self):
        """Test creating event from dictionary."""
        data = {
            "event_type": "notification",
            "title": "Alert",
            "message": "Something happened",
            "severity": "warning",
            "display": {"sticky": True, "play_sound": True, "timeout_ms": 5000}
        }
        event = NotificationEvent.from_dict(data)
        assert event.event_type == "notification"
        assert event.title == "Alert"
        assert event.message == "Something happened"
        assert event.severity == "warning"
        assert event.display.sticky is True

    def test_to_json(self):
        """Test converting event to JSON."""
        event = NotificationEvent(
            event_type="test",
            title="Test Event"
        )
        json_str = event.to_json()
        data = json.loads(json_str)
        assert data["event_type"] == "test"
        assert data["title"] == "Test Event"

    def test_from_json(self):
        """Test creating event from JSON."""
        json_str = '{"event_type":"test","title":"JSON Test","message":"From JSON"}'
        event = NotificationEvent.from_json(json_str)
        assert event.event_type == "test"
        assert event.title == "JSON Test"
        assert event.message == "From JSON"


class TestDisplayConfig:
    """Test DisplayConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = DisplayConfig()
        assert config.sticky is True
        assert config.play_sound is True
        assert config.timeout_ms == 5000

    def test_custom_values(self):
        """Test custom configuration values."""
        config = DisplayConfig(
            sticky=False,
            play_sound=False,
            timeout_ms=0
        )
        assert config.sticky is False
        assert config.play_sound is False
        assert config.timeout_ms == 0

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config = DisplayConfig(timeout_ms=3000)
        data = config.to_dict()
        assert data["timeout_ms"] == 3000
        assert data["sticky"] is True
        assert data["play_sound"] is True


class TestHookMapping:
    """Test hook to event mapping logic."""

    def test_notification_hook_mapping(self):
        """Test mapping Notification hook to event."""
        from hooks.notify_hook import map_hook_to_event

        hook_data = {
            "hook_event_name": "Notification",
            "title": "Test Title",
            "message": "Test Message",
            "session_id": "test-session-123"
        }

        event = map_hook_to_event(hook_data)
        assert event["event_type"] == "notification"
        assert event["title"] == "Test Title"
        assert event["message"] == "Test Message"
        assert event["session_id"] == "test-session-123"

    def test_stop_hook_mapping(self):
        """Test mapping Stop hook to event."""
        from hooks.notify_hook import map_hook_to_event

        hook_data = {
            "hook_event_name": "Stop",
            "session_id": "test-session"
        }

        event = map_hook_to_event(hook_data)
        assert event["event_type"] == "stop"
        assert "task" in event["title"].lower() or "任务" in event["title"]
        assert "completed" in event["message"].lower() or "完成" in event["message"]

    def test_permission_request_mapping(self):
        """Test mapping PermissionRequest hook to event."""
        from hooks.notify_hook import map_hook_to_event

        hook_data = {
            "hook_event_name": "PermissionRequest",
            "tool_name": "Bash",
            "session_id": "test-session"
        }

        event = map_hook_to_event(hook_data)
        assert event["event_type"] == "permission_request"
        assert "permission" in event["title"].lower() or "权限" in event["title"]
        assert "Bash" in event["message"]
        assert event["display"]["sticky"] is True
        assert event["display"]["timeout_ms"] == 0

    def test_unknown_hook_mapping(self):
        """Test mapping unknown hook type."""
        from hooks.notify_hook import map_hook_to_event

        hook_data = {
            "hook_event_name": "UnknownEvent",
            "session_id": "test"
        }

        event = map_hook_to_event(hook_data)
        assert event["event_type"] == "notification"
        assert "UnknownEvent" in event["title"]

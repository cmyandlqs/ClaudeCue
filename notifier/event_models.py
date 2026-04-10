"""
Unified event model for ccCue notifier.
Defines the data structures for events passed between hooks and notifier.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from typing import Optional
import uuid


class EventType(Enum):
    """Types of events that can be triggered."""
    NOTIFICATION = "notification"
    STOP = "stop"
    PERMISSION_REQUEST = "permission_request"
    NEEDS_INPUT = "needs_input"


class Severity(Enum):
    """Severity levels for notifications."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class DisplayConfig:
    """Display configuration for notifications."""
    sticky: bool = True
    play_sound: bool = True
    timeout_ms: int = 5000  # 0 = no auto-close

    def to_dict(self) -> dict:
        return {
            "sticky": self.sticky,
            "play_sound": self.play_sound,
            "timeout_ms": self.timeout_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DisplayConfig":
        return cls(
            sticky=data.get("sticky", True),
            play_sound=data.get("play_sound", True),
            timeout_ms=data.get("timeout_ms", 5000)
        )


@dataclass
class NotificationEvent:
    """
    Unified notification event model.
    This is the standard format for all events between hooks and notifier.
    """
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""
    severity: str = "info"
    title: str = ""
    message: str = ""
    source: str = "claude-hook"
    session_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    display: DisplayConfig = field(default_factory=DisplayConfig)

    def to_dict(self) -> dict:
        """Convert event to dictionary for JSON serialization."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "display": self.display.to_dict()
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "NotificationEvent":
        """Create event from dictionary."""
        display_data = data.get("display", {})
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=data.get("event_type", ""),
            severity=data.get("severity", "info"),
            title=data.get("title", ""),
            message=data.get("message", ""),
            source=data.get("source", "claude-hook"),
            session_id=data.get("session_id", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            display=DisplayConfig.from_dict(display_data)
        )

    @classmethod
    def from_json(cls, json_str: str) -> "NotificationEvent":
        """Create event from JSON string."""
        return cls.from_dict(json.loads(json_str))

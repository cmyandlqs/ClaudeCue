"""标准事件模型，对应开发文档 §9.3 的 JSON 结构。"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .constants import EventType, Severity


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class TerminalHint:
    window_title: str = ""
    cwd: str = ""


@dataclass
class MatchInfo:
    rule_id: str = ""
    pattern: str = ""
    sample_text: str = ""


@dataclass
class Timestamps:
    occurred_at: str = field(default_factory=_now_iso)
    sent_at: str = ""


@dataclass
class Display:
    sticky: bool = True
    play_sound: bool = True
    timeout_ms: int = 0


@dataclass
class EventObject:
    event_type: EventType
    severity: Severity
    title: str = ""
    message: str = ""
    source: str = "cc-wrapper"
    session_id: str = ""
    process_id: int = 0
    terminal_hint: TerminalHint = field(default_factory=TerminalHint)
    match: MatchInfo = field(default_factory=MatchInfo)
    timestamps: Timestamps = field(default_factory=Timestamps)
    display: Display = field(default_factory=Display)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "session_id": self.session_id,
            "process_id": self.process_id,
            "terminal_hint": {
                "window_title": self.terminal_hint.window_title,
                "cwd": self.terminal_hint.cwd,
            },
            "match": {
                "rule_id": self.match.rule_id,
                "pattern": self.match.pattern,
                "sample_text": self.match.sample_text[:200],
            },
            "timestamps": {
                "occurred_at": self.timestamps.occurred_at,
                "sent_at": self.timestamps.sent_at,
            },
            "display": {
                "sticky": self.display.sticky,
                "play_sound": self.display.play_sound,
                "timeout_ms": self.display.timeout_ms,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> EventObject:
        th = data.get("terminal_hint", {})
        mt = data.get("match", {})
        ts = data.get("timestamps", {})
        dp = data.get("display", {})
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=EventType(data["event_type"]),
            severity=Severity(data["severity"]),
            title=data.get("title", ""),
            message=data.get("message", ""),
            source=data.get("source", "cc-wrapper"),
            session_id=data.get("session_id", ""),
            process_id=data.get("process_id", 0),
            terminal_hint=TerminalHint(
                window_title=th.get("window_title", ""),
                cwd=th.get("cwd", ""),
            ),
            match=MatchInfo(
                rule_id=mt.get("rule_id", ""),
                pattern=mt.get("pattern", ""),
                sample_text=mt.get("sample_text", ""),
            ),
            timestamps=Timestamps(
                occurred_at=ts.get("occurred_at", _now_iso()),
                sent_at=ts.get("sent_at", ""),
            ),
            display=Display(
                sticky=dp.get("sticky", True),
                play_sound=dp.get("play_sound", True),
                timeout_ms=dp.get("timeout_ms", 0),
            ),
        )

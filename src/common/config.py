"""YAML 配置加载，支持 app.yaml + rules.yaml。"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

from .constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    IDLE_NOTIFY_SEC,
    IDLE_SUSPECTED_SEC,
    OVERLAY_HEIGHT,
    OVERLAY_OPACITY,
    OVERLAY_WIDTH,
)


@dataclass
class ServerConfig:
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT


@dataclass
class OverlayConfig:
    position: str = "bottom_right"
    width: int = OVERLAY_WIDTH
    height: int = OVERLAY_HEIGHT
    opacity: float = OVERLAY_OPACITY
    always_on_top: bool = True
    auto_close_ms_info: int = 5000
    auto_close_ms_warning: int = 0
    auto_close_ms_critical: int = 0


@dataclass
class SoundConfig:
    enabled: bool = True
    warning_sound: str = "default"
    critical_sound: str = "default"


@dataclass
class IdleConfig:
    suspected_after_sec: int = IDLE_SUSPECTED_SEC
    notify_after_sec: int = IDLE_NOTIFY_SEC


@dataclass
class FocusConfig:
    enabled: bool = True
    terminal_window_title_keywords: list[str] = field(
        default_factory=lambda: ["Claude", "Windows Terminal"]
    )


@dataclass
class LoggingConfig:
    level: str = "INFO"
    dir: str = "logs"


@dataclass
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    idle: IdleConfig = field(default_factory=IdleConfig)
    focus: FocusConfig = field(default_factory=FocusConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


@dataclass
class RuleDefinition:
    id: str
    enabled: bool = True
    event_type: str = ""
    severity: str = "info"
    match_type: str = "contains"  # contains | regex | any_of
    pattern: str = ""
    applies_to: list[str] = field(default_factory=lambda: ["stdout", "stderr"])


def _deep_update(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_update(result[k], v)
        else:
            result[k] = v
    return result


def _section_to_dataclass(cls, data: dict):
    """将 dict 映射到 dataclass，忽略多余字段。"""
    import dataclasses

    valid_keys = {f.name for f in dataclasses.fields(cls)}
    filtered = {k: v for k, v in data.items() if k in valid_keys}
    return cls(**filtered)


def load_app_config(path: Optional[str] = None) -> AppConfig:
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        raw = {}

    server = _section_to_dataclass(ServerConfig, raw.get("server", {}))
    overlay = _section_to_dataclass(OverlayConfig, raw.get("overlay", {}))
    sound = _section_to_dataclass(SoundConfig, raw.get("sound", {}))
    idle = _section_to_dataclass(IdleConfig, raw.get("idle", {}))
    focus = _section_to_dataclass(FocusConfig, raw.get("focus", {}))
    logging_cfg = _section_to_dataclass(LoggingConfig, raw.get("logging", {}))

    return AppConfig(
        server=server, overlay=overlay, sound=sound,
        idle=idle, focus=focus, logging=logging_cfg,
    )


def load_rules(path: Optional[str] = None) -> list[RuleDefinition]:
    if path and os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or []
    else:
        raw = []

    rules = []
    for item in raw:
        if isinstance(item, dict) and "id" in item:
            rules.append(RuleDefinition(
                id=item["id"],
                enabled=item.get("enabled", True),
                event_type=item.get("event_type", ""),
                severity=item.get("severity", "info"),
                match_type=item.get("match_type", "contains"),
                pattern=item.get("pattern", ""),
                applies_to=item.get("applies_to", ["stdout", "stderr"]),
            ))
    return rules

"""事件检测器 — 状态机 + 去重 + 规则匹配调度。"""

from __future__ import annotations

import time
from typing import Callable, Optional

from src.common.config import AppConfig
from src.common.constants import (
    DEDUP_INTERVAL_SEC,
    EventType,
    Severity,
    SessionState,
    EVENT_SEVERITY_MAP,
)
from src.common.logger import setup_logger
from src.common.models import EventObject, MatchInfo, TerminalHint, Timestamps, Display
from src.wrapper.client import NotifierClient
from src.wrapper.rule_engine import RuleEngine

logger = setup_logger("wrapper.event_detector")


class EventDetector:
    """事件检测器：维护状态机，对输出做规则匹配，去重后发送事件。"""

    def __init__(
        self,
        config: AppConfig,
        client: NotifierClient,
        rule_engine: RuleEngine,
        session_id: str = "",
        process_id: int = 0,
        cwd: str = "",
    ):
        self.config = config
        self.client = client
        self.rule_engine = rule_engine
        self.session_id = session_id
        self.process_id = process_id
        self.cwd = cwd

        self.state = SessionState.RUNNING
        self._last_event_time: dict[EventType, float] = {}
        self._idle_notified = False

    def process_line(self, line: str, source: str):
        """处理一行输出文本。"""
        hits = self.rule_engine.match(line, source)
        for rule, match_info in hits:
            self._handle_hit(rule.event_type, rule.severity, match_info, line)

    def check_idle(self, idle_seconds: float):
        """检查空闲状态。"""
        suspected_sec = self.config.idle.suspected_after_sec
        notify_sec = self.config.idle.notify_after_sec

        if self.state in (SessionState.COMPLETED, SessionState.EXITED):
            return

        if idle_seconds >= notify_sec and not self._idle_notified:
            self._transition(SessionState.IDLE_SUSPECTED)
            self._send_event(EventObject(
                event_type=EventType.IDLE_TIMEOUT,
                severity=Severity.WARNING,
                title="Claude Code 长时间无输出",
                message=f"已 {int(idle_seconds)} 秒无输出，可能需要你的关注。",
                session_id=self.session_id,
                process_id=self.process_id,
                terminal_hint=TerminalHint(cwd=self.cwd),
                display=Display(sticky=True, play_sound=True, timeout_ms=0),
            ))
            self._idle_notified = True

    def mark_exited(self):
        """标记进程已退出。"""
        self._transition(SessionState.EXITED)

    def _handle_hit(self, event_type_str: str, severity_str: str,
                    match_info: MatchInfo, line: str):
        try:
            event_type = EventType(event_type_str)
        except ValueError:
            logger.warning("未知事件类型: %s", event_type_str)
            return

        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = EVENT_SEVERITY_MAP.get(event_type, Severity.INFO)

        # 状态转换
        if event_type == EventType.PERMISSION_BLOCKED:
            self._transition(SessionState.WAITING_PERMISSION)
        elif event_type == EventType.NEEDS_INPUT:
            self._transition(SessionState.WAITING_INPUT)
        elif event_type == EventType.TASK_COMPLETED:
            self._transition(SessionState.COMPLETED)
        elif event_type == EventType.ERROR_DETECTED:
            pass  # 错误不改变状态

        # 去重
        if self._is_deduped(event_type):
            logger.debug("去重跳过: type=%s", event_type.value)
            return

        # 构建标题和消息
        title, message = self._build_text(event_type, line)

        # 空闲后恢复输出，重置空闲标记
        self._idle_notified = False

        event = EventObject(
            event_type=event_type,
            severity=severity,
            title=title,
            message=message,
            session_id=self.session_id,
            process_id=self.process_id,
            terminal_hint=TerminalHint(cwd=self.cwd),
            match=match_info,
            display=self._build_display(severity),
        )
        self._send_event(event)
        self._last_event_time[event_type] = time.monotonic()

    def _transition(self, new_state: SessionState):
        if self.state != new_state:
            logger.info("状态切换: %s → %s", self.state.value, new_state.value)
            self.state = new_state

    def _is_deduped(self, event_type: EventType) -> bool:
        last = self._last_event_time.get(event_type)
        if last is None:
            return False
        return (time.monotonic() - last) < DEDUP_INTERVAL_SEC

    def _build_text(self, event_type: EventType, line: str) -> tuple[str, str]:
        titles = {
            EventType.PERMISSION_BLOCKED: "Claude Code 等待权限批准",
            EventType.NEEDS_INPUT: "Claude Code 等待你的输入",
            EventType.TASK_COMPLETED: "任务已完成",
            EventType.ERROR_DETECTED: "Claude Code 遇到错误",
            EventType.IDLE_TIMEOUT: "Claude Code 长时间无输出",
        }
        title = titles.get(event_type, event_type.value)
        message = line[:200] if line else ""
        return title, message

    def _build_display(self, severity: Severity) -> Display:
        cfg = self.config.overlay
        timeout_map = {
            Severity.INFO: cfg.auto_close_ms_info,
            Severity.WARNING: cfg.auto_close_ms_warning,
            Severity.CRITICAL: cfg.auto_close_ms_critical,
        }
        timeout_ms = timeout_map.get(severity, 0)
        sticky = timeout_ms == 0
        play_sound = severity in (Severity.WARNING, Severity.CRITICAL)

        return Display(sticky=sticky, play_sound=play_sound, timeout_ms=timeout_ms)

    def _send_event(self, event: EventObject):
        self.client.send_event(event)

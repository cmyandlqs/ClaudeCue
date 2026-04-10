"""事件检测器单元测试 — 状态机、去重、空闲检测。"""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from src.common.config import AppConfig
from src.common.constants import EventType, SessionState
from src.wrapper.event_detector import EventDetector
from src.wrapper.rule_engine import RuleEngine


@pytest.fixture
def detector():
    config = AppConfig()
    client = MagicMock()
    engine = RuleEngine(custom_rules=[])
    return EventDetector(
        config=config,
        client=client,
        rule_engine=engine,
        session_id="test-session",
        process_id=999,
        cwd="/test",
    )


class TestStateMachine:
    def test_initial_state(self, detector):
        assert detector.state == SessionState.RUNNING

    def test_permission_transitions(self, detector):
        detector.process_line("Claude wants to read a file", "stdout")
        assert detector.state == SessionState.WAITING_PERMISSION

    def test_input_transitions(self, detector):
        detector.process_line("Press enter to continue", "stdout")
        assert detector.state == SessionState.WAITING_INPUT

    def test_completed_transitions(self, detector):
        detector.process_line("All tasks completed", "stdout")
        assert detector.state == SessionState.COMPLETED

    def test_exited(self, detector):
        detector.mark_exited()
        assert detector.state == SessionState.EXITED


class TestDedup:
    def test_same_event_deduped(self, detector):
        # 第一次命中
        detector.process_line("Claude wants to read file1", "stdout")
        call_count_1 = detector.client.send_event.call_count

        # 短时间内第二次命中 — 应被去重
        detector.process_line("Claude wants to read file2", "stdout")
        call_count_2 = detector.client.send_event.call_count

        assert call_count_2 == call_count_1  # 没有增加

    def test_different_events_not_deduped(self, detector):
        detector.process_line("Claude wants to read a file", "stdout")
        call_count_1 = detector.client.send_event.call_count

        detector.process_line("Press enter to continue", "stdout")
        call_count_2 = detector.client.send_event.call_count

        assert call_count_2 > call_count_1


class TestIdle:
    def test_idle_triggers_event(self, detector):
        # 模拟长时间空闲
        detector.check_idle(idle_seconds=150)
        assert detector.client.send_event.called

        # 检查事件类型
        last_call = detector.client.send_event.call_args_list[-1]
        event = last_call[0][0]
        assert event.event_type == EventType.IDLE_TIMEOUT

    def test_idle_not_triggered_when_completed(self, detector):
        detector.state = SessionState.COMPLETED
        detector.check_idle(idle_seconds=150)
        # IDLE_TIMEOUT 不应在 COMPLETED 状态触发
        idle_calls = [
            c for c in detector.client.send_event.call_args_list
            if c[0][0].event_type == EventType.IDLE_TIMEOUT
        ]
        assert len(idle_calls) == 0

    def test_idle_only_once(self, detector):
        detector.check_idle(idle_seconds=150)
        call_count_1 = detector.client.send_event.call_count

        detector.check_idle(idle_seconds=200)
        call_count_2 = detector.client.send_event.call_count

        # 不应重复触发
        assert call_count_2 == call_count_1


class TestEventContent:
    def test_event_has_correct_fields(self, detector):
        detector.process_line("Claude wants to read a file", "stdout")
        assert detector.client.send_event.called

        event = detector.client.send_event.call_args[0][0]
        assert event.event_type == EventType.PERMISSION_BLOCKED
        assert event.severity.value == "critical"
        assert event.session_id == "test-session"
        assert event.process_id == 999
        assert event.terminal_hint.cwd == "/test"

"""HTTP 接口测试 — /health、/events、/focus。"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from fastapi.testclient import TestClient

from src.notifier.server import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestHealth:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["service"] == "notifier-app"


class TestEvents:
    def _make_event(self, **overrides):
        base = {
            "event_id": "test-uuid-001",
            "event_type": "needs_input",
            "severity": "warning",
            "title": "测试标题",
            "message": "测试消息",
            "source": "cc-wrapper",
            "session_id": "test-session",
            "process_id": 12345,
            "terminal_hint": {"window_title": "Claude", "cwd": "/test"},
            "match": {"rule_id": "test.01", "pattern": "test", "sample_text": "test"},
            "timestamps": {"occurred_at": "2026-01-01T00:00:00+00:00", "sent_at": ""},
            "display": {"sticky": True, "play_sound": True, "timeout_ms": 0},
        }
        base.update(overrides)
        return base

    def test_post_event_accepted(self, client):
        received = []
        app = create_app(on_event=lambda d: received.append(d))
        tc = TestClient(app)

        event = self._make_event()
        resp = tc.post("/events", json=event)
        assert resp.status_code == 200
        assert resp.json()["accepted"] is True

    def test_post_event_missing_field(self, client):
        resp = client.post("/events", json={"event_id": "x"})
        assert resp.status_code == 422  # validation error

    def test_event_callback_called(self):
        received = []
        app = create_app(on_event=lambda d: received.append(d))
        tc = TestClient(app)

        event = self._make_event()
        tc.post("/events", json=event)

        assert len(received) == 1
        assert received[0]["event_type"] == "needs_input"

    def test_all_event_types(self, client):
        for etype in ["task_completed", "needs_input", "permission_blocked",
                       "error_detected", "idle_timeout", "process_started",
                       "process_exited"]:
            event = self._make_event(event_type=etype)
            resp = client.post("/events", json=event)
            assert resp.status_code == 200

    def test_all_severities(self, client):
        for sev in ["info", "warning", "critical"]:
            event = self._make_event(severity=sev)
            resp = client.post("/events", json=event)
            assert resp.status_code == 200


class TestFocus:
    def test_focus_endpoint(self, client):
        resp = client.post("/focus", json={"window_title": "Claude", "cwd": "/test"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_focus_callback(self):
        received = []
        app = create_app(on_focus=lambda d: received.append(d))
        tc = TestClient(app)

        tc.post("/focus", json={"window_title": "Windows Terminal"})
        assert len(received) == 1
        assert received[0]["window_title"] == "Windows Terminal"

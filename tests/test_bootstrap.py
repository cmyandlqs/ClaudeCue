from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from hooks import bootstrap

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".bootstrap_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_startup_hint_emits_once_per_session(monkeypatch):
    case_dir = _new_case_dir()
    try:
        monkeypatch.setenv("LOCALAPPDATA", str(case_dir))

        session_id = "session-one"
        first = bootstrap._should_emit_startup_hint(session_id)
        second = bootstrap._should_emit_startup_hint(session_id)

        assert first is True
        assert second is False

        cache_path = Path(case_dir) / "ccCue" / "runtime" / "seen_sessions.json"
        assert cache_path.exists()
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        assert session_id in data
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_startup_hint_event_shape():
    event = bootstrap._build_startup_hint_event("s-1")
    assert event["title"] == "ccCue Ready"
    assert event["event_type"] == "notification"
    assert event["session_id"] == "s-1"

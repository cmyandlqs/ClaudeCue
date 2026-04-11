"""Tests for doctor grading and remediation hints."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from cli.main import _print_doctor_result
from config.state_manager import MANAGED_EVENTS, SettingsStateManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".state_manager_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def _write_settings(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_doctor_returns_fail_for_critical_checks():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)

        result = manager.doctor(expected_hook_command=None, notifier_port=19527)

        assert result["overall"] == "FAIL"
        assert result["ok"] is False
        failed = [item for item in result["checks"] if not item["ok"]]
        assert any(item["name"] == "settings_exists" for item in failed)
        assert any("fix" in item for item in failed)
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_doctor_returns_warn_when_only_runtime_checks_fail():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)

        python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        bootstrap = PROJECT_ROOT / "hooks" / "bootstrap.py"
        command = manager.build_hook_command(str(python_exe), str(bootstrap))

        hooks = {}
        for event in MANAGED_EVENTS:
            hooks[event] = [{"hooks": [{"type": "command", "command": command}]}]
        _write_settings(settings_path, {"hooks": hooks})

        manager._check_notifier_health = lambda _port: False  # type: ignore[method-assign]
        manager._is_port_open = lambda _host, _port: False  # type: ignore[method-assign]
        manager._check_backup_index_integrity = lambda: (True, "ok")  # type: ignore[method-assign]

        result = manager.doctor(expected_hook_command=command, notifier_port=19527)

        assert result["overall"] == "WARN"
        assert result["ok"] is True
        warn_items = [item for item in result["checks"] if item.get("level") == "WARN" and not item["ok"]]
        assert len(warn_items) >= 2
        assert all("fix" in item for item in warn_items)
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_doctor_text_output_includes_fix(capsys):
    result = {
        "ok": True,
        "overall": "WARN",
        "checks": [
            {"name": "settings_exists", "ok": True, "detail": "ok", "level": "PASS"},
            {
                "name": "notifier_health",
                "ok": False,
                "detail": "http://127.0.0.1:19527/health",
                "level": "WARN",
                "fix": "Trigger a Claude hook event.",
            },
        ],
    }

    _print_doctor_result(result, as_json=False)
    out = capsys.readouterr().out
    assert "doctor: WARN" in out
    assert "[WARN] notifier_health" in out
    assert "fix: Trigger a Claude hook event." in out


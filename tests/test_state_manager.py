"""Tests for state manager safe install/uninstall/restore logic."""
from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path

from config.state_manager import SettingsStateManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".state_manager_tmp"


def _write_settings(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _new_case_dir() -> Path:
    case_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_install_creates_backup_and_baseline():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        bootstrap = PROJECT_ROOT / "hooks" / "bootstrap.py"

        _write_settings(settings_path, {"model": "gpt-5", "hooks": {"Custom": [{"hooks": []}]}})

        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)
        command = manager.build_hook_command(str(python_exe), str(bootstrap))
        result = manager.install(command)

        assert result.ok
        assert "backup_id" in result.data
        assert manager.baseline_path.exists()

        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        assert settings["model"] == "gpt-5"
        assert "Notification" in settings["hooks"]
        assert settings["hooks"]["Notification"][0]["hooks"][0]["command"] == command
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_restore_latest():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        bootstrap = PROJECT_ROOT / "hooks" / "bootstrap.py"

        _write_settings(settings_path, {"foo": "bar"})
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)

        command = manager.build_hook_command(str(python_exe), str(bootstrap))
        install_result = manager.install(command)
        assert install_result.ok

        _write_settings(settings_path, {"foo": "changed"})
        restored = manager.restore(latest=True)
        assert restored.ok

        current = json.loads(settings_path.read_text(encoding="utf-8"))
        assert current.get("foo") == "bar"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_validate_hook_command_rejects_unsafe():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)

        ok, reason = manager.validate_hook_command('python "x"; rm -rf /')
        assert not ok
        assert "unsafe" in reason
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_uninstall_restores_baseline():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        bootstrap = PROJECT_ROOT / "hooks" / "bootstrap.py"

        _write_settings(settings_path, {"model": "baseline"})
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)
        command = manager.build_hook_command(str(python_exe), str(bootstrap))
        assert manager.install(command).ok

        _write_settings(settings_path, {"model": "modified-after-install"})
        uninstall_result = manager.uninstall(restore_baseline=True)
        assert uninstall_result.ok

        current = json.loads(settings_path.read_text(encoding="utf-8"))
        assert current["model"] == "baseline"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_uninstall_with_purge_removes_state_dirs():
    case_dir = _new_case_dir()
    try:
        settings_path = case_dir / ".claude" / "settings.json"
        appdata_root = case_dir / "appdata"
        python_exe = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        bootstrap = PROJECT_ROOT / "hooks" / "bootstrap.py"

        _write_settings(settings_path, {"model": "baseline"})
        manager = SettingsStateManager(settings_path=settings_path, appdata_root=appdata_root)
        command = manager.build_hook_command(str(python_exe), str(bootstrap))
        assert manager.install(command).ok

        result = manager.uninstall(restore_baseline=True, purge=True)
        assert result.ok
        assert result.data.get("purged") is True
        assert not manager.backup_dir.exists()
        assert not manager.state_dir.exists()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)

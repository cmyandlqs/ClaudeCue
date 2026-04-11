"""State manager for safe settings.json mutation, backup and restore."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.error

MANAGED_EVENTS = ("Notification", "Stop", "PermissionRequest")
UNSAFE_COMMAND_CHARS = set(";&|`\n\r")
CHECK_LEVEL_FAIL = "FAIL"
CHECK_LEVEL_WARN = "WARN"
CHECK_LEVEL_PASS = "PASS"


@dataclass
class OperationResult:
    ok: bool
    message: str
    data: Dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _default_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def _default_appdata_root() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "ccCue"
    return Path.home() / ".cccue"


class SettingsStateManager:
    """Manage safe install/uninstall/restore lifecycle for Claude settings."""

    def __init__(
        self,
        settings_path: Optional[Path] = None,
        appdata_root: Optional[Path] = None,
    ) -> None:
        self.settings_path = Path(settings_path) if settings_path else _default_settings_path()
        self.appdata_root = Path(appdata_root) if appdata_root else _default_appdata_root()
        self.backup_dir = self.appdata_root / "backups"
        self.state_dir = self.appdata_root / "state"
        self.index_path = self.state_dir / "backup_index.json"
        self.baseline_path = self.state_dir / "baseline.json"

        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def build_hook_command(self, python_exe: str, bootstrap_script: str) -> str:
        return f'"{python_exe}" "{bootstrap_script}"'

    def validate_hook_command(self, command: str) -> tuple[bool, str]:
        if not command or not command.strip():
            return False, "empty hook command"

        if any(ch in command for ch in UNSAFE_COMMAND_CHARS):
            return False, "unsafe characters found in hook command"

        try:
            parts = shlex.split(command, posix=False)
        except ValueError as exc:
            return False, f"cannot parse command: {exc}"

        if len(parts) != 2:
            return False, "command must have exactly two parts: python_exe and bootstrap.py"

        python_part = Path(parts[0].strip('"'))
        script_part = Path(parts[1].strip('"'))

        if not python_part.exists():
            return False, f"python executable does not exist: {python_part}"

        if not script_part.exists():
            return False, f"bootstrap script does not exist: {script_part}"

        if script_part.name.lower() != "bootstrap.py":
            return False, "hook target must be bootstrap.py"

        return True, "ok"

    def install(self, hook_command: str) -> OperationResult:
        valid, reason = self.validate_hook_command(hook_command)
        if not valid:
            return OperationResult(False, f"invalid hook command: {reason}", {})

        action = "pre_install" if not self.baseline_path.exists() else "pre_update"
        backup_entry = self._create_backup(action)
        had_settings = self.settings_path.exists()
        old_bytes = self.settings_path.read_bytes() if had_settings else b""

        try:
            settings = self._load_settings_or_empty()
            hooks = settings.get("hooks")
            if hooks is None:
                hooks = {}
            if not isinstance(hooks, dict):
                raise ValueError("settings.hooks must be an object")

            for event in MANAGED_EVENTS:
                hooks[event] = [{"hooks": [{"type": "command", "command": hook_command}]}]

            settings["hooks"] = hooks
            self._write_settings(settings)
            self._validate_post_write(hook_command)

            if action == "pre_install" and not self.baseline_path.exists():
                self._write_baseline(backup_entry)

            return OperationResult(
                True,
                "install/update completed",
                {
                    "backup_id": backup_entry["id"],
                    "settings_path": str(self.settings_path),
                    "baseline_created": action == "pre_install",
                },
            )
        except Exception as exc:
            self._rollback_bytes(old_bytes, had_settings)
            return OperationResult(False, f"install failed and rolled back: {exc}", {})

    def uninstall(self, restore_baseline: bool = True, purge: bool = False) -> OperationResult:
        pre_backup = self._create_backup("pre_uninstall")
        had_settings = self.settings_path.exists()
        old_bytes = self.settings_path.read_bytes() if had_settings else b""

        try:
            if restore_baseline and self.baseline_path.exists():
                baseline = self._read_json(self.baseline_path)
                backup_id = str(baseline.get("backup_id", "")).strip()
                if not backup_id:
                    raise ValueError("baseline file missing backup_id")
                restore_result = self.restore(backup_id=backup_id, create_pre_restore=False)
                if not restore_result.ok:
                    raise ValueError(restore_result.message)
                result = OperationResult(
                    True,
                    "uninstall completed with baseline restore",
                    {
                        "pre_uninstall_backup_id": pre_backup["id"],
                        "restored_backup_id": backup_id,
                    },
                )
                if purge:
                    self._purge_state_files()
                    result.data["purged"] = True
                return result

            settings = self._load_settings_or_empty()
            hooks = settings.get("hooks")
            if isinstance(hooks, dict):
                for event in MANAGED_EVENTS:
                    if event in hooks and self._looks_managed_hook_entry(hooks[event]):
                        del hooks[event]
                settings["hooks"] = hooks

            self._write_settings(settings)
            self._validate_json_file(self.settings_path)
            result = OperationResult(
                True,
                "uninstall completed by removing managed hooks",
                {"pre_uninstall_backup_id": pre_backup["id"]},
            )
            if purge:
                self._purge_state_files()
                result.data["purged"] = True
            return result
        except Exception as exc:
            self._rollback_bytes(old_bytes, had_settings)
            return OperationResult(False, f"uninstall failed and rolled back: {exc}", {})

    def list_backups(self) -> List[Dict[str, Any]]:
        index = self._load_index()
        items = index.get("items", [])
        if not isinstance(items, list):
            return []
        return list(reversed(items))

    def restore(
        self,
        backup_id: Optional[str] = None,
        latest: bool = False,
        create_pre_restore: bool = True,
    ) -> OperationResult:
        index = self._load_index()
        items = index.get("items", []) if isinstance(index.get("items", []), list) else []

        target = None
        if latest:
            target = items[-1] if items else None
        elif backup_id:
            target = next((item for item in items if item.get("id") == backup_id), None)

        if target is None:
            return OperationResult(False, "target backup not found", {})

        if create_pre_restore:
            self._create_backup("pre_restore")

        backup_path = Path(target["path"])
        if not backup_path.exists():
            return OperationResult(False, f"backup file missing: {backup_path}", {})

        payload = backup_path.read_bytes()
        actual_hash = _sha256_bytes(payload)
        expected_hash = str(target.get("sha256", ""))
        if expected_hash and actual_hash != expected_hash:
            return OperationResult(False, f"backup hash mismatch for {target['id']}", {})

        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_bytes(payload)

        try:
            self._validate_json_file(self.settings_path)
        except Exception as exc:
            return OperationResult(False, f"restore wrote invalid json: {exc}", {})

        self._mark_backup_restored(str(target.get("id", "")))
        return OperationResult(True, "restore completed", {"restored_backup_id": target["id"]})

    def doctor(self, expected_hook_command: Optional[str] = None, notifier_port: int = 19527) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []

        def add_check(name: str, ok: bool, detail: str, level_on_fail: str, fix: str | None = None) -> None:
            level = CHECK_LEVEL_PASS if ok else level_on_fail
            check: Dict[str, Any] = {"name": name, "ok": ok, "detail": detail, "level": level}
            if fix and not ok:
                check["fix"] = fix
            checks.append(check)

        settings_ok = self.settings_path.exists()
        add_check(
            "settings_exists",
            settings_ok,
            str(self.settings_path),
            CHECK_LEVEL_FAIL,
            "Run: python -m cli.main install --source . --target \"%LOCALAPPDATA%\\ccCue\"",
        )

        parsed_settings: Optional[Dict[str, Any]] = None
        if settings_ok:
            try:
                parsed_settings = self._load_settings_or_empty()
                add_check("settings_json_valid", True, "valid json", CHECK_LEVEL_FAIL)
            except Exception as exc:
                add_check(
                    "settings_json_valid",
                    False,
                    str(exc),
                    CHECK_LEVEL_FAIL,
                    "Run: python -m cli.main restore --latest",
                )

        if parsed_settings is not None:
            hooks = parsed_settings.get("hooks")
            if not isinstance(hooks, dict):
                add_check(
                    "hooks_object_valid",
                    False,
                    "settings.hooks is not object",
                    CHECK_LEVEL_FAIL,
                    "Run: python -m cli.main restore --latest",
                )
            else:
                for event in MANAGED_EVENTS:
                    value = hooks.get(event)
                    ok, detail = self._validate_hook_entry_shape(value)
                    add_check(
                        f"hook_shape_{event}",
                        ok,
                        detail,
                        CHECK_LEVEL_FAIL,
                        "Run: python -m cli.main install --source . --target \"%LOCALAPPDATA%\\ccCue\"",
                    )

                    if expected_hook_command:
                        cmd_ok = self._extract_hook_command(value) == expected_hook_command
                        add_check(
                            f"hook_command_match_{event}",
                            cmd_ok,
                            self._extract_hook_command(value) or "missing",
                            CHECK_LEVEL_FAIL,
                            "Run: python -m cli.main install --source . --target \"%LOCALAPPDATA%\\ccCue\"",
                        )

        backup_ok, backup_detail = self._check_backup_index_integrity()
        add_check(
            "backup_index_integrity",
            backup_ok,
            backup_detail,
            CHECK_LEVEL_WARN,
            "Run: python -m cli.main uninstall --purge",
        )

        notifier_ok = self._check_notifier_health(notifier_port)
        add_check(
            "notifier_health",
            notifier_ok,
            f"http://127.0.0.1:{notifier_port}/health",
            CHECK_LEVEL_WARN,
            "Trigger a Claude hook event, or start manually: python -m notifier.main",
        )

        port_open = self._is_port_open("127.0.0.1", notifier_port)
        add_check(
            "port_occupied",
            port_open,
            f"127.0.0.1:{notifier_port}",
            CHECK_LEVEL_WARN,
            "Check notifier process and retry: python -m cli.main doctor --json",
        )

        overall = CHECK_LEVEL_PASS
        if any((not c["ok"]) and c["level"] == CHECK_LEVEL_FAIL for c in checks):
            overall = CHECK_LEVEL_FAIL
        elif any((not c["ok"]) and c["level"] == CHECK_LEVEL_WARN for c in checks):
            overall = CHECK_LEVEL_WARN

        return {"ok": overall != CHECK_LEVEL_FAIL, "overall": overall, "checks": checks}

    def _validate_post_write(self, hook_command: str) -> None:
        settings = self._load_settings_or_empty()
        hooks = settings.get("hooks")
        if not isinstance(hooks, dict):
            raise ValueError("settings.hooks is not an object after write")

        for event in MANAGED_EVENTS:
            value = hooks.get(event)
            ok, detail = self._validate_hook_entry_shape(value)
            if not ok:
                raise ValueError(f"{event} invalid: {detail}")
            cmd = self._extract_hook_command(value)
            if cmd != hook_command:
                raise ValueError(f"{event} command mismatch")

    def _looks_managed_hook_entry(self, value: Any) -> bool:
        command = self._extract_hook_command(value)
        if not command:
            return False
        return "bootstrap.py" in command.lower() and ("cccue" in command.lower() or "hooks" in command.lower())

    def _extract_hook_command(self, value: Any) -> Optional[str]:
        try:
            command = value[0]["hooks"][0]["command"]
            if isinstance(command, str):
                return command
        except (IndexError, KeyError, TypeError):
            return None
        return None

    def _validate_hook_entry_shape(self, value: Any) -> tuple[bool, str]:
        command = self._extract_hook_command(value)
        if command is None:
            return False, "expected hooks[0].hooks[0].command"
        valid, reason = self.validate_hook_command(command)
        if not valid:
            return False, reason
        return True, "ok"

    def _load_settings_or_empty(self) -> Dict[str, Any]:
        if not self.settings_path.exists():
            return {}
        data = self._read_json(self.settings_path)
        if not isinstance(data, dict):
            raise ValueError("settings root must be an object")
        return data

    def _write_settings(self, settings: Dict[str, Any]) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(settings, ensure_ascii=False, indent=2)
        self.settings_path.write_text(text, encoding="utf-8")

    def _create_backup(self, action: str) -> Dict[str, Any]:
        payload = b"{}"
        if self.settings_path.exists():
            payload = self.settings_path.read_bytes()

        ts = _utc_now()
        suffix = re.sub(r"[^a-z0-9_\-]", "_", action.lower())
        backup_id = f"{ts}_{len(self._load_index().get('items', [])) + 1:04d}"
        backup_file = self.backup_dir / f"settings.{ts}.{suffix}.{backup_id}.json"
        backup_file.write_bytes(payload)

        entry = {
            "id": backup_id,
            "timestamp": _iso_now(),
            "action": action,
            "path": str(backup_file),
            "sha256": _sha256_bytes(payload),
            "restored": False,
        }

        index = self._load_index()
        items = index.setdefault("items", [])
        if not isinstance(items, list):
            items = []
            index["items"] = items
        items.append(entry)
        self._write_json(self.index_path, index)
        return entry

    def _write_baseline(self, backup_entry: Dict[str, Any]) -> None:
        baseline = {
            "created_at": _iso_now(),
            "backup_id": backup_entry["id"],
            "path": backup_entry["path"],
            "sha256": backup_entry["sha256"],
        }
        self._write_json(self.baseline_path, baseline)

    def _rollback_bytes(self, old_bytes: bytes, had_settings: bool) -> None:
        if had_settings:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_bytes(old_bytes)
        elif self.settings_path.exists():
            self.settings_path.unlink()

    def _check_notifier_health(self, port: int) -> bool:
        url = f"http://127.0.0.1:{port}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=0.3) as response:
                return response.status == 200
        except Exception:
            return False

    def _is_port_open(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            return sock.connect_ex((host, port)) == 0

    def _check_backup_index_integrity(self) -> tuple[bool, str]:
        index = self._load_index()
        items = index.get("items", [])
        if not isinstance(items, list):
            return False, "backup index items is not a list"

        for item in items:
            try:
                path = Path(item["path"])
                if not path.exists():
                    return False, f"missing backup: {path}"
                expected_hash = str(item.get("sha256", ""))
                if expected_hash:
                    actual_hash = _sha256_bytes(path.read_bytes())
                    if actual_hash != expected_hash:
                        return False, f"hash mismatch: {item.get('id', 'unknown')}"
            except Exception as exc:
                return False, f"invalid index entry: {exc}"

        return True, "ok"

    def _load_index(self) -> Dict[str, Any]:
        if not self.index_path.exists():
            return {"items": []}
        data = self._read_json(self.index_path)
        if not isinstance(data, dict):
            return {"items": []}
        return data

    def _mark_backup_restored(self, backup_id: str) -> None:
        if not backup_id:
            return
        index = self._load_index()
        items = index.get("items", [])
        if not isinstance(items, list):
            return
        changed = False
        for item in items:
            if item.get("id") == backup_id:
                item["restored"] = True
                item["restored_at"] = _iso_now()
                changed = True
                break
        if changed:
            self._write_json(self.index_path, index)

    def _purge_state_files(self) -> None:
        shutil.rmtree(self.backup_dir, ignore_errors=True)
        shutil.rmtree(self.state_dir, ignore_errors=True)

    def _validate_json_file(self, file_path: Path) -> None:
        self._read_json(file_path)

    def _read_json(self, file_path: Path) -> Dict[str, Any]:
        text = file_path.read_text(encoding="utf-8")
        return json.loads(text)

    def _write_json(self, file_path: Path, data: Dict[str, Any]) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

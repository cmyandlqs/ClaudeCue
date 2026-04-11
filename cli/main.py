"""CLI for ccCue install/uninstall/doctor/restore workflows."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from config.state_manager import SettingsStateManager
from installer.runtime_installer import install_runtime


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_python_exe(explicit_python: str | None, target_root: Path) -> str:
    if explicit_python and explicit_python.strip():
        return explicit_python

    bundled_python = target_root / "runtime" / "python" / "python.exe"
    if bundled_python.exists():
        return str(bundled_python)

    local_venv_python = target_root / ".venv" / "Scripts" / "python.exe"
    if local_venv_python.exists():
        return str(local_venv_python)

    return sys.executable


def _print_doctor_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    overall = str(result.get("overall", "PASS" if result.get("ok") else "FAIL")).upper()
    print(f"doctor: {overall}")
    for check in result.get("checks", []):
        mark = f"[{check.get('level', 'PASS')}]"
        print(f"{mark} {check.get('name')}: {check.get('detail')}")
        if (not check.get("ok")) and check.get("fix"):
            print(f"      fix: {check.get('fix')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cccue", description="ccCue productization CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install runtime + configure hooks")
    install_p.add_argument("--python-exe", default=None, help="Override python executable used for hook command")
    install_p.add_argument("--source", default=str(_project_root()), help="Runtime source directory")
    install_p.add_argument("--target", default=None, help="Runtime install target (default: %LOCALAPPDATA%\\ccCue)")
    install_p.add_argument("--project-root", default=None, help="DEPRECATED: config-only mode root")

    uninstall_p = sub.add_parser("uninstall", help="Uninstall ccCue configuration")
    uninstall_p.add_argument("--no-restore", action="store_true", help="Do not restore baseline snapshot")
    uninstall_p.add_argument("--purge", action="store_true", help="Remove ccCue backup/state files after uninstall")

    doctor_p = sub.add_parser("doctor", help="Run health checks")
    doctor_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    doctor_p.add_argument("--python-exe", default=None, help="Override python executable used for expected command")
    doctor_p.add_argument("--project-root", default=str(_project_root()))

    restore_p = sub.add_parser("restore", help="Restore settings from backup")
    restore_group = restore_p.add_mutually_exclusive_group(required=True)
    restore_group.add_argument("--latest", action="store_true", help="Restore latest backup")
    restore_group.add_argument("--id", dest="backup_id", help="Restore specific backup id")

    sub.add_parser("list-backups", help="List known backups")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    manager = SettingsStateManager()

    if args.command == "install":
        # Backward-compatible mode: only configure hooks against existing root
        if args.project_root:
            project_root = Path(args.project_root)
            bootstrap_script = project_root / "hooks" / "bootstrap.py"
            python_exe = _resolve_python_exe(args.python_exe, project_root)
            hook_command = manager.build_hook_command(python_exe, str(bootstrap_script))
            result = manager.install(hook_command)
            print(result.message)
            if result.data:
                print(json.dumps(result.data, ensure_ascii=False, indent=2))
            return 0 if result.ok else 1

        source_root = Path(args.source)
        default_target = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "ccCue"
        target_root = Path(args.target) if args.target else default_target

        runtime_result = install_runtime(source_root, target_root)
        if not runtime_result.ok:
            print(runtime_result.message)
            return 1

        bootstrap_script = target_root / "hooks" / "bootstrap.py"
        python_exe = _resolve_python_exe(args.python_exe, target_root)
        hook_command = manager.build_hook_command(python_exe, str(bootstrap_script))
        result = manager.install(hook_command)
        if result.data:
            result.data["runtime_target"] = str(target_root)
            result.data["runtime_source"] = str(source_root)
        print(result.message)
        if result.data:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    if args.command == "uninstall":
        result = manager.uninstall(restore_baseline=not args.no_restore, purge=args.purge)
        print(result.message)
        if result.data:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    if args.command == "doctor":
        project_root = Path(args.project_root)
        bootstrap_script = project_root / "hooks" / "bootstrap.py"
        python_exe = _resolve_python_exe(args.python_exe, project_root)
        expected_command = manager.build_hook_command(python_exe, str(bootstrap_script))
        result = manager.doctor(expected_hook_command=expected_command)
        _print_doctor_result(result, as_json=args.json)
        return 0 if result.get("ok") else 1

    if args.command == "restore":
        if args.latest:
            result = manager.restore(latest=True)
        else:
            result = manager.restore(backup_id=args.backup_id)
        print(result.message)
        if result.data:
            print(json.dumps(result.data, ensure_ascii=False, indent=2))
        return 0 if result.ok else 1

    if args.command == "list-backups":
        backups = manager.list_backups()
        print(json.dumps(backups, ensure_ascii=False, indent=2))
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

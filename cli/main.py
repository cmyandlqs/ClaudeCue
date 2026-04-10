"""CLI for ccCue install/uninstall/doctor/restore workflows."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config.state_manager import SettingsStateManager


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _print_doctor_result(result: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    status = "OK" if result.get("ok") else "ISSUES"
    print(f"doctor: {status}")
    for check in result.get("checks", []):
        mark = "[OK]" if check.get("ok") else "[FAIL]"
        print(f"{mark} {check.get('name')}: {check.get('detail')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cccue", description="ccCue productization CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    install_p = sub.add_parser("install", help="Install/update ccCue hook configuration")
    install_p.add_argument("--python-exe", default=sys.executable)
    install_p.add_argument("--project-root", default=str(_project_root()))

    uninstall_p = sub.add_parser("uninstall", help="Uninstall ccCue configuration")
    uninstall_p.add_argument("--no-restore", action="store_true", help="Do not restore baseline snapshot")
    uninstall_p.add_argument("--purge", action="store_true", help="Remove ccCue backup/state files after uninstall")

    doctor_p = sub.add_parser("doctor", help="Run health checks")
    doctor_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    doctor_p.add_argument("--python-exe", default=sys.executable)
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
        project_root = Path(args.project_root)
        bootstrap_script = project_root / "hooks" / "bootstrap.py"
        hook_command = manager.build_hook_command(args.python_exe, str(bootstrap_script))
        result = manager.install(hook_command)
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
        expected_command = manager.build_hook_command(args.python_exe, str(bootstrap_script))
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

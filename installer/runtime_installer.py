"""Install ccCue runtime files into target directory."""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

RUNTIME_DIRS = ("hooks", "notifier", "cli", "config", "installer")
RUNTIME_FILES = ("requirements.txt", "AGENTS.md", "CLAUDE.md")


@dataclass
class RuntimeInstallResult:
    ok: bool
    message: str
    target: Path


def _copy_dir(src: Path, dst: Path) -> None:
    shutil.copytree(
        src,
        dst,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".pytest_cache", ".venv"),
    )


def install_runtime(source_root: Path, target_root: Path) -> RuntimeInstallResult:
    source_root = source_root.resolve()
    target_root = target_root.resolve()

    if not source_root.exists():
        return RuntimeInstallResult(False, f"source does not exist: {source_root}", target_root)

    missing = [name for name in RUNTIME_DIRS if not (source_root / name).exists()]
    if missing:
        return RuntimeInstallResult(False, f"source missing required directories: {', '.join(missing)}", target_root)

    staging = target_root.parent / f"{target_root.name}.staging"
    backup = target_root.parent / f"{target_root.name}.backup"

    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    try:
        for dirname in RUNTIME_DIRS:
            _copy_dir(source_root / dirname, staging / dirname)

        for filename in RUNTIME_FILES:
            src = source_root / filename
            if src.exists():
                shutil.copy2(src, staging / filename)

        if target_root.exists():
            target_root.rename(backup)

        staging.rename(target_root)

        shutil.rmtree(backup, ignore_errors=True)
        return RuntimeInstallResult(True, "runtime installed", target_root)
    except Exception as exc:
        # rollback
        shutil.rmtree(staging, ignore_errors=True)
        if not target_root.exists() and backup.exists():
            backup.rename(target_root)
        return RuntimeInstallResult(False, f"runtime install failed: {exc}", target_root)

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from installer.runtime_installer import install_runtime

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".runtime_installer_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_install_runtime_to_target():
    case_dir = _new_case_dir()
    try:
        src = PROJECT_ROOT
        dst = case_dir / "target"
        result = install_runtime(src, dst)
        assert result.ok
        assert (dst / "hooks" / "bootstrap.py").exists()
        assert (dst / "cli" / "main.py").exists()
        assert (dst / "notifier" / "main.py").exists()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_install_runtime_copies_optional_runtime_when_present():
    case_dir = _new_case_dir()
    try:
        src = case_dir / "src"
        dst = case_dir / "target"

        for dirname in ("hooks", "notifier", "cli", "config", "installer"):
            dir_path = src / dirname
            dir_path.mkdir(parents=True, exist_ok=True)
            (dir_path / ".keep").write_text("x", encoding="utf-8")

        runtime_python = src / "runtime" / "python" / "python.exe"
        runtime_python.parent.mkdir(parents=True, exist_ok=True)
        runtime_python.write_text("x", encoding="utf-8")

        result = install_runtime(src, dst)
        assert result.ok
        assert (dst / "runtime" / "python" / "python.exe").exists()
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)

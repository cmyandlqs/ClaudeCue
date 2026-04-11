from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from cli.main import _resolve_python_exe

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_TMP_ROOT = PROJECT_ROOT / "tests" / ".bootstrap_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_TMP_ROOT / uuid.uuid4().hex
    case_dir.mkdir(parents=True, exist_ok=True)
    return case_dir


def test_resolve_python_exe_prefers_explicit():
    case_dir = _new_case_dir()
    try:
        target_root = case_dir / "target"
        target_root.mkdir(parents=True, exist_ok=True)
        resolved = _resolve_python_exe("C:\\custom\\python.exe", target_root)
        assert resolved == "C:\\custom\\python.exe"
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


def test_resolve_python_exe_prefers_bundled_runtime():
    case_dir = _new_case_dir()
    try:
        target_root = case_dir / "target"
        bundled = target_root / "runtime" / "python" / "python.exe"
        bundled.parent.mkdir(parents=True, exist_ok=True)
        bundled.write_text("", encoding="utf-8")

        resolved = _resolve_python_exe(None, target_root)
        assert resolved == str(bundled)
    finally:
        shutil.rmtree(case_dir, ignore_errors=True)


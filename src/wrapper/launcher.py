"""Claude Code 进程启动器。"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

from src.common.config import AppConfig
from src.common.constants import EventType, Severity
from src.common.logger import setup_logger
from src.common.models import EventObject, TerminalHint, Timestamps

logger = setup_logger("wrapper.launcher")


class Launcher:
    """启动并管理 Claude Code 子进程。"""

    def __init__(self, config: AppConfig, cwd: Optional[str] = None):
        self.config = config
        self.cwd = cwd or os.getcwd()
        self.process: Optional[subprocess.Popen] = None
        self.pid: int = 0
        self.session_id: str = ""
        self.started_at: str = ""

    def start(self, extra_args: Optional[list[str]] = None) -> subprocess.Popen:
        cmd = [sys.executable, "-m", "claude"]
        if extra_args:
            cmd.extend(extra_args)

        logger.info("启动 Claude Code: %s (cwd=%s)", " ".join(cmd), self.cwd)

        self.process = subprocess.Popen(
            cmd,
            stdin=sys.stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.cwd,
            bufsize=1,
        )
        self.pid = self.process.pid
        self.session_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + str(self.pid)
        self.started_at = datetime.now(timezone.utc).isoformat()

        logger.info("Claude Code 已启动: PID=%d session=%s", self.pid, self.session_id)
        return self.process

    def build_started_event(self) -> EventObject:
        return EventObject(
            event_type=EventType.PROCESS_STARTED,
            severity=Severity.INFO,
            title="Claude Code 已启动",
            message=f"PID={self.pid}, cwd={self.cwd}",
            session_id=self.session_id,
            process_id=self.pid,
            terminal_hint=TerminalHint(cwd=self.cwd),
            timestamps=Timestamps(occurred_at=self.started_at),
        )

    def build_exited_event(self, exit_code: int) -> EventObject:
        return EventObject(
            event_type=EventType.PROCESS_EXITED,
            severity=Severity.INFO if exit_code == 0 else Severity.CRITICAL,
            title="Claude Code 已退出",
            message=f"退出码={exit_code}",
            session_id=self.session_id,
            process_id=self.pid,
            terminal_hint=TerminalHint(cwd=self.cwd),
        )

    def wait(self) -> int:
        """等待进程退出，返回退出码。"""
        if self.process:
            return self.process.wait()
        return -1

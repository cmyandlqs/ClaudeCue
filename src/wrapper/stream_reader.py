"""Claude Code 输出流读取器。"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from src.common.logger import setup_logger

logger = setup_logger("wrapper.stream_reader")


class StreamReader:
    """分别读取 stdout 和 stderr，按行回调。"""

    def __init__(
        self,
        process,  # subprocess.Popen
        on_line: Optional[Callable[[str, str], None]] = None,
        on_idle_check: Optional[Callable[[], None]] = None,
        idle_interval: float = 5.0,
    ):
        self.process = process
        self.on_line = on_line  # (line_text, source) source="stdout"|"stderr"
        self.on_idle_check = on_idle_check
        self.idle_interval = idle_interval
        self.last_output_time = time.monotonic()
        self._stop_event = threading.Event()

    def start(self):
        """启动读取线程。"""
        t_out = threading.Thread(target=self._read_stream, args=("stdout", self.process.stdout), daemon=True)
        t_err = threading.Thread(target=self._read_stream, args=("stderr", self.process.stderr), daemon=True)
        t_idle = threading.Thread(target=self._idle_monitor, daemon=True)

        t_out.start()
        t_err.start()
        t_idle.start()

        return t_out, t_err, t_idle

    def stop(self):
        self._stop_event.set()

    def _read_stream(self, source: str, stream):
        """读取单个流。"""
        try:
            for raw_line in iter(stream.readline, b""):
                if self._stop_event.is_set():
                    break
                try:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                except Exception:
                    line = raw_line.decode("latin-1", errors="replace").rstrip("\r\n")

                self.last_output_time = time.monotonic()

                if self.on_line and line.strip():
                    self.on_line(line, source)
        except ValueError:
            pass  # stream closed
        finally:
            try:
                stream.close()
            except Exception:
                pass

    def _idle_monitor(self):
        """定期检查是否空闲。"""
        while not self._stop_event.is_set():
            self._stop_event.wait(self.idle_interval)
            if not self._stop_event.is_set() and self.on_idle_check:
                self.on_idle_check()

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self.last_output_time

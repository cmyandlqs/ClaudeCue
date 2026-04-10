"""终端窗口聚焦 — 通过 Win32 API 将 Windows Terminal 置前。"""

from __future__ import annotations

import ctypes
import platform
from typing import Optional

from src.common.logger import setup_logger

logger = setup_logger("notifier.window_focus")

_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32


def find_window_by_title_keyword(keywords: list[str]) -> Optional[int]:
    """通过窗口标题关键词查找窗口句柄。"""
    if not _IS_WINDOWS:
        return None

    found_hwnd = ctypes.c_void_p(0)

    def enum_callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value

        for kw in keywords:
            if kw.lower() in title.lower():
                found_hwnd.value = hwnd
                return False  # 停止枚举
        return True

    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(callback_type(enum_callback), 0)

    return found_hwnd.value if found_hwnd.value else None


def focus_window(hwnd: int) -> bool:
    """将指定窗口置前。"""
    if not _IS_WINDOWS or not hwnd:
        return False

    try:
        # 允许 SetForegroundWindow 工作
        user32.AllowSetForegroundWindow(ctypes.windll.kernel32.GetCurrentProcessId())

        # 如果窗口最小化则恢复
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE

        user32.SetForegroundWindow(hwnd)
        logger.info("窗口聚焦成功: hwnd=%d", hwnd)
        return True
    except Exception as e:
        logger.warning("窗口聚焦失败: %s", e)
        return False


def focus_terminal(keywords: list[str]) -> bool:
    """查找并聚焦终端窗口。"""
    hwnd = find_window_by_title_keyword(keywords)
    if not hwnd:
        logger.warning("未找到匹配的终端窗口 (keywords=%s)", keywords)
        return False
    return focus_window(hwnd)

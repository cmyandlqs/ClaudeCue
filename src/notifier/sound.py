"""提醒声音模块 — 使用 winsound 播放系统声音。"""

from __future__ import annotations

import platform

from src.common.constants import Severity
from src.common.logger import setup_logger

logger = setup_logger("notifier.sound")

_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    import winsound


# 严重级别对应的 Windows 系统声音
SEVERITY_SOUNDS = {
    Severity.WARNING: "SystemAsterisk",
    Severity.CRITICAL: "SystemExclamation",
}


def play(severity: Severity, enabled: bool = True):
    """播放对应严重级别的系统声音。"""
    if not enabled or not _IS_WINDOWS:
        return

    sound_name = SEVERITY_SOUNDS.get(severity)
    if not sound_name:
        return

    try:
        winsound.PlaySound(sound_name, winsound.SND_ALIAS | winsound.SND_ASYNC)
        logger.debug("播放声音: %s (severity=%s)", sound_name, severity.value)
    except RuntimeError as e:
        logger.warning("声音播放失败: %s", e)

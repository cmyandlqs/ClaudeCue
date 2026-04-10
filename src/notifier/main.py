"""notifier-app 入口 — 常驻桌面程序。"""

import sys
from pathlib import Path

# 将项目根目录加入 sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication

from src.common.config import load_app_config
from src.common.constants import Severity
from src.common.logger import setup_logger
from src.notifier.overlay import OverlayWindow
from src.notifier.server import ServerThread
from src.notifier.sound import play
from src.notifier.tray import TrayIcon
from src.notifier.window_focus import focus_terminal


def main():
    # 加载配置
    config_path = ROOT / "config" / "app.yaml"
    config = load_app_config(str(config_path) if config_path.exists() else None)

    logger = setup_logger("notifier", config.logging.level, config.logging.dir)
    logger.info("启动 notifier-app，端口=%s:%d", config.server.host, config.server.port)

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 悬浮窗
    overlay = OverlayWindow()

    # 悬浮窗点击 → 聚焦终端
    def _on_overlay_click():
        if config.focus.enabled:
            ok = focus_terminal(config.focus.terminal_window_title_keywords)
            if not ok:
                logger.warning("未能自动切回终端，请手动切换")

    overlay.focus_requested.connect(_on_overlay_click)

    # 事件回调：从 HTTP 线程转发到 UI 线程
    def on_event(data: dict):
        # 播放声音
        play_sound = data.get("display", {}).get("play_sound", False)
        if play_sound and config.sound.enabled:
            try:
                severity = Severity(data.get("severity", "info"))
            except ValueError:
                severity = Severity.INFO
            play(severity, enabled=True)

        # 展示悬浮窗
        overlay.show_event(data)

    def on_focus(data: dict):
        keywords = config.focus.terminal_window_title_keywords
        if data.get("window_title"):
            keywords = [data["window_title"]] + keywords
        focus_terminal(keywords)

    # HTTP 服务线程
    server = ServerThread(config, on_event=on_event, on_focus=on_focus)
    server.start()
    logger.info("HTTP 服务已启动")

    # 系统托盘
    tray = TrayIcon(app, on_quit=lambda: logger.info("退出 notifier-app"))

    logger.info("notifier-app 就绪")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

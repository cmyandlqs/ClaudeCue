"""系统托盘图标与菜单。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from src.common.logger import setup_logger

logger = setup_logger("notifier.tray")


class TrayIcon:
    """系统托盘管理器。"""

    def __init__(
        self,
        app: QApplication,
        on_quit: Optional[Callable] = None,
        on_status: Optional[Callable] = None,
    ):
        self._app = app
        self._on_quit = on_quit
        self._tray = QSystemTrayIcon(app)

        # 使用系统默认应用图标
        self._tray.setIcon(QIcon.fromTheme("application-x-executable"))
        self._tray.setToolTip("Claude Code 提醒助手")

        self._menu = QMenu()
        self._status_action = self._menu.addAction("状态: 运行中")
        self._status_action.setEnabled(False)
        self._menu.addSeparator()

        quit_action = self._menu.addAction("退出")
        quit_action.triggered.connect(self._handle_quit)

        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _handle_quit(self):
        logger.info("用户从托盘退出")
        if self._on_quit:
            self._on_quit()
        self._app.quit()

    def update_status(self, text: str):
        self._status_action.setText(f"状态: {text}")

"""置顶悬浮提醒窗 — PySide6 实现。"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.common.constants import Severity

# 严重级别对应的颜色
SEVERITY_COLORS = {
    Severity.INFO: ("#2196F3", "#E3F2FD"),      # 蓝色
    Severity.WARNING: ("#FF9800", "#FFF3E0"),    # 橙色
    Severity.CRITICAL: ("#F44336", "#FFEBEE"),   # 红色
}

SEVERITY_ICONS = {
    Severity.INFO: "i",
    Severity.WARNING: "!",
    Severity.CRITICAL: "!!",
}


class OverlayWindow(QWidget):
    """始终置顶的悬浮提醒窗口。"""

    focus_requested = Signal()  # 用户点击主体请求聚焦终端

    def __init__(self, parent=None):
        super().__init__(parent)
        self._auto_close_timer = QTimer(self)
        self._auto_close_timer.setSingleShot(True)
        self._auto_close_timer.timeout.connect(self.hide)

        self._init_ui()
        self._position_window()

    def _init_ui(self):
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(360, 120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # 标题行：级别图标 + 标题 + 关闭按钮
        header = QHBoxLayout()
        self._icon_label = QLabel("")
        self._icon_label.setFixedWidth(24)
        self._icon_label.setFont(QFont("", 14, QFont.Bold))
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel("")
        self._title_label.setFont(QFont("", 10, QFont.Bold))
        self._title_label.setWordWrap(True)

        self._close_btn = QPushButton("x")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setFont(QFont("", 10))
        self._close_btn.clicked.connect(self._on_close)

        header.addWidget(self._icon_label)
        header.addWidget(self._title_label, 1)
        header.addWidget(self._close_btn)
        layout.addLayout(header)

        # 消息内容
        self._msg_label = QLabel("")
        self._msg_label.setFont(QFont("", 9))
        self._msg_label.setWordWrap(True)
        self._msg_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._msg_label, 1)

        # 点击主体聚焦终端
        self._title_label.mousePressEvent = lambda e: self.focus_requested.emit()
        self._msg_label.mousePressEvent = lambda e: self.focus_requested.emit()

    def _position_window(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - 20
            y = geo.bottom() - self.height() - 20
            self.move(x, y)

    def show_event(self, event_data: dict):
        """接收标准事件 dict 并展示。"""
        self._auto_close_timer.stop()

        severity_str = event_data.get("severity", "info")
        try:
            severity = Severity(severity_str)
        except ValueError:
            severity = Severity.INFO

        border_color, bg_color = SEVERITY_COLORS.get(
            severity, SEVERITY_COLORS[Severity.INFO]
        )

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 8px;
            }}
        """)
        self._icon_label.setStyleSheet(f"color: {border_color};")
        self._icon_label.setText(SEVERITY_ICONS.get(severity, "i"))

        self._title_label.setText(event_data.get("title", ""))
        self._msg_label.setText(event_data.get("message", ""))

        # 显示属性
        opacity = event_data.get("display", {}).get("sticky", True)
        timeout_ms = event_data.get("display", {}).get("timeout_ms", 0)
        if not opacity and timeout_ms > 0:
            self._auto_close_timer.start(timeout_ms)

        self.show()
        self.raise_()

    def _on_close(self):
        self._auto_close_timer.stop()
        self.hide()

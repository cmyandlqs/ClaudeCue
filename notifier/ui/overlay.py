"""
Floating notification overlay window.
Displays toast-style notifications with fade in/out animations.
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QGraphicsDropShadowEffect, QFrame
)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QCursor, QColor

logger = logging.getLogger(__name__)


class OverlayWidget(QWidget):
    """
    Floating notification overlay window.

    Features:
    - Always on top
    - Frameless transparent window
    - Fade in/out animations
    - Click to dismiss and focus terminal
    - Auto-dismiss after timeout
    """

    # Default dimensions
    WIDTH = 420
    HEIGHT = 138

    # Animation durations (ms)
    FADE_IN_DURATION = 200
    FADE_OUT_DURATION = 150

    # Positioning
    MARGIN = 20

    def __init__(self, focus_callback=None):
        super().__init__()
        self.focus_callback = focus_callback
        self.fade_in_animation = None
        self.fade_out_animation = None
        self.dismiss_timer = None  # Timer for auto-dismiss
        self.current_event = {}
        self.setup_ui()

    def setup_ui(self):
        """Setup the UI components."""
        # Window flags - frameless, always on top, tool window (no taskbar)
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )

        # Transparent background
        self.setAttribute(Qt.WA_TranslucentBackground)

        # No focus on show (don't steal focus from terminal)
        # Note: WA_ShowWithoutActivation may not be available in all PySide6 versions
        if hasattr(Qt, 'WA_ShowWithoutActivation'):
            self.setAttribute(Qt.WA_ShowWithoutActivation)

        # Set size
        self.setFixedSize(self.WIDTH, self.HEIGHT)

        # Create main container widget
        self.container = QWidget()
        self.container.setObjectName("notificationContainer")

        # macOS-inspired light card style
        self.container.setStyleSheet("""
            #notificationContainer {
                background-color: rgba(248, 248, 250, 242);
                border-radius: 14px;
                border: 1px solid rgba(0, 0, 0, 0.08);
            }
        """)

        # Drop shadow effect
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(0, 0, 0, 55))
        shadow.setOffset(0, 8)
        self.container.setGraphicsEffect(shadow)

        # Layout
        layout = QVBoxLayout(self.container)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: traffic lights + app text
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        for dot_color in ("#FF5F57", "#FEBC2E", "#28C840"):
            dot = QFrame()
            dot.setFixedSize(9, 9)
            dot.setStyleSheet(
                f"background-color: {dot_color}; border-radius: 4px; border: 1px solid rgba(0,0,0,0.12);"
            )
            header_layout.addWidget(dot)

        header_layout.addSpacing(8)
        self.app_label = QLabel("ccCue")
        self.app_label.setStyleSheet("color: rgba(60, 60, 67, 0.68);")
        self.app_label.setFont(QFont("SF Pro Text", 9))
        header_layout.addWidget(self.app_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Title label
        self.title_label = QLabel()
        self.title_label.setObjectName("titleLabel")
        self.title_label.setStyleSheet("""
            #titleLabel {
                color: rgba(28, 28, 30, 0.95);
                font-weight: bold;
            }
        """)
        self.title_label.setFont(QFont("SF Pro Display", 12, QFont.Bold))
        self.title_label.setWordWrap(True)

        # Message label
        self.message_label = QLabel()
        self.message_label.setObjectName("messageLabel")
        self.message_label.setStyleSheet("""
            #messageLabel {
                color: rgba(60, 60, 67, 0.92);
            }
        """)
        self.message_label.setFont(QFont("SF Pro Text", 10))
        self.message_label.setWordWrap(True)

        layout.addWidget(self.title_label)
        layout.addWidget(self.message_label)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)

    def show_notification(
        self,
        title: str,
        message: str,
        duration: int = 5000,
        severity: str = "info",
        event_payload: dict | None = None
    ):
        """
        Show a notification.

        Args:
            title: Notification title
            message: Notification message
            duration: Auto-dismiss duration in ms (0 = no auto-dismiss)
            severity: Severity level ('info', 'warning', 'error')
        """
        # Cancel any existing dismiss timer
        if self.dismiss_timer:
            self.dismiss_timer.stop()
            self.dismiss_timer = None

        # Set content
        self.current_event = event_payload or {}
        self.title_label.setText(title)
        self.message_label.setText(message)

        # Apply severity styling
        self._apply_severity_style(severity)

        # Position window at top-right corner
        self._position_window()

        # Show window
        self.show()

        # Fade in
        self._fade_in()

        # Schedule fade out
        if duration > 0:
            self.dismiss_timer = QTimer()
            self.dismiss_timer.timeout.connect(self.fade_out)
            self.dismiss_timer.setSingleShot(True)
            self.dismiss_timer.start(duration)

    def _apply_severity_style(self, severity: str):
        """Apply styling based on severity level."""
        border_colors = {
            "info": "rgba(100, 180, 255, 0.8)",
            "warning": "rgba(255, 170, 54, 0.85)",
            "error": "rgba(255, 69, 58, 0.9)"
        }

        border_color = border_colors.get(severity, border_colors["info"])
        self.container.setStyleSheet(f"""
            #notificationContainer {{
                background-color: rgba(248, 248, 250, 242);
                border-radius: 14px;
                border: 1px solid rgba(0, 0, 0, 0.08);
                border-left: 4px solid {border_color};
            }}
        """)

    def _position_window(self):
        """Position window at top-right corner of screen."""
        screen = self.screen().availableGeometry()
        self.move(
            screen.right() - self.WIDTH - self.MARGIN,
            screen.top() + self.MARGIN
        )

    def _fade_in(self):
        """Fade in animation."""
        self.setWindowOpacity(0)

        self.fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_in_animation.setDuration(self.FADE_IN_DURATION)
        self.fade_in_animation.setStartValue(0)
        self.fade_in_animation.setEndValue(1)
        self.fade_in_animation.setEasingCurve(QEasingCurve.OutCubic)
        self.fade_in_animation.start()

    def fade_out(self):
        """Fade out animation and close window."""
        if self.fade_out_animation and self.fade_out_animation.state() == QPropertyAnimation.Running:
            return  # Already fading out

        self.fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_out_animation.setDuration(self.FADE_OUT_DURATION)
        self.fade_out_animation.setStartValue(1)
        self.fade_out_animation.setEndValue(0)
        self.fade_out_animation.setEasingCurve(QEasingCurve.InCubic)
        self.fade_out_animation.finished.connect(self.close)
        self.fade_out_animation.start()

    def mousePressEvent(self, event):
        """Handle mouse click - dismiss and focus terminal."""
        # Call focus callback if provided
        if self.focus_callback:
            try:
                self.focus_callback(self.current_event)
            except TypeError:
                # Backward compatibility for old callback signatures.
                self.focus_callback()

        # Close the notification
        self.fade_out()

    def enterEvent(self, event):
        """Mouse enter - pause auto-dismiss and change cursor."""
        self.setCursor(QCursor(Qt.PointingHandCursor))
        # Pause auto-dismiss timer
        if self.dismiss_timer and self.dismiss_timer.isActive():
            self.dismiss_timer.stop()

    def leaveEvent(self, event):
        """Mouse leave - resume auto-dismiss and reset cursor."""
        self.setCursor(QCursor(Qt.ArrowCursor))
        # Resume auto-dismiss timer with 1 second delay
        if self.dismiss_timer:
            self.dismiss_timer.start(1000)

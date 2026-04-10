"""
Main entry point for ccCue notifier application.

Runs the Qt application with:
- HTTP server for receiving hook events
- Overlay window for displaying notifications
- System tray icon for app control
"""
import sys
import logging
import signal
import time
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler
import ctypes
from ctypes import wintypes
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, QAbstractNativeEventFilter, QCoreApplication

from .server import NotifierServer
from .single_instance import SingleInstanceGuard
from .ui.overlay import OverlayWidget
from .ui.tray import TrayIcon
from .utils.sound import play_notification_sound
from .utils.window_focus import (
    focus_windows_terminal,
    bind_session_to_active_terminal,
    get_active_terminal_hwnd,
)


WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
VK_SPACE = 0x20
VK_Q = 0x51
HOTKEY_ID = 1

HOTKEY_CANDIDATES = [
    ("Ctrl+Alt+Space", MOD_CONTROL | MOD_ALT, VK_SPACE),
    ("Ctrl+Alt+Q", MOD_CONTROL | MOD_ALT, VK_Q),
    ("Ctrl+Shift+Space", MOD_CONTROL | MOD_SHIFT, VK_SPACE),
]


def configure_logging() -> Path:
    """Configure console + file logging."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        log_dir = Path(local_app_data) / "ccCue" / "logs"
    else:
        project_root = Path(__file__).resolve().parents[1]
        log_dir = project_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "notifier.log"

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    return log_path


class GlobalHotkeyFilter(QAbstractNativeEventFilter):
    """Global hotkey listener using Windows WM_HOTKEY."""

    def __init__(self, callback):
        super().__init__()
        self.callback = callback

    def nativeEventFilter(self, event_type, message):
        if event_type not in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            return False, 0

        try:
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                self.callback()
                return True, 0
        except Exception:
            return False, 0

        return False, 0


LOG_PATH = configure_logging()
logger = logging.getLogger(__name__)


class NotifierApp:
    """
    Main notifier application.

    Coordinates the HTTP server, overlay window, tray icon,
    and event processing.
    """

    # Event processing interval (ms)
    EVENT_CHECK_INTERVAL = 100

    def __init__(self):
        """Initialize the notifier application."""
        # Create Qt application
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)

        # Set application info
        self.app.setApplicationName("ccCue Notifier")
        self.app.setOrganizationName("ccCue")

        # Create components
        self.server = NotifierServer()
        self.overlay = OverlayWidget(focus_callback=self._on_overlay_click)
        self.tray = TrayIcon(self.app, on_quit=self._on_quit)
        self.latest_event: dict | None = None
        self.last_seen_terminal_hwnd: int | None = None
        self.last_seen_terminal_ts: float = 0.0

        # Event processing timer
        self.event_timer = QTimer()
        self.event_timer.timeout.connect(self._process_events)
        self.terminal_probe_timer = QTimer()
        self.terminal_probe_timer.timeout.connect(self._probe_active_terminal)
        self.signal_timer = QTimer()
        self.signal_timer.timeout.connect(lambda: None)

        # Global hotkey setup
        self.hotkey_filter = GlobalHotkeyFilter(self._on_hotkey_focus)
        QCoreApplication.instance().installNativeEventFilter(self.hotkey_filter)
        self.hotkey_registered = False
        self.hotkey_label = "未注册"
        self._register_hotkey()
        self.overlay.set_hotkey_hint(self.hotkey_label)

        # Enable Ctrl+C graceful shutdown in Qt event loop
        signal.signal(signal.SIGINT, self._handle_interrupt_signal)
        if hasattr(signal, "SIGBREAK"):
            signal.signal(signal.SIGBREAK, self._handle_interrupt_signal)

        # Statistics
        self.events_received = 0
        self.events_displayed = 0

        logger.info("NotifierApp initialized")
        logger.info("Debug log file: %s", LOG_PATH)

    def start(self):
        """Start the notifier application."""
        # Start HTTP server
        if not self.server.start():
            logger.error("Failed to start HTTP server")
            return 1

        # Start event processing timer
        self.event_timer.start(self.EVENT_CHECK_INTERVAL)
        self.terminal_probe_timer.start(300)
        self.signal_timer.start(200)

        # Show tray notification
        if self.tray.is_available:
            self.tray.show_message(
                "ccCue Notifier",
                "Notifier is running in the background",
                3000
            )

        logger.info("ccCue notifier started")
        logger.info(f"Listening for events on {self.server.url}")
        logger.info("Global focus hotkey: %s", self.hotkey_label)

        # Run Qt event loop
        return self.app.exec()

    def _process_events(self):
        """Process pending events from the server queue."""
        for event in self.server.get_events():
            self.events_received += 1
            self._handle_event(event)

    def _handle_event(self, event: dict):
        """
        Handle a single event.

        Args:
            event: Event dictionary with title, message, display config
        """
        title = event.get("title", "")
        message = event.get("message", "")
        severity = event.get("severity", "info")
        display = event.get("display", {})
        session_id = str(event.get("session_id", "")).strip()

        # Best-effort binding so popup click can focus the matching terminal.
        if session_id:
            bind_session_to_active_terminal(session_id)

        # Capture active terminal hint at arrival time if hook-side hint is missing.
        if not isinstance(event.get("terminal_hwnd_hint"), int):
            active_hwnd = get_active_terminal_hwnd()
            if active_hwnd:
                event["terminal_hwnd_hint"] = active_hwnd
            elif self.last_seen_terminal_hwnd:
                # Fallback: use recently observed terminal window.
                event["terminal_hwnd_hint"] = self.last_seen_terminal_hwnd

        # Play sound
        if display.get("play_sound", True):
            play_notification_sound(severity)

        # Show overlay notification
        timeout_ms = display.get("timeout_ms", 5000)
        self.latest_event = event
        self.overlay.show_notification(
            title,
            message,
            timeout_ms,
            severity,
            event
        )

        self.events_displayed += 1
        logger.debug(f"Displayed notification: {title}")

    def _on_overlay_click(self, event: dict | None = None):
        """Handle overlay click - focus terminal."""
        focus_windows_terminal(event)

    def _on_hotkey_focus(self):
        """Handle global hotkey to focus terminal for latest event."""
        logger.debug("Hotkey pressed, trying focus with latest event")
        focus_windows_terminal(self.latest_event)

    def _probe_active_terminal(self):
        """Track most recently active terminal window for fallback focus."""
        hwnd = get_active_terminal_hwnd()
        if hwnd:
            if hwnd != self.last_seen_terminal_hwnd:
                logger.debug("Observed active terminal hwnd=%s", hwnd)
            self.last_seen_terminal_hwnd = hwnd
            self.last_seen_terminal_ts = time.time()

    def _register_hotkey(self):
        """Register global hotkey with fallback candidates."""
        try:
            user32 = ctypes.windll.user32
            for label, modifiers, vkey in HOTKEY_CANDIDATES:
                if bool(user32.RegisterHotKey(None, HOTKEY_ID, modifiers, vkey)):
                    self.hotkey_registered = True
                    self.hotkey_label = label
                    logger.info("Registered global hotkey: %s", label)
                    return
            logger.warning("Failed to register global hotkey from candidates: %s", [x[0] for x in HOTKEY_CANDIDATES])
        except Exception as e:
            logger.warning("Hotkey registration error: %s", e)
            self.hotkey_registered = False

    def _unregister_hotkey(self):
        """Unregister global hotkey."""
        if not self.hotkey_registered:
            return
        try:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
        except Exception:
            pass
        self.hotkey_registered = False

    def _handle_interrupt_signal(self, signum, frame):
        """Handle Ctrl+C/SIGBREAK for graceful shutdown."""
        logger.info("Received interrupt signal %s", signum)
        self._on_quit()

    def _on_quit(self):
        """Handle quit request."""
        logger.info("Shutting down...")
        logger.info(f"Total events received: {self.events_received}")
        logger.info(f"Total events displayed: {self.events_displayed}")

        # Stop server
        self.server.stop()

        # Stop timer
        self.event_timer.stop()
        self.terminal_probe_timer.stop()
        self.signal_timer.stop()

        # Unregister hotkey
        self._unregister_hotkey()

        # Quit application
        self.app.quit()


def main():
    """Entry point for the notifier application."""
    guard = SingleInstanceGuard()
    if not guard.acquire():
        logger.info("Notifier already running; exiting duplicate instance.")
        sys.exit(0)

    try:
        app = NotifierApp()
        sys.exit(app.start())
    finally:
        guard.release()


if __name__ == "__main__":
    main()

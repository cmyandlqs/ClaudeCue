"""
Main entry point for ccCue notifier application.

Runs the Qt application with:
- HTTP server for receiving hook events
- Overlay window for displaying notifications
- System tray icon for app control
"""
import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from .server import NotifierServer
from .ui.overlay import OverlayWidget
from .ui.tray import TrayIcon
from .utils.sound import play_notification_sound
from .utils.window_focus import focus_windows_terminal, bind_session_to_active_terminal

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(name)s: %(message)s"
)
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

        # Event processing timer
        self.event_timer = QTimer()
        self.event_timer.timeout.connect(self._process_events)

        # Statistics
        self.events_received = 0
        self.events_displayed = 0

        logger.info("NotifierApp initialized")

    def start(self):
        """Start the notifier application."""
        # Start HTTP server
        if not self.server.start():
            logger.error("Failed to start HTTP server")
            return 1

        # Start event processing timer
        self.event_timer.start(self.EVENT_CHECK_INTERVAL)

        # Show tray notification
        if self.tray.is_available:
            self.tray.show_message(
                "ccCue Notifier",
                "Notifier is running in the background",
                3000
            )

        logger.info("ccCue notifier started")
        logger.info(f"Listening for events on {self.server.url}")

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

        # Play sound
        if display.get("play_sound", True):
            play_notification_sound(severity)

        # Show overlay notification
        timeout_ms = display.get("timeout_ms", 5000)
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

    def _on_quit(self):
        """Handle quit request."""
        logger.info("Shutting down...")
        logger.info(f"Total events received: {self.events_received}")
        logger.info(f"Total events displayed: {self.events_displayed}")

        # Stop server
        self.server.stop()

        # Stop timer
        self.event_timer.stop()

        # Quit application
        self.app.quit()


def main():
    """Entry point for the notifier application."""
    app = NotifierApp()
    sys.exit(app.start())


if __name__ == "__main__":
    main()

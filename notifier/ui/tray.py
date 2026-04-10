"""
System tray icon for ccCue notifier.
Provides a menu for controlling the notifier application.
"""
import logging
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QStyle
from PySide6.QtGui import QAction

logger = logging.getLogger(__name__)


class TrayIcon:
    """
    System tray icon manager.

    Provides:
    - Tray icon with context menu
    - Show/hide functionality
    - Quit action
    """

    def __init__(self, app, on_quit=None):
        self.app = app
        self.on_quit = on_quit
        self.tray = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("System tray is not available on this system")
            return

        self.setup_tray()

    def setup_tray(self):
        """Setup the system tray icon and menu."""
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.app.style().standardIcon(QStyle.SP_ComputerIcon))
        self.tray.setToolTip("ccCue Notifier")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #444;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #3d3d3d;
            }
            QMenu::separator {
                height: 1px;
                background-color: #444;
                margin: 4px 8px;
            }
        """)

        status_action = QAction("ccCue Notifier Running", menu)
        status_action.setEnabled(False)
        menu.addAction(status_action)
        menu.addSeparator()

        quit_action = QAction("退出", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.show()
        logger.info("System tray icon created")

    def show_message(self, title: str, message: str, duration: int = 5000):
        """Show a system tray notification bubble."""
        if self.tray:
            self.tray.showMessage(
                title,
                message,
                QSystemTrayIcon.Information,
                duration
            )

    def quit(self):
        """Handle quit action."""
        logger.info("Quit requested from tray")
        if self.on_quit:
            self.on_quit()
        else:
            self.app.quit()

    def hide(self):
        """Hide the tray icon."""
        if self.tray:
            self.tray.hide()

    def show(self):
        """Show the tray icon."""
        if self.tray:
            self.tray.show()

    @property
    def is_available(self) -> bool:
        """Check if system tray is available."""
        return self.tray is not None


"""
Window focus utilities for Windows.
Uses pywin32 to find and focus windows.
"""
import logging
import win32gui
import win32con

logger = logging.getLogger(__name__)


# Common window titles/class names to search for
TERMINAL_TITLES = [
    "Windows Terminal",
    "Windows PowerShell",
    "Command Prompt",
    "Claude Code",  # For Claude Code terminals
]

TERMINAL_CLASSES = [
    "CascadiaHost",  # Windows Terminal
    "ConsoleWindowClass",  # Generic console
]


def focus_windows_terminal() -> bool:
    """
    Find and focus the Windows Terminal window.

    Returns:
        True if window was found and focused, False otherwise
    """
    try:
        # First try to find by exact title match
        for title in TERMINAL_TITLES:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                return _focus_window(hwnd)

        # If not found, enumerate all windows and look for matches
        found = [False]  # Use list to allow mutation in nested function

        def callback(hwnd, _):
            if not found[0] and _is_terminal_window(hwnd):
                if _focus_window(hwnd):
                    found[0] = True
                return False  # Stop enumeration if found
            return True  # Continue enumeration

        win32gui.EnumWindows(callback, None)
        return found[0]

    except Exception as e:
        logger.error(f"Error focusing terminal: {e}")
        return False


def _is_terminal_window(hwnd: int) -> bool:
    """Check if a window is likely a terminal window."""
    try:
        if not win32gui.IsWindowVisible(hwnd):
            return False

        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)

        # Check title
        for term_title in TERMINAL_TITLES:
            if term_title.lower() in title.lower():
                return True

        # Check class name
        for term_class in TERMINAL_CLASSES:
            if term_class.lower() in class_name.lower():
                return True

        return False

    except Exception:
        return False


def _focus_window(hwnd: int) -> bool:
    """
    Bring a window to the foreground.

    Args:
        hwnd: Window handle

    Returns:
        True if successful, False otherwise
    """
    try:
        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Bring to foreground
        win32gui.SetForegroundWindow(hwnd)
        return True

    except Exception as e:
        logger.debug(f"Failed to focus window: {e}")
        return False


def focus_window_by_title(title: str) -> bool:
    """
    Find and focus a window by its title.

    Args:
        title: Window title to search for (partial match)

    Returns:
        True if found and focused, False otherwise
    """
    try:
        found = [False]  # Use list to allow mutation in nested function

        def callback(hwnd, _):
            if not found[0] and win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if title.lower() in window_title.lower():
                    if _focus_window(hwnd):
                        found[0] = True
                    return False  # Stop enumeration if found
            return True  # Continue enumeration

        win32gui.EnumWindows(callback, None)
        return found[0]

    except Exception as e:
        logger.error(f"Error focusing window by title: {e}")
        return False


def get_active_window_title() -> str:
    """
    Get the title of the currently active window.

    Returns:
        Window title or empty string if error
    """
    try:
        hwnd = win32gui.GetForegroundWindow()
        return win32gui.GetWindowText(hwnd)
    except Exception:
        return ""

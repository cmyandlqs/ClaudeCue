"""
Window focus utilities for Windows.
Uses pywin32 to find and focus windows.
"""
import logging
import win32gui
import win32con
from typing import Dict, Optional

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

_SESSION_WINDOW_MAP: Dict[str, int] = {}
_LAST_TERMINAL_HWND: Optional[int] = None


def bind_session_to_active_terminal(session_id: str) -> bool:
    """
    Bind a session id to current active terminal window.

    This allows clicking a notification to focus the matching terminal.
    """
    if not session_id:
        return False

    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and _is_terminal_window(hwnd):
            _SESSION_WINDOW_MAP[session_id] = hwnd
            global _LAST_TERMINAL_HWND
            _LAST_TERMINAL_HWND = hwnd
            return True
    except Exception:
        return False

    return False


def focus_windows_terminal(event: Optional[dict] = None) -> bool:
    """
    Find and focus terminal window, preferring the matching session window.

    Returns:
        True if window was found and focused, False otherwise
    """
    session_id = ""
    if event:
        session_id = str(event.get("session_id", "")).strip()

    try:
        # 1) Exact session hit from cached mapping.
        if session_id:
            mapped = _SESSION_WINDOW_MAP.get(session_id)
            if mapped and win32gui.IsWindow(mapped) and win32gui.IsWindowVisible(mapped):
                if _focus_window(mapped):
                    return True

        # 2) Last successful terminal window.
        global _LAST_TERMINAL_HWND
        if _LAST_TERMINAL_HWND and win32gui.IsWindow(_LAST_TERMINAL_HWND):
            if win32gui.IsWindowVisible(_LAST_TERMINAL_HWND) and _focus_window(_LAST_TERMINAL_HWND):
                if session_id:
                    _SESSION_WINDOW_MAP[session_id] = _LAST_TERMINAL_HWND
                return True

        # First try to find by exact title match
        for title in TERMINAL_TITLES:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                if _focus_window(hwnd):
                    if session_id:
                        _SESSION_WINDOW_MAP[session_id] = hwnd
                    _LAST_TERMINAL_HWND = hwnd
                    return True

        # If not found, enumerate all windows and look for matches
        best_hwnd = [None]
        best_score = [-1]

        def callback(hwnd, _):
            if _is_terminal_window(hwnd):
                score = _window_score(hwnd, event)
                if score > best_score[0]:
                    best_score[0] = score
                    best_hwnd[0] = hwnd
            return True  # Continue enumeration

        win32gui.EnumWindows(callback, None)

        if best_hwnd[0] and _focus_window(best_hwnd[0]):
            if session_id:
                _SESSION_WINDOW_MAP[session_id] = best_hwnd[0]
            _LAST_TERMINAL_HWND = best_hwnd[0]
            return True

        return False

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


def _window_score(hwnd: int, event: Optional[dict]) -> int:
    """Score terminal candidate window."""
    try:
        title = win32gui.GetWindowText(hwnd).lower()
        class_name = win32gui.GetClassName(hwnd).lower()
    except Exception:
        return -1

    score = 0

    for term_class in TERMINAL_CLASSES:
        if term_class.lower() in class_name:
            score += 80

    for term_title in TERMINAL_TITLES:
        if term_title.lower() in title:
            score += 40

    if "claude" in title:
        score += 30

    if event:
        session_id = str(event.get("session_id", "")).strip().lower()
        if session_id and session_id in title:
            score += 120

        for key in ("title", "message"):
            value = str(event.get(key, "")).strip().lower()
            if value and len(value) >= 4 and value in title:
                score += 10

    return score


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
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Bring to top first, then request foreground focus.
        win32gui.BringWindowToTop(hwnd)
        win32gui.SetForegroundWindow(hwnd)

        # Foreground restrictions sometimes block focus; force topmost toggle.
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_TOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
        win32gui.SetWindowPos(
            hwnd,
            win32con.HWND_NOTOPMOST,
            0, 0, 0, 0,
            win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
        )
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
                        global _LAST_TERMINAL_HWND
                        _LAST_TERMINAL_HWND = hwnd
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

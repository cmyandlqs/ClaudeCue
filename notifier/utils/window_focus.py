"""
Window focus utilities for Windows.
Uses pywin32 to find and focus windows.
"""
import logging
import win32gui
import win32con
from typing import Dict, Optional
import win32api
import win32process

logger = logging.getLogger(__name__)


# Common window titles/class names to search for
TERMINAL_TITLES = [
    "Windows Terminal",
    "Windows PowerShell",
    "Command Prompt",
    "Claude Code",  # For Claude Code terminals
]

TERMINAL_CLASSES = [
    "CASCADIA_HOSTING_WINDOW_CLASS",  # Windows Terminal (common)
    "CascadiaHost",  # Windows Terminal
    "ConsoleWindowClass",  # Generic console
]

_SESSION_WINDOW_MAP: Dict[str, int] = {}
_LAST_TERMINAL_HWND: Optional[int] = None


def get_active_terminal_hwnd() -> Optional[int]:
    """Return current foreground hwnd if it looks like a terminal."""
    try:
        hwnd = win32gui.GetForegroundWindow()
        if hwnd and _is_terminal_window(hwnd):
            return hwnd
    except Exception:
        return None
    return None


def is_terminal_window(hwnd: int) -> bool:
    """Public helper for terminal window detection."""
    return _is_terminal_window(hwnd)


def bind_session_to_active_terminal(session_id: str) -> bool:
    """
    Bind a session id to current active terminal window.

    This allows clicking a notification to focus the matching terminal.
    """
    if not session_id:
        return False

    try:
        hwnd = get_active_terminal_hwnd()
        if hwnd:
            _SESSION_WINDOW_MAP[session_id] = hwnd
            global _LAST_TERMINAL_HWND
            _LAST_TERMINAL_HWND = hwnd
            logger.debug("Bound session '%s' -> hwnd=%s", session_id, hwnd)
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
        # 0) Event-specific exact terminal hint (captured at hook time/arrival).
        if event:
            hinted_hwnd = event.get("terminal_hwnd_hint")
            if not isinstance(hinted_hwnd, int):
                hinted_hwnd = event.get("_terminal_hwnd")  # backward compatibility
            if isinstance(hinted_hwnd, int):
                if win32gui.IsWindow(hinted_hwnd) and win32gui.IsWindowVisible(hinted_hwnd):
                    if _is_terminal_window(hinted_hwnd):
                        logger.debug("Trying hinted window: %s", _describe_window(hinted_hwnd))
                        if _window_matches_event_hint(hinted_hwnd, event) and _focus_window(hinted_hwnd):
                            return True
                    else:
                        logger.debug("Skip hinted non-terminal window: %s", _describe_window(hinted_hwnd))

        # 0.5) Try process id hint when hwnd is stale or mismatched.
        if event:
            pid_hint = event.get("terminal_pid_hint")
            if isinstance(pid_hint, int) and pid_hint > 0:
                hwnd_by_pid = _find_best_window_by_pid(pid_hint, event)
                if hwnd_by_pid:
                    logger.debug("Trying pid-hint window: %s", _describe_window(hwnd_by_pid))
                    if _focus_window(hwnd_by_pid):
                        return True

        # 1) Exact session hit from cached mapping.
        if session_id:
            mapped = _SESSION_WINDOW_MAP.get(session_id)
            if mapped and win32gui.IsWindow(mapped) and win32gui.IsWindowVisible(mapped):
                logger.debug("Trying mapped session window=%s for session=%s", _describe_window(mapped), session_id)
                if _focus_window(mapped):
                    return True

        # 2) Last successful terminal window.
        global _LAST_TERMINAL_HWND
        if _LAST_TERMINAL_HWND and win32gui.IsWindow(_LAST_TERMINAL_HWND):
            logger.debug("Trying last terminal window=%s", _describe_window(_LAST_TERMINAL_HWND))
            if win32gui.IsWindowVisible(_LAST_TERMINAL_HWND) and _focus_window(_LAST_TERMINAL_HWND):
                if session_id:
                    _SESSION_WINDOW_MAP[session_id] = _LAST_TERMINAL_HWND
                return True

        # First try to find by exact title match
        for title in TERMINAL_TITLES:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                logger.debug("Trying exact title match window=%s", _describe_window(hwnd))
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
                logger.debug(
                    "Candidate score=%s window=%s",
                    score, _describe_window(hwnd)
                )
            return True  # Continue enumeration

        win32gui.EnumWindows(callback, None)

        if best_hwnd[0] and _focus_window(best_hwnd[0]):
            logger.debug("Focused best candidate score=%s window=%s", best_score[0], _describe_window(best_hwnd[0]))
            if session_id:
                _SESSION_WINDOW_MAP[session_id] = best_hwnd[0]
            _LAST_TERMINAL_HWND = best_hwnd[0]
            return True

        logger.warning("No terminal window could be focused for event session=%s", session_id or "<none>")
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

        pid_hint = event.get("terminal_pid_hint")
        if isinstance(pid_hint, int) and pid_hint > 0:
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid == pid_hint:
                    score += 180
            except Exception:
                pass

        class_hint = str(event.get("terminal_class_hint", "")).strip().lower()
        if class_hint and class_hint == class_name:
            score += 80

        title_hint = str(event.get("terminal_title_hint", "")).strip().lower()
        if title_hint and title_hint == title:
            score += 120
        elif title_hint and title_hint in title:
            score += 50

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
        logger.debug("Focus attempt window=%s", _describe_window(hwnd))

        # Restore if minimized
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Bring to top first.
        win32gui.BringWindowToTop(hwnd)

        # Foreground restrictions on Windows can block focus from background app.
        _set_foreground_with_attach(hwnd)

        # Force topmost toggle as fallback.
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
        _set_foreground_with_attach(hwnd)

        # Verify result
        fg = win32gui.GetForegroundWindow()
        ok = fg == hwnd
        logger.debug("Focus result target=%s foreground=%s ok=%s", _describe_window(hwnd), _describe_window(fg) if fg else "<none>", ok)
        return ok

    except Exception as e:
        logger.debug(f"Failed to focus window: {e}")
        return False


def _window_matches_event_hint(hwnd: int, event: dict) -> bool:
    """Verify hinted hwnd with pid/class/title to avoid wrong-window focus."""
    if not event:
        return True

    try:
        title = win32gui.GetWindowText(hwnd).strip().lower()
        class_name = win32gui.GetClassName(hwnd).strip().lower()
    except Exception:
        return False

    pid_hint = event.get("terminal_pid_hint")
    if isinstance(pid_hint, int) and pid_hint > 0:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid != pid_hint:
                return False
        except Exception:
            return False

    class_hint = str(event.get("terminal_class_hint", "")).strip().lower()
    if class_hint and class_name and class_name != class_hint:
        return False

    title_hint = str(event.get("terminal_title_hint", "")).strip().lower()
    if title_hint and title and title != title_hint and title_hint not in title:
        return False

    return True


def _find_best_window_by_pid(pid: int, event: Optional[dict]) -> Optional[int]:
    """Enumerate windows and return best visible window by process id."""
    best = [None]
    best_score = [-1]

    def callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return True
        try:
            _, wpid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return True
        if wpid != pid:
            return True

        score = _window_score(hwnd, event)
        if score > best_score[0]:
            best_score[0] = score
            best[0] = hwnd
        return True

    win32gui.EnumWindows(callback, None)
    return best[0]


def _describe_window(hwnd: int) -> str:
    """Human-readable window snapshot for diagnostics."""
    if not hwnd or not win32gui.IsWindow(hwnd):
        return f"hwnd={hwnd} <invalid>"
    try:
        title = win32gui.GetWindowText(hwnd)
        class_name = win32gui.GetClassName(hwnd)
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return f"hwnd={hwnd} pid={pid} class={class_name} title={title!r}"
    except Exception:
        return f"hwnd={hwnd} <describe-error>"


def _set_foreground_with_attach(hwnd: int) -> None:
    """Try to set foreground by temporarily attaching input threads."""
    current_tid = win32api.GetCurrentThreadId()
    fg_hwnd = win32gui.GetForegroundWindow()
    fg_tid, _ = win32process.GetWindowThreadProcessId(fg_hwnd) if fg_hwnd else (0, 0)
    target_tid, _ = win32process.GetWindowThreadProcessId(hwnd)

    attached_fg = False
    attached_target = False
    try:
        if fg_tid and fg_tid != current_tid:
            win32process.AttachThreadInput(current_tid, fg_tid, True)
            attached_fg = True

        if target_tid and target_tid != current_tid and target_tid != fg_tid:
            win32process.AttachThreadInput(current_tid, target_tid, True)
            attached_target = True

        # ALT keystroke hack improves SetForegroundWindow success on some systems.
        win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
        win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

        win32gui.SetForegroundWindow(hwnd)
        win32gui.SetActiveWindow(hwnd)
        win32gui.SetFocus(hwnd)
    finally:
        if attached_target:
            win32process.AttachThreadInput(current_tid, target_tid, False)
        if attached_fg:
            win32process.AttachThreadInput(current_tid, fg_tid, False)


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

"""
Sound playback utilities for Windows.
Uses the built-in winsound module - no external dependencies.
"""
import logging
import threading
import winsound

logger = logging.getLogger(__name__)


# Windows sound constants
SOUND_DEFAULT = winsound.MB_OK
SOUND_INFORMATION = winsound.MB_ICONASTERISK
SOUND_EXCLAMATION = winsound.MB_ICONEXCLAMATION
SOUND_ERROR = winsound.MB_ICONHAND
SOUND_QUESTION = winsound.MB_ICONQUESTION


def play_notification_sound(sound_type: str = "default") -> None:
    """
    Play a notification sound in a background thread.

    Args:
        sound_type: Type of sound ('default', 'info', 'warning', 'error')
    """
    sound_map = {
        "default": SOUND_DEFAULT,
        "info": SOUND_INFORMATION,
        "warning": SOUND_EXCLAMATION,
        "error": SOUND_ERROR,
        "question": SOUND_QUESTION
    }

    sound = sound_map.get(sound_type, SOUND_DEFAULT)

    # Play in background thread to avoid blocking
    thread = threading.Thread(target=_play_sound, args=(sound,), daemon=True)
    thread.start()


def _play_sound(sound: int) -> None:
    """Internal function to play sound (runs in background thread)."""
    try:
        winsound.MessageBeep(sound)
    except Exception as e:
        logger.debug(f"Failed to play sound: {e}")


def play_custom_sound(frequency: int = 800, duration: int = 200) -> None:
    """
    Play a custom tone using frequency and duration.

    Args:
        frequency: Frequency in Hz (37-32767)
        duration: Duration in milliseconds
    """
    def _play():
        try:
            winsound.Beep(frequency, duration)
        except Exception as e:
            logger.debug(f"Failed to play beep: {e}")

    thread = threading.Thread(target=_play, daemon=True)
    thread.start()

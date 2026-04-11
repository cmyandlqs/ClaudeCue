# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ccCue is a Windows desktop notification helper for Claude Code. It receives events via Claude Hooks, displays overlay notifications, and refocuses the terminal when the user clicks a notification or presses a global hotkey.

**Architecture**: Event-driven hooks (no wrapper). Claude runs natively in the terminal; hooks forward events to a local HTTP notifier service.

**Data flow**:
```
Claude hooks (stdin JSON)
  → hooks/bootstrap.py (ensure notifier running, forward events)
    → hooks/notify_hook.py (map hook payloads to unified event format)
      → HTTP POST to notifier (localhost:19527/event)
        → notifier/ (PySide6 overlay, tray icon, sound, terminal refocus)
```

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (all)
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_state_manager.py -v

# Run a single test by name
python -m pytest tests/test_hook.py::test_map_notification -v

# CLI operations
python -m cli.main install                       # install hooks into ~/.claude/settings.json
python -m cli.main install --project-root <path> # config-only mode (deprecated)
python -m cli.main uninstall                     # remove hooks, restore baseline
python -m cli.main doctor --json                 # health check
python -m cli.main restore --latest              # restore settings from backup

# Start notifier manually (for development)
python -m notifier.main

# Build installer
cd installer && build_inno.bat
```

## Architecture

### Module Responsibilities

| Module | Role |
|--------|------|
| `hooks/bootstrap.py` | Hook entry point. Reads stdin, ensures notifier is running (health check + auto-start), forwards events. Always exits 0 to never block Claude. |
| `hooks/notify_hook.py` | Maps `hook_event_name` (Notification, Stop, PermissionRequest, etc.) to unified event dicts. Captures terminal hwnd/pid hints via ctypes. |
| `notifier/main.py` | PySide6 Qt app. Coordinates HTTP server, overlay, tray, global hotkey (Ctrl+Alt+Space/Q/Shift+Space with fallback). |
| `notifier/server.py` | HTTP server on `127.0.0.1:19527`. Endpoints: `POST /event`, `GET /health`. Thread-safe queue for events. |
| `notifier/ui/overlay.py` | Frameless always-on-top overlay. Fade in/out, click-to-focus, auto-dismiss, severity-colored left border. |
| `notifier/ui/tray.py` | System tray icon with quit action. |
| `notifier/utils/window_focus.py` | Terminal window detection and focus logic. Session-to-hwnd binding, pid/class/title scoring, `AttachThreadInput` for foreground steal. |
| `notifier/utils/sound.py` | Notification sound playback. |
| `notifier/single_instance.py` | Named mutex (`Global\ccCueNotifier`) to prevent duplicate notifier processes. |
| `notifier/event_models.py` | Event data models. |
| `config/state_manager.py` | Safe mutation of `~/.claude/settings.json`. Backup/restore/baseline/rollback with SHA-256 integrity. Only modifies `hooks.Notification/Stop/PermissionRequest` entries. |
| `cli/main.py` | CLI interface for install/uninstall/doctor/restore/list-backups. Supports runtime installation via `installer/runtime_installer.py`. |
| `installer/runtime_installer.py` | Copies runtime dirs (hooks, notifier, cli, config, installer) to `%LOCALAPPDATA%\ccCue` with staging/backup/rollback. |
| `installer/source_downloader.py` | Downloads runtime source for installation. |

### Key Constants

- Notifier port: `19527` (defined in both `hooks/notify_hook.py` and `notifier/server.py`)
- Managed hook events: `Notification`, `Stop`, `PermissionRequest`
- Log path: `%LOCALAPPDATA%\ccCue\logs\notifier.log` (rotating, 2MB x 5)
- Runtime data: `%LOCALAPPDATA%\ccCue\` (backups in `backups/`, state in `state/`)
- Session cache: `%LOCALAPPDATA%\ccCue\runtime\seen_sessions.json` (max 200 entries)

### Dependencies

- **PySide6** (>=6.6.0) — overlay, tray, hotkey
- **pywin32** (>=306) — terminal detection, window focus, process enumeration
- **pytest** (>=8.0) — testing

Target platform: **Windows 10/11 with Windows Terminal only**.

## Constraints

1. **No wrapper approach.** Claude must run natively in the terminal. Hooks are the only event source.
2. **settings.json safety.** All writes to `~/.claude/settings.json` must backup first, validate after, and rollback on failure. Never corrupt user settings.
3. **Hooks always exit 0.** `bootstrap.py` and `notify_hook.py` wrap all logic in try/except that exits 0 to never block the Claude workflow.
4. **Keep docs aligned.** When changing code, update `docs/` design documents and `CLAUDE.md` in the same change.

## Testing

Tests live in `tests/` and cover:
- `test_hook.py` — hook payload parsing and event mapping
- `test_events.py` — event model validation
- `test_server.py` — HTTP server endpoints and queue behavior
- `test_state_manager.py` — settings backup/restore/install/uninstall/doctor
- `test_bootstrap.py` — bootstrap notifier startup logic
- `test_runtime_installer.py` — runtime file installation

Tests use `pytest` with `tmp_path` fixtures. No external services or GUI needed for tests.

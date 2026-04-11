# ccCue

Windows desktop notification and terminal refocus helper for Claude Code.

> Platform note: currently supports Windows 10/11 only.

## Overview

ccCue listens to Claude Hooks events, shows desktop notifications on Windows, and helps you jump back to the terminal quickly.

## Highlights

- Hooks pipeline: `hooks -> bootstrap -> notifier`
- Notification UI: overlay + tray + sound
- Refocus flow: click notification + global hotkey
- Safe settings workflow: backup / validate / rollback / restore
- CLI commands: `install / uninstall / doctor / restore / list-backups`

## Architecture

```text
Claude hooks (stdin JSON)
  -> hooks/bootstrap.py
  -> hooks/notify_hook.py
  -> notifier/server.py (/event)
  -> notifier UI (overlay / tray / focus-back)
```

## Installation

### Option A: EXE installer (general users)

1. Download `ccCue-Setup-*.exe` from Releases
2. Run the installer
3. You can choose a custom install path (for example `D:\Apps\ccCue`)

Note:
- The current installer script in this repository still checks Python availability.
- The roadmap already targets a standalone runtime that removes user-side Python dependency.

### Option B: Source + one-command install (developers)

```bash
git clone https://github.com/cmyandlqs/ClaudeCue.git
cd ClaudeCue
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m cli.main install --source . --target "%LOCALAPPDATA%\ccCue"
```

Install to `D:` example:

```bash
.venv\Scripts\python -m cli.main install --source . --target "D:\Apps\ccCue"
```

## Daily Usage

1. Run Claude Code as usual
2. ccCue receives hook events and shows notifications
3. Click notifications or use hotkey to refocus terminal

## Diagnosis and Recovery

```bash
.venv\Scripts\python -m cli.main doctor
.venv\Scripts\python -m cli.main doctor --json
.venv\Scripts\python -m cli.main restore --latest
.venv\Scripts\python -m cli.main uninstall --purge
```

`doctor` supports `PASS / WARN / FAIL` grading and outputs remediation hints for failed checks.

## Development

```bash
.venv\Scripts\python -m ruff check cli config tests
.venv\Scripts\python -m vulture cli config tests --min-confidence 80
.venv\Scripts\python -m pytest -q
```

## Documentation

- [Requirements (Chinese)](./docs/需求文档.md)
- [Problems & Solutions (Chinese)](./docs/问题文档.md)
- [Improvement Plan (Chinese)](./docs/项目改进文档.md)

## Roadmap (short)

- Standalone runtime delivery
- Standardized release flow
- Better diagnostics and focus-back stability

## License

Not declared yet. Add a `LICENSE` file and update this section.

---

If ccCue helped you, give it a Star before it starts emotionally buffering ✨

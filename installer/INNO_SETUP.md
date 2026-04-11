# Inno Setup Packaging

## Prerequisites

1. Install Inno Setup 6.
2. Optional: provide bundled runtime at `runtime/python/python.exe` to avoid system Python dependency.

## Build

Run:

```bat
installer\build_inno.bat
```

Output installer:

- `installer\ccCue-Setup-0.2.0.exe`

## Runtime behavior

- Install phase runs:
  - `{app}\installer\install.bat --no-pause`
- Uninstall phase runs:
  - `{app}\installer\uninstall.bat --no-pause`

## Notes

- Installer copies runtime code (`hooks`, `notifier`, `cli`, `config`, `installer`) into `%LOCALAPPDATA%\ccCue`.
- If bundled runtime exists, installer/CLI prefer it first (`runtime\python\python.exe`).
- `--purge` removes ccCue backup/state files after uninstall.

# Inno Setup Packaging

## Prerequisites

1. Install Inno Setup 6.
2. Ensure `python` command is available in PATH on target machine.

## Build

Run:

```bat
installer\build_inno.bat
```

Output installer:

- `installer\ccCue-Setup-0.2.0.exe`

## Runtime behavior

- Install phase runs:
  - `python -m cli.main install --project-root "{app}"`
- Uninstall phase runs:
  - `python -m cli.main uninstall --purge`

## Notes

- Installer copies runtime code (`hooks`, `notifier`, `cli`, `config`, `installer`) into `%LOCALAPPDATA%\ccCue`.
- If Python is missing, setup aborts with guidance.
- `--purge` removes ccCue backup/state files after uninstall.

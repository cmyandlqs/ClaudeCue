# Repository Guidelines

## Current State
This repository is in a docs-first reset state. The previous `wrapper` implementation was removed because Claude Code requires a real TTY and cannot be reliably monitored through `subprocess.Popen(..., stdout=PIPE)` on Windows. Do not restore the old wrapper pipeline.

## Planned Structure
The next implementation should follow a hook-based architecture:

- `hooks/`: Claude Code hook scripts that read hook JSON from stdin and forward normalized events.
- `notifier/`: the desktop presentation layer, including overlay, tray, sound, focus-back behavior, and local event intake.
- `installer/`: Windows setup scripts such as `install.bat`.

The display layer is still required. Only the event source changes: hooks replace stdout/stderr scraping.

## Source Of Truth
Before adding code, keep these root documents aligned:

- `需求.md`
- `方案设计.md`
- `第一阶段开发文档.md`
- `CLAUDE.md`

If code and documents disagree, update the documents first or in the same change.

## Development Rules
Target platform is Windows with Windows Terminal. Keep Claude running natively in the user’s terminal and use localhost HTTP or an equivalent local bridge between hooks and the notifier app. Separate responsibilities clearly:

- hook ingestion
- event normalization
- notifier presentation
- installation and user configuration

Do not couple hook parsing directly to UI widgets.

## Testing Guidance
There is no active source tree at the moment. When implementation resumes, tests should focus on hook payload parsing, event mapping, notifier HTTP intake, and non-GUI presentation logic. Avoid rebuilding heavy end-to-end tests around terminal wrapping.

## Commit Guidance
Use small, architecture-scoped commits such as `docs: switch plan to hooks` or `feat: add notification hook bridge`. Avoid mixed commits that combine installer, notifier, and protocol changes without a clear boundary.

# AGENTS.md — DOSping

DOSping is a terminal-based network stress testing tool (Python, Textual, asyncio).
Main entry: `dosping.py` · settings editor: `settings.py` · config layer: `config.py` · event log: `eventlog.py`.

## Current version

- `APP_VERSION = "2.1.0"`, `APP_CODENAME = "juice"` — defined in `config.py`
- Reflected in `pyproject.toml`, the settings menu (About panel + sub-title), the debug log header, `docs/index.html`, both installers, and this file's changelog rule below

## Changelog requirement (README.md)

Every changelog entry in `README.md` must include the date the version was introduced, e.g. `### v2.1.0 "juice" — introduced 2026-11-01`. An entry without an introduction date is incomplete. Add one entry per version (including older versions such as v2.0.0) and put all of that version's changes into its entry.

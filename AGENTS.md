# AGENTS.md

Guide for coding agents working in this repository. Read this before making changes.

## 1. Project

DOSping is a terminal network stress-testing tool (Python, Textual TUI). It floods a target with concurrent TCP connections while monitoring connectivity via ICMP ping and TCP port probes, and includes a port scanner, an event log, and a settings editor.

> FOR PENETRATION TESTING AND EDUCATIONAL PURPOSES ONLY. Unauthorized use against systems you don't own or have permission to test is illegal. You accept full responsibility. Use at your own risk.

(The canonical text is the `DISCLAIMER` constant in `config.py`.)

Requires **Python 3.12+**.

## 2. Run / build / test commands

```bash
pip install -e .        # install in editable mode (also installs the `dosping` command)
dosping                 # launch the TUI
python settings.py      # launch the standalone settings editor
pytest                  # run the test suite (install with: pip install -e ".[dev]")
```

No linter or type checker is configured in this repo. Don't introduce one unasked.

## 3. File map

| File | Purpose |
| --- | --- |
| `dosping.py` | Main Textual app: home screen, session tabs, flood/scan panels, settings modal, command palette. Entry point `dosping:main`. |
| `flooder.py` | Async TCP flood engine (concurrent connections, stats reporting). |
| `scanner.py` | Async port scanner and network scan engine, banner grabbing. |
| `config.py` | Config schema (`_default_config()`), migration/clamping (`_migrate()`), `Config` wrapper for `config.json`, shared constants (`APP_VERSION`, `DISCLAIMER`, guardrails). |
| `theme.py` | Theme palettes and live theming (`apply_live`, `rebuild_from_config`). |
| `eventlog.py` | Disk event log under `logs/`: level gating, rotation, retention, `log_event` / `log_error`. |
| `settings.py` | Full settings editor (`SettingsScreen`), also runnable standalone via `python settings.py`. |
| `pyproject.toml` | Package metadata, version, dependencies, `dosping` script entry, `py-modules` list. |
| `requirements.txt` | Runtime dependencies (mirrors `pyproject.toml`). |
| `setup.sh` | Bash installer/launcher: clones the repo if needed, installs, optionally runs. Supports `--channel=stable\|dev`. |
| `setup.bat` | Windows equivalent of `setup.sh`. |
| `README.md` | User-facing overview, quick start, project structure. |
| `docs/index.html` | Standalone documentation site (also served at the docs URL in `config.py`). |
| `tests/` | pytest suite: engine, config, persistence, and event-log tests (`test_*.py`), shared fixtures in `conftest.py`. |
| `.gitignore` | Ignored artifacts: `config.json`, `logs/`, build output, editor/OS junk. |

## 4. Conventions an agent must follow

- **Config changes go through `_default_config()` + `_migrate()` in `config.py`.** Add new keys there, additively, with clamping/coercion for hand-edited garbage. Never read or write `config.json` directly; use `get_config()` / `Config.get` / `Config.set` / `Config.save`.
- **Version lives in two places, kept in sync by hand:** `config.py:APP_VERSION` and `pyproject.toml`'s `version`. There is no version-sync tooling.
- **Event logging uses `eventlog.log_event(category, event, **fields)`** and `eventlog.log_error(component, context, exc)`. Reuse an existing category (`app`, `config`, `session`, `flood`, `scanner`, `settings`, `ui`, `update`, `error`) rather than inventing one per feature. Categories must also be allowed at the configured verbosity in `eventlog.py` (`_LEVEL_CATEGORIES`, `_ALWAYS_EVENTS`); check that a new category actually gets written.
- **Background and network work in the TUI runs in a worker.** Use `self.run_worker(self._some_async_method())`, and inside it call blocking code (`requests`, `subprocess`) via `await asyncio.to_thread(...)`. Never call `requests` or `subprocess` directly from a synchronous UI callback.
- **Tests cover engine, config, and logging logic only.** There are no automated UI tests for the Textual screens. For new UI code, do a `python -c "import <module>"` smoke check. Don't add a new UI test framework unasked.
- **Tests must not touch the network, real git repos, or the real `config.json`.** Use `monkeypatch` and `tmp_path`, as the existing tests do.

## 5. Branches & channels

- **`main` is the stable channel.** It holds tagged releases (e.g. `v3.7.1`). The `curl | bash` installer tracks it by default.
- **`dev` is the dev channel.** It gets every commit, untagged, bleeding edge. Day-to-day work lands on `dev`. When a release is cut, `dev` is merged or fast-forwarded into `main` and tagged.
- **Never rename `main`.** That would break installer URLs and existing clones.

## 6. Commit style

Short imperative subject line with a conventional prefix where it fits (`feat:`, `fix:`, `docs:`), matching the existing history:

```
feat: add advanced.update config schema
docs: mention auto-updating and AGENTS.md in README
```

Release commits use the version and codename, e.g. `v3.7.1: Code Red - Advanced Event Logging & Log Settings`. Run `git log --oneline -20` to see the current style before committing.

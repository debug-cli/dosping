# ═══════════════════════════════════════════════════════════════
#  tests/test_updater.py — update checker / applier (updater.py)
# ═══════════════════════════════════════════════════════════════
#  Every git, pip and HTTP call is mocked. No test touches the
#  network, a real repository, or the real config.json.

import subprocess
import sys

import requests

import updater


class FakeResponse:
    def __init__(self, *, json_data=None, text=""):
        self._json = json_data
        self.text = text

    def raise_for_status(self):
        return None

    def json(self):
        return self._json


def _ok(args, **kwargs):
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def _record(monkeypatch, returncode=0, stdout="", stderr=""):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


# ── check_for_update ─────────────────────────────────────────

def test_check_not_git_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: False)
    result = updater.check_for_update(str(tmp_path), "stable", "3.8.0")
    assert result.error is not None
    assert result.update_available is False


def test_check_network_error(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_local_commit_sha", lambda p: "abc123")

    def boom(*a, **k):
        raise requests.RequestException("down")

    monkeypatch.setattr(requests, "get", boom)
    result = updater.check_for_update(str(tmp_path), "stable", "3.8.0")
    assert result.error is not None
    assert result.update_available is False


def test_check_reports_update_available(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_local_commit_sha", lambda p: "old111")

    def fake_get(url, **kwargs):
        assert kwargs["timeout"] > 0  # every call carries an explicit timeout
        if "api.github.com" in url:
            assert url.endswith("/commits/dev")
            return FakeResponse(json_data={"sha": "new222"})
        assert url.startswith("https://raw.githubusercontent.com/")
        assert "/dev/pyproject.toml" in url
        return FakeResponse(text='[project]\nversion = "3.8.1"\n')

    monkeypatch.setattr(requests, "get", fake_get)
    result = updater.check_for_update(str(tmp_path), "dev", "3.8.0")
    assert result.error is None
    assert result.update_available is True
    assert result.remote_sha == "new222"
    assert result.current_sha == "old111"
    assert result.remote_version == "3.8.1"


def test_check_up_to_date(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_local_commit_sha", lambda p: "same")
    monkeypatch.setattr(
        requests, "get",
        lambda url, **k: FakeResponse(json_data={"sha": "same"})
        if "api.github.com" in url
        else FakeResponse(text='[project]\nversion = "3.8.0"\n'),
    )
    result = updater.check_for_update(str(tmp_path), "stable", "3.8.0")
    assert result.error is None
    assert result.update_available is False


def test_check_unknown_channel(tmp_path):
    result = updater.check_for_update(str(tmp_path), "nightly", "3.8.0")
    assert result.error is not None
    assert result.update_available is False


# ── apply_update ─────────────────────────────────────────────

def test_apply_not_git_checkout(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: False)
    result = updater.apply_update(str(tmp_path), "stable")
    assert result.success is False
    assert result.error is not None


def test_apply_refuses_dirty_tree(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_working_tree_dirty", lambda p: True)
    calls = _record(monkeypatch)
    result = updater.apply_update(str(tmp_path), "stable")
    assert result.success is False
    assert "dirty" in (result.error or "").lower()
    # Refused before any git mutation.
    assert calls == []


def test_dirty_check_ignores_untracked_files(monkeypatch, tmp_path):
    # Untracked files (e.g. a local .agents/ folder) cannot block a
    # fast-forward pull, so the dirty check must not count them.
    calls = _record(monkeypatch, stdout="")
    assert updater._working_tree_dirty(str(tmp_path)) is False
    status_calls = [c for c in calls if "status" in c]
    assert status_calls, "expected a git status call"
    assert "--untracked-files=no" in status_calls[0]


def test_dirty_check_sees_modified_tracked_file(monkeypatch, tmp_path):
    _record(monkeypatch, stdout=" M config.py\n")
    assert updater._working_tree_dirty(str(tmp_path)) is True


def test_apply_checks_out_target_branch(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_working_tree_dirty", lambda p: False)
    calls = _record(monkeypatch)
    updater.apply_update(str(tmp_path), "dev")
    joined = [" ".join(c) for c in calls]
    assert any("checkout" in c and "dev" in c for c in joined)
    # Fetch and checkout must happen before the pull.
    idx = {name: next(i for i, c in enumerate(joined) if name in c)
           for name in ("fetch", "checkout", "pull")}
    assert idx["fetch"] < idx["checkout"] < idx["pull"]


def test_apply_reinstalls_after_pull(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_working_tree_dirty", lambda p: False)
    calls = _record(monkeypatch)
    updater.apply_update(str(tmp_path), "stable")
    joined = [" ".join(c) for c in calls]
    assert any("pip" in c and "install" in c for c in joined)
    pip_call = next(c for c in calls if "pip" in c)
    assert pip_call[0] == sys.executable


def test_apply_pull_failure_reports_stderr(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_working_tree_dirty", lambda p: False)

    def fake_run(args, **kwargs):
        if "pull" in args:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="fatal: Not possible to fast-forward")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = updater.apply_update(str(tmp_path), "stable")
    assert result.success is False
    assert "fast-forward" in (result.error or "")


def test_apply_reports_new_version(monkeypatch, tmp_path):
    monkeypatch.setattr(updater, "is_git_checkout", lambda p: True)
    monkeypatch.setattr(updater, "_working_tree_dirty", lambda p: False)
    _record(monkeypatch)
    (tmp_path / "pyproject.toml").write_text('[project]\nversion = "3.8.1"\n', encoding="utf-8")
    result = updater.apply_update(str(tmp_path), "stable")
    assert result.success is True
    assert result.new_version == "3.8.1"
    assert result.error is None

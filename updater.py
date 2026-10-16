# ═══════════════════════════════════════════════════════════════
#  updater.py  —  DOSping update checker / applier (v3.8.0)
# ═══════════════════════════════════════════════════════════════
#  UI-agnostic.  Callers pass the channel and the checkout path in
#  explicitly; this module never reads config.json and never logs
#  (the caller records the result via eventlog).
#
#  Channels map to git branches:  stable → main,  dev → dev.
#
#  check_for_update()  — GitHub REST + raw.githubusercontent, read-only.
#  apply_update()      — mutates the working tree: fetch, checkout,
#                        pull --ff-only, pip install -e.  Refuses on a
#                        dirty tree before touching git.  Never restarts.
# ═══════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from typing import Optional

import requests

REPO_SLUG = "debug-cli/dosping"
CHANNEL_BRANCHES = {"stable": "main", "dev": "dev"}
API_URL = "https://api.github.com/repos/" + REPO_SLUG + "/commits/{branch}"
RAW_URL = "https://raw.githubusercontent.com/" + REPO_SLUG + "/{branch}/pyproject.toml"

GIT_TIMEOUT = 5.0
PIP_TIMEOUT = 300.0  # dependency installs can be slow; not a UI-blocking call


@dataclass
class UpdateCheckResult:
    channel: str
    current_version: str
    remote_version: Optional[str] = None
    current_sha: Optional[str] = None
    remote_sha: Optional[str] = None
    update_available: bool = False
    error: Optional[str] = None


@dataclass
class UpdateApplyResult:
    success: bool
    new_version: Optional[str] = None
    error: Optional[str] = None


def repo_dir() -> str:
    """Directory containing this module (the checkout, when run from git)."""
    return os.path.dirname(os.path.abspath(__file__))


def is_git_checkout(path: str) -> bool:
    """True when *path* looks like a git working tree (has a .git entry)."""
    return os.path.exists(os.path.join(path, ".git"))


def _run_git(path: str, args: list[str], timeout: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=path,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _local_commit_sha(path: str) -> str:
    r = _run_git(path, ["rev-parse", "HEAD"], GIT_TIMEOUT)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git rev-parse HEAD failed")
    return r.stdout.strip()


def _working_tree_dirty(path: str) -> bool:
    """True when tracked files have local modifications.

    Untracked files are ignored on purpose: they cannot block a
    fast-forward pull, and a stray local folder (e.g. .agents/) should
    not stop updates.
    """
    r = _run_git(path, ["status", "--porcelain", "--untracked-files=no"], GIT_TIMEOUT)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "git status failed")
    return bool(r.stdout.strip())


def _read_version(pyproject_text: str) -> str:
    return tomllib.loads(pyproject_text)["project"]["version"]


def check_for_update(
    path: str,
    channel: str,
    current_version: str,
    timeout: float = 5.0,
) -> UpdateCheckResult:
    """Compare the local HEAD with the tip of the channel's branch.

    Never raises: any failure is reported in ``result.error``.
    """
    result = UpdateCheckResult(channel=channel, current_version=current_version)
    branch = CHANNEL_BRANCHES.get(channel)
    if branch is None:
        result.error = f"unknown update channel: {channel!r}"
        return result
    if not is_git_checkout(path):
        result.error = "not a git checkout — cannot check for updates"
        return result

    try:
        current_sha = _local_commit_sha(path)
        api = requests.get(
            API_URL.format(branch=branch),
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json"},
        )
        api.raise_for_status()
        remote_sha = api.json()["sha"]

        raw = requests.get(RAW_URL.format(branch=branch), timeout=timeout)
        raw.raise_for_status()
        remote_version = _read_version(raw.text)
    except (requests.RequestException, subprocess.SubprocessError,
            OSError, KeyError, ValueError, RuntimeError) as exc:
        result.error = str(exc) or type(exc).__name__
        return result

    result.current_sha = current_sha
    result.remote_sha = remote_sha
    result.remote_version = remote_version
    result.update_available = remote_sha != current_sha
    return result


def apply_update(path: str, channel: str, timeout: float = 30.0) -> UpdateApplyResult:
    """Bring the checkout up to date with the channel's branch.

    Order: refuse on dirty tree → fetch → checkout target branch →
    pull --ff-only → pip install -e . (picks up dependency changes).
    Never raises: any failure is reported in ``result.error``.
    """
    branch = CHANNEL_BRANCHES.get(channel)
    if branch is None:
        return UpdateApplyResult(False, error=f"unknown update channel: {channel!r}")
    if not is_git_checkout(path):
        return UpdateApplyResult(False, error="not a git checkout — cannot update")

    try:
        if _working_tree_dirty(path):
            return UpdateApplyResult(
                False,
                error="dirty working tree — commit or stash local changes, then retry",
            )

        for label, args in (
            ("fetch", ["fetch", "origin", branch]),
            ("checkout", ["checkout", branch]),
            ("pull", ["pull", "--ff-only", "origin", branch]),
        ):
            r = _run_git(path, args, timeout)
            if r.returncode != 0:
                detail = (r.stderr or r.stdout).strip()
                return UpdateApplyResult(False, error=f"git {label} failed: {detail}")

        pip = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", ".", "--quiet"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=max(timeout, PIP_TIMEOUT),
        )
        if pip.returncode != 0:
            detail = (pip.stderr or pip.stdout).strip()
            return UpdateApplyResult(False, error=f"pip install failed: {detail}")
    except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
        return UpdateApplyResult(False, error=str(exc) or type(exc).__name__)

    new_version: Optional[str] = None
    try:
        with open(os.path.join(path, "pyproject.toml"), "r", encoding="utf-8") as f:
            new_version = _read_version(f.read())
    except (OSError, KeyError, ValueError):
        pass  # update succeeded; the version is informational only
    return UpdateApplyResult(True, new_version=new_version)

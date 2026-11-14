"""D5 — `fr_dispatch.lifecycle.invoke_lifecycle_hook` runs `FR_LIFECYCLE_HOOK_SCRIPT`.

When the env var points at an executable script, the hook is called with
`(issue_url, transition)`. When the env var is unset, no external process
is invoked. A hook crash (script missing / non-zero exit / timeout) is
logged and swallowed — the caller is a best-effort notifier, not a
transactional supervisor.
"""

from __future__ import annotations

import stat
from pathlib import Path


def _write_recorder_script(tmp_path: Path) -> tuple[Path, Path]:
    """Create a shell script that appends its argv to a log file.

    Returns `(script_path, log_path)`.
    """
    log = tmp_path / "hook-calls.log"
    script = tmp_path / "hook.sh"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script, log


def test_lifecycle_hook_invoked_directly_via_helper(tmp_path, monkeypatch):
    """`invoke_lifecycle_hook` is the public surface; tests can use it
    independently of any runner to assert the env-gated behaviour.
    """
    from fr_dispatch.lifecycle import invoke_lifecycle_hook

    script, log = _write_recorder_script(tmp_path)
    monkeypatch.setenv("FR_LIFECYCLE_HOOK_SCRIPT", str(script))

    invoke_lifecycle_hook("https://example/issues/7", "in-progress")
    assert log.exists()
    assert "in-progress" in log.read_text()


def test_lifecycle_hook_not_invoked_when_env_unset(tmp_path, monkeypatch):
    from fr_dispatch.lifecycle import invoke_lifecycle_hook

    _script, log = _write_recorder_script(tmp_path)
    monkeypatch.delenv("FR_LIFECYCLE_HOOK_SCRIPT", raising=False)

    invoke_lifecycle_hook("https://example/issues/7", "in-progress")
    assert not log.exists()


def test_lifecycle_hook_failure_is_logged_not_raised(tmp_path, monkeypatch, caplog):
    from fr_dispatch.lifecycle import invoke_lifecycle_hook

    monkeypatch.setenv("FR_LIFECYCLE_HOOK_SCRIPT", str(tmp_path / "missing.sh"))

    invoke_lifecycle_hook("https://example/issues/7", "in-progress")  # no raise
    assert any("lifecycle hook" in r.getMessage() for r in caplog.records)

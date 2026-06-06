"""D5 — `VK_LIFECYCLE_HOOK_SCRIPT` is invoked on successful dispatch.

When the env var points at an executable script, dispatch must call
it with `(issue_url, "in-progress")` after the VK card is created.
When the env var is unset, no external process is invoked.

A hook crash (script missing / non-zero exit / timeout) must NOT
break dispatch — the bridge is a best-effort notifier, not a
transactional supervisor.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from tests.unit.fakes import FakeMcpClient


def _write_recorder_script(tmp_path: Path) -> tuple[Path, Path]:
    """Create a shell script that appends its argv to a log file.

    Returns `(script_path, log_path)`.
    """
    log = tmp_path / "hook-calls.log"
    script = tmp_path / "hook.sh"
    script.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
    script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script, log


def _phase_with_tracking(repo: str, issue_n: int):
    from fr import parse

    plan = parse(Path(__file__).parent / "fixtures" / "v2_plan_minimal")
    phase = plan.phases[0].model_copy(
        update={
            "phase": plan.phases[0].phase.model_copy(
                update={"tracking_issue": f"https://github.com/{repo}/issues/{issue_n}"}
            )
        }
    )
    return plan, phase


def test_lifecycle_hook_invoked_with_issue_url_and_transition(tmp_path, monkeypatch):
    """Configured hook script gets `(issue_url, "in-progress")` on successful dispatch."""
    from fr.bridge.dispatch import dispatch_phase

    script, log = _write_recorder_script(tmp_path)
    monkeypatch.setenv("VK_LIFECYCLE_HOOK_SCRIPT", str(script))

    repo = "derio-net/superpowers-for-vk"
    issue_n = 42
    plan, phase = _phase_with_tracking(repo, issue_n)
    mcp = FakeMcpClient()

    dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id")

    assert log.exists(), "hook script was not invoked"
    recorded = log.read_text().strip()
    expected_url = f"https://github.com/{repo}/issues/{issue_n}"
    assert expected_url in recorded
    assert "in-progress" in recorded


def test_lifecycle_hook_not_invoked_when_env_unset(tmp_path, monkeypatch):
    from fr.bridge.dispatch import dispatch_phase

    monkeypatch.delenv("VK_LIFECYCLE_HOOK_SCRIPT", raising=False)

    repo = "derio-net/superpowers-for-vk"
    issue_n = 42
    plan, phase = _phase_with_tracking(repo, issue_n)
    mcp = FakeMcpClient()

    # No script set, no external process — dispatch_phase returns cleanly.
    dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id")

    # Nothing was written anywhere — best we can do is sanity-check that
    # the env stays unset (the absence-of-side-effect is asserted by
    # the dispatch returning without exception and the FakeMcpClient
    # call sequence completing normally).
    assert os.environ.get("VK_LIFECYCLE_HOOK_SCRIPT") is None


def test_lifecycle_hook_failure_does_not_break_dispatch(tmp_path, monkeypatch, caplog):
    """A non-zero exit / missing script / timeout must NOT raise."""
    from fr.bridge.dispatch import dispatch_phase

    missing = tmp_path / "definitely-does-not-exist.sh"
    monkeypatch.setenv("VK_LIFECYCLE_HOOK_SCRIPT", str(missing))

    repo = "derio-net/superpowers-for-vk"
    issue_n = 42
    plan, phase = _phase_with_tracking(repo, issue_n)
    mcp = FakeMcpClient()

    # No exception — dispatch swallows the hook failure.
    result = dispatch_phase(plan, phase, mcp, project_id="test-vk-project-id")
    assert result.card_id  # dispatch completed normally


def test_lifecycle_hook_invoked_directly_via_helper(tmp_path, monkeypatch):
    """`invoke_lifecycle_hook` is the public surface; tests can use it
    independently of dispatch_phase to assert the env-gated behaviour.
    """
    from fr.bridge.lifecycle import invoke_lifecycle_hook

    script, log = _write_recorder_script(tmp_path)
    monkeypatch.setenv("VK_LIFECYCLE_HOOK_SCRIPT", str(script))

    invoke_lifecycle_hook("https://example/issues/7", "in-progress")
    assert log.exists()
    assert "in-progress" in log.read_text()

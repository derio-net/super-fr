"""The fr-claude-cloud package wiring and the run-unit contract (cloud-triage §F).

The package registers under `fr.runners` as `claude-cloud`, builds through
`from_env()`, and meets `fr_dispatch.testing`'s run-unit contract: what a dispatch
hands its backend (here the mailbox's pending request) carries the brief and the model.
"""

from __future__ import annotations

import json

from fr_dispatch.testing import (
    check_close_contract,
    check_constructible,
    check_run_unit_contract,
    run_item,
)


def test_the_package_imports_and_names_its_runner() -> None:
    import fr_claude_cloud

    assert fr_claude_cloud.ClaudeCloudRunner.name == "claude-cloud"


def test_claude_cloud_is_a_registered_runner_whose_entry_point_is_the_class() -> None:
    from fr_claude_cloud.runner import ClaudeCloudRunner
    from fr_dispatch.registry import available_runners, load_runner, runner_units

    ep = available_runners()["claude-cloud"]
    assert ep.load() is ClaudeCloudRunner  # type: ignore[attr-defined]
    assert runner_units("claude-cloud") == frozenset({"run"})
    assert isinstance(load_runner("claude-cloud"), ClaudeCloudRunner)


def test_the_runner_meets_the_run_unit_contract() -> None:
    from fr_claude_cloud.runner import ClaudeCloudRunner

    check_constructible(ClaudeCloudRunner)
    runner = ClaudeCloudRunner.from_env()
    check_run_unit_contract(runner, run_item(), sent=lambda: json.dumps(runner.outbox()))


def test_the_runner_meets_the_close_contract() -> None:
    from fr_claude_cloud.runner import ClaudeCloudRunner

    check_close_contract(ClaudeCloudRunner.from_env(), run_item(run_id="never-dispatched"))

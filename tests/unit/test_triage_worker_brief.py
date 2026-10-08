"""The claude-cloud worker brief's first step (spec 2026-10-07-cloud-triage R19, §H,
Test Plan 13): check fr, check the two agent types, end BLOCKED naming the `agents`
artifact when they are missing (never asking for a re-home), and enter isolation
through the CLI before any edit."""

from __future__ import annotations

import pytest
import yaml
from fr.triage.batch_dispatch import CLOUD_PREFLIGHT_RUNNERS, render_brief
from fr.triage.model import Judgements

from tests.unit.test_triage_batch_dispatch import JUDGEMENTS, MEMBERS, REPO, _facts


def _brief(runner: str | None, *, remedy: str | None = None) -> str:
    j = Judgements.model_validate(yaml.safe_load(JUDGEMENTS))
    return render_brief(
        j.batches[0],
        j,
        _facts(),
        repo=REPO,
        closing_refs=[f"Closes {REPO}#{n}" for n in MEMBERS],
        reserved_version=None,
        runner=runner,
        remedy=remedy,
    )


def _preflight(brief: str) -> str:
    start = brief.index("## Before anything else")
    return brief[start : brief.index("\n## ", start + 1)]


def test_only_the_claude_cloud_runner_gets_the_preflight() -> None:
    assert CLOUD_PREFLIGHT_RUNNERS == frozenset({"claude-cloud"})
    for runner in (None, "herdr", "fake"):
        assert "## Before anything else" not in _brief(runner)


def test_the_preflight_comes_before_the_batch() -> None:
    brief = _brief("claude-cloud")
    lines = brief.splitlines()
    assert lines[0].startswith("/fr-goal ")
    assert brief.index("## Before anything else") < brief.index("Batch `lifecycle`")


def test_it_checks_fr_and_installs_super_fr_only_when_missing() -> None:
    step = _preflight(_brief("claude-cloud"))
    assert "`fr --version`" in step
    assert "only if" in step and "super-fr" in step and "scripts/install.sh" in step


def test_fr_off_path_is_found_before_it_is_called_missing() -> None:
    """p7-r6: an installed fr merely off PATH is `~/.local/bin/fr`: put it on PATH,
    never re-clone over the existing source."""
    step = _preflight(_brief("claude-cloud"))
    assert "`~/.local/bin/fr --version`" in step
    assert step.index("`fr --version`") < step.index("`~/.local/bin/fr --version`")
    assert 'export PATH="$HOME/.local/bin:$PATH"' in step


def test_a_missing_fr_is_installed_by_the_cloud_setup_script_itself() -> None:
    """p7-r6: one install recipe, the setup script `fr cloud setup-script` prints (it
    installs rsync/jq/uv and reuses an existing clone), embedded whole — never a second
    hand-written one-liner."""
    from fr import cloud

    step = _preflight(_brief("claude-cloud"))
    body = cloud.setup_script(REPO)
    assert body.strip() in step
    assert "git clone --quiet --branch main https://" not in step.replace(body.strip(), "")


def test_the_setup_script_reuses_an_existing_clone_and_installs_its_dependencies() -> None:
    from fr import cloud

    body = cloud.setup_script()
    assert 'if [ -d "$src/.git" ]' in body
    assert "checkout --quiet --force -B main origin/main" in body
    assert "clean -fdxq" in body, "a leftover file would fail install.sh's preflight"
    for dep in ("rsync", "jq", "uv"):
        assert dep in body


def test_it_checks_both_agent_types() -> None:
    step = _preflight(_brief("claude-cloud"))
    assert "`fr-spec-reviewer`" in step and "`fr-phase-executor`" in step
    assert "dispatchable" in step


def test_missing_agents_end_the_turn_blocked_naming_the_artifact() -> None:
    step = _preflight(_brief("claude-cloud"))
    assert "BLOCKED" in step and "needs_action" in step
    assert "`agents` artifact" in step
    assert "`fr init agents`" in step and "`fr migrate artifacts --yes`" in step
    assert "re-home" in step and "same way" in step


def test_isolation_is_entered_through_the_cli_before_any_edit() -> None:
    step = _preflight(_brief("claude-cloud"))
    assert "`fr isolation up --branch fr/lifecycle`" in step or "fr isolation up" in step
    assert "before any edit" in step


def test_the_remedy_block_rides_on_the_needs_action_when_given() -> None:
    from fr.cloud import AGENTS_ITEM, remedy_block

    block = remedy_block([AGENTS_ITEM])
    step = _preflight(_brief("claude-cloud", remedy=block))
    assert block.splitlines()[0] in step
    assert step.count("This is a Claude Code cloud session") == 1
    assert "This is a Claude Code cloud session" not in _preflight(_brief("claude-cloud"))


@pytest.mark.parametrize("status", ["blocked", "working", "unknown"])
def test_a_blocked_worker_is_never_asked_to_re_home(status: str) -> None:
    """A worker that stopped on the missing agents is `blocked`: drift never re-homes a
    session that is not idle, so no rehome request is emitted for that state."""
    from fr.triage.drift import Ledger, RunVersion, plan_drift

    rv = RunVersion("lifecycle", "item", "fr/lifecycle", "run-1", "5.0.0", status)
    assert plan_drift([rv], "6.0.0", Ledger()).rehomes == ()

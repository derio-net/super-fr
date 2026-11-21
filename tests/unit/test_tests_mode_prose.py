"""The declared `tests: ci` default in the executor's and fr-goal's prose (spec
2026-11-19-local-suite-cost R8, §3.F "Text changes that go with it").

The executor reads only its agent file and the orchestrator only its skill, so
each says what the brief's `tests: {mode: ci, fast_tier}` key changes: the fast
tier is the executor's last act and it returns `tests_log: none` with the fast
tier's pass/fail line; fr-goal's §5 says so too, §6 limits the early draft PR to
phases that use `tests: ci`, and §8 names the declared default and `-m ""`.
"""

from __future__ import annotations

from tests.unit.test_fr_goal_ci_evidence_prose import AGENT, _section


def _agent() -> str:
    return " ".join(AGENT.read_text().split())


def test_the_executor_runs_the_fast_tier_last_under_the_declared_default() -> None:
    agent = _agent()
    assert "`tests.mode: ci`" in agent
    assert "`fast_tier`" in agent
    assert "advisory" in agent
    # The `none` rule gains that case.
    assert "`tests_log: none`" in agent and "fast tier's pass/fail line" in agent


def test_the_executor_keeps_its_ci_mode_for_repos_that_do_not_declare_it() -> None:
    assert "**CI evidence.**" in _agent()


def test_fr_goal_section_5_says_what_tests_log_is_under_the_declared_default() -> None:
    s5 = _section(5)
    assert "`tests.mode: ci`" in s5 and "`tests_log: none`" in s5


def test_fr_goal_section_6_limits_the_early_draft_pr_to_tests_ci_phases() -> None:
    s6 = _section(6)
    assert "only to phases that use `tests: ci`" in s6


def test_fr_goal_section_8_names_the_declared_default_and_the_full_local_run() -> None:
    s8 = _section(8)
    assert "declared default" in s8
    assert '`-m ""`' in s8


def test_the_fast_tier_is_the_repos_own_never_supers_frs() -> None:
    """p3-r1: fr ships no fast tier. The executor runs the repo's `fast_tier` when
    the brief names one, else the tests its change touches; no shipped prose names
    super-fr's own `--fr-scope` as if every repo had it."""
    agent = _agent()
    assert "fr ships no fast tier" in agent
    assert "without it, run the tests your changes touch" in agent
    assert "--fr-scope" not in agent
    s5 = _section(5)
    assert "fr ships none" in s5 and "--fr-scope" not in s5

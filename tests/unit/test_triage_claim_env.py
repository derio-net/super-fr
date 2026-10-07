"""`ClaimEnv`'s fact lookups are indexed once and answer exactly what a scan would (p2-r6)."""

from __future__ import annotations

from typing import Any

from fr.triage.claim_sync import ClaimEnv
from fr.triage.model import Facts, Issue
from fr.triage.scope_config import ScopeConfig


def _issue(repo: str, n: int) -> Issue:
    return Issue(repo=repo, number=n, title=f"t{n}", state="open", url=f"https://x.example/{n}")


def _env(repos: list[str], issues: list[Issue]) -> ClaimEnv:
    facts = Facts(
        schema=6,
        scope="s",
        kind="org",
        collected_at="2026-10-06T00:00:00+00:00",
        repos=repos,
        issues=issues,
    )
    return ClaimEnv(
        me="s-1",
        config=ScopeConfig(),
        facts=facts,
        client_for=lambda r: None,  # type: ignore[arg-type,return-value]
    )


def test_lookups_match_a_linear_scan_and_the_first_match_wins() -> None:
    repos = ["acme/Alpha", "acme/beta", "other/beta"]
    issues = [_issue("acme/Alpha", 1), _issue("acme/beta", 2), _issue("other/beta", 2)]
    env = _env(repos, issues)
    for key in ("Alpha#1", "alpha#1", "beta#2", "gamma#3", "beta#9"):
        name = key.rpartition("#")[0]
        scan_repo = next((r for r in repos if r.split("/", 1)[1].lower() == name), None)
        scan_issue = next((i for i in issues if i.key == key), None)
        assert env.owner_repo(key) == scan_repo
        assert env.issue(key) == scan_issue
    assert env.owner_repo("beta#2") == "acme/beta"  # the first of two same-named repos


def test_the_indexes_are_built_once_per_env() -> None:
    env = _env(["acme/a"], [_issue("acme/a", 1)])
    env.owner_repo("a#1")
    env.issue("a#1")
    first: Any = (env._repo_index, env._issue_index)
    env.owner_repo("a#2")
    env.issue("a#2")
    assert (env._repo_index, env._issue_index) == first
    assert env._repo_index is first[0] and env._issue_index is first[1]

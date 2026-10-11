"""`GhClient.base_rules` (spec 2026-10-11-merge-train-safety §D, R12): a merge-queue
rule and a strict required-status-checks rule, on both GitHub backends and the
declared-unsupported ones. The captured `rules/branches/main` has neither, and the
captured `branches/main/protection` is a 404; the positive shapes are the documented
GitHub ruleset records, inline here because the repo's own ruleset has no such rule.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fr import gh as _gh
from fr.ghclient import BaseRules, GhClient, UnsupportedBatchOps
from fr.real_ghclient import RealGhClient
from fr.real_ghrestclient import RealGhRestClient

from tests.unit.github_rest_support import REPO, FixtureGh, R, forbidden

_QUEUE = {"type": "merge_queue", "parameters": {"merge_method": "SQUASH"}}
_STRICT = {
    "type": "required_status_checks",
    "parameters": {
        "strict_required_status_checks_policy": True,
        "required_status_checks": [{"context": "ci-ok"}],
    },
}
_LOOSE = {
    "type": "required_status_checks",
    "parameters": {
        "strict_required_status_checks_policy": False,
        "required_status_checks": [{"context": "ci-ok"}],
    },
}


def _404() -> _gh.GhError:
    return _gh.GhError(
        "gh: Branch not protected (HTTP 404)", stderr="gh: Branch not protected (HTTP 404)\n",
        returncode=1,
    )  # fmt: skip


class _Gh:
    """Answers `rules/branches/main` with *rules* and `.../protection` with *protection*
    (a dict, or an exception to raise)."""

    def __init__(self, rules: list[dict[str, Any]], protection: dict[str, Any] | Exception):
        self.rules, self.protection = rules, protection
        self.calls: list[str] = []

    def __call__(self, args: list[str]) -> str:
        assert args[0] == "api"
        route = args[-1]
        self.calls.append(route)
        if route.endswith("/protection"):
            if isinstance(self.protection, Exception):
                raise self.protection
            return json.dumps(self.protection)
        assert route.endswith("/rules/branches/main"), route
        return json.dumps(self.rules)


def test_the_captured_rules_carry_neither() -> None:
    fake = FixtureGh()
    assert RealGhRestClient(run=fake).base_rules(REPO, "main") == BaseRules(False, False)
    assert fake.routes() == [f"{R}/rules/branches/main", f"{R}/branches/main/protection"]


def test_a_merge_queue_rule_sets_merge_queue() -> None:
    got = RealGhRestClient(run=_Gh([_QUEUE], _404())).base_rules(REPO, "main")
    assert got == BaseRules(merge_queue=True, strict_checks=False)


def test_a_strict_required_status_checks_rule_sets_strict_checks() -> None:
    got = RealGhRestClient(run=_Gh([_STRICT], _404())).base_rules(REPO, "main")
    assert got == BaseRules(merge_queue=False, strict_checks=True)


def test_a_loose_required_status_checks_rule_is_not_strict() -> None:
    assert (
        RealGhRestClient(run=_Gh([_LOOSE], _404())).base_rules(REPO, "main").strict_checks is False
    )


def test_classic_protection_strict_sets_strict_checks() -> None:
    fake = _Gh([], {"required_status_checks": {"strict": True, "contexts": ["ci-ok"]}})
    assert RealGhRestClient(run=fake).base_rules(REPO, "main").strict_checks is True


def test_classic_protection_not_strict_stays_false() -> None:
    fake = _Gh([_LOOSE], {"required_status_checks": {"strict": False}})
    assert RealGhRestClient(run=fake).base_rules(REPO, "main").strict_checks is False


def test_a_protection_403_is_raised_not_read_as_not_strict() -> None:
    with pytest.raises(_gh.GhError, match="403"):
        RealGhRestClient(run=FixtureGh(fail=forbidden)).base_rules(REPO, "main")


def test_gh_client_reads_the_same_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _Gh([_QUEUE, _STRICT], _404())
    monkeypatch.setattr(_gh, "_run_gh", fake)
    assert RealGhClient().base_rules(REPO, "main") == BaseRules(True, True)
    assert fake.calls == [f"{R}/rules/branches/main"]  # strict from the rules: no second read


def test_the_verb_is_on_the_protocol_and_every_client() -> None:
    assert "base_rules" in GhClient.__dict__
    for client in (RealGhClient(), RealGhRestClient(), UnsupportedBatchOps()):
        assert callable(client.base_rules)


def test_an_unsupported_forge_has_neither_rule_and_raises_nothing() -> None:
    assert UnsupportedBatchOps().base_rules(REPO, "main") == BaseRules(False, False)

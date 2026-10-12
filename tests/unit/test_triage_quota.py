"""Pure pacing decisions (spec 2026-10-12-quota-pacing §A, R1-R5, R13)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fr.triage import quota
from fr.triage.pacing_state import PacingState

NOW = datetime(2026, 10, 12, 16, 30, tzinfo=UTC)
RESET = datetime(2026, 10, 12, 16, 43, tzinfo=UTC)


def _raw(graphql: int = 812, core: int = 4900) -> dict:
    # Shape of `gh api rate_limit` (captured 2026-10-12; the free route).
    stamp = int(RESET.timestamp())
    return {
        "resources": {
            "core": {"limit": 5000, "used": 5000 - core, "remaining": core, "reset": stamp},
            "graphql": {
                "limit": 5000,
                "used": 5000 - graphql,
                "remaining": graphql,
                "reset": stamp,
            },
            "search": {"limit": 30, "used": 0, "remaining": 30, "reset": stamp},
        },
        "rate": {"limit": 5000, "used": 100, "remaining": core, "reset": stamp},
    }


def _budget(remaining: int, resource: str = "graphql") -> quota.Budget:
    return quota.Budget(resource, remaining, 5000, RESET)


def test_graphql_api_paces_on_the_lower_of_graphql_and_core() -> None:
    budget = quota.budget_from_rate_limit(_raw(graphql=812, core=4900), "graphql")
    assert (budget.resource, budget.remaining, budget.limit) == ("graphql", 812, 5000)
    assert budget.reset == RESET
    low_core = quota.budget_from_rate_limit(_raw(graphql=4000, core=100), "graphql")
    assert low_core.resource == "core"


def test_rest_api_paces_on_core_only() -> None:
    budget = quota.budget_from_rate_limit(_raw(graphql=0, core=4900), "rest")
    assert (budget.resource, budget.remaining) == ("core", 4900)


def test_an_unusable_rate_limit_answer_is_refused() -> None:
    with pytest.raises(ValueError):
        quota.budget_from_rate_limit({"resources": {}}, "graphql")


@pytest.mark.parametrize(
    "text",
    [
        "GraphQL: API rate limit exceeded for user ID 123.",
        "gh: API rate limit exceeded for user ID 1. (HTTP 403)",
        "You have exceeded a secondary rate limit (HTTP 403)",
        "HTTP 429 rate limit",
        "RATE_LIMITED",
    ],
)
def test_rate_limit_text_is_recognised(text: str) -> None:
    assert quota.is_rate_limited(text)


@pytest.mark.parametrize("text", ["HTTP 404 Not Found", "timed out after 30s", ""])
def test_other_failures_are_not_rate_limits(text: str) -> None:
    assert not quota.is_rate_limited(text)


def test_ample_budget_runs() -> None:
    pace = quota.decide(_budget(4000), 0.2, NOW, PacingState())
    assert pace.kind == "run" and not pace.essential


def test_below_the_floor_is_essential_only() -> None:
    pace = quota.decide(_budget(812), 0.2, NOW, PacingState(), interval=120)
    assert pace.kind == "essential" and pace.essential
    assert pace.until == NOW + timedelta(seconds=480)  # R7: four intervals


def test_exhausted_budget_waits_for_the_reset_plus_thirty_seconds() -> None:
    pace = quota.decide(_budget(0), 0.2, NOW, PacingState())
    assert pace.kind == "wait" and pace.until == RESET + timedelta(seconds=30)


def test_a_recorded_wait_in_the_future_holds() -> None:
    until = NOW + timedelta(minutes=5)
    pace = quota.decide(_budget(4000), 0.2, NOW, PacingState(wait_until=until))
    assert pace.kind == "wait" and pace.until == until
    over = quota.decide(_budget(4000), 0.2, NOW, PacingState(wait_until=NOW))
    assert over.kind == "run"


def test_an_unreadable_budget_fails_open() -> None:
    assert quota.decide(None, 0.2, NOW, PacingState()).kind == "run"


def test_exhaustion_after_a_rate_limit_waits_for_the_reset() -> None:
    pace, state = quota.after_rate_limit(_budget(0), NOW, PacingState(), 120)
    assert pace.until == RESET + timedelta(seconds=30)
    assert state.wait_until == pace.until  # R15: every rate limit writes wait_until
    assert state.backoff == 0


def test_secondary_limit_backs_off_exponentially_to_a_cap() -> None:
    state = PacingState()
    waits = []
    for _ in range(8):
        pace, state = quota.after_rate_limit(_budget(900), NOW, state, 120)
        assert pace.until is not None
        waits.append((pace.until - NOW).total_seconds())
    assert waits[:3] == [120, 240, 480]
    assert waits[3:] == [900] * 5
    assert state.backoff == 8


def test_a_clean_pass_resets_the_backoff() -> None:
    _, state = quota.after_rate_limit(_budget(900), NOW, PacingState(), 120)
    clean = quota.clean_pass(state)
    assert clean.backoff == 0 and clean.wait_until is None


def test_the_quota_line_names_resource_remaining_reset_and_action() -> None:
    pace = quota.decide(_budget(812), 0.2, NOW, PacingState(), interval=120)
    assert quota.quota_line(_budget(812), 0.2, pace, NOW) == (
        "quota: graphql 812/5000 (16%), resets 16:43Z; below floor 20%: "
        "essential-only pass, dispatch held, next pass in 8m"
    )
    wait = quota.decide(_budget(0), 0.2, NOW, PacingState())
    line = quota.quota_line(_budget(0), 0.2, wait, NOW)
    assert line.startswith("quota: graphql 0/5000 (0%), resets 16:43Z; exhausted: waiting")

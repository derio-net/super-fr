"""fr.checkstate: the one check-verdict rule (spec 2026-11-24-ci-economy R3)."""

from __future__ import annotations

import fr.checkstate as checkstate
import pytest
from fr.checkstate import FAILING_BUCKETS, bucket_verdict, is_superseded, verdict_of


def test_the_module_names_its_spec() -> None:
    assert "2026-11-24-ci-economy" in (checkstate.__doc__ or "")


@pytest.mark.parametrize(
    "state", ["SUCCESS", "success", "SKIPPED", "skipped", "NEUTRAL", "Neutral"]
)
def test_finished_and_harmless_states_pass(state: str) -> None:
    assert verdict_of(state) == "pass"


@pytest.mark.parametrize(
    "state", ["CANCELLED", "cancelled", "PENDING", "QUEUED", "IN_PROGRESS", "EXPECTED", "", "bogus"]
)
def test_cancelled_unfinished_and_unknown_states_are_pending(state: str) -> None:
    assert verdict_of(state) == "pending"


@pytest.mark.parametrize(
    "state",
    ["FAILURE", "failure", "ERROR", "error", "TIMED_OUT", "timed_out", "ACTION_REQUIRED",
     "STARTUP_FAILURE", "STALE", "stale"],
)  # fmt: skip
def test_failed_states_fail(state: str) -> None:
    assert verdict_of(state) == "fail"


def test_none_reads_as_pending() -> None:
    assert verdict_of(None) == "pending"


def test_only_the_fail_bucket_fails() -> None:
    assert FAILING_BUCKETS == {"fail"}
    assert bucket_verdict("fail") == "fail"
    assert bucket_verdict("cancel") == "pending"
    assert bucket_verdict("pending") == "pending"
    assert bucket_verdict("skipping") == "pass"
    assert bucket_verdict("pass") == "pass"
    assert bucket_verdict("") == "pending"


def test_superseded_is_cancelled_alone() -> None:
    assert is_superseded("CANCELLED") and is_superseded("cancelled")
    assert not is_superseded("FAILURE") and not is_superseded("") and not is_superseded(None)

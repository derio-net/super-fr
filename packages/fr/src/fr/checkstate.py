"""One definition of a GitHub check's verdict: pass, pending or fail.

Spec 2026-11-24-ci-economy R3: every reader that turns a check on a pull-request head or
a merge-queue combination into a verdict reads a ``CANCELLED`` check as superseded, that
is pending, never failing. A newer run replaces a cancelled one (CI cancels a superseded
pull-request run); one that no newer run replaces stays pending, and the merge queue
reports it late (R4).

Stdlib only and no ``fr`` import, so every package layer may use it.
"""

from __future__ import annotations

from typing import Final, Literal

Verdict = Literal["pass", "pending", "fail"]

#: A check's conclusion (or a status context's state) that passes, lower case.
PASSED_STATES: Final = frozenset({"success", "skipped", "neutral"})

#: One that fails, lower case: the check-run conclusions and the status-context states
#: `error` and `failure`. `failed` is the spelling some forges' rollups use.
FAILED_STATES: Final = frozenset(
    {"failure", "failed", "error", "timed_out", "action_required", "startup_failure", "stale"}
)

#: One whose run a newer run superseded: pending, never failing.
SUPERSEDED_STATES: Final = frozenset({"cancelled"})

#: The `gh pr checks` buckets that fail. `cancel` is pending; `skipping` passes.
FAILING_BUCKETS: Final = frozenset({"fail"})
_PASSING_BUCKETS: Final = frozenset({"pass", "skipping"})


def verdict_of(state: str | None) -> Verdict:
    """A check's conclusion or state, any case, as `pass`, `pending` or `fail`. A
    cancelled check, an unfinished one and an unknown state are all `pending`."""
    key = (state or "").lower()
    if key in PASSED_STATES:
        return "pass"
    if key in FAILED_STATES:
        return "fail"
    return "pending"


def is_superseded(state: str | None) -> bool:
    """True for a cancelled check: a run a newer one replaces, or one still owed one."""
    return (state or "").lower() in SUPERSEDED_STATES


def bucket_verdict(bucket: str | None) -> Verdict:
    """A `gh pr checks` bucket as a verdict: `cancel` and any unknown bucket are pending."""
    if bucket in FAILING_BUCKETS:
        return "fail"
    if bucket in _PASSING_BUCKETS:
        return "pass"
    return "pending"

"""The batch model, its derived stages and the open-batch rule
(spec 2026-09-25-triage-batches §3.A, §3.E stage; Test Plan 1-2).

Everything here is pure: judgements and facts are constructed in memory, and
the one write (`save_batches`) goes to tmp_path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.triage.batch import (
    BatchConflictError,
    batch_branch,
    batch_item_id,
    batch_pr,
    check_open_membership,
    derive_batch_stage,
    is_open,
    save_batches,
)
from fr.triage.errors import TriageError
from fr.triage.model import (
    JUDGEMENTS_SCHEMA,
    Batch,
    Facts,
    Issue,
    Judgements,
    PullRequest,
    load_judgements,
)
from fr.triage.stage import derive_stage
from pydantic import ValidationError

REPO = "derio-net/super-fr"
BRANCH = "feat/batch-lifecycle"

_BASE: dict[str, Any] = {
    "schema": 2,
    "tiers": [{"n": 1, "title": "Now"}],
    "issues": {
        "super-fr#577": {"tier": 1},
        "super-fr#575": {"tier": 1},
        "super-fr#471": {"tier": 1},
    },
}


def _judgements(*batches: dict[str, Any]) -> Judgements:
    return Judgements.model_validate({**_BASE, "batches": list(batches)})


def _batch(bid: str = "lifecycle", ids: list[str] | None = None, **kw: Any) -> dict[str, Any]:
    return {"id": bid, "title": "t", "ids": ids or ["super-fr#577", "super-fr#575"], **kw}


def _dispatch(at: str = "2026-09-25T10:12:00Z", branch: str = BRANCH) -> dict[str, Any]:
    return {
        "kind": "dispatch",
        "at": at,
        "runner": "herdr",
        "handle": "w2:p1K",
        "branch": branch,
        "reserved_version": "4.22.0",
    }


def _cancel(at: str = "2026-09-26T08:00:00Z") -> dict[str, Any]:
    return {"kind": "cancel", "at": at, "reason": "split"}


def _pr(number: int, state: str, *, head: str = BRANCH, repo: str = REPO) -> PullRequest:
    return PullRequest(
        repo=repo,
        number=number,
        title=f"pr {number}",
        state=state,  # type: ignore[arg-type]
        is_draft=False,
        url=f"https://github.com/{repo}/pull/{number}",
        head_ref=head,
    )


def _issue(number: int, *, state: str = "open", prs: list[PullRequest] = (), labels=()) -> Issue:
    return Issue(
        repo=REPO,
        number=number,
        title=f"issue {number}",
        state=state,  # type: ignore[arg-type]
        labels=list(labels),
        url=f"https://github.com/{REPO}/issues/{number}",
        prs=list(prs),
    )


def _facts(issues: list[Issue], *, prs: list[PullRequest] = (), batch_prs=()) -> Facts:
    return Facts(
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-09-26T00:00:00+00:00",
        repos=[REPO],
        issues=issues,
        prs=list(prs),
        batch_prs=list(batch_prs),
    )


def _one(judgements: Judgements) -> Batch:
    (batch,) = judgements.batches
    return batch


# ------------------------------------------------------------ load checks


def test_a_case_variant_member_key_normalises_to_the_judged_key() -> None:
    batch = _one(_judgements(_batch(ids=["Super-FR#577"])))
    assert batch.ids == ["super-fr#577"]


def test_an_unjudged_member_is_refused() -> None:
    with pytest.raises(ValidationError, match=r"super-fr#999.*not judged"):
        _judgements(_batch(ids=["super-fr#577", "super-fr#999"]))


def test_a_malformed_member_key_is_refused() -> None:
    with pytest.raises(ValidationError, match="repo-name"):
        _judgements(_batch(ids=["577"]))


def test_empty_ids_are_refused() -> None:
    with pytest.raises(ValidationError, match="ids"):
        _judgements(_batch(ids=[]) | {"ids": []})


def test_case_colliding_batch_ids_are_refused() -> None:
    with pytest.raises(ValidationError, match=r"batch ids.*lifecycle"):
        _judgements(_batch("lifecycle"), _batch("Lifecycle", ids=["super-fr#471"]))


@pytest.mark.parametrize("bid", ["9lives", "has space", "a" * 41, ""])
def test_a_batch_id_outside_the_slug_grammar_is_refused(bid: str) -> None:
    with pytest.raises(ValidationError, match="batch id"):
        _judgements(_batch(bid))


def test_out_of_order_events_are_refused() -> None:
    with pytest.raises(ValidationError, match="time-ordered"):
        _judgements(
            _batch(events=[_cancel("2026-09-26T08:00:00Z"), _dispatch("2026-09-25T00:00:00Z")])
        )


def test_an_unknown_event_kind_is_refused() -> None:
    with pytest.raises(ValidationError):
        _judgements(_batch(events=[{"kind": "merge", "at": "2026-09-25T00:00:00Z"}]))


@pytest.mark.parametrize("dupe", ["super-fr#577", "Super-FR#577"])
def test_a_member_listed_twice_is_refused_naming_it(dupe: str) -> None:
    """Review r2p-f5: after normalisation, a key may appear once in a batch."""
    with pytest.raises(ValidationError, match=r"lists super-fr#577 more than once"):
        _judgements(_batch(ids=["super-fr#577", "super-fr#575", dupe]))


def test_members_in_two_repos_are_refused() -> None:
    base = {**_BASE, "issues": {**_BASE["issues"], "other#1": {"tier": 1}}}
    with pytest.raises(ValidationError, match="one repo"):
        Judgements.model_validate({**base, "batches": [_batch(ids=["super-fr#577", "other#1"])]})


def test_the_full_batch_shape_loads() -> None:
    batch = _one(
        _judgements(
            _batch(
                rationale="r",
                order=1,
                bump="minor",
                launch={"runner": "herdr", "harness": "claude", "model": "claude-opus-5-5"},
                events=[_dispatch(), _cancel()],
            )
        )
    )
    assert (batch.order, batch.bump, batch.launch.model) == (1, "minor", "claude-opus-5-5")
    assert [e.kind for e in batch.events] == ["dispatch", "cancel"]


def test_schema_1_loads_as_zero_batches() -> None:
    assert Judgements.model_validate({**_BASE, "schema": 1}).batches == []


# ------------------------------------------------------------------ write


def test_a_write_upgrades_schema_1_to_2_and_touches_only_the_batches_section(
    tmp_path: Path,
) -> None:
    path = tmp_path / "judgements.yaml"
    original = (
        "schema: 1\n"
        "# the agent's own comment survives\n"
        "tiers:\n  - {n: 1, title: Now}\n"
        "issues:\n  super-fr#577: {tier: 1, note: 'keep: me'}\n  super-fr#575: {tier: 1}\n"
    )
    path.write_text(original, encoding="utf-8")
    judgements = load_judgements(path)
    batch = Batch.model_validate(_batch())

    save_batches(path, [batch])

    text = path.read_text(encoding="utf-8")
    assert JUDGEMENTS_SCHEMA == 2
    assert text.startswith("schema: 2\n")
    assert "# the agent's own comment survives" in text
    assert "super-fr#577: {tier: 1, note: 'keep: me'}" in text
    again = load_judgements(path)
    assert again.batches == [batch]
    assert again.issues == judgements.issues


def test_a_write_replaces_an_existing_batches_section(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump({**_BASE, "batches": [_batch()]}), encoding="utf-8")

    save_batches(path, [Batch.model_validate(_batch("other", ids=["super-fr#471"]))])

    assert [b.id for b in load_judgements(path).batches] == ["other"]


def test_a_write_stores_only_the_launch_values_given(tmp_path: Path) -> None:
    path = tmp_path / "judgements.yaml"
    path.write_text(yaml.safe_dump(_BASE), encoding="utf-8")

    save_batches(path, [Batch.model_validate(_batch(launch={"model": "m"}))])

    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["batches"][0]["launch"] == {"model": "m"}


def test_a_write_that_breaks_a_load_rule_is_refused_and_the_file_is_untouched(
    tmp_path: Path,
) -> None:
    path = tmp_path / "judgements.yaml"
    before = yaml.safe_dump(_BASE)
    path.write_text(before, encoding="utf-8")
    bad = Batch.model_validate(_batch(ids=["super-fr#999"]))  # valid alone, unjudged in the file

    with pytest.raises(TriageError, match="not judged"):
        save_batches(path, [bad])

    assert path.read_text(encoding="utf-8") == before


# ------------------------------------------------------------------ stages


def _stage(events: list[dict[str, Any]], facts: Facts) -> str:
    return derive_batch_stage(_one(_judgements(_batch(events=events))), facts)


def test_no_events_is_proposed() -> None:
    assert _stage([], _facts([_issue(577), _issue(575)])) == "proposed"


def test_a_last_cancel_is_cancelled() -> None:
    assert _stage([_dispatch(), _cancel()], _facts([_issue(577), _issue(575)])) == "cancelled"


def test_a_dispatch_with_no_pr_on_its_branch_is_dispatched() -> None:
    assert _stage([_dispatch()], _facts([_issue(577), _issue(575)])) == "dispatched"


def test_a_redispatch_after_cancel_is_dispatched() -> None:
    events = [_dispatch("2026-09-25T00:00:00Z"), _cancel(), _dispatch("2026-09-27T00:00:00Z")]
    assert _stage(events, _facts([_issue(577), _issue(575)])) == "dispatched"


def test_an_open_pr_on_the_branch_is_pr_open() -> None:
    pr = _pr(50, "OPEN")
    assert (
        _stage([_dispatch()], _facts([_issue(577, prs=[pr]), _issue(575, prs=[pr])])) == "pr-open"
    )


def test_a_merged_pr_with_every_member_closed_is_merged() -> None:
    pr = _pr(50, "MERGED")
    facts = _facts([_issue(577, state="closed", prs=[pr]), _issue(575, state="closed", prs=[pr])])
    assert _stage([_dispatch()], facts) == "merged"


def test_a_merged_pr_with_a_member_still_open_is_partial() -> None:
    pr = _pr(50, "MERGED")
    facts = _facts([_issue(577, state="closed", prs=[pr]), _issue(575)])
    assert _stage([_dispatch()], facts) == "partial"


def test_a_pr_closed_unmerged_is_abandoned() -> None:
    pr = _pr(50, "CLOSED")
    assert _stage([_dispatch()], _facts([_issue(577, prs=[pr]), _issue(575)])) == "abandoned"


def test_the_highest_pr_number_on_the_branch_wins() -> None:
    old, new = _pr(50, "CLOSED"), _pr(61, "OPEN")
    facts = _facts([_issue(577, prs=[new, old]), _issue(575)])
    batch = _one(_judgements(_batch(events=[_dispatch()])))
    assert batch_pr(batch, facts) == new
    assert derive_batch_stage(batch, facts) == "pr-open"


def test_a_pr_on_another_branch_or_repo_is_not_the_batch_pr() -> None:
    elsewhere = [_pr(70, "OPEN", head="feat/other"), _pr(71, "OPEN", repo="derio-net/other")]
    facts = _facts([_issue(577, prs=elsewhere), _issue(575)], prs=elsewhere)
    assert _stage([_dispatch()], facts) == "dispatched"


def test_an_unlinked_open_pr_on_the_branch_is_found_in_facts_prs() -> None:
    assert _stage([_dispatch()], _facts([_issue(577), _issue(575)], prs=[_pr(52, "OPEN")])) == (
        "pr-open"
    )


def test_batch_prs_find_a_merged_pr_with_no_closes_lines_and_give_partial() -> None:
    facts = _facts([_issue(577), _issue(575)], batch_prs=[_pr(40, "MERGED")])
    assert _stage([_dispatch()], facts) == "partial"


def test_identity_is_repo_plus_batch_id() -> None:
    from fr_dispatch.work_item import run_item_id

    assert batch_branch("lifecycle") == BRANCH
    assert batch_item_id(REPO, "lifecycle") == run_item_id(REPO, "batch-lifecycle")


# ------------------------------------------------------- open-batch rule


def test_a_key_in_two_open_batches_is_refused() -> None:
    judgements = _judgements(_batch("a"), _batch("b", ids=["super-fr#577"]))
    with pytest.raises(BatchConflictError, match=r"super-fr#577.*\ba\b.*\bb\b"):
        check_open_membership(judgements.batches, _facts([_issue(577), _issue(575)]))


@pytest.mark.parametrize(
    ("events", "prs", "closed"),
    [
        ([_dispatch(), _cancel()], [], set()),  # cancelled
        ([_dispatch()], [_pr(50, "MERGED")], {577}),  # partial: 575 still open
        ([_dispatch()], [_pr(50, "CLOSED")], set()),  # abandoned
    ],
    ids=["cancelled", "partial", "abandoned"],
)
def test_members_of_a_closed_out_batch_are_released(
    events: list[dict[str, Any]], prs: list[PullRequest], closed: set[int]
) -> None:
    judgements = _judgements(_batch("a", events=events), _batch("b", ids=["super-fr#575"]))
    facts = _facts(
        [
            _issue(577, state="closed" if 577 in closed else "open", prs=prs),
            _issue(575, prs=prs),
        ]
    )
    first = judgements.batches[0]
    assert not is_open(first, facts)
    check_open_membership(judgements.batches, facts)  # no raise


def test_a_proposed_batch_is_open() -> None:
    batch = _one(_judgements(_batch()))
    assert is_open(batch, _facts([_issue(577), _issue(575)]))


# ---------------------------------------------------- issue stage in-progress


def test_the_in_progress_label_gives_in_progress() -> None:
    issue = _issue(1, labels=["fr:in-progress"])
    assert derive_stage(issue, []) == "in-progress"


def test_a_linked_pr_outranks_in_progress() -> None:
    draft = _pr(9, "OPEN").model_copy(update={"is_draft": True})
    assert derive_stage(_issue(1, labels=["fr:in-progress"]), [draft]) == "pr-draft"


def test_in_progress_outranks_blocked() -> None:
    assert derive_stage(_issue(1, labels=["blocked", "fr:in-progress"]), []) == "in-progress"

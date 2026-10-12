"""A partial collect: only the changed repos are read, the rest carried from the last
facts (spec 2026-10-12-quota-pacing §B, R10).

The forge is `FakeForge` over two fictional repos of one org; the previous facts are a
full collect of the same forge, as on a real drive.
"""

from __future__ import annotations

import pytest
from fr.triage.collect import collect_facts_counted
from fr.triage.model import Scope

from tests.unit.triage_fixtures import NOW, FakeForge, _issue, _pr_closing

ORG = Scope(kind="org", target="example-org")
A, B = "example-org/alpha", "example-org/beta"
CONFIG = "max_inflight: 2\n"


def _forge() -> FakeForge:
    """alpha#7 and beta#5 open; alpha's PR #900 closes beta#5, beta's PR #800 alpha#7;
    beta has a config and a judged closed issue #99."""
    return FakeForge(
        repos=[{"name": "alpha", "isArchived": False}, {"name": "beta", "isArchived": False}],
        issues={A: [_issue(7, title="a7")], B: [_issue(5, title="b5")]},
        prs={
            A: [_pr_closing(owner="example-org", name="beta", number=5, pr_number=900)],
            B: [_pr_closing(owner="example-org", name="alpha", number=7, pr_number=800)],
        },
        closed={
            (B, 99): {
                "title": "gone",
                "url": f"https://github.com/{B}/issues/99",
                "state": "CLOSED",
                "labels": [],
            }
        },  # fmt: skip
        file_bodies={(B, ".fr/triage.yaml", "HEAD"): "{}\n"},
        visibility={A: "public", B: "private"},
    )


def _collect(forge: FakeForge, **kw):  # type: ignore[no-untyped-def]
    return collect_facts_counted(forge, ORG, now=NOW, judged=["beta#99"], carried=(), **kw)[0]


def _prs(facts, key: str) -> list[tuple[str, int]]:  # type: ignore[no-untyped-def]
    issue = next(i for i in facts.issues if i.key == key)
    return [(p.repo, p.number) for p in issue.prs]


def test_only_the_named_repos_are_read_and_the_rest_carried() -> None:
    previous = _collect(_forge())
    forge = _forge()
    facts = _collect(forge, only={A}, previous=previous)

    assert {kw["repo"] for kw in forge.called("list_issues")} == {A}
    assert {kw["repo"] for kw in forge.called("list_prs")} == {A}
    assert {kw["repo"] for kw in forge.called("list_open_prs")} == {A}
    assert not forge.called("list_repos")
    assert not forge.called("view_issue")  # beta#99 resolves from the previous facts
    assert facts.repos == previous.repos
    assert [i for i in facts.issues if i.repo == B] == [i for i in previous.issues if i.repo == B]
    assert facts.config == previous.config and B in facts.config
    assert facts.visibility == {A: "public"}  # B's is never carried
    assert [p for p in facts.prs if p.repo == B] == [p for p in previous.prs if p.repo == B]
    assert facts.batch_prs == previous.batch_prs
    assert facts.skipped == []
    assert next(i for i in facts.issues if i.key == "beta#99").state == "closed"


@pytest.mark.parametrize("read", [A, B])
def test_cross_repo_links_survive_whichever_side_is_read(read: str) -> None:
    previous = _collect(_forge())
    assert _prs(previous, "beta#5") == [(A, 900)]
    assert _prs(previous, "alpha#7") == [(B, 800)]

    facts = _collect(_forge(), only={read}, previous=previous)

    assert _prs(facts, "beta#5") == [(A, 900)]
    assert _prs(facts, "alpha#7") == [(B, 800)]


def test_a_read_repo_drops_its_own_stale_links() -> None:
    """A link whose PR lives in the repo read this pass is recomputed from that read."""
    previous = _collect(_forge())
    forge = _forge()
    forge.prs[A] = []  # alpha's PR #900 is gone
    facts = _collect(forge, only={A}, previous=previous)
    assert _prs(facts, "beta#5") == []


def test_no_previous_facts_reads_every_repo() -> None:
    forge = _forge()
    _collect(forge, only={A}, previous=None)
    assert {kw["repo"] for kw in forge.called("list_issues")} == {A, B}


def test_a_repo_skipped_last_time_is_read_even_when_unchanged() -> None:
    failing = _forge()
    failing.failing = {B: "HTTP 502"}
    previous = _collect(failing)
    assert [s.repo for s in previous.skipped] == [B]
    forge = _forge()
    facts = _collect(forge, only={A}, previous=previous)
    assert {kw["repo"] for kw in forge.called("list_issues")} == {A, B}
    assert facts.skipped == []


def test_nothing_named_reads_nothing_and_carries_everything() -> None:
    previous = _collect(_forge())
    forge = _forge()
    facts = _collect(forge, only=set(), previous=previous)
    assert not forge.calls
    assert facts.issues == previous.issues and facts.prs == previous.prs


def test_only_none_is_today_s_collect() -> None:
    previous = _collect(_forge())
    a, b = _forge(), _forge()
    plain = _collect(a)
    with_previous = _collect(b, only=None, previous=previous)
    assert plain == with_previous
    assert a.calls == b.calls


def test_collect_into_carries_and_calls_back_after_facts_json(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The drive's pacing write follows the facts it describes (R11): `after_write` runs
    once `facts.json` is on disk, never before."""
    import json

    from fr.commands import triage_cmd
    from fr.triage.model import load_facts

    previous = _collect(_forge())
    (tmp_path / "facts.json").write_text(json.dumps(previous.to_json()), "utf-8")
    forge = _forge()
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    seen: list[object] = []

    def after(facts, carried):  # type: ignore[no-untyped-def]
        seen.append(load_facts(tmp_path / "facts.json") == facts)
        assert carried == {B}, "the repos the collect actually carried (p2-r5)"

    facts, _, _ = triage_cmd.collect_into(
        ORG, tmp_path, carry=True, lenient=True, only={A}, after_write=after
    )
    assert seen == [True]
    assert {kw["repo"] for kw in forge.called("list_issues")} == {A}
    assert _prs(facts, "alpha#7") == [(B, 800)]


def test_a_carried_repo_s_visibility_is_left_out_for_the_guard_to_read_live() -> None:
    """A stale carried "public" would pass the leak check for a repo made private since
    (orchestrator correction to R10): a carried repo has no visibility in the facts."""
    previous = _collect(_forge())
    previous = previous.model_copy(update={"visibility": {A: "public", B: "public"}})
    forge = _forge()
    facts = _collect(forge, only={A}, previous=previous)
    assert B not in facts.visibility
    assert forge.visibility_calls == [A]


def test_the_stats_name_the_repos_actually_carried() -> None:
    """p2-r5: the drive takes the carried set from the collect, never re-derives it."""
    previous = _collect(_forge())
    stats = collect_facts_counted(
        _forge(), ORG, now=NOW, judged=["beta#99"], only={A}, previous=previous
    )[1]
    assert stats.carried_repos == {B}
    failing = _forge()
    failing.failing = {B: "HTTP 502"}
    skipped = _collect(failing)
    stats = collect_facts_counted(
        _forge(), ORG, now=NOW, judged=["beta#99"], only={A}, previous=skipped
    )[1]
    assert stats.carried_repos == frozenset(), "a repo skipped last time is read"
    full = collect_facts_counted(_forge(), ORG, now=NOW, judged=["beta#99"])[1]
    assert full.carried_repos == frozenset()


def test_a_carried_repo_s_unviewed_key_is_viewed_again() -> None:
    """p2-r2: an `Unviewed` (a rate limit, say) is never carried: carrying it would
    re-raise the same rate limit every partial pass until the next full one."""
    from fr.triage.model import Unviewed

    previous = _collect(_forge())
    previous = previous.model_copy(
        update={
            "issues": [i for i in previous.issues if i.key != "beta#99"],
            "unviewed": [Unviewed(key="beta#99", reason="API rate limit exceeded")],
        }
    )
    forge = _forge()
    facts = _collect(forge, only={A}, previous=previous)
    assert [kw["number"] for kw in forge.called("view_issue")] == [99]
    assert facts.unviewed == []
    assert next(i for i in facts.issues if i.key == "beta#99").state == "closed"

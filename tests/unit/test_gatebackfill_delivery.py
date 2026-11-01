"""The delivering-PR evidence chain over real git histories and a fake forge
(spec 2026-11-01-gate-backfill §C, R3)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.gatebackfill.candidates import Candidate
from fr.gatebackfill.delivery import Delivery, delivering_pr, subject_pr
from fr.gatebackfill.forge import Git
from fr.ghclient import UnsupportedForgeOperation

from tests.unit.gatebackfill_fixtures import (
    REPO,
    SP,
    FakeForge,
    commit_at,
    git,
    make_repo,
    publish,
)
from tests.unit.test_merge_evidence import _write_plan

PLAN = "2026-10-20-ops"
KEY = f"plan:{PLAN}#p1"
REF = "origin/main"


@pytest.fixture(autouse=True)
def _hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def _cand(**kw: object) -> Candidate:
    base: dict[str, object] = {"key": KEY, "source": "plan", "title": "t", "plans": (PLAN,)}
    return Candidate.model_validate({**base, **kw})


def _deliver(repo: Path, forge: FakeForge, c: Candidate | None = None) -> Delivery:
    return delivering_pr(c or _cand(), root=repo, forge=forge, git=Git(repo), ref=REF)


def _land_plan(repo: Path, subject: str, *, with_code: bool = True) -> str:
    """Add the plan (and a code file) in one commit on main and publish it."""
    _write_plan(repo, PLAN, [("manual", False)])
    if with_code:
        (repo / "src.py").write_text("x = 1\n")
    sha = commit_at(repo, subject, "2026-10-20T00:00:00+00:00")
    publish(repo)
    return sha


def _merged(forge: FakeForge, *numbers: int) -> None:
    for n in numbers:
        forge.add_pr(n)


def _cursor(repo: Path, rel: str, branch: str) -> None:
    p = repo / rel / "run-ops.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"run: run-ops\nworkflow: fr-goal@1\nbranch: {branch}\n"
        "started: '2026-01-01T09:00:00Z'\ncursor: deliver\nsteps:\n"
        f"  plan:\n    state: done\n    emitted: {{plan: {SP}/plans/{PLAN}}}\n"
    )


def test_a_manifest_pr_wins_and_says_so(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "feat: ops (#12)")
    forge = FakeForge()
    _merged(forge, 12, 90)

    got = _deliver(repo, forge, _cand(manifest_pr=90))

    assert got.pr is not None and (got.pr.number, got.pr.basis) == (90, "manifest")


def test_an_archived_run_cursor_names_the_branch_and_its_merged_pr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _cursor(repo, f"{SP}/implemented/runs", "feat/ops")
    commit_at(repo, "archive", "2026-10-21T00:00:00+00:00")
    publish(repo)
    forge = FakeForge()
    _merged(forge, 21)
    forge.by_head["feat/ops"] = [21]

    got = _deliver(repo, forge)

    assert got.pr is not None and (got.pr.number, got.pr.basis) == (21, "run")


def test_a_squash_subject_names_the_pr_that_added_the_plan(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "feat: ops (#12)")
    forge = FakeForge()
    _merged(forge, 12)

    got = _deliver(repo, forge)

    assert got.pr is not None
    assert (got.pr.number, got.pr.basis, got.pr.planning) == (12, "commit", False)
    assert ("prs_for_commit", got.pr) not in forge.calls and not any(
        c[0] == "prs_for_commit" for c in forge.calls
    )


def test_a_merge_commit_whose_branch_added_the_plan_names_its_pr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    git(repo, "checkout", "-q", "-b", "feat/ops")
    _write_plan(repo, PLAN, [("manual", False)])
    (repo / "src.py").write_text("x = 1\n")
    commit_at(repo, "work", "2026-10-19T00:00:00+00:00")
    git(repo, "checkout", "-q", "main")
    (repo / "other").write_text("y\n")
    commit_at(repo, "other", "2026-10-19T12:00:00+00:00")
    git(
        repo, "merge", "-q", "--no-ff", "-m", "Merge pull request #34 from example-org/feat-ops",
        "feat/ops", env={"GIT_COMMITTER_DATE": "2026-10-20T00:00:00+00:00"},
    )  # fmt: skip
    publish(repo)
    forge = FakeForge()
    _merged(forge, 34)

    got = _deliver(repo, forge)

    assert got.pr is not None and (got.pr.number, got.pr.basis) == (34, "commit")


def test_a_subject_naming_no_pr_asks_the_forge_and_an_unsupported_forge_yields_nothing(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    sha = _land_plan(repo, "add the ops plan")
    forge = FakeForge()
    _merged(forge, 77)
    forge.by_commit[sha] = [77]

    got = _deliver(repo, forge)
    assert got.pr is not None and (got.pr.number, got.pr.basis) == (77, "commit")

    forge.commit_error = UnsupportedForgeOperation("prs_for_commit", "gitlab")
    none = _deliver(repo, forge)
    assert none.pr is None and none.ambiguous == ()
    assert "no delivering PR" in none.why


def test_a_closed_issue_resolves_through_its_single_merged_linked_pr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    forge = FakeForge()
    _merged(forge, 89)
    forge.linked[37] = [89]

    got = _deliver(repo, forge, _cand(key=f"issue:{REPO}#37", plans=(), issue_number=37))

    assert got.pr is not None and (got.pr.number, got.pr.basis) == (89, "issue")


def test_two_merged_prs_at_one_step_are_an_ambiguity_with_every_number(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _cursor(repo, f"{SP}/runs", "feat/ops")
    _cursor(repo, f"{SP}/implemented/runs", "feat/ops-2")
    commit_at(repo, "cursors", "2026-10-21T00:00:00+00:00")
    publish(repo)
    forge = FakeForge()
    _merged(forge, 21, 22)
    forge.by_head = {"feat/ops": [21], "feat/ops-2": [22]}

    got = _deliver(repo, forge)

    assert got.pr is None and got.ambiguous == (21, 22)


def test_a_hit_the_forge_says_is_not_merged_is_dropped_with_its_reason(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    forge = FakeForge()
    forge.add_pr(40, state="CLOSED")

    got = _deliver(repo, forge, _cand(manifest_pr=40))

    assert got.pr is None
    assert "#40 is CLOSED" in got.why


def test_a_merge_that_touched_only_docs_is_a_planning_pr(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "docs: plan the ops (#15)", with_code=False)
    forge = FakeForge()
    _merged(forge, 15)

    got = _deliver(repo, forge)

    assert got.pr is not None and got.pr.number == 15 and got.pr.planning is True


def test_nothing_found_is_unresolved_and_never_guessed(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "add the ops plan")  # no (#N), no forge mapping

    got = _deliver(repo, FakeForge())

    assert got == Delivery(why="no delivering PR found")


def test_the_subject_pattern() -> None:
    assert subject_pr("feat: x (#12)") == 12
    assert subject_pr("Merge pull request #34 from a/b") == 34
    assert subject_pr("fix: mentions #9 in passing") is None


# --- review fixes (p1-r1, r3, r6, r7) ---------------------------------------------------------


def _archive_plan(repo: Path) -> None:
    dst = repo / SP / "implemented" / "plans"
    dst.mkdir(parents=True, exist_ok=True)
    git(repo, "mv", f"{SP}/plans/{PLAN}", f"{SP}/implemented/plans/{PLAN}")
    commit_at(repo, "archive (#2)", "2026-10-25T00:00:00+00:00")
    publish(repo)


def test_p1_r1_an_archived_plan_resolves_to_the_pr_that_added_it_not_the_archive_pr(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "feat (#1)")
    _archive_plan(repo)
    forge = FakeForge()
    _merged(forge, 1, 2)

    got = _deliver(repo, forge)

    assert got.ambiguous == ()
    assert got.pr is not None and (got.pr.number, got.pr.basis) == (1, "commit")


def test_p1_r1_an_archived_spec_with_no_plans_resolves_to_the_pr_that_added_it(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    name = "2026-05-01-thing-design.md"
    (repo / SP / "specs").mkdir(parents=True)
    (repo / SP / "specs" / name).write_text("# t\n")
    (repo / "src.py").write_text("x = 1\n")
    commit_at(repo, "feat (#1)", "2026-10-20T00:00:00+00:00")
    (repo / SP / "implemented" / "specs").mkdir(parents=True)
    git(repo, "mv", f"{SP}/specs/{name}", f"{SP}/implemented/specs/{name}")
    commit_at(repo, "archive (#2)", "2026-10-25T00:00:00+00:00")
    publish(repo)
    forge = FakeForge()
    _merged(forge, 1, 2)
    cand = _cand(
        key="spec:2026-05-01-thing#step1", plans=(), spec_rel=f"{SP}/implemented/specs/{name}"
    )

    got = _deliver(repo, forge, cand)

    assert got.ambiguous == ()
    assert got.pr is not None and got.pr.number == 1


def test_p1_r3_an_unconfirmed_manifest_pr_is_never_replaced_by_an_inferred_one(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    _land_plan(repo, "feat: ops (#12)")
    forge = FakeForge()
    _merged(forge, 12)
    forge.add_pr(40, state="CLOSED")

    got = _deliver(repo, forge, _cand(manifest_pr=40))

    assert got.pr is None and got.ambiguous == ()
    assert got.why.startswith("manifest pr #40: ") and "CLOSED" in got.why


def test_p1_r6_a_pr_is_viewed_once_per_run_across_candidates(tmp_path: Path) -> None:
    from fr.gatebackfill.delivery import DeliveryCache

    repo = make_repo(tmp_path)
    _land_plan(repo, "feat: ops (#12)")
    forge = FakeForge()
    _merged(forge, 12)
    cache = DeliveryCache()
    for _ in range(2):
        got = delivering_pr(_cand(), root=repo, forge=forge, git=Git(repo), ref=REF, cache=cache)
        assert got.pr is not None and got.pr.number == 12

    assert [c for c in forge.calls if c[0] == "pr_view"] == [("pr_view", 12)]


def test_p1_r6_one_candidate_views_a_pr_once(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    forge = FakeForge()
    _merged(forge, 90)

    _deliver(repo, forge, _cand(manifest_pr=90))

    assert [c for c in forge.calls if c[0] == "pr_view"] == [("pr_view", 90)]


def test_p1_r6_the_first_parent_line_is_listed_once_per_git(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    sha = _land_plan(repo, "feat: ops (#12)")
    g = Git(repo)
    calls: list[tuple[str, ...]] = []
    real = g._out

    def spy(*args: str) -> str | None:
        calls.append(args)
        return real(*args)

    g._out = spy  # type: ignore[method-assign]
    g.first_containing(REF, sha)
    g.first_containing(REF, sha)

    assert len([a for a in calls if a[:2] == ("rev-list", "--first-parent")]) == 1


def test_p1_r7_an_archived_spec_matches_a_cursor_that_emitted_its_live_path(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    name = "2026-05-01-thing-design.md"
    p = repo / SP / "implemented" / "runs" / "run-spec.yaml"
    p.parent.mkdir(parents=True)
    p.write_text(
        "run: run-spec\nworkflow: fr-goal@1\nbranch: feat/thing\n"
        "started: '2026-01-01T09:00:00Z'\ncursor: deliver\nsteps:\n"
        f"  spec:\n    state: done\n    emitted: {{spec: {SP}/specs/{name}}}\n"
    )
    commit_at(repo, "cursor", "2026-10-21T00:00:00+00:00")
    publish(repo)
    forge = FakeForge()
    _merged(forge, 31)
    forge.by_head["feat/thing"] = [31]
    cand = _cand(
        key="spec:2026-05-01-thing#step1", plans=(), spec_rel=f"{SP}/implemented/specs/{name}"
    )

    got = _deliver(repo, forge, cand)

    assert got.pr is not None and (got.pr.number, got.pr.basis) == (31, "run")

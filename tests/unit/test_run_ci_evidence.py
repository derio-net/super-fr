"""`fr.run.ci_evidence.verify_ci` — spec 2026-10-07-cloud-triage R22, §I steps 1-6.

Every test runs over a tmp repo whose `origin` is a bare repo at
`../derio-net/super-fr.git` (so `origin_slug` reads `derio-net/super-fr`, and
`git ls-remote` really answers) and a `FakeGhClient` serving check records read
from the CAPTURED fixtures (`tests/fixtures/github_rest/commit_checks/`) through
the real REST client. Where a state could not be captured (a failed, skipped or
cancelled gate on an otherwise green head, a gate that is itself
`in_progress`), the test derives it from the captured green records and says so.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.real_ghrestclient import RealGhRestClient
from fr.run.ci_evidence import (
    CI_PENDING_EXIT,
    WALK_LIMIT,
    CiEvidenceRefused,
    CiPending,
    load_gate_checks,
    verify_ci,
)
from fr.run.code_tree import code_tree

from tests.unit.fakes import FakeGhClient
from tests.unit.test_commit_checks import BASE, MomentGh, _sha

REPO = "derio-net/super-fr"
BRANCH = "feat/x"


def _captured(moment: str) -> list[dict[str, Any]]:
    """The records `commit_checks` reads from a captured moment."""
    return RealGhRestClient(run=MomentGh(moment)).commit_checks(REPO, _sha(moment))


def _with(moment: str, name: str, **fields: Any) -> list[dict[str, Any]]:
    """DERIVED from a captured moment: check *name*'s record with *fields* changed."""
    out = _captured(moment)
    for r in out:
        if r["name"] == name:
            r.update(fields)
    return out


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


def _world(
    tmp_path: Path, *, ci_yaml: str | None = "gate_checks: [ci-ok]\n", workflows: bool = True
) -> tuple[Path, FakeGhClient, str]:
    """A pushed branch with an open PR. Returns `(repo, client, head sha)`."""
    bare = tmp_path / "derio-net" / "super-fr.git"
    bare.parent.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    repo = tmp_path / "work"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", BRANCH)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "remote", "add", "origin", "../derio-net/super-fr.git")
    (repo / "src").mkdir()
    (repo / "src" / "x.py").write_text("x = 1\n")
    if workflows:
        (repo / ".github" / "workflows").mkdir(parents=True)
        (repo / ".github" / "workflows" / "ci.yml").write_text("on: pull_request\n")
    if ci_yaml is not None:
        (repo / ".fr").mkdir()
        (repo / ".fr" / "ci.yaml").write_text(ci_yaml)
    (repo / "docs" / "superpowers" / "runs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\n")
    head = _commit(repo, "seed")
    _git(repo, "push", "-q", "origin", BRANCH)
    client = FakeGhClient()
    client.add_pr(REPO, 7, head_ref=BRANCH)
    client.commit_checks_by_sha[(REPO, head)] = _captured("green-head")
    return repo, client, head


def _forge_calls(client: FakeGhClient) -> list[str]:
    return [name for name, _ in client.calls]


# --- green -----------------------------------------------------------------


def test_a_green_gate_on_head_is_the_witness(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)

    witness = verify_ci(repo, client)

    assert witness == f"ci:{head}+{BASE};tree={code_tree(repo)}"


def test_a_bookkeeping_commit_on_a_tested_sha_needs_no_new_run(tmp_path: Path) -> None:
    repo, client, tested = _world(tmp_path)
    (repo / "docs" / "superpowers" / "runs" / "r1.yaml").write_text("run: r1\nstep: x\n")
    head = _commit(repo, "chore(fr): run r1 — resolve")
    _git(repo, "push", "-q", "origin", BRANCH)

    witness = verify_ci(repo, client)

    assert witness.startswith(f"ci:{tested}+{BASE};tree=")
    assert ("commit_checks", {"repo": REPO, "sha": head}) in client.calls


def test_a_code_commit_on_a_tested_sha_is_not_covered(tmp_path: Path) -> None:
    """The walk stops at the first commit whose code tree differs: the new head
    has no checks yet, so CI is still to report — pending, never the old run."""
    repo, client, _ = _world(tmp_path)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit(repo, "code")
    _git(repo, "push", "-q", "origin", BRANCH)

    with pytest.raises(CiPending):
        verify_ci(repo, client)


def test_a_gate_re_run_green_after_a_failed_attempt_counts(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = _captured("rerun")

    witness = verify_ci(repo, client)

    # f1919d4's PR is merged, so GitHub names no base for its runs.
    assert witness.startswith(f"ci:{head}+unknown;tree=")


def test_a_failing_non_gate_check_is_ignored(tmp_path: Path) -> None:
    """DERIVED: the captured green head (`green-head/`) with `lint` failed."""
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = _with("green-head", "lint", conclusion="failure")

    assert verify_ci(repo, client).startswith(f"ci:{head}+")


# --- pending ---------------------------------------------------------------


def test_a_running_ci_with_no_gate_yet_is_pending(tmp_path: Path) -> None:
    """The captured mid-run head: shards in progress, `ci-ok` not yet created."""
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = _captured("pending")

    with pytest.raises(CiPending) as exc:
        verify_ci(repo, client)

    assert head in str(exc.value) and "resolve again" in str(exc.value)
    assert CI_PENDING_EXIT == 75


def test_an_in_progress_gate_is_pending(tmp_path: Path) -> None:
    """DERIVED: the captured green head (`green-head/`) with `ci-ok` itself in progress."""
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = _with(
        "green-head", "ci-ok", status="in_progress", conclusion=""
    )

    with pytest.raises(CiPending):
        verify_ci(repo, client)


def test_a_head_with_no_checks_yet_is_pending(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha.pop((REPO, head))

    with pytest.raises(CiPending):
        verify_ci(repo, client)


# --- refused (exit 2) -----------------------------------------------------


@pytest.mark.parametrize("conclusion", ["failure", "cancelled", "skipped"])
def test_a_gate_that_did_not_succeed_is_refused_with_its_url(
    tmp_path: Path, conclusion: str
) -> None:
    """DERIVED: the captured green head (`green-head/`) with `ci-ok` concluded otherwise."""
    repo, client, head = _world(tmp_path)
    records = _with("green-head", "ci-ok", conclusion=conclusion)
    client.commit_checks_by_sha[(REPO, head)] = records
    url = next(r["url"] for r in records if r["name"] == "ci-ok")

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "ci-ok" in str(exc.value) and conclusion in str(exc.value) and url in str(exc.value)


def test_an_absent_gate_on_a_finished_head_is_refused(tmp_path: Path) -> None:
    """DERIVED: the captured green head (`green-head/`) without its `ci-ok` record."""
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = [
        r for r in _captured("green-head") if r["name"] != "ci-ok"
    ]

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "ci-ok" in str(exc.value) and "absent" in str(exc.value)


def test_an_unpushed_head_is_refused_naming_it(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)
    (repo / "src" / "x.py").write_text("x = 2\n")
    head = _commit(repo, "code")

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert head[:12] in str(exc.value) and "push" in str(exc.value)
    assert "commit_checks" not in _forge_calls(client)


def test_a_dirty_code_path_is_refused_naming_it(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)
    (repo / "src" / "x.py").write_text("x = 3\n")

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "src/x.py" in str(exc.value)
    assert client.calls == []


def test_no_open_pr_is_refused(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)
    client.prs[(REPO, 7)]["state"] = "CLOSED"

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "no open pull request" in str(exc.value)


def test_a_conflicting_pr_is_refused(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)
    client.prs[(REPO, 7)]["mergeable"] = "CONFLICTING"

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "conflict" in str(exc.value).lower()


def test_ci_none_is_refused_before_any_forge_call(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path, workflows=False)

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "none" in str(exc.value)
    assert client.calls == []


def test_a_non_github_forge_is_refused_before_any_forge_call(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)
    (repo / ".devcontainer").mkdir()
    (repo / ".devcontainer" / "fr-profiles.yaml").write_text(
        "schema_version: 2\nforge: {type: gitlab, host: gitlab.example.com}\n"
    )
    _commit(repo, "gitlab")
    _git(repo, "push", "-q", "origin", BRANCH)

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "gitlab" in str(exc.value)
    assert client.calls == []


# --- the gate names --------------------------------------------------------


def test_the_gate_names_come_from_ci_yaml_at_head(tmp_path: Path) -> None:
    repo, _, _ = _world(tmp_path, ci_yaml="gate_checks: [ci-ok, lint]\n")
    (repo / ".fr" / "ci.yaml").write_text("gate_checks: [other]\n")  # uncommitted

    assert load_gate_checks(repo) == ["ci-ok", "lint"]


def test_without_ci_yaml_the_required_checks_are_the_gates(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path, ci_yaml=None)
    client.required_names[(REPO, "main")] = ["lint"]
    client.commit_checks_by_sha[(REPO, head)] = _with("green-head", "ci-ok", conclusion="failure")

    assert load_gate_checks(repo) is None
    assert verify_ci(repo, client).startswith(f"ci:{head}+")  # ci-ok is no gate here
    assert ("required_check_names", {"repo": REPO, "base": "main"}) in client.calls


def test_with_no_gates_declared_ci_is_refused_naming_both_ways(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path, ci_yaml=None)

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert ".fr/ci.yaml" in str(exc.value) and "required" in str(exc.value)


@pytest.mark.parametrize("text", ["gate_checks: []\n", "gate_checks: ci-ok\n", "- ci-ok\n"])
def test_a_malformed_ci_yaml_is_refused(tmp_path: Path, text: str) -> None:
    repo, _, _ = _world(tmp_path, ci_yaml=text)

    with pytest.raises(CiEvidenceRefused) as exc:
        load_gate_checks(repo)

    assert ".fr/ci.yaml" in str(exc.value)


def test_this_repo_declares_ci_ok_as_its_gate() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    assert (repo_root / ".fr" / "ci.yaml").read_text().strip() == "gate_checks: [ci-ok]"


# --- p2-r1: without a file, the required NAMES, reported or not ------------


def test_required_gates_with_nothing_reported_are_pending(tmp_path: Path) -> None:
    """Right after a push no check exists yet: pending, never "no gates"."""
    repo, client, head = _world(tmp_path, ci_yaml=None)
    client.required_names[(REPO, "main")] = ["ci-ok"]
    client.commit_checks_by_sha.pop((REPO, head))

    with pytest.raises(CiPending):
        verify_ci(repo, client)


def test_a_partially_reported_required_set_is_pending(tmp_path: Path) -> None:
    """Captured mid-run head: `lint` reported green, `ci-ok` not created yet."""
    repo, client, head = _world(tmp_path, ci_yaml=None)
    client.required_names[(REPO, "main")] = ["lint", "ci-ok"]
    client.commit_checks_by_sha[(REPO, head)] = _captured("pending")

    with pytest.raises(CiPending) as exc:
        verify_ci(repo, client)

    assert "ci-ok" in str(exc.value)


# --- p2-r2: the gate set is base ∪ HEAD ------------------------------------


def _base_declares(repo: Path, text: str) -> None:
    """Put *text* as `.fr/ci.yaml` on `origin/main` (pushed, then fetched)."""
    _git(repo, "checkout", "-q", "-b", "base-side")
    (repo / ".fr").mkdir(exist_ok=True)
    (repo / ".fr" / "ci.yaml").write_text(text)
    _commit(repo, "base gates")
    _git(repo, "push", "-q", "origin", "base-side:main")
    _git(repo, "checkout", "-q", BRANCH)
    _git(repo, "fetch", "-q", "origin")


def test_a_branch_cannot_drop_a_gate_its_base_declares(tmp_path: Path) -> None:
    """DERIVED: the captured green head (`green-head/`) with `ci-ok` failed. HEAD's file names
    only `lint`; the base's still names `ci-ok`, so the failure counts."""
    repo, client, head = _world(tmp_path, ci_yaml="gate_checks: [lint]\n")
    _base_declares(repo, "gate_checks: [ci-ok]\n")
    client.commit_checks_by_sha[(REPO, head)] = _with("green-head", "ci-ok", conclusion="failure")

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client)

    assert "ci-ok" in str(exc.value)


def test_a_base_file_alone_declares_the_gates(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path, ci_yaml=None)
    _base_declares(repo, "gate_checks: [ci-ok]\n")

    assert verify_ci(repo, client).startswith(f"ci:{head}+{BASE}")
    assert "required_check_names" not in _forge_calls(client)


# --- p2-r3: the witness's base ---------------------------------------------


def test_a_run_whose_pr_moved_on_witnesses_an_unknown_base(tmp_path: Path) -> None:
    """Captured `green/`: a green commit whose PR's head had already moved on
    when it was read, so no listed PR's head is the CI sha."""
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha[(REPO, head)] = _captured("green")

    assert verify_ci(repo, client).startswith(f"ci:{head}+unknown;tree=")


# --- p2-r4: a failed gate with a re-run in flight ---------------------------


def test_a_failed_gate_while_its_workflow_re_runs_is_pending(tmp_path: Path) -> None:
    """DERIVED: the captured green head (`green-head/`) with `ci-ok` failed and one CI shard
    back `in_progress` — a re-run whose new `ci-ok` does not exist yet."""
    repo, client, head = _world(tmp_path)
    records = _with("green-head", "ci-ok", conclusion="failure")
    shard = next(r for r in records if r["name"] == "test (py3.11, 1)")
    assert shard["workflow"] == "CI"
    shard.update(status="in_progress", conclusion="")
    client.commit_checks_by_sha[(REPO, head)] = records

    with pytest.raises(CiPending) as exc:
        verify_ci(repo, client)

    assert shard["url"] in str(exc.value)


def test_a_failed_gate_while_another_workflow_runs_is_refused(tmp_path: Path) -> None:
    """DERIVED: as above, but the unfinished check is another workflow's."""
    repo, client, head = _world(tmp_path)
    records = _with("green-head", "ci-ok", conclusion="failure")
    other = next(r for r in records if r["workflow"] not in {"CI", ""})
    other.update(status="in_progress", conclusion="")
    client.commit_checks_by_sha[(REPO, head)] = records

    with pytest.raises(CiEvidenceRefused):
        verify_ci(repo, client)


# --- p2-r5: a walk no CI ever answered ---------------------------------------


def _committed_at(repo: Path) -> float:
    return float(_git(repo, "log", "-1", "--format=%ct", "HEAD"))


def test_no_check_on_a_fresh_head_is_pending(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha.pop((REPO, head))
    at = _committed_at(repo)

    with pytest.raises(CiPending):
        verify_ci(repo, client, now=lambda: at + 14 * 60)


def test_no_check_fifteen_minutes_on_is_refused(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha.pop((REPO, head))
    at = _committed_at(repo)

    with pytest.raises(CiEvidenceRefused) as exc:
        verify_ci(repo, client, now=lambda: at + 15 * 60)

    assert f"no CI ran for {head[:12]}" in str(exc.value)


# --- p2-r6: a pending message says where to look -----------------------------


def test_pending_names_each_unfinished_checks_url(tmp_path: Path) -> None:
    """Captured mid-run head: every in-progress check's URL is in the message."""
    repo, client, head = _world(tmp_path)
    records = _captured("pending")
    client.commit_checks_by_sha[(REPO, head)] = records
    running = [r["url"] for r in records if r["status"] != "completed"]
    assert running

    with pytest.raises(CiPending) as exc:
        verify_ci(repo, client)

    assert all(url in str(exc.value) for url in running)


def test_pending_with_nothing_reported_names_the_prs_checks_page(tmp_path: Path) -> None:
    repo, client, head = _world(tmp_path)
    client.commit_checks_by_sha.pop((REPO, head))

    with pytest.raises(CiPending) as exc:
        verify_ci(repo, client)

    assert f"https://github.com/{REPO}/pull/7/checks" in str(exc.value)


# --- p2-r7: the open-PR lookup reads no files ---------------------------------


def test_the_open_pr_lookup_reads_no_files(tmp_path: Path) -> None:
    repo, client, _ = _world(tmp_path)

    verify_ci(repo, client)

    assert "list_prs_by_head" not in _forge_calls(client)
    assert ("open_pr_for_head", {"repo": REPO, "branch": BRANCH}) in client.calls


# --- p2-r10: the walk's bounds -------------------------------------------------


def _bookkeeping(repo: Path, n: int) -> str:
    runs = repo / "docs" / "superpowers" / "runs" / "r1.yaml"
    head = ""
    for i in range(n):
        runs.write_text(f"run: r1\nstep: {i}\n")
        head = _commit(repo, f"chore(fr): run r1 — {i}")
    _git(repo, "push", "-q", "origin", BRANCH)
    return head


def test_a_tested_sha_fifty_commits_back_is_the_last_one_walked(tmp_path: Path) -> None:
    repo, client, tested = _world(tmp_path)
    _bookkeeping(repo, WALK_LIMIT - 1)

    assert verify_ci(repo, client).startswith(f"ci:{tested}+")


def test_a_tested_sha_past_the_walk_limit_is_never_read(tmp_path: Path) -> None:
    repo, client, tested = _world(tmp_path)
    _bookkeeping(repo, WALK_LIMIT)

    with pytest.raises(CiPending):
        verify_ci(repo, client)

    read = [c["sha"] for name, c in client.calls if name == "commit_checks"]
    assert len(read) == WALK_LIMIT and tested not in read


def test_a_code_change_then_its_revert_breaks_the_walk_at_the_change(tmp_path: Path) -> None:
    """HEAD's tree equals the tested sha's again, but the walk stops at the
    commit between them: CI never tested the reverted history's head."""
    repo, client, tested = _world(tmp_path)
    (repo / "src" / "x.py").write_text("x = 2\n")
    _commit(repo, "code")
    (repo / "src" / "x.py").write_text("x = 1\n")
    _commit(repo, "revert code")
    _git(repo, "push", "-q", "origin", BRANCH)
    assert code_tree(repo, tested) == code_tree(repo)

    with pytest.raises(CiPending):
        verify_ci(repo, client)

    assert ("commit_checks", {"repo": REPO, "sha": tested}) not in client.calls

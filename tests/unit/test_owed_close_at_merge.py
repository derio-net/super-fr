"""An owed issue closes at merge (spec 2026-11-15-owed-archive-side-effects R4, R5):
the PR body `deliver` renders lists, under `## Owed actions discharged`, one
`Closes <owner/repo>#<n>` line per owed entry the BRANCH discharged — in any
journal, live or archived — and a held issue as `Refs <ref> — held: <reason>`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    archived_journal_path,
    journal_path,
    owed_body,
    resolution_entry,
)
from fr.record.pr_body import (
    DischargedOwed,
    discharged_owed,
    held_issues,
    premature_closes,
    render_owed_discharged,
    render_pr_body,
)
from fr.run.model import RunState

OWN = "acme/widgets"
SLUG = "2026-10-01-old-plan"
KEY = f"plan:{SLUG}#p2"


def _git(root: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return done.stdout


def _owed(eid: str = "owed-phase-2", key: str = KEY) -> JournalEntry:
    return JournalEntry(
        kind="owed",
        scope="plan",
        id=eid,
        created="2026-10-01T10:00:00+00:00",
        title="phase 2 owed",
        body=owed_body(what="do it", why="manual", how="resolve it", key=key),
    )


def _filed(owed: JournalEntry, ref: str, taken: set[str]) -> JournalEntry:
    return resolution_entry(
        target=owed,
        scope="plan",
        taken=taken,
        created="2026-10-01T11:00:00+00:00",
        state="open",
        body="filed",
        filed_as=ref,
    )


def _fixed(owed: JournalEntry, taken: set[str]) -> JournalEntry:
    return resolution_entry(
        target=owed,
        scope="plan",
        taken=taken,
        created="2026-11-15T11:00:00+00:00",
        state="fixed",
        body="done by hand",
    )


def _append(path: Path, *entries: JournalEntry) -> None:
    for e in entries:
        append_journal_entry(path, SLUG, e)


def _world(tmp_path: Path, filed_as: str = f"{OWN}#12", *, archived: bool = True) -> Path:
    """`main` (= `origin/main`) carries a journal with one filed owed entry; HEAD
    is a feature branch cut from it."""
    root = tmp_path
    _git(root, "init", "-q", "-b", "main")
    _git(root, "remote", "add", "origin", f"https://github.com/{OWN}.git")
    path = (archived_journal_path if archived else journal_path)(root, "plan", SLUG)
    owed = _owed()
    _append(path, owed, _filed(owed, filed_as, {owed.id}))
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "main")
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(root, "checkout", "-q", "-b", "feat/x")
    return root


def _discharge_on_branch(root: Path, *, archived: bool = True) -> None:
    path = (archived_journal_path if archived else journal_path)(root, "plan", SLUG)
    owed = _owed()
    _append(path, _fixed(owed, {owed.id, f"{owed.id}-resolved"}))
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "discharge")


def _state() -> RunState:
    return RunState(
        run="run-1",
        workflow="fr-goal@1",
        branch="feat/x",
        started="2026-11-15T00:00:00+00:00",
        cursor="deliver",
        steps={},
    )


def _section(body: str) -> str:
    return body.split("## Owed actions discharged\n\n")[1].split("\n\n## ")[0]


# --- R4: what the branch discharged ----------------------------------------------


def test_an_archived_journals_owed_entry_discharged_on_the_branch_is_closed_by_the_body(
    tmp_path: Path,
) -> None:
    root = _world(tmp_path)
    _discharge_on_branch(root)
    assert discharged_owed(root) == [DischargedOwed(ref=f"{OWN}#12", entry="owed-phase-2")]
    assert _section(render_pr_body(root, _state())).strip() == f"Closes {OWN}#12"


def test_a_live_journals_discharge_is_listed_too(tmp_path: Path) -> None:
    root = _world(tmp_path, archived=False)
    _discharge_on_branch(root, archived=False)
    assert [d.ref for d in discharged_owed(root)] == [f"{OWN}#12"]


def test_a_journal_archived_on_the_branch_compares_with_its_live_copy(tmp_path: Path) -> None:
    root = _world(tmp_path, archived=False)
    live = journal_path(root, "plan", SLUG)
    gone = archived_journal_path(root, "plan", SLUG)
    gone.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "mv", str(live), str(gone))
    _git(root, "commit", "-qm", "archive")
    assert discharged_owed(root) == [], "moving the journal discharges nothing"
    _discharge_on_branch(root)
    assert [d.ref for d in discharged_owed(root)] == [f"{OWN}#12"]


def test_an_entry_already_fixed_at_the_default_ref_is_not_listed(tmp_path: Path) -> None:
    root = _world(tmp_path)
    _git(root, "checkout", "-q", "main")
    _discharge_on_branch(root)
    _git(root, "update-ref", "refs/remotes/origin/main", "HEAD")
    _git(root, "checkout", "-q", "-B", "feat/x")
    other = _owed("another-owed", f"plan:{SLUG}#p3")
    _append(archived_journal_path(root, "plan", SLUG), other)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "branch touches the journal")
    assert discharged_owed(root) == []


def test_a_filed_as_in_another_repo_is_not_listed(tmp_path: Path) -> None:
    root = _world(tmp_path, filed_as="mallory/elsewhere#12")
    _discharge_on_branch(root)
    assert discharged_owed(root) == []


def test_nothing_discharged_renders_none(tmp_path: Path) -> None:
    root = _world(tmp_path)
    assert discharged_owed(root) == []
    assert _section(render_pr_body(root, _state())).strip() == "None."


def test_without_a_default_ref_nothing_is_listed(tmp_path: Path) -> None:
    root = _world(tmp_path)
    _discharge_on_branch(root)
    _git(root, "update-ref", "-d", "refs/remotes/origin/main")
    assert discharged_owed(root) == []


# --- R5: a held issue is a Refs, and a listed Closes is no premature close --------


def test_a_held_discharged_issue_renders_refs_with_its_reason() -> None:
    items = [DischargedOwed(ref=f"{OWN}#12", entry="owed-phase-2")]
    held = {f"{OWN}#12": "row r1 still holds it open"}
    assert (
        render_owed_discharged(items, held) == f"Refs {OWN}#12 — held: row r1 still holds it open"
    )
    assert render_owed_discharged(items, {}) == f"Closes {OWN}#12"
    assert render_owed_discharged([], {}) == "None."


def _matrix(status: str, issues: list[str]):  # noqa: ANN202
    from fr.acceptance.model import Matrix, Row

    return Matrix(
        org="acme",
        repo="widgets",
        rows=[
            Row(
                id="r1",
                capability="c",
                acceptance="a",
                origin=["spec:x#R1"],
                levels={},
                status=status,
                issues=issues,
            )
        ],
    )


def test_held_issues_names_why_each_issue_is_held() -> None:
    matrix = _matrix("walk-owed", [f"{OWN}#12"])
    held = held_issues(matrix, ("acme", "widgets"), lambda row: False)
    assert set(held) == {f"{OWN}#12"} and "r1" in held[f"{OWN}#12"]
    assert held_issues(_matrix("ci", [f"{OWN}#12"]), ("acme", "widgets"), lambda r: False) == {}


def test_a_listed_closes_that_nothing_holds_is_not_a_premature_close() -> None:
    body = f"## Owed actions discharged\n\nCloses {OWN}#12\n"
    assert (
        premature_closes(body, _matrix("ci", [f"{OWN}#12"]), ("acme", "widgets"), lambda r: False)
        == []
    )
    found = premature_closes(
        body, _matrix("walk-owed", [f"{OWN}#12"]), ("acme", "widgets"), lambda r: False
    )
    assert [p.ref for p in found] == [f"{OWN}#12"], "a hold still wins over the listing"


def test_the_section_renders_held_refs_from_the_runs_matrix(tmp_path: Path) -> None:
    from tests.unit.acceptance_helpers import write_matrix_fragments

    root = _world(tmp_path)
    write_matrix_fragments(
        root,
        "schema_version: 5\norg: acme\nrepo: widgets\nrows:\n"
        "  - id: r1\n    capability: c\n    acceptance: a\n    origin: ['spec:x#R1']\n"
        f"    levels: {{}}\n    status: walk-owed\n    issues: ['{OWN}#12']\n",
    )
    _discharge_on_branch(root)
    section = _section(render_pr_body(root, _state())).strip()
    assert section.startswith(f"Refs {OWN}#12 — held: ")
    assert "r1" in section

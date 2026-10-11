"""The archive hold, owed filing and manual-phase owed (spec 2026-10-11-debt-engine
§E, R19, R21, R22)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr.journal.model import (
    JournalEntry,
    append_journal_entry,
    archived_journal_path,
    journal_path,
    open_owed_ids,
    owed_body,
    owed_fields,
    owed_filed_as,
    parse_journal,
)

from tests.unit import test_archive_branch as tb
from tests.unit.fakes import FakeGhClient
from tests.unit.test_archive_cmd import _add_plan, _invoke, _repo, _seed

PLAN = "2026-10-11-widget"
SPEC_NAME = "2026-10-11-widget-design.md"
SPEC_SLUG = "2026-10-11-widget"
OWN = "acme/widgets"
MATRIX = "schema_version: 5\norg: acme\nrepo: widgets\nrows: []\n"
TEST_PLAN = "\n## Test Plan\n\n1. Walk the widget live.\n2. Dispatch the weekly job.\n"


class ListingGh(FakeGhClient):
    """A forge double that lists the open issues it holds."""

    def __init__(self, existing: list[dict] | None = None) -> None:
        super().__init__()
        self.listed = existing or []

    def viewer_login(self) -> str:
        return "me"

    def list_issues(self, repo, state, limit, fields=None):  # noqa: ANN001, ANN201
        return list(self.listed)


def _created(gh: FakeGhClient) -> list[dict]:
    return [kw for name, kw in gh.calls if name == "create_issue"]


def _spec_text(test_plan: str = TEST_PLAN) -> str:
    return (
        f"# Widget\n{test_plan}\n## Implementation Plans\n\n"
        "| Plan | Repo | File | Depends on |\n|---|---|---|---|\n"
        f"| {PLAN} | acme/widgets | `docs/superpowers/plans/{PLAN}` | — |\n"
    )


def _outcome(n: int, kind: str = "discovery") -> JournalEntry:
    body = (
        owed_body(
            what=f"step {n}",
            why="needs main",
            how="fr journal resolve …",
            key=f"spec:{SPEC_SLUG}#step{n}",
        )
        if kind == "owed"
        else f"Step: step {n}\n\nReason: in CI"
    )
    return JournalEntry(
        kind=kind,  # type: ignore[arg-type]
        scope="spec",
        id=f"test-plan-step-{n}",
        created="2026-10-11T10:00:00+00:00",
        title=f"Test Plan step {n}",
        body=body,
    )


def _plan_repo(tmp_path: Path, *, outcomes: list[JournalEntry], test_plan: str = TEST_PLAN):
    repo = _repo(tmp_path)
    _add_plan(repo, PLAN, ticked=True, spec_name=SPEC_NAME)
    (repo / "docs/superpowers/specs" / SPEC_NAME).write_text(_spec_text(test_plan))
    (repo / "docs/acceptance").mkdir(parents=True)
    (repo / "docs/acceptance/matrix.yaml").write_text(MATRIX)
    path = journal_path(repo, "spec", SPEC_SLUG)
    for e in outcomes:
        append_journal_entry(path, SPEC_SLUG, e)
    _seed(repo)
    return repo


def _archive(monkeypatch, repo: Path, gh: FakeGhClient, *flags: str):  # noqa: ANN001, ANN202
    return _invoke(monkeypatch, repo, gh, ["archive", f"docs/superpowers/plans/{PLAN}", *flags])


# --- R19: the hold, plan-dir mode -----------------------------------------


def test_plan_dir_archive_holds_a_step_with_no_outcome_and_names_its_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1)])
    result = _archive(monkeypatch, repo, FakeGhClient())
    assert result.exit_code == 2, result.output
    assert (repo / "docs/superpowers/plans" / PLAN).is_dir(), "nothing moved"
    assert "step 2" in result.output
    assert "fr closeout outcome --spec docs/superpowers/specs/" in result.output
    assert "--step 2" in result.output
    assert "--step 1 " not in result.output


def test_force_does_not_lift_the_outcome_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[])
    result = _archive(monkeypatch, repo, FakeGhClient(), "--force")
    assert result.exit_code == 2, result.output
    assert (repo / "docs/superpowers/plans" / PLAN).is_dir()


def test_every_step_recorded_archives(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1), _outcome(2)])
    result = _archive(monkeypatch, repo, FakeGhClient())
    assert result.exit_code == 0, result.output
    assert not (repo / "docs/superpowers/plans" / PLAN).exists()


def test_a_spec_without_a_test_plan_is_never_held(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[], test_plan="")
    result = _archive(monkeypatch, repo, FakeGhClient())
    assert result.exit_code == 0, result.output


def test_archive_all_skips_a_held_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _plan_repo(tmp_path, outcomes=[])
    result = _invoke(monkeypatch, repo, FakeGhClient(), ["archive", "--all"])
    assert result.exit_code == 0, result.output
    assert (repo / "docs/superpowers/plans" / PLAN).is_dir()
    assert "no recorded outcome" in result.output


# --- R19: the hold, --branch mode -----------------------------------------


def test_branch_archive_holds_a_step_with_no_outcome(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tb._base(tmp_path)

    def build(r: Path) -> None:
        tb._plan(r, PLAN, ticked=True, spec=SPEC_NAME)
        tb._write(r, tb.SP / "specs" / SPEC_NAME, _spec_text())

    tb._merged(repo, build)
    result = tb._invoke(monkeypatch, repo, ["archive", "--branch", tb.BRANCH])
    assert result.exit_code == 0, result.output
    assert f"held: docs/superpowers/plans/{PLAN}" in result.output
    assert "no recorded outcome" in result.output
    assert "--step 1" in result.output and "--step 2" in result.output
    assert (repo / tb.SP / "plans" / PLAN).is_dir()


# --- R21: owed filing -----------------------------------------------------


def test_open_owed_entries_are_filed_even_under_no_issues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1), _outcome(2, "owed")])
    gh = ListingGh()
    result = _archive(monkeypatch, repo, gh, "--no-issues")
    assert result.exit_code == 0, result.output
    (made,) = _created(gh)
    assert made["repo"] == OWN
    assert made["labels"] == frozenset({"fr:owed"})
    assert made["body"].rstrip().endswith(f"<!-- fr-owed:spec:{SPEC_SLUG}#step2 -->")
    assert "step 2" in made["body"] and "fr journal resolve" in made["body"]
    entries = parse_journal(archived_journal_path(repo, "spec", SPEC_SLUG).read_text())
    assert owed_filed_as(entries) == {"test-plan-step-2": f"{OWN}#1"}
    assert open_owed_ids(entries) == ["test-plan-step-2"], "filed is still owed"
    assert any(n == "ensure_labels" for n, _ in gh.calls)


def test_an_open_issue_with_the_owed_marker_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1), _outcome(2, "owed")])
    marker = f"<!-- fr-owed:spec:{SPEC_SLUG}#step2 -->"
    gh = ListingGh(
        [
            {
                "number": 7,
                "url": f"https://github.com/{OWN}/issues/7",
                "body": f"x\n{marker}",
                "author": {"login": "me"},
            }
        ]
    )
    result = _archive(monkeypatch, repo, gh)
    assert result.exit_code == 0, result.output
    assert _created(gh) == []
    entries = parse_journal(archived_journal_path(repo, "spec", SPEC_SLUG).read_text())
    assert owed_filed_as(entries) == {"test-plan-step-2": f"{OWN}#7"}


def test_an_already_filed_owed_entry_is_not_filed_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.journal.model import resolution_entry

    owed = _outcome(2, "owed")
    filed = resolution_entry(
        target=owed,
        scope="spec",
        taken={owed.id},
        created="2026-10-11T11:00:00+00:00",
        state="open",
        body="filed",
        filed_as=f"{OWN}#3",
    )
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1), owed, filed])
    gh = ListingGh()
    result = _archive(monkeypatch, repo, gh)
    assert result.exit_code == 0, result.output
    assert _created(gh) == []


def test_nothing_is_filed_under_tracking_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _plan_repo(tmp_path, outcomes=[_outcome(1), _outcome(2, "owed")])
    prof = repo / ".devcontainer"
    prof.mkdir()
    (prof / "fr-profiles.yaml").write_text(
        "schema_version: 2\nprofiles:\n  dev:\n    purpose: x\ntracking: {type: none}\n"
    )
    gh = ListingGh()
    result = _archive(monkeypatch, repo, gh, "--issues", "all")
    assert result.exit_code == 0, result.output
    assert _created(gh) == []
    entries = parse_journal(archived_journal_path(repo, "spec", SPEC_SLUG).read_text())
    assert open_owed_ids(entries) == ["test-plan-step-2"]
    assert owed_filed_as(entries) == {}


# --- R22: a held manual phase ---------------------------------------------

MANUAL_PHASE = """schema_version: 2
phase:
  number: 2
  title: Walk it live
  tag: manual
  depends_on: [1]
  tracking_issue: null
  files: []
tasks:
  - number: 1
    title: Walk
    steps:
      - id: P2.T1.S1
        text: Walk the widget
state:
  steps:
    P2.T1.S1:
      state: " "
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
"""


def _manual_repo(tmp_path: Path) -> Path:
    repo = _repo(tmp_path)
    plan = _add_plan(repo, PLAN, ticked=True)
    (plan / "02.yaml").write_text(MANUAL_PHASE)
    (repo / "docs/acceptance").mkdir(parents=True)
    (repo / "docs/acceptance/matrix.yaml").write_text(MATRIX)
    _seed(repo)
    return repo


def test_a_held_manual_phase_writes_and_files_its_owed_entry_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _manual_repo(tmp_path)
    gh = ListingGh()
    result = _archive(monkeypatch, repo, gh)
    assert result.exit_code == 2, result.output
    assert (repo / "docs/superpowers/plans" / PLAN).is_dir()
    entries = parse_journal(journal_path(repo, "plan", PLAN).read_text())
    owed = [e for e in entries if e.kind == "owed"]
    assert [e.id for e in owed] == ["manual-phase-2"]
    assert owed[0].phase == 2
    assert owed_fields(owed[0])["owed_key"] == f"plan:{PLAN}#p2"
    (made,) = _created(gh)
    assert made["body"].rstrip().endswith(f"<!-- fr-owed:plan:{PLAN}#p2 -->")
    assert owed_filed_as(entries) == {"manual-phase-2": f"{OWN}#1"}

    again = _archive(monkeypatch, repo, gh)
    assert again.exit_code == 2, again.output
    entries = parse_journal(journal_path(repo, "plan", PLAN).read_text())
    assert [e.id for e in entries if e.kind == "owed"] == ["manual-phase-2"]
    assert len(_created(gh)) == 1, "a re-run files nothing new"


# --- R19: the close-out brief lists the steps -----------------------------


def test_the_closeout_brief_lists_each_step_with_its_command(tmp_path: Path) -> None:
    from fr.run.closeout import RunExtras, branch_closeout_brief

    repo = _plan_repo(tmp_path, outcomes=[_outcome(1)])
    brief = branch_closeout_brief(
        repo,
        "feat/widget",
        run_extras=RunExtras(
            run_id="2026-10-11-feat-widget",
            pr=None,
            spec_path=f"docs/superpowers/specs/{SPEC_NAME}",
            plan_path=f"docs/superpowers/plans/{PLAN}",
            has_test_plan=True,
            out_of_scope=[],
            test_plan_steps=[(2, "Dispatch the weekly job.")],
        ),
    )
    assert "step 2: Dispatch the weekly job." in brief
    assert "fr closeout outcome --run 2026-10-11-feat-widget --step 2" in brief

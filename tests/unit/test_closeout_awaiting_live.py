"""The close-out brief's awaiting-live lines (spec 2026-10-06-verification-strategies
§F, R17) and the label's registration."""

from __future__ import annotations

from pathlib import Path

import pytest
from fr import labels
from fr.run.closeout import closeout_brief
from fr.run.model import RunState, StepRecord, save_run_state

from tests.unit.test_pr_body_verification import _matrix
from tests.unit.test_verification_walk import RUN, SPEC, _git, _repo

PR = "https://github.com/o/proj/pull/9"
WALK = {
    "strategy": "live",
    "harness": "h",
    "model": "m",
    "outcome": "pass",
    "at": "2026-10-06T00:00:00+00:00",
    "evidence": "note",
}


def test_the_label_is_registered() -> None:
    assert labels.FR_AWAITING_LIVE.name == "fr:awaiting-live"


class _Forge:
    def __init__(self, body: str | Exception) -> None:
        self.body = body

    def pr_body(self, ref: str, *, cwd: Path) -> str:
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def _delivered(root: Path) -> RunState:
    state = RunState(
        run=RUN,
        workflow="fr-goal@1",
        branch="b",
        started="2026-10-06T11:00:00+00:00",
        cursor="deliver",
        steps={
            "spec": StepRecord(
                state="done", at="2026-10-06T12:00:00+00:00", emitted={"spec": SPEC}
            ),
            "deliver": StepRecord(state="done", at="2026-10-06T13:00:00+00:00", emitted={"pr": PR}),
        },
    )
    save_run_state(root, state)
    return state


def _brief(root: Path, monkeypatch: pytest.MonkeyPatch, body: str | Exception) -> str:
    import fr.hostclient

    monkeypatch.setattr(fr.hostclient, "client_for", lambda _root: _Forge(body))
    return closeout_brief(root, _delivered(root))


def _rows(root: Path) -> None:
    _matrix(
        root,
        [
            {"id": "held", "verify": "live", "issues": ["o/proj#5"]},
            {"id": "done", "verify": "live", "issues": ["o/proj#6"], "walks": [WALK]},
            {"id": "early", "verify": "candidate", "issues": ["o/proj#7"]},
        ],
    )


def test_a_refsd_issue_a_waiting_row_cites_gets_the_label_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _rows(root)

    brief = _brief(root, monkeypatch, "Summary\n\nRefs o/proj#5\n")

    assert "gh issue edit 5 --repo o/proj --add-label fr:awaiting-live" in brief
    assert brief.index("fr:awaiting-live") < brief.index("fr archive")


def test_a_bare_hash_ref_takes_the_repos_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _rows(root)

    assert "--add-label fr:awaiting-live" in _brief(root, monkeypatch, "Refs #5\n")


@pytest.mark.parametrize(
    "body",
    [
        "Closes o/proj#5\n",  # closed, not Refs'd
        "Refs o/proj#6\n",  # its row is walk-verified
        "Refs o/proj#7\n",  # its row is pre-merge
        "Refs o/proj#99\n",  # no row cites it
        "See o/proj#5\n",  # mentioned, not Refs'd
        "```\nRefs o/proj#5\n```\n",  # code
    ],
)
def test_other_issues_get_no_label_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    root = _repo(tmp_path)
    _rows(root)

    assert "fr:awaiting-live" not in _brief(root, monkeypatch, body)


def test_an_unreadable_pr_is_said_not_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.hostclient import FORGE_ERRORS

    root = _repo(tmp_path)
    _rows(root)

    brief = _brief(root, monkeypatch, FORGE_ERRORS[0]("no such pr"))

    assert "awaiting-live" in brief and "could not read" in brief
    _git(root, "status")  # the brief wrote nothing


@pytest.mark.parametrize(
    ("backend", "create"),
    [
        (
            "github",
            "gh label create fr:awaiting-live --color FBCA04 --description "
            "'Merged; a post-merge acceptance row still awaits its live walk' --force --repo o/r",
        ),
        (
            "gitlab",
            "glab label create --name fr:awaiting-live --color '#FBCA04' --description "
            "'Merged; a post-merge acceptance row still awaits its live walk' --repo o/r",
        ),
        (
            "gitea",
            "tea labels create --name fr:awaiting-live --color FBCA04 --description "
            "'Merged; a post-merge acceptance row still awaits its live walk' --repo o/r",
        ),
    ],
)
def test_the_command_table_renders_label_create_per_backend(
    tmp_path: Path, backend: str, create: str
) -> None:
    """p4-r4: the label may not exist yet on the repo; the brief creates it first."""
    from fr.hostclient import label_command

    from tests.unit.test_acceptance_walks import _repo_on

    root = _repo_on(tmp_path, backend)
    assert label_command(root, labels.FR_AWAITING_LIVE, repo="o/r") == create


def test_the_brief_creates_the_label_once_per_repo_before_its_add_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path)
    _matrix(
        root,
        [
            {"id": "held", "verify": "live", "issues": ["o/proj#5", "o/proj#6"]},
            {"id": "other", "verify": "live", "issues": ["o/other#8"]},
        ],
    )

    brief = _brief(root, monkeypatch, "Refs o/proj#5\nRefs o/proj#6\nRefs o/other#8\n")

    lines = [ln.strip() for ln in brief.splitlines() if "fr:awaiting-live" in ln]
    assert [ln.split(" --repo ")[1].split()[0] if "--repo" in ln else ln for ln in lines] == [
        "o/other", "o/other", "o/proj", "o/proj", "o/proj",
    ]  # fmt: skip
    assert lines[0].startswith("gh label create fr:awaiting-live")
    assert lines[1] == "gh issue edit 8 --repo o/other --add-label fr:awaiting-live"
    assert lines[2].startswith("gh label create fr:awaiting-live")
    assert lines[2].endswith("--force --repo o/proj")
    assert lines[3:] == [
        "gh issue edit 5 --repo o/proj --add-label fr:awaiting-live",
        "gh issue edit 6 --repo o/proj --add-label fr:awaiting-live",
    ]

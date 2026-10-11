"""Label creation, the board's approval asks and the briefs (spec
2026-10-11-merge-train-safety §A "Label creation", "The walk", "Briefs and the
tripwire"; R4, R5, R6).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.ghclient import UnsupportedForgeOperation
from fr.labels import APPROVED_FR
from fr.triage.approval import ensure_approval_label
from fr.triage.batch_dispatch import NO_APPROVAL_LINE, conflict_brief, render_brief
from fr.triage.kanban import HINT_AWAITING_APPROVAL, build_board
from fr.triage.model import Batch, Facts, Judgements
from fr.triage.views import NEED_LABELS, needs_you
from typer.testing import CliRunner

from tests.unit.triage_board_fixtures import (
    REPO,
    URL,
    batch,
    dispatch,
    facts,
    issue,
    j,
    judgements,
    pr,
)

# ------------------------------------------------------------------ label creation (R4)


class Labels:
    def __init__(self, *, exists: bool = False, unsupported: bool = False) -> None:
        self.exists, self.unsupported = exists, unsupported
        self.calls: list[str] = []

    def label_exists(self, repo: str, name: str) -> bool:
        self.calls.append(f"exists {repo} {name}")
        if self.unsupported:
            raise UnsupportedForgeOperation("label_exists", "gitlab")
        return self.exists

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        self.calls.append(f"create {repo} {[getattr(x, 'name', x) for x in labels]}")
        self.exists = True


def test_a_missing_label_is_created_once_per_repo_and_said() -> None:
    client, said, seen = Labels(), [], set()  # type: ignore[var-annotated]
    ensure_approval_label(client, "o/r", said.append, seen=seen)
    ensure_approval_label(client, "o/r", said.append, seen=seen)
    assert client.calls == ["exists o/r approved-fr", "create o/r ['approved-fr']"]
    assert said == ["created label approved-fr on o/r"]


def test_an_existing_label_is_silent() -> None:
    client, said = Labels(exists=True), []  # type: ignore[var-annotated]
    ensure_approval_label(client, "o/r", said.append, seen=set())
    assert client.calls == ["exists o/r approved-fr"] and said == []


def test_a_forge_that_cannot_check_labels_warns_and_never_fails() -> None:
    said: list[str] = []
    ensure_approval_label(Labels(unsupported=True), "o/r", said.append, seen=set())
    (line,) = said
    assert line.startswith("warning:") and "approved-fr" in line and "o/r" in line


def test_a_forge_error_warns_too() -> None:
    from fr.gh import GhError

    class Refuses(Labels):
        def ensure_labels(self, repo: str, labels: list[Any]) -> None:
            raise GhError("HTTP 403", returncode=1)

    said: list[str] = []
    ensure_approval_label(Refuses(), "o/r", said.append, seen=set())
    assert said[0].startswith("warning:")


def test_collect_creates_the_label_on_each_collected_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_cmd
    from fr.triage.collect import ClientForge

    from tests.unit.triage_fixtures import FakeForge

    labels = Labels()  # the label verbs, reached through the real `ClientForge`
    fake = FakeForge(issues={"derio-net/super-fr": []}, prs={"derio-net/super-fr": []})
    forge = ClientForge(labels)  # type: ignore[arg-type]
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    monkeypatch.setattr(triage_cmd, "collect_facts_counted", _collected(fake))
    result = CliRunner().invoke(
        app, ["triage", "collect", "--repo", "derio-net/super-fr", "--dir", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "create derio-net/super-fr ['approved-fr']" in labels.calls
    assert "created label approved-fr on derio-net/super-fr" in result.output


def _collected(fake: Any) -> Any:
    from datetime import UTC, datetime

    from fr.triage.collect import collect_facts_counted

    def run(forge: Any, scope: Any, **kw: Any) -> Any:
        return collect_facts_counted(fake, scope, **{**kw, "now": datetime.now(UTC)})

    return run


def test_init_scaffold_creates_the_label_on_a_github_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import init_cmd

    labels = Labels()
    monkeypatch.setattr(init_cmd, "approval_label_target", lambda root: (labels, "o/r"))
    monkeypatch.setattr(init_cmd, "scaffold_profile", lambda *a, **kw: tmp_path / "p")
    result = CliRunner().invoke(
        app, ["init", "scaffold", "--repo", str(tmp_path), "--profile", "dev", "--purpose", "x"]
    )
    assert result.exit_code == 0, result.output
    assert labels.calls[-1] == "create o/r ['approved-fr']"


@pytest.mark.parametrize(
    ("origin", "slug"),
    [
        (None, None),
        ("https://github.com/derio-net/widgets.git", "derio-net/widgets"),
        ("git@github.com:derio-net/widgets.git", "derio-net/widgets"),
        ("https://gitlab.com/derio-net/widgets.git", None),
    ],
    ids=["no-origin", "github-https", "github-ssh", "gitlab"],
)
def test_init_scaffold_targets_only_a_github_origin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, origin: str | None, slug: str | None
) -> None:
    """p1-r3: the REAL `approval_label_target` (the autouse conftest stub undone)."""
    monkeypatch.undo()  # also undoes the suite's sandbox: set back what this reads
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("FR_FORGE_API", "graphql")
    from fr.commands import init_cmd
    from fr.real_ghclient import RealGhClient

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    if origin is not None:
        subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", origin], check=True)
    got = init_cmd.approval_label_target(tmp_path)
    if slug is None:
        assert got is None
    else:
        assert got is not None and got[1] == slug and isinstance(got[0], RealGhClient)


# ------------------------------------------------------------------ the board (R5)


def _one(*, labels: list[str] | None, events: list[dict[str, Any]] | None = None,
         **kw: Any) -> tuple[Facts, Judgements]:  # fmt: skip
    the_pr = pr(20, "feat/batch-x", labels=labels, **kw)
    f = facts([issue(1, prs=[the_pr])], prs=[the_pr], schema=9)
    jd = judgements(
        {"widgets#1": j(1)},
        [batch("x", [1], wave=1, events=[dispatch("x"), *(events or [])])],
        schema=9,
    )
    return f, jd


def test_a_green_unlabelled_batch_pr_asks_for_the_label_draft_or_not() -> None:
    for draft in (False, True):
        f, jd = _one(labels=[], is_draft=draft)
        (need,) = [n for n in needs_you(f, jd) if n.kind == "approve-pr"]
        assert need.ref == "x" and need.href == f"{URL}/pull/20"
        assert need.text == "PR #20 is green: label it approved-fr to merge"


def test_a_labelled_green_pr_asks_nothing() -> None:
    f, jd = _one(labels=[APPROVED_FR.name])
    assert not [n for n in needs_you(f, jd) if n.kind == "approve-pr"]


def test_a_red_or_pending_pr_is_not_asked_for_approval() -> None:
    f, jd = _one(labels=[], checks={"pass": 1, "fail": 1, "pending": 0})
    assert not [n for n in needs_you(f, jd) if n.kind == "approve-pr"]


_APPROVED = {"kind": "approval", "at": "2026-10-01T12:00:00Z", "pr": 20, "head": "sha-old"}


def test_a_voided_approval_asks_for_a_re_label() -> None:
    f, jd = _one(labels=[APPROVED_FR.name], events=[_APPROVED])  # a head fr did not make
    (need,) = [n for n in needs_you(f, jd) if n.kind == "approve-pr"]
    assert need.text == "PR #20 changed since you approved it at sha-old: re-label to merge"
    # after fr removed the label and recorded the void, the ask is the same
    voided = {**_APPROVED, "voided_at": "sha-20"}
    f, jd = _one(labels=[], events=[_APPROVED, voided])
    (need,) = [n for n in needs_you(f, jd) if n.kind == "approve-pr"]
    assert "re-label to merge" in need.text


def test_need_labels_name_the_new_kinds_and_drop_ready_pr() -> None:
    assert {"approve-pr", "red-pr", "queue-ejected"} <= set(NEED_LABELS)
    assert "ready-pr" not in NEED_LABELS


def test_the_kanban_card_of_an_unapproved_green_member_awaits_approval() -> None:
    f, jd = _one(labels=[])
    board = build_board(f, jd, {})
    (card,) = [c for col in board.columns for c in col.cards if c.batch.id == "x"]
    assert card.hint == HINT_AWAITING_APPROVAL == "awaiting approval"


# ------------------------------------------------------------------ the briefs (R6)


def _brief_inputs() -> tuple[Batch, Judgements, Facts]:
    f, jd = _one(labels=[])
    return jd.batches[0], jd, f


def test_the_dispatch_brief_says_never_to_add_the_label() -> None:
    b, jd, f = _brief_inputs()
    text = render_brief(b, jd, f, repo="example-org/widgets", closing_refs=["Closes #1"],
                        reserved_version=None)  # fmt: skip
    assert NO_APPROVAL_LINE in text
    assert "Never add the `approved-fr` label" in NO_APPROVAL_LINE


def test_the_conflict_brief_says_never_to_add_the_label() -> None:
    b, _, _ = _brief_inputs()
    text = conflict_brief(b, pr=20, head="h", paths=["a.py"], branch="feat/batch-x",
                          base="origin/main", mirrors=[])  # fmt: skip
    assert NO_APPROVAL_LINE in text


def test_the_adopt_message_says_never_to_add_the_label() -> None:
    from fr.commands.triage_batch_cmd import adopt_message

    b, _, _ = _brief_inputs()
    assert NO_APPROVAL_LINE in adopt_message(b, "item", "old", "new", None, None)


# ------------------------------------------------------------------ review fixes


def test_a_ci_none_repo_asks_for_the_label_with_no_check_at_all() -> None:
    """p1-r2: a `ci none` repo's PR has no checks; the driver holds it for the label,
    so the board must ask for it (and show the card awaiting approval)."""
    f, jd = _one(labels=[], checks={"pass": 0, "fail": 0, "pending": 0})
    assert not [n for n in needs_you(f, jd) if n.kind == "approve-pr"]  # CI repo: pending
    (need,) = [n for n in needs_you(f, jd, ci_none={REPO}) if n.kind == "approve-pr"]
    assert need.ref == "x"
    board = build_board(f, jd, {}, ci_none={REPO})
    (card,) = [c for col in board.columns for c in col.cards if c.batch.id == "x"]
    assert card.hint == HINT_AWAITING_APPROVAL


def test_the_page_threads_ci_none_to_needs_you() -> None:
    from fr.triage.render import render

    f, jd = _one(labels=[], checks={"pass": 0, "fail": 0, "pending": 0})
    assert 'data-need="approve-pr"' not in render(f, jd)
    assert 'data-need="approve-pr"' in render(f, jd, ci_none={REPO})


def test_a_board_render_builds_one_snapshot_and_one_pass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """p1-r8: the board's actions and its awaiting-approval cards share one plan."""
    from fr.triage import kanban

    counts = {"snapshot": 0, "pass": 0}
    real_snap, real_pass = kanban.drive_snapshot, kanban.drive_pass

    def snap(*a: Any, **kw: Any) -> Any:
        counts["snapshot"] += 1
        return real_snap(*a, **kw)

    def one_pass(*a: Any, **kw: Any) -> Any:
        counts["pass"] += 1
        return real_pass(*a, **kw)

    monkeypatch.setattr(kanban, "drive_snapshot", snap)
    monkeypatch.setattr(kanban, "drive_pass", one_pass)
    f, jd = _one(labels=[])
    build_board(f, jd, {})
    assert counts == {"snapshot": 1, "pass": 1}

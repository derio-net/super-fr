"""Driver-managed branches (spec 2026-11-23-pr-readiness-wait R5)."""

from __future__ import annotations

from pathlib import Path

import fr.settle.managed as managed_mod
import pytest
from fr.settle.managed import driver_managed


@pytest.mark.parametrize(
    "branch",
    [
        "feat/batch-x",
        "fix/batch-x",
        "chore/closeout-2026-11-23-1",
        "chore/closeout-feat-batch-x",
        "chore/closeout-fix-batch-x",
        "chore/triage-state-s-wave-2",
        "chore/ops-p",
    ],
)
def test_a_driver_branch_is_managed(branch: str) -> None:
    assert driver_managed(branch)


@pytest.mark.parametrize(
    "branch",
    [
        "chore/archive-p",
        "chore/closeout-2026-11-23-feat-x",
        "feat/other",
        "fix/other",
        "main",
        "",
    ],
)
def test_any_other_branch_is_not_managed(branch: str) -> None:
    assert not driver_managed(branch)


def test_managed_names_no_prefix_of_its_own() -> None:
    source = Path(managed_mod.__file__).read_text()
    for literal in (
        "feat/batch-",
        "fix/batch-",
        "chore/closeout-",
        "chore/triage-state-",
        "chore/ops-",
        "batch-",
    ):
        assert literal not in source, literal


# ---- the driver briefs carry the managed sentence (R5) -----------------------------


def _driver_briefs() -> dict[str, str]:
    import yaml
    from fr.triage.batch_closeout import handback_brief
    from fr.triage.batch_dispatch import (
        archive_conflict_brief,
        conflict_brief,
        red_brief,
        render_brief,
    )
    from fr.triage.batch_drive import closeout_brief
    from fr.triage.model import Facts, Issue, Judgements

    repo = "derio-net/super-fr"
    judgements = Judgements.model_validate(
        yaml.safe_load(
            "schema: 2\nranked_at: 2026-11-23\ntiers:\n  - {n: 1, title: Now}\n"
            "issues:\n  super-fr#1: {tier: 1}\n"
            "batches:\n  - id: b1\n    title: one\n    ids: ['super-fr#1']\n"
            "    launch: {runner: fake, harness: claude, model: claude-opus-5-5}\n"
        )
    )
    facts = Facts(
        viewer="operator",
        schema=3,
        scope="derio-net--super-fr",
        kind="repo",
        collected_at="2026-11-23T12:00:00+00:00",
        repos=[repo],
        issues=[
            Issue(
                repo=repo,
                number=1,
                title="t",
                state="open",
                url=f"https://github.com/{repo}/issues/1",
                author_association="OWNER",
            )
        ],
    )
    b = judgements.batches[0]
    return {
        "batch": render_brief(
            b, judgements, facts, repo=repo, closing_refs=["Closes #1"], reserved_version=None
        ),
        "red": red_brief(b, pr_url="https://x/pull/1", head="abc", checks=["lint"]),
        "conflict": conflict_brief(
            b,
            pr=1,
            head="abc",
            paths=("a.py",),
            branch="feat/batch-b1",
            base="origin/main",
            mirrors=(),
        ),  # fmt: skip
        "archive": archive_conflict_brief(b, pr=2, head="abc", branch="c/a", base="origin/main"),
        "closeout": closeout_brief(b, run=None, checkout=Path("/w")),
        "handback": handback_brief(pr=3, branch="chore/x", base="main", checks=["lint"]),
    }


@pytest.mark.parametrize("name", ["batch", "red", "conflict", "archive", "closeout", "handback"])
def test_every_driver_brief_carries_the_managed_sentence(name: str) -> None:
    from fr.settle.managed import MANAGED_SENTENCE

    assert MANAGED_SENTENCE in _driver_briefs()[name]

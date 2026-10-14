"""`fr gate pass` — R14's explicit route (spec 2026-10-14-exit-gates §D).

It swaps a PR's `gate:<g>` for `gate:<g>-passed` and comments what passed it, through
the forge adapter, only with `--yes`; it refuses an unknown gate, a gate that holds no
merge (not post-merge), and a PR that does not carry `gate:<g>`; and it prints the
release dispatch, so a final follows the last pass (R20). The forge is faked.
"""

from __future__ import annotations

from typing import Any

import pytest
from fr.artifacts import trigger
from fr.cli import app
from fr.commands import gate_cmd
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient

REPO = "derio-net/super-fr"


def _fake(labels: list[str]) -> FakeGhClient:
    fake = FakeGhClient()
    fake.prs[(REPO, 5)] = {
        "state": "MERGED", "draft": False, "head_ref": "feat/x", "base_ref": "main",
        "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": list(labels),
    }  # fmt: skip
    return fake


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> Any:
    holder: dict[str, FakeGhClient] = {}

    def install(labels: list[str]) -> FakeGhClient:
        holder["fake"] = _fake(labels)
        monkeypatch.setattr(gate_cmd, "client_for_repo", lambda repo: holder["fake"])
        return holder["fake"]

    return install


def _pass(*args: str) -> Any:
    return CliRunner().invoke(
        app, ["gate", "pass", "--repo", REPO, "--pr", "5", "--notes", "walked live", *args]
    )


def _writes(fake: FakeGhClient) -> list[str]:
    return [c[0] for c in fake.calls if c[0] in ("edit_pr_labels", "comment_pr", "ensure_labels")]


def test_without_yes_it_prints_the_swap_and_the_comment_and_writes_nothing(forge: Any) -> None:
    fake = forge(["gate:tester", "verification:live"])

    result = _pass("--gate", "tester")

    assert result.exit_code == 0, result.output
    assert "gate:tester -> gate:tester-passed" in result.output
    assert "walked live" in result.output
    assert "re-run with --yes" in result.output
    assert _writes(fake) == []


def test_with_yes_it_swaps_the_label_and_comments(forge: Any) -> None:
    fake = forge(["gate:tester"])

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    (edit,) = [c[1] for c in fake.calls if c[0] == "edit_pr_labels"]
    assert (edit["add"], edit["remove"]) == (
        frozenset({"gate:tester-passed"}),
        frozenset({"gate:tester"}),
    )
    (comment,) = [c[1] for c in fake.calls if c[0] == "comment_pr"]
    assert comment["pr"] == 5 and "tester" in comment["body"] and "walked live" in comment["body"]
    assert f"gh workflow run release.yml --repo {REPO}" in result.output


@pytest.mark.parametrize(
    ("gate", "labels", "why"),
    [
        ("qa", ["gate:tester"], "unknown gate"),
        ("owner", ["gate:owner"], "not a post-merge gate"),
        ("devops", ["gate:tester"], "does not carry gate:devops"),
        ("tester", ["gate:tester-passed"], "does not carry gate:tester"),
    ],
)
def test_it_refuses_what_is_not_a_held_post_merge_gate(
    forge: Any, gate: str, labels: list[str], why: str
) -> None:
    fake = forge(labels)

    result = _pass("--gate", gate, "--yes")

    assert result.exit_code == 2, result.output
    assert why in result.output
    assert _writes(fake) == []


def test_gate_is_a_read_only_command() -> None:
    assert "gate" in trigger.READ_ONLY_COMMANDS

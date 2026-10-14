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


def _fake(labels: list[str], state: str = "MERGED") -> FakeGhClient:
    fake = FakeGhClient()
    fake.prs[(REPO, 5)] = {
        "state": state, "draft": False, "head_ref": "feat/x", "base_ref": "main",
        "mergeable": "UNKNOWN", "title": "t", "body": "b", "labels": list(labels),
    }  # fmt: skip
    return fake


@pytest.fixture
def forge(monkeypatch: pytest.MonkeyPatch) -> Any:
    holder: dict[str, Any] = {"urls": []}

    def client(url: str) -> FakeGhClient:
        holder["urls"].append(url)
        return holder["fake"]

    def install(labels: list[str], state: str = "MERGED") -> FakeGhClient:
        holder["fake"] = _fake(labels, state)
        holder["fake"].urls = holder["urls"]
        monkeypatch.setattr(gate_cmd, "client_for_url", client)
        monkeypatch.setattr("fr._hosts.origin_slug", lambda root: None)
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


# ------------------------------------------------------------ review p4-r4..r9


def test_p4_r5_it_refuses_a_pr_that_is_not_merged(forge: Any) -> None:
    fake = forge(["gate:tester"], state="OPEN")

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 2, result.output
    assert "is OPEN, not merged" in result.output
    assert _writes(fake) == []


def test_p4_r9_no_release_command_while_another_gate_still_holds(forge: Any) -> None:
    forge(["gate:tester", "gate:devops"])

    result = _pass("--gate", "tester", "--yes")

    assert result.exit_code == 0, result.output
    assert "gh workflow run" not in result.output
    assert "gate:devops still holds" in result.output


def test_p4_r6_the_host_is_the_named_one_or_the_checkouts_origin(
    forge: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = forge(["gate:tester"])
    assert _pass("--gate", "tester", "--host", "ghe.example.com").exit_code == 0
    assert fake.urls[-1] == f"https://ghe.example.com/{REPO}"

    monkeypatch.setattr("fr._hosts.origin_slug", lambda root: REPO)
    monkeypatch.setattr("fr._hosts.origin_hostname", lambda root: "git.example.org")
    assert _pass("--gate", "tester").exit_code == 0
    assert fake.urls[-1] == f"https://git.example.org/{REPO}"


def test_p4_r4_pass_gate_comments_first_and_never_twice() -> None:
    from fr.verification.labels import gate_pass_comment, pass_gate

    fake = _fake(["gate:tester"])
    pass_gate(fake, REPO, 5, "tester", why="walked")
    order = [c[0] for c in fake.calls if c[0] in ("comment_pr", "edit_pr_labels")]
    assert order == ["comment_pr", "edit_pr_labels"]

    again = _fake(["gate:tester"])
    again.issue_comments[(REPO, 5)] = [{"body": gate_pass_comment("tester", "walked")}]
    pass_gate(again, REPO, 5, "tester", why="walked")
    assert [c[0] for c in again.calls if c[0] == "comment_pr"] == []
    assert [c[0] for c in again.calls if c[0] == "edit_pr_labels"] == ["edit_pr_labels"]

    failing = _fake(["gate:tester"])
    failing.fail_on_mutation = 0  # the comment
    with pytest.raises(Exception, match="configured failure"):
        pass_gate(failing, REPO, 5, "tester", why="walked")
    assert [c[0] for c in failing.calls if c[0] == "edit_pr_labels"] == []

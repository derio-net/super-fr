"""`fr triage queue add|remove --pr N` (spec 2026-11-24-wave-queue-gaps R11, §C, §F 7).

Every state directory is tmp_path; the forge is a fake behind the command's `make_client`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_queue_cmd
from fr.commands.triage_cmd import _scope
from fr.gh import GhError
from fr.triage.errors import TriageError
from fr.triage.model import (
    Facts,
    Issue,
    PullRequest,
    QueueAddEvent,
    QueueRemoveEvent,
    load_judgements,
)
from fr.triage.scope_config import scope_id
from typer.testing import CliRunner

REPO = "derio-net/super-fr"
FACTS_SCOPE = "derio-net--super-fr"


def _pr(number: int, head_ref: str, *, author: str = "operator", cross: bool = False,
        **over: Any) -> PullRequest:  # fmt: skip
    return PullRequest(
        repo=REPO, number=number, title=f"pr {number}", state="OPEN", is_draft=False,
        url=f"https://github.com/{REPO}/pull/{number}", head_ref=head_ref, head_oid="h" * 40,
        author=author, cross_repo=cross, created_at="2026-11-20T09:30:00Z", **over,
    )  # fmt: skip


PRS = [
    _pr(10, "fix/typo"),
    _pr(11, "fix/fork", cross=True),
    _pr(12, "fix/stranger", author="mallory"),
    _pr(13, "chore/ops-deploy"),
    _pr(14, "chore/closeout-2026-11-24-1"),
    _pr(15, "chore/archive-foo"),
    _pr(16, "chore/triage-state-derio-net--super-fr-wave-1"),
    _pr(17, "feat/batch-a"),
    _pr(18, "fix/other-base"),
]


class FakeClient:
    def __init__(self, login: str = "operator") -> None:
        self.login = login
        self.views: dict[int, dict[str, Any]] = {
            p.number: {"state": "OPEN", "head_oid": "h" * 40, "head_ref": p.head_ref,
                       "base_ref": "main", "labels": [], "draft": False}
            for p in PRS
        }  # fmt: skip
        self.views[18]["base_ref"] = "release"
        self.reads: list[str] = []

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.reads.append(f"pr_view {number}")
        return self.views[number]

    def viewer_login(self) -> str:
        return self.login

    def repo_default_branch(self, repo: str) -> str:
        return "main"


def _facts(linked: list[PullRequest] | None = None) -> Facts:
    """The scope's facts. *linked* are PRs whose Closes lines name issue 1: collect files
    them under that issue's `prs`, never in the unlinked `facts.prs` (gh#1741)."""
    linked = linked or []
    numbers = {p.number for p in linked}
    return Facts(
        viewer="operator", schema=3, scope=FACTS_SCOPE, kind="repo",
        collected_at="2026-11-20T12:00:00+00:00", repos=[REPO],
        issues=[Issue(repo=REPO, number=1, title="issue 1", state="open",
                      url=f"https://github.com/{REPO}/issues/1", author_association="OWNER",
                      prs=linked)],
        prs=[p for p in PRS if p.number not in numbers], config={},
    )  # fmt: skip


def _state(
    tmp_path: Path,
    requests: list[dict[str, Any]] | None = None,
    linked: list[PullRequest] | None = None,
) -> Path:
    doc: dict[str, Any] = {
        "schema": 14,
        "tiers": [{"n": 1, "title": "Now"}],
        "issues": {"super-fr#1": {"tier": 1}},
        "batches": [
            {"id": "a", "title": "A", "ids": ["super-fr#1"], "wave": 1,
             "events": [{"kind": "dispatch", "at": "2026-11-20T09:00:00Z", "runner": "fake",
                         "handle": "h", "branch": "feat/batch-a"}]},
        ],
    }  # fmt: skip
    if requests:
        doc["queue_requests"] = requests
    (tmp_path / "judgements.yaml").write_text(yaml.safe_dump(doc, sort_keys=False), "utf-8")
    (tmp_path / "facts.json").write_text(json.dumps(_facts(linked).to_json()), "utf-8")
    return tmp_path


def _sid() -> str:
    return scope_id(_scope(REPO, None))


def _run(monkeypatch: Any, tmp_path: Path, client: FakeClient, *args: str) -> tuple[int, str]:
    monkeypatch.setattr(triage_queue_cmd, "make_client", lambda url: client)
    result = CliRunner().invoke(
        app, ["triage", "queue", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, " ".join(result.output.split())


def _requests(tmp_path: Path) -> list[Any]:
    return list(load_judgements(tmp_path / "judgements.yaml").queue_requests)


def test_add_records_one_queue_add_by_the_authenticated_login(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _state(tmp_path)

    code, out = _run(monkeypatch, tmp_path, FakeClient(login="alice"), "add", "--pr", "10")

    assert code == 0, out
    (event,) = _requests(tmp_path)
    assert isinstance(event, QueueAddEvent)
    assert (event.repo, event.scope, event.pr, event.by, event.preapproved) == (
        REPO, _sid(), 10, "alice", False,
    )  # fmt: skip
    assert "added derio-net/super-fr#10" in out and "alice" in out


def test_add_preapproved_records_the_preapproval(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10", "--preapproved")

    assert code == 0, out
    (event,) = _requests(tmp_path)
    assert isinstance(event, QueueAddEvent) and event.preapproved
    assert "preapproved" in out


@pytest.mark.parametrize(
    ("number", "why"),
    [
        (11, "fork"),
        (12, "not an allowed author"),
        (13, "housekeeping"),
        (14, "close-out"),
        (15, "archive"),
        (16, "export"),
        (18, "not the default branch"),
    ],
)
def test_add_refuses_and_writes_nothing(
    monkeypatch: Any, tmp_path: Path, number: int, why: str
) -> None:
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_bytes()

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", str(number))

    assert code == 2 and why in out, out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


@pytest.mark.parametrize("state", ["CLOSED", "MERGED"])
def test_add_refuses_a_pr_that_is_not_open(monkeypatch: Any, tmp_path: Path, state: str) -> None:
    _state(tmp_path)
    client = FakeClient()
    client.views[10]["state"] = state

    code, out = _run(monkeypatch, tmp_path, client, "add", "--pr", "10")

    assert code == 2 and "not open" in out, out
    assert _requests(tmp_path) == []


def test_add_refuses_a_pr_collect_never_read(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    client = FakeClient()
    client.views[99] = dict(client.views[10])

    code, out = _run(monkeypatch, tmp_path, client, "add", "--pr", "99")

    assert code == 2 and "re-collect" in out, out


def test_add_refuses_an_already_added_pr(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")[0] == 0

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")

    assert code == 2 and "already added" in out, out
    assert len(_requests(tmp_path)) == 1


def test_a_batch_pr_is_refused_without_preapproved(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "17")

    assert code == 2 and "batch a" in out and "--preapproved" in out, out
    assert _requests(tmp_path) == []


def test_a_batch_pr_with_preapproved_records_the_preapproval_alone(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _state(tmp_path)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "17", "--preapproved")

    assert code == 0, out
    (event,) = _requests(tmp_path)
    assert isinstance(event, QueueAddEvent) and event.preapproved and event.pr == 17
    assert "batch a" in out


def test_a_batch_pr_known_only_through_its_member_issue_is_preapproved(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """gh#1741: a batch PR whose Closes lines name its members is collected under those
    issues' `prs`, not the unlinked `facts.prs`; its trust is the batch's own verdict."""
    _state(tmp_path, linked=[_pr(17, "feat/batch-a")])

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "17", "--preapproved")

    assert code == 0, out
    (event,) = _requests(tmp_path)
    assert isinstance(event, QueueAddEvent) and event.preapproved and event.pr == 17
    assert "batch a" in out


def test_a_linked_pr_that_is_no_batch_s_is_added(monkeypatch: Any, tmp_path: Path) -> None:
    """A PR known only through an issue's `prs`, on no batch's branch, is trusted on the
    same read as an unlinked one."""
    _state(tmp_path, linked=[_pr(10, "fix/typo")])

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")

    assert code == 0, out
    (event,) = _requests(tmp_path)
    assert isinstance(event, QueueAddEvent) and event.pr == 10


@pytest.mark.parametrize(
    ("pr", "why"),
    [
        (_pr(17, "feat/batch-a", cross=True), "fork"),
        (_pr(17, "feat/batch-a", author="mallory"), "not an allowed author"),
        (_pr(11, "fix/fork", cross=True), "fork"),
        (_pr(12, "fix/stranger", author="mallory"), "not an allowed author"),
    ],
)
def test_a_linked_fork_or_foreign_pr_is_still_refused(
    monkeypatch: Any, tmp_path: Path, pr: PullRequest, why: str
) -> None:
    """Searching the member-linked PRs widens what is READ, never what is trusted: a fork
    or foreign PR on a batch branch is not the batch's, and is refused as itself."""
    _state(tmp_path, linked=[pr])
    before = (tmp_path / "judgements.yaml").read_bytes()

    code, out = _run(
        monkeypatch, tmp_path, FakeClient(), "add", "--pr", str(pr.number), "--preapproved"
    )

    assert code == 2 and why in out, out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_remove_refuses_a_pr_not_added(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "remove", "--pr", "10")

    assert code == 2 and "not added" in out, out


def test_remove_records_queue_remove(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")[0] == 0

    code, out = _run(monkeypatch, tmp_path, FakeClient(login="bob"), "remove", "--pr", "10")

    assert code == 0, out
    _, event = _requests(tmp_path)
    assert isinstance(event, QueueRemoveEvent) and event.by == "bob" and event.pr == 10
    assert "removed derio-net/super-fr#10" in out


def test_remove_of_a_batch_pr_withdraws_the_preapproval(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    assert _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "17", "--preapproved")[0] == 0

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "remove", "--pr", "17")

    assert code == 0 and "preapproval" in out, out


def test_a_state_changed_since_read_exits_2_and_says_to_run_again(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _state(tmp_path)

    def refuse(*a: Any, **k: Any) -> None:
        raise TriageError("judgements.yaml changed since it was read; re-run")

    monkeypatch.setattr(triage_queue_cmd, "save_queue_requests", refuse)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")

    assert code == 2 and "run the command again" in out, out


def test_a_refused_push_restores_the_file_and_exits_2(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_bytes()

    def refuse(*a: Any, **k: Any) -> None:
        raise TriageError("the state ref moved; fetch and retry")

    monkeypatch.setattr(triage_queue_cmd, "push_now", refuse)

    code, out = _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "10")

    assert code == 2 and "run the command again" in out, out
    assert (tmp_path / "judgements.yaml").read_bytes() == before


def test_an_unreadable_default_branch_refuses(monkeypatch: Any, tmp_path: Path) -> None:
    _state(tmp_path)
    client = FakeClient()

    def boom(repo: str) -> str:
        raise GhError("HTTP 502")

    client.repo_default_branch = boom  # type: ignore[method-assign]

    code, out = _run(monkeypatch, tmp_path, client, "add", "--pr", "10")

    assert code == 2 and "HTTP 502" in out, out
    assert _requests(tmp_path) == []


@pytest.mark.parametrize("verb", ["add", "remove"])
def test_a_forge_without_the_operation_refuses_cleanly(  # l-errors-r6
    monkeypatch: Any, tmp_path: Path, verb: str
) -> None:
    from fr.ghclient import UnsupportedForgeOperation

    add = {"kind": "queue_add", "at": "2026-11-20T10:00:00Z", "repo": REPO, "scope": _sid(),
           "pr": 10, "by": "operator"}  # fmt: skip
    requests = [add] if verb == "remove" else None
    _state(tmp_path, requests)
    client = FakeClient()

    def unsupported(*a: Any) -> str:
        raise UnsupportedForgeOperation("repo_default_branch", "gitlab")

    client.repo_default_branch = unsupported  # type: ignore[method-assign]
    client.viewer_login = unsupported  # type: ignore[method-assign]

    code, out = _run(monkeypatch, tmp_path, client, verb, "--pr", "10")

    assert code == 2, out
    assert f"the merge queue needs a GitHub repo ({REPO} is gitlab); nothing written" in out
    assert len(_requests(tmp_path)) == (1 if verb == "remove" else 0)


def test_remove_of_a_batch_pr_records_the_queue_remove_on_disk(
    monkeypatch: Any, tmp_path: Path
) -> None:
    _state(tmp_path)
    assert _run(monkeypatch, tmp_path, FakeClient(), "add", "--pr", "17", "--preapproved")[0] == 0
    assert _run(monkeypatch, tmp_path, FakeClient(), "remove", "--pr", "17")[0] == 0
    added, removed = _requests(tmp_path)
    assert isinstance(added, QueueAddEvent) and added.preapproved
    assert isinstance(removed, QueueRemoveEvent) and removed.pr == 17 and removed.repo == REPO


def test_an_undecodable_default_branch_answer_is_a_gh_error(monkeypatch: Any) -> None:
    from fr import gh as _gh
    from fr.real_ghclient import RealGhClient

    monkeypatch.setattr(_gh, "_run_gh", lambda args: "<html>502</html>")
    with pytest.raises(GhError, match="repos/derio-net/super-fr"):
        RealGhClient().repo_default_branch(REPO)

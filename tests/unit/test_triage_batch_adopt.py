"""`fr triage batch adopt` (spec 2026-10-06-triage-batch-adopt §A, §C, §D; R1–R12).

Nothing here reaches a real forge, runner, clone or isolation record: the
adapter is `FakeGhClient`, the runner a `FakeRunner` that also adopts and
messages, the clone a `FakeCheckout` that also knows its local branches and
worktrees, and `rename_branch` a fake acting on that clone (the real one is
`tests/unit/test_isolation_branch_rename.py`'s).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fr.cli import app
from fr.commands import triage_batch_cmd
from fr.isolation.types import IsolationError
from fr.triage.gitseam import GitError
from fr.triage.model import DispatchEvent, load_judgements
from fr_dispatch.protocols import AdoptTarget
from fr_dispatch.work_item import WorkItem
from typer.testing import CliRunner

from tests.unit.fakes import FakeGhClient
from tests.unit.test_triage_batch_dispatch import (
    ITEM,
    MEMBERS,
    REPO,
    VERSION_CONFIG,
    FakeCheckout,
    FakeRunner,
    _facts,
    _state,
)

OLD = "feat/hand-started"
NEW = "feat/batch-lifecycle"
TAB = "w7:t5"
AGENT = "w7:p5"


class AdoptRunner(FakeRunner):
    """`FakeRunner`, also a `SessionAdopter` and a `SessionMessenger`."""

    def __init__(self) -> None:
        super().__init__()
        self.targets: dict[str, AdoptTarget] = {
            TAB: AdoptTarget(
                tab=TAB, label="super-fr#577 fr-goal", group="super-fr", agent=AGENT, status="idle"
            ),  # fmt: skip
            "w7:t1": AdoptTarget(
                tab="w7:t1",
                label="frank#551 fr-goal finish",
                group="frank",
                agent="w7:p1",
                status="working",
            ),  # fmt: skip
        }
        self.adopted: list[tuple[str, str]] = []
        self.messages: list[tuple[str, str]] = []
        self.fail_adopt: Exception | None = None
        self.fail_message: Exception | None = None

    def describe(self, tab: str) -> AdoptTarget | None:
        self.calls.append("describe")
        return self.targets.get(tab)

    def list_sessions(self) -> list[AdoptTarget]:
        self.calls.append("list_sessions")
        return list(self.targets.values())

    def adopt(self, item: WorkItem, tab: str) -> str:
        self.calls.append("adopt")
        if self.fail_adopt is not None:
            raise self.fail_adopt
        t = self.targets[tab]
        if t.label == item.id:
            return tab  # adopted already: a no-op, as the protocol says
        self.targets[tab] = AdoptTarget(tab=tab, label=item.id, group=t.group,
                                        agent=f"b-{item.id[-9:]}", status=t.status)  # fmt: skip
        self.adopted.append((item.id, tab))
        return tab

    def message(self, item: WorkItem, text: str) -> None:
        self.calls.append("message")
        if self.fail_message is not None:
            raise self.fail_message
        self.messages.append((item.id, text))


class PlainRunner(FakeRunner):
    """A runner that cannot adopt sessions."""


class AdoptCheckout(FakeCheckout):
    """`FakeCheckout`, with local branches, worktrees and a publish that pushes; its
    remote is the fake forge's branch set, so a forge delete shows in `ls-remote`."""

    def __init__(self, path: Path, remote: set[tuple[str, str]]) -> None:
        super().__init__(path)
        self.remote = remote
        self.local: set[str] = {"main", OLD}
        self.worktrees: dict[str, Path] = {OLD: path.parent / "wt"}
        self.published: list[str] = []
        self.fail_publish: Exception | None = None

    def has_branch(self, branch: str) -> bool:
        return branch in self.local

    def worktree_of(self, branch: str) -> Path | None:
        return self.worktrees.get(branch)

    def remote_branch_exists(self, branch: str) -> bool:
        return (REPO, branch) in self.remote

    def publish_branch(self, branch: str) -> None:
        if self.fail_publish is not None:
            raise self.fail_publish
        self.published.append(branch)
        self.remote.add((REPO, branch))


class FakeRename:
    """`rename_branch` over the fake clone: refuses with *refusal*, else moves the
    branch between the clone's local set and its worktrees."""

    def __init__(self, checkout: AdoptCheckout) -> None:
        self.checkout = checkout
        self.calls: list[tuple[str, str, bool]] = []
        self.refusal: str | None = None
        self.fail: Exception | None = None

    def __call__(
        self, repo_root: Path, worktree: Path, old: str, new: str, *, dry_run: bool = False
    ) -> list[str]:
        self.calls.append((old, new, dry_run))
        if self.refusal:
            raise IsolationError(self.refusal)
        local = self.checkout.local
        if old in local and new in local:
            raise IsolationError(f"branch {new} already exists and is not {old} renamed")
        if old not in local and new not in local:
            raise IsolationError(f"no branch {old} (nor {new})")
        steps = [f"git branch -m {old} {new}"] if old in local else []
        if dry_run or not steps:
            return steps
        if self.fail is not None:
            raise self.fail
        local.discard(old)
        local.add(new)
        self.checkout.worktrees[new] = self.checkout.worktrees.pop(old)
        return steps


@pytest.fixture(autouse=True)
def _isolate_models_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGhClient:
    client = FakeGhClient()
    for n in (*MEMBERS, 420):
        client.add_issue(REPO, n)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: client)
    return client


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> AdoptRunner:
    fake = AdoptRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


@pytest.fixture
def checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, gh: FakeGhClient) -> AdoptCheckout:
    fake = AdoptCheckout(tmp_path / "clone", gh.remote_branches)
    gh.remote_branches.add((REPO, OLD))
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    return fake


@pytest.fixture
def rename(monkeypatch: pytest.MonkeyPatch, checkout: AdoptCheckout) -> FakeRename:
    fake = FakeRename(checkout)
    monkeypatch.setattr(triage_batch_cmd, "rename_branch", fake)
    return fake


@pytest.fixture
def old_pr(gh: FakeGhClient) -> dict[str, Any]:
    return gh.add_pr(REPO, 90, title="Lifecycle work", body="Closes #577\n\nnotes",
                     draft=True, head_ref=OLD, base_ref="main")  # fmt: skip


def _adopt(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "adopt", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


def _args(*extra: str, tab: str = TAB, branch: str = OLD) -> list[str]:
    return ["lifecycle", "--tab", tab, "--branch", branch, *extra]


def _writes(gh: FakeGhClient) -> list[str]:
    return [n for n, _ in gh.calls if n not in ("list_issue_comments", "list_prs_by_head",
                                                "pr_view")]  # fmt: skip


def _events(tmp_path: Path) -> list[Any]:
    j = load_judgements(tmp_path / "judgements.yaml")
    return list(j.batches[0].events)


# ------------------------------------------------------------------ dry run (R8)


def test_without_yes_the_full_plan_prints_and_nothing_changes(
    tmp_path: Path, gh: FakeGhClient, runner: AdoptRunner, checkout: AdoptCheckout,
    rename: FakeRename, old_pr: dict[str, Any],
) -> None:  # fmt: skip
    _state(tmp_path)
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _adopt(tmp_path, *_args())
    assert code == 0, out
    for needle in (f"git branch -m {OLD} {NEW}", f"publish {NEW}", "supersede PR #90",
                   f"delete remote branch {OLD}", f"rename tab {TAB}", ITEM,
                   "dispatch event", "fr:in-progress", "nothing written"):  # fmt: skip
        assert needle in out, needle
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert _writes(gh) == []
    assert all(dry for _, _, dry in rename.calls)
    assert checkout.published == [] and checkout.local == {"main", OLD}
    assert runner.adopted == [] and runner.messages == []


# ----------------------------------------------------------------- refusals (R9)


def _refused(tmp_path: Path, gh: FakeGhClient, runner: AdoptRunner, checkout: AdoptCheckout,
             rename: FakeRename, *args: str, match: str) -> None:  # fmt: skip
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _adopt(tmp_path, *args)
    assert code == 2, out
    assert match in out, out
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert _writes(gh) == []
    assert all(dry for _, _, dry in rename.calls)
    assert checkout.published == [] and checkout.local == {"main", OLD}
    assert runner.adopted == [] and runner.messages == []
    assert "dispatch" not in runner.calls


@pytest.fixture
def world(
    tmp_path: Path, gh: FakeGhClient, runner: AdoptRunner, checkout: AdoptCheckout,
    rename: FakeRename,
) -> tuple[Path, FakeGhClient, AdoptRunner, AdoptCheckout, FakeRename]:  # fmt: skip
    _state(tmp_path)
    return tmp_path, gh, runner, checkout, rename


def test_an_unknown_batch_is_refused(world: Any) -> None:
    _refused(*world, "nope", "--tab", TAB, "--branch", OLD, "--yes", match="no batch 'nope'")


def test_a_merged_batch_is_refused(world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(triage_batch_cmd, "derive_batch_stage", lambda b, f: "merged")
    _refused(*world, *_args("--yes"), match="is merged")


def test_a_runner_that_cannot_adopt_is_refused(world: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: PlainRunner())
    _refused(*world, *_args("--yes"), match="cannot adopt")


def test_an_unknown_tab_is_refused(world: Any) -> None:
    _refused(*world, *_args("--yes", tab="w9:t9"), match="no tab w9:t9")


def test_a_tab_labelled_with_another_batchs_item_id_is_refused(world: Any) -> None:
    runner = world[2]
    runner.targets[TAB] = AdoptTarget(tab=TAB, label=f"{REPO}/run/batch-other", group=None,
                                      agent=AGENT, status="idle")  # fmt: skip
    _refused(*world, *_args("--yes"), match="batch-other")


@pytest.mark.parametrize("why", ["no agent", "several agents"])
def test_a_tab_without_exactly_one_agent_is_refused(world: Any, why: str) -> None:
    runner = world[2]
    runner.targets[TAB] = AdoptTarget(tab=TAB, label="x", group=None, agent=None, status="idle")
    _refused(*world, *_args("--yes"), match="exactly one agent")


def test_a_working_agent_is_refused(world: Any) -> None:
    _refused(*world, *_args("--yes", tab="w7:t1"), match="working")


def test_an_unknown_branch_is_refused(world: Any) -> None:
    _refused(*world, *_args("--yes", branch="feat/nope"), match="feat/nope")


@pytest.mark.parametrize(
    "refusal", ["wt is mid-rebase", "wt is mid-merge", "run cursor x.yaml is modified"]
)
def test_a_worktree_rename_refuses_is_refused(world: Any, refusal: str) -> None:
    world[4].refusal = refusal
    _refused(*world, *_args("--yes"), match=refusal)


def test_an_unrelated_local_batch_branch_is_refused(world: Any) -> None:
    checkout = world[3]
    checkout.local.add(NEW)
    before_local = set(checkout.local)
    code, out = _adopt(world[0], *_args("--yes"))
    assert code == 2 and "already exists" in out
    assert checkout.local == before_local and checkout.published == []
    assert _writes(world[1]) == []


def test_an_unrelated_remote_batch_branch_is_refused(world: Any) -> None:
    world[1].remote_branches.add((REPO, NEW))
    _refused(*world, *_args("--yes"), match=f"{NEW} is already on origin")


# --------------------------------------------------------------- happy path (R1–R7, R11)


def test_adopt_with_an_open_pr_moves_everything_in_order(
    world: Any, old_pr: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    tmp_path, gh, runner, checkout, rename = world
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 0, out

    assert [c for c in rename.calls if not c[2]] == [(OLD, NEW, False)]
    assert checkout.published == [NEW]
    (create,) = [kw for n, kw in gh.calls if n == "create_pr"]
    assert create == {"repo": REPO, "head": NEW, "base": "main", "title": "Lifecycle work",
                      "body": "Closes #577\n\nnotes", "draft": True}  # fmt: skip
    new_number = gh.prs[(REPO, 100)]["number"]
    comment = next(kw for n, kw in gh.calls if n == "comment_issue" and kw["number"] == 90)
    assert comment["body"].startswith(f"Superseded by #{new_number}")
    assert "batch lifecycle" in comment["body"]
    assert gh.prs[(REPO, 90)]["state"] == "CLOSED"
    assert (REPO, OLD) not in gh.remote_branches
    order = [n for n, _ in gh.calls if n in ("create_pr", "close_pr", "delete_branch")]
    assert order == ["create_pr", "close_pr", "delete_branch"]
    assert runner.adopted == [(ITEM, TAB)]

    (event,) = _events(tmp_path)
    assert isinstance(event, DispatchEvent)
    assert (event.runner, event.handle, event.branch) == ("fake", TAB, NEW)
    created = datetime.fromisoformat(gh.prs[(REPO, 100)]["created_at"])
    assert event.at <= created

    for n in MEMBERS:
        assert "fr:in-progress" in gh.issues[(REPO, n)].labels
        assert any(ITEM in c["body"] for c in gh.issue_comments[(REPO, n)])
    ((item, text),) = runner.messages
    assert item == ITEM
    for needle in (OLD, NEW, f"#{new_number}", f"git push origin {NEW}"):
        assert needle in text, needle
    assert runner.calls.index("adopt") < runner.calls.index("message")


def test_a_repo_that_reserves_versions_reserves_one_and_says_so(
    tmp_path: Path, gh: FakeGhClient, runner: AdoptRunner, checkout: AdoptCheckout,
    rename: FakeRename,
) -> None:  # fmt: skip
    _state(tmp_path, _facts(config=VERSION_CONFIG))
    checkout.serve(VERSION_CONFIG)
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 0, out
    (event,) = _events(tmp_path)
    assert event.reserved_version == "4.22.0"
    assert "4.22.0" in runner.messages[0][1]


def test_without_a_remote_branch_the_pr_and_remote_steps_are_skipped(world: Any) -> None:
    tmp_path, gh, runner, checkout, rename = world
    gh.remote_branches.discard((REPO, OLD))
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 0, out
    assert checkout.published == []
    assert [n for n, _ in gh.calls if n in ("create_pr", "close_pr", "delete_branch")] == []
    (event,) = _events(tmp_path)
    assert event.branch == NEW
    assert runner.adopted == [(ITEM, TAB)] and len(runner.messages) == 1


def test_a_pushed_branch_without_a_pr_is_published_and_the_old_one_deleted(world: Any) -> None:
    tmp_path, gh, runner, checkout, rename = world
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 0, out
    assert checkout.published == [NEW]
    assert [n for n, _ in gh.calls if n in ("create_pr", "close_pr", "delete_branch")] == [
        "delete_branch"
    ]


# --------------------------------------------------------------- resumable (R10)


def _fail_at(world: Any, step: str, monkeypatch: pytest.MonkeyPatch) -> None:
    tmp_path, gh, runner, checkout, rename = world
    boom = {
        "rename": lambda: setattr(rename, "fail", IsolationError("disk full")),
        "publish": lambda: setattr(checkout, "fail_publish", GitError("push refused")),
        "adopt": lambda: setattr(runner, "fail_adopt", RuntimeError("herdr down")),
        "message": lambda: setattr(runner, "fail_message", RuntimeError("herdr down")),
    }
    if step in boom:
        boom[step]()
        return
    if step == "event":
        real = triage_batch_cmd._save

        def once(*a: Any, **kw: Any) -> None:
            if kw.get("dry_run"):
                return real(*a, **kw)
            monkeypatch.setattr(triage_batch_cmd, "_save", real)
            from fr.triage.errors import TriageError

            raise TriageError("judgements.yaml changed since it was read")

        monkeypatch.setattr(triage_batch_cmd, "_save", once)
        return
    forge = {"create_pr": 0, "comment": 1, "close_pr": 2, "delete_branch": 3, "labels": 5}
    gh.fail_on_mutation = forge[step]


def _heal(world: Any) -> None:
    tmp_path, gh, runner, checkout, rename = world
    rename.fail = None
    checkout.fail_publish = None
    runner.fail_adopt = runner.fail_message = None
    gh.fail_on_mutation = None


@pytest.mark.parametrize(
    "step",
    ["rename", "publish", "create_pr", "comment", "close_pr", "delete_branch", "adopt",
     "event", "labels", "message"],
)  # fmt: skip
def test_a_failure_at_each_step_exits_1_and_the_same_command_finishes_it(
    world: Any, old_pr: dict[str, Any], monkeypatch: pytest.MonkeyPatch, step: str
) -> None:
    tmp_path, gh, runner, checkout, rename = world
    _fail_at(world, step, monkeypatch)
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 1, out
    assert "re-run" in out.lower() and "remain" in out

    _heal(world)
    code, out = _adopt(tmp_path, *_args("--yes"))
    assert code == 0, out

    assert len([c for c in rename.calls if not c[2] and c[0] == OLD]) <= 2
    assert checkout.local == {"main", NEW}
    assert checkout.published.count(NEW) == 1
    creates = [n for n, _ in gh.calls if n == "create_pr"]
    assert creates == ["create_pr"]
    supersedes = [kw for n, kw in gh.calls if n == "comment_issue" and kw["number"] == 90]
    assert len(supersedes) == 1
    assert gh.prs[(REPO, 90)]["state"] == "CLOSED"
    assert [n for n, _ in gh.calls if n == "close_pr"] == ["close_pr"]
    assert [n for n, _ in gh.calls if n == "delete_branch"] == ["delete_branch"]
    assert runner.adopted == [(ITEM, TAB)]
    events = _events(tmp_path)
    assert len(events) == 1 and events[0].branch == NEW
    created = datetime.fromisoformat(gh.prs[(REPO, 100)]["created_at"])
    assert events[0].at <= created
    for n in MEMBERS:
        markers = [c for c in gh.issue_comments[(REPO, n)] if ITEM in c["body"]]
        assert len(markers) == 1
    assert len(runner.messages) == 1


# ------------------------------------------------------------------- --list (R12)


def test_list_prints_every_session_with_its_issue_refs_and_writes_nothing(
    world: Any,
) -> None:
    tmp_path, gh, runner, checkout, rename = world
    before = (tmp_path / "judgements.yaml").read_bytes()
    code, out = _adopt(tmp_path, "--list")
    assert code == 0, out
    lines = out.splitlines()
    tab5 = next(line for line in lines if line.startswith(TAB))
    assert "super-fr" in tab5 and "idle" in tab5 and "super-fr#577" in tab5
    tab1 = next(line for line in lines if line.startswith("w7:t1"))
    assert "working" in tab1 and "frank#551" in tab1
    assert (tmp_path / "judgements.yaml").read_bytes() == before
    assert gh.calls == [] and rename.calls == []
    assert runner.adopted == [] and runner.messages == []


def test_label_refs_parses_repo_issue_refs() -> None:
    from fr.triage.batch import label_refs

    assert label_refs("frank#551 fr-goal finish") == ["frank#551"]
    assert label_refs("5 · frank › claude › frank#813") == ["frank#813"]
    assert label_refs("8 · frank › claude › Merge #820") == []
    assert label_refs("cnc-fr#97 and willikins#422") == ["cnc-fr#97", "willikins#422"]


def test_the_help_says_it_is_not_the_drivers_closeout_adopt() -> None:
    result = CliRunner().invoke(app, ["triage", "batch", "adopt", "--help"])
    assert "close-out" in result.output

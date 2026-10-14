"""`fr triage batch drive` (wave-driver spec §B, §C; Test Plan 2-5, 11).

Nothing here reaches a real forge, runner or clone. `World` is one in-memory
forge: its PRs answer the adapter calls (`make_client`) AND are what each
pass's re-collect writes into facts.json (`recollect`), so a merge on one pass
is a merged PR in the next pass's facts, as on a real forge. The runner is the
dispatch tests' `FakeRunner`; the clone is `DriveCheckout`.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd, triage_kanban_cmd
from fr.gh import GhError
from fr.ghclient import BaseRules, QueueState
from fr.triage import drive_lock
from fr.triage.batch_merge import HeadMovedError, MergeAttempt, MergeStopError
from fr.triage.claims import claims_from_comments, to_issue_claim
from fr.triage.collect import CollectStats
from fr.triage.errors import ForgeError
from fr.triage.gitseam import Checkout
from fr.triage.merge_stops import load_stops
from fr.triage.model import Facts, Issue, PullRequest, TriageConfig, load_judgements
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeRunner

REAL_CI_IS_NONE = triage_batch_cmd.ci_is_none
REAL_RECOLLECT = triage_batch_cmd.recollect

REPO = "derio-net/super-fr"
NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)
DISPATCHED = "2026-10-01T10:00:00Z"
LAUNCH = "{runner: fake, harness: claude, model: claude-opus-5-5}"


# ------------------------------------------------------------------ fakes


class World:
    """The forge: issues and PRs, served to the adapter and to re-collect."""

    def __init__(self) -> None:
        self.issues: dict[int, str] = {}
        self.prs: dict[int, dict[str, Any]] = {}
        self.checks: dict[int, list[dict[str, Any]]] = {}
        self.all_checks: dict[int, dict[str, int]] = {}
        self.merged: list[tuple[int, str, str]] = []
        self.refuse_merge: str | None = None
        self.refuse_ready: str | None = None
        self.refuse_create: str | None = None
        self.create_files: list[str] = []  # what a PR pr_create opens changes
        self.head_of: Any = lambda branch: "sha-created"  # the head a pushed branch has
        self.calls: list[str] = []
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.config: dict[str, Any] | None = None
        self.titles: dict[int, str] = {}
        self.labels_defined: set[str] = {"approved-fr"}
        self.queue_states: dict[int, QueueState] = {}  # PR -> its merge-queue state
        self.stale_in_progress: list[Any] = []  # closed hits collect read (post-merge truth)
        self.skipped: list[Any] = []  # repos collect did not read
        self.hidden: set[int] = set()  # PRs opened after the facts' collect (merge-truth R7)

    # -- world building
    def pr(self, number: int, head_ref: str, closes: list[int], **kw: Any) -> None:
        self.prs[number] = {
            "state": "OPEN",
            "draft": False,
            "head_oid": f"sha-{number}",
            "head_ref": head_ref,
            "closes": closes,
            "files": [],
            "created_at": "2026-10-01T11:00:00+00:00",
            "merged_at": None,
            "author": "operator",
            "cross_repo": False,
            # The operator's approval (merge-train-safety §A): on unless a test says not.
            "labels": ["approved-fr"],
            **kw,
        }

    def facts(self) -> Facts:
        prs = {n: self._pr(n) for n in self.prs}
        seen = {n: p for n, p in self.prs.items() if n not in self.hidden}
        linked = {i: [prs[n] for n, p in seen.items() if i in p["closes"]] for i in self.issues}
        return Facts(
            schema=3,
            scope="derio-net--super-fr",
            kind="repo",
            collected_at=NOW.isoformat(),
            repos=[REPO],
            issues=[
                Issue(
                    repo=REPO,
                    number=i,
                    title=self.titles.get(i, f"issue {i}"),
                    state=s,  # type: ignore[arg-type]
                    url=f"https://github.com/{REPO}/issues/{i}",
                    prs=linked[i],
                    claims=self._claims(i) if s == "open" else [],
                )
                for i, s in self.issues.items()
            ],  # fmt: skip
            prs=[prs[n] for n, p in seen.items() if not p["closes"] and p["state"] == "OPEN"],
            config={REPO: TriageConfig.model_validate(self.config)} if self.config else {},
            stale_in_progress=self.stale_in_progress,
            skipped=self.skipped,
            viewer="operator",
        )

    def _claims(self, number: int) -> list[Any]:
        """The un-released markers in the issue's comments, as collect records them."""
        found = claims_from_comments(self.comments.get(number, []), {"operator"})
        return [to_issue_claim(c) for c in found]

    def _pr(self, n: int) -> PullRequest:
        p = self.prs[n]
        return PullRequest(
            repo=REPO,
            number=n,
            title=p["head_ref"],
            state=p["state"],
            is_draft=p["draft"],
            merged_at=p["merged_at"],
            created_at=p["created_at"],
            url=f"https://github.com/{REPO}/pull/{n}",
            head_ref=p["head_ref"],
            head_oid=p["head_oid"] if p["state"] == "OPEN" else "",
            files=p["files"] if p["state"] == "OPEN" else [],
            checks=self.all_checks.get(n, {"pass": 1, "fail": 0, "pending": 0}),
            author=p["author"],
            cross_repo=p["cross_repo"],
            labels=list(p["labels"]) if p["state"] == "OPEN" else None,
        )

    # -- the GhClient adapter
    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(f"pr_view {number}")
        p = self.prs[number]
        view = {k: p[k] for k in ("state", "draft", "head_oid", "head_ref")}
        merge = p.get("merge_commit", f"merge-{number}")
        return {**view, "base_ref": p.get("base", "main"), "merge_commit": merge,
                "labels": list(p["labels"]),
                "mergeable": p.get("mergeable", "MERGEABLE")}  # fmt: skip

    def pr_ready(self, repo: str, number: int) -> None:
        self.calls.append(f"pr_ready {number}")
        if self.refuse_ready:
            raise GhError(self.refuse_ready, returncode=1)
        self.prs[number]["draft"] = False

    def label_exists(self, repo: str, name: str) -> bool:
        self.calls.append(f"label_exists {name}")
        return name in self.labels_defined

    def base_rules(self, repo: str, branch: str) -> BaseRules:
        self.calls.append("base_rules")
        return getattr(self, "rules", BaseRules())

    def pr_enqueue(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        self.calls.append(f"pr_enqueue {number}")
        if getattr(self, "refuse_enqueue", None):
            raise GhError(self.refuse_enqueue, returncode=1)  # type: ignore[attr-defined]
        if self.prs[number]["draft"]:  # GitHub refuses to enqueue a draft
            raise GhError("GraphQL: Pull request is in draft state", returncode=1)
        assert self.prs[number]["head_oid"] == head_sha
        self.enqueued: list[tuple[int, str, str]] = [
            *getattr(self, "enqueued", []),
            (number, head_sha, method),
        ]
        self.queue_states[number] = QueueState(in_queue=True, auto_merge=True)

    def pr_dequeue(self, repo: str, number: int) -> None:
        self.calls.append(f"pr_dequeue {number}")
        self.dequeued: list[int] = [*getattr(self, "dequeued", []), number]
        self.queue_states[number] = QueueState(in_queue=False, auto_merge=False)

    def pr_queue_state(self, repo: str, number: int) -> QueueState:
        self.calls.append(f"pr_queue_state {number}")
        return self.queue_states.get(number, QueueState(in_queue=False, auto_merge=False))

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.checks.get(number, [{"name": "test", "bucket": "pass"}]))

    def pr_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        """Every check, live: the same counts the collect reports for the PR."""
        counts = self.all_checks.get(number, {"pass": 1, "fail": 0, "pending": 0})
        return [
            {"name": f"{bucket}-{i}", "bucket": bucket}
            for bucket in ("pass", "fail", "pending")
            for i in range(counts.get(bucket, 0))
        ]

    def pr_merge(self, repo: str, number: int, *, head_sha: str, method: str) -> None:
        self.calls.append(f"pr_merge {number}")
        if self.refuse_merge:
            raise GhError(self.refuse_merge, returncode=1)
        assert self.prs[number]["head_oid"] == head_sha
        self.merged.append((number, head_sha, method))
        self.prs[number].update(state="MERGED", merged_at=NOW.isoformat())
        for i in self.prs[number]["closes"]:
            self.issues[i] = "closed"

    def repo_merge_methods(self, repo: str) -> dict[str, Any]:
        return {"default": "squash", "allowed": ["squash"]}

    def list_prs_by_head(self, repo: str, branch: str) -> list[dict[str, Any]]:
        return [
            {"number": n, "state": p["state"], "isDraft": p["draft"], "headRefName": branch,
             "headRefOid": p["head_oid"], "files": [{"path": f} for f in p["files"]],
             "author": {"login": p["author"]}, "isCrossRepository": p["cross_repo"]}
            for n, p in self.prs.items() if p["head_ref"] == branch
        ]  # fmt: skip

    def pr_create(self, repo: str, *, head: str, base: str, title: str, body: str) -> int:
        self.calls.append(f"pr_create {head} -> {base}")
        if self.refuse_create:
            raise GhError(self.refuse_create, returncode=1)
        number = max([*self.prs, 199]) + 1
        self.pr(number, head, [], head_oid=self.head_of(head), files=list(self.create_files))
        return number

    def closing_ref(self, repo: str, number: int) -> str:
        return f"Closes {repo}#{number}"

    def list_issue_comments(self, repo: str, number: int) -> list[dict[str, Any]]:
        return [dict(c) for c in self.comments.get(number, [])]

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        self.calls.append("ensure_labels")
        self.labels_defined.update(getattr(x, "name", x) for x in labels)

    def edit_issue_labels(self, repo: str, number: int, **kw: Any) -> None:
        self.calls.append(f"label {number}")
        if number in self.prs:
            gone = kw.get("remove", frozenset())
            self.prs[number]["labels"] = [x for x in self.prs[number]["labels"] if x not in gone]

    def view_issue(self, repo: str, number: int) -> dict[str, Any]:
        # a dispatched member carries both labels; an unlabelling release reads them first
        state = "OPEN" if self.issues.get(number) == "open" else "CLOSED"
        return {"state": state, "labels": ["fr:claimed", "fr:in-progress"]}

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        # an id and a time, like the gh adapter's, and authored as the facts' viewer: a
        # dispatch claims its members first (triage-claims R3, R17)
        cid = 1 + sum(len(c) for c in self.comments.values())
        self.comments.setdefault(number, []).append(
            {"author": "operator", "body": body, "created_at": NOW.isoformat(), "id": cid}
        )

    def edit_issue_comment(self, repo: str, comment_id: int, body: str) -> None:
        for comments in self.comments.values():
            for c in comments:
                if c.get("id") == comment_id:
                    c["body"] = body


def test_closeout_payload_uses_primary_checkout(tmp_path, world, checkout, runner, monkeypatch):
    primary = tmp_path / "primary"
    monkeypatch.setattr(checkout, "main_worktree", lambda: primary)
    _merged(world, tmp_path)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert runner.dispatched[0].payload["checkout"] == str(primary)


def test_conflict_payload_uses_primary_checkout(
    tmp_path, world, checkout, runner, train, monkeypatch
):
    primary = tmp_path / "primary"
    monkeypatch.setattr(checkout, "main_worktree", lambda: primary)
    _one_conflicted(world, tmp_path)
    train.script[101] = _conflict_error()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert runner.dispatched, out
    assert runner.dispatched[0].payload["checkout"] == str(primary)


class DriveCheckout:
    """The clone: origin is REPO, on main, fast-forwardable."""

    def __init__(self, path: Path, world: World) -> None:
        self.path = path
        self.world = world
        self.released = False
        self.behind: set[str] = set()
        self.commands: list[list[str]] = []
        self.command_fails: str | None = None
        self.forwarded = 0
        self.switched: list[bool] = []  # each fast-forward's `switch`
        self.files: dict[tuple[str, str], str] = {}
        self.release_probes: list[str] = []
        self.added: dict[str, tuple[str, ...]] = {}  # merge commit -> paths it added
        self.live: set[str] = set()  # paths still on origin/main

    def origin_repo(self) -> str | None:
        return REPO

    def main_worktree(self) -> Path:
        return self.path

    def default_branch(self) -> str:
        return "main"

    def fetch(self) -> None:
        pass

    def show(self, ref: str, file: str) -> str | None:
        if file == ".fr/triage.yaml":
            return yaml.safe_dump(self.world.config) if self.world.config else None
        return self.files.get((ref, file))

    def remote_branch_exists(self, branch: str) -> bool:
        return False

    def is_ancestor(self, ancestor: str, descendant: str) -> bool:
        return descendant not in self.behind

    def commits_behind(
        self, head: str, ref: str
    ) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
        return (("code", (("M", "packages/x.py"),)),)

    def changed_paths(self, ref: str, head: str) -> frozenset[str]:
        return frozenset()

    def add_worktree(self, where: Path, ref: str) -> Any:
        return _Worktree(self, where)

    def remove_worktree(self, where: Path) -> None:
        pass

    def rev_parse(self, ref: str) -> str:
        return f"{ref}@fetched"

    def fast_forward(self, *, switch: bool = False) -> None:
        self.forwarded += 1
        self.switched.append(switch)

    def released_after(self, merge_commit: str) -> bool:
        self.release_probes.append(merge_commit)
        return self.released

    def added_paths(self, merge_commit: str) -> tuple[str, ...]:
        return self.added.get(merge_commit, ())

    def exists_at(self, ref: str, path: str) -> bool:
        return path in self.live

    def snapshot_paths(self, ref: str, paths: tuple[str, ...], dest: Path) -> None:
        """origin/<default>'s copy of *paths*: what `ci none` is read from."""
        for (at, file), text in self.files.items():
            if at == ref and any(file == p or file.startswith(p + "/") for p in paths):
                (dest / file).parent.mkdir(parents=True, exist_ok=True)
                (dest / file).write_text(text)

    def run_command(self, argv: list[str]) -> str:
        self.commands.append(list(argv))
        if self.command_fails:
            from fr.triage.gitseam import GitError

            raise GitError(self.command_fails)
        return ""


class _Worktree:
    """merge's scratch worktree: an update push moves the PR head."""

    def __init__(self, checkout: DriveCheckout, path: Path) -> None:
        self.checkout, self.path = checkout, path

    def merge(self, ref: str) -> list[str]:
        return []

    def commit_all(self, message: str, version_files: list[str]) -> str | None:
        return "sha-updated"

    def push(self, branch: str) -> None:
        for p in self.checkout.world.prs.values():
            if p["head_ref"] == branch:
                self.checkout.behind.discard(p["head_oid"])
                p["head_oid"] = "sha-updated"


# ---------------------------------------------------------------- fixtures
# Registered by name; the functions are named apart so another module can import
# them (test_triage_batch_drive_disruption.py) without F811 on its parameters.


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: False)


@pytest.fixture(name="world")
def world_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> World:
    w = World()
    passes: list[int] = []

    def _recollect(scope: Any, target: Path, **_: Any) -> None:
        passes.append(1)
        (target / "facts.json").write_text(json.dumps(w.facts().to_json()), "utf-8")

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: w)
    w.passes = passes  # type: ignore[attr-defined]
    return w


@pytest.fixture(name="checkout")
def checkout_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: World
) -> DriveCheckout:
    fake = DriveCheckout(tmp_path / "clone", world)
    fake.path.mkdir()
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    return fake


@pytest.fixture(name="runner")
def runner_fixture(monkeypatch: pytest.MonkeyPatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


@pytest.fixture(name="sleeps")
def sleeps_fixture(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    out: list[float] = []

    def _sleep(seconds: float) -> None:
        out.append(seconds)
        if len(out) > 10:
            raise AssertionError("the loop did not end")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _sleep)
    return out


def _batch(bid: str, n: int, *, wave: int = 1, events: str = "", **kw: Any) -> str:
    extra = "".join(f"    {k}: {v}\n" for k, v in kw.items())
    ev = f"    events:\n{events}" if events else ""
    return (
        f'  - id: {bid}\n    title: {bid}\n    ids: ["super-fr#{n}"]\n    wave: {wave}\n'
        f"    launch: {LAUNCH}\n{extra}{ev}"
    )


def _dispatch_event(bid: str, prefix: str = "feat") -> str:
    return (
        f"      - {{kind: dispatch, at: {DISPATCHED}, runner: fake, handle: h, "
        f"branch: {prefix}/batch-{bid}}}\n"
    )


def _state(tmp_path: Path, world: World, *batches: str) -> Path:
    issues = "".join(f"  super-fr#{n}: {{tier: 1}}\n" for n in world.issues)
    (tmp_path / "judgements.yaml").write_text(
        "schema: 3\ntiers:\n  - {n: 1, title: Now}\nissues:\n" + issues
        + ("batches:\n" + "".join(batches) if batches else ""),
        encoding="utf-8",
    )  # fmt: skip
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    return tmp_path


def _drive(tmp_path: Path, *args: str) -> tuple[int, str]:
    result = CliRunner().invoke(
        app, ["triage", "batch", "drive", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )
    return result.exit_code, result.output


def _summary(out: str) -> str:
    """The pass's last line before any closing `warning:` (the single-pass notice)."""
    return [x for x in out.rstrip().splitlines() if not x.startswith("warning:")][-1]


def _lines(out: str, kind: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith(f"{kind} ")]


def _events(tmp_path: Path, bid: str) -> list[str]:
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)
    return [e.kind for e in batch.events]


def _proposed(world: World, tmp_path: Path, n: int = 2) -> Path:
    ids = [f"b{i}" for i in range(1, n + 1)]
    for i in range(1, n + 1):
        world.issues[i] = "open"
    return _state(tmp_path, world, *(_batch(b, i) for i, b in enumerate(ids, 1)))


# ------------------------------------------------- plan mode and passes (R2)


def test_without_yes_a_pass_prints_its_plan_and_writes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, sleeps: list[float]
) -> None:
    _proposed(world, tmp_path)
    before = (tmp_path / "judgements.yaml").read_text()
    code, out = _drive(tmp_path)  # loop mode, no --yes: one pass, then exit
    assert code == 0, out
    assert _lines(out, "dispatch") == ["dispatch b1: wave 1", "dispatch b2: wave 1"]
    assert "in flight 2, merged 0, pending 0, closing 0" in out
    assert "re-run with --yes" in out
    assert runner.dispatched == [] and sleeps == []
    assert (tmp_path / "judgements.yaml").read_text() == before
    assert world.passes == [1]  # type: ignore[attr-defined]


def test_once_yes_dispatches_up_to_the_cap_with_one_line_each(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 3)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass", "--max-inflight", "2")
    assert code == 0, out
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b1", f"{REPO}/run/batch-b2"]
    assert _lines(out, "dispatch") == [
        f"dispatch b1: dispatched to fake as {REPO}/run/batch-b1",
        f"dispatch b2: dispatched to fake as {REPO}/run/batch-b2",
    ]
    assert "brief:" not in out  # dispatch_batch's own plan is not echoed
    assert _events(tmp_path, "b1") == ["dispatch"]
    assert _events(tmp_path, "b3") == []
    assert _summary(out) == "in flight 2, merged 0, pending 1, closing 0"


def test_a_driven_dispatch_carries_its_waves_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    (item,) = runner.dispatched
    assert item.payload["group"] == "drive-wave-1"


def test_workspace_prefix_renames_the_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass", "--workspace-prefix", "bugfix")
    assert code == 0, out
    assert runner.dispatched[0].payload["group"] == "bugfix-wave-1"


def test_the_closeout_item_carries_its_batchs_current_wave_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    _cursor(checkout, "2026-10-01-b1", "feat/batch-b1")
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes", "--workspace-prefix", "bugfix")
    assert code == 0, out
    (item,) = runner.dispatched
    assert item.payload["kind"] == "closeout"
    assert item.payload["group"] == "bugfix-wave-1"


def test_the_closeout_probe_carries_the_same_group_as_the_closeout(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    # Review p1-r1: a group-less probe is what herdr's preflight still refuses with
    # HERDR_WORKSPACE_ID unset, so the drive would exit 2 at the close-out it may start.
    _merged(world, tmp_path)
    _cursor(checkout, "2026-10-01-b1", "feat/batch-b1")
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes", "--workspace-prefix", "bugfix")
    assert code == 0, out
    probes = [i for items in runner.preflighted for i in items]
    assert probes and all(i.payload.get("group") == "bugfix-wave-1" for i in probes)


def test_a_driven_batch_with_no_wave_opens_in_the_no_wave_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    _state(tmp_path, world, _batch("b1", 1).replace("wave: 1", "wave: null"))
    code, out = _drive(
        tmp_path, "--once", "--yes", "--single-pass", "b1", "--workspace-prefix", "bugfix"
    )
    assert code == 0, out
    assert runner.dispatched[0].payload["group"] == "bugfix-no-wave"


@pytest.mark.parametrize("prefix", ["", "  "])
def test_a_blank_workspace_prefix_is_refused(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, prefix: str
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--workspace-prefix", prefix)
    assert code == 2 and "prefix" in out
    assert runner.dispatched == []


def test_the_same_action_reads_the_same_line_in_once_and_loop_mode(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, sleeps: list[float]
) -> None:
    _proposed(world, tmp_path, 1)
    _, once = _drive(tmp_path, "--once")
    _, loop = _drive(tmp_path)
    assert _lines(once, "dispatch") == _lines(loop, "dispatch") == ["dispatch b1: wave 1"]


def test_only_batches_with_a_wave_are_driven_by_default(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues.update({1: "open", 2: "open"})
    loose = '  - id: loose\n    title: loose\n    ids: ["super-fr#2"]\n'
    _state(tmp_path, world, _batch("waved", 1), loose)
    _, out = _drive(tmp_path, "--once")
    assert _lines(out, "dispatch") == ["dispatch waved: wave 1"]
    _, named = _drive(tmp_path, "--once", "loose")
    assert _lines(named, "dispatch") == ["dispatch loose: wave -"]


# ------------------------------------------------------------- exit codes (R7)


def test_nothing_to_do_while_work_remains_exits_3(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True, labels=[])  # an unapproved draft
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert world.merged == []
    assert "in flight 1" in out


def test_everything_done_exits_0(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    _state(tmp_path, world)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "in flight 0, merged 0, pending 0, closing 0" in out


def test_a_failed_forge_write_exits_1(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1])
    world.refuse_merge = "protected branch"
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1, out
    assert "protected branch" in out


def test_a_runner_preflight_refusal_exits_2_and_is_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 2)
    runner.refusal = "not inside a herdr session"
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 2
    assert out.count("not inside a herdr session") == 1
    assert runner.dispatched == []


# ------------------------------------------------------------- merge (R4)


def _pr_open(world: World, tmp_path: Path, **kw: Any) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], **kw)
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))


def test_a_ready_green_pr_is_merged_without_waiting(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]
    assert _lines(out, "merge") == ["merge b1: merged PR #101 at sha-101"]


@pytest.mark.parametrize(
    "setup",
    [
        lambda w: w.prs[101].update(draft=True, labels=[]),  # an approved draft merges
        lambda w: w.checks.update({101: [{"name": "test", "bucket": "pending"}]}),
        lambda w: (
            w.all_checks.update({101: {"pass": 0, "fail": 0, "pending": 2}})
            or w.checks.update({101: []})
        ),
    ],
    ids=["draft", "pending-required", "pending-all"],
)
def test_a_pr_that_is_not_ready_and_green_is_left(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, setup: Any
) -> None:
    _pr_open(world, tmp_path)
    setup(world)
    code, _ = _drive(tmp_path, "--once", "--yes")
    assert code == 3
    assert world.merged == []
    assert not any(c.startswith(("ready", "approve", "pr_ready")) for c in world.calls)


def test_a_ci_none_repo_merges_on_non_draft_alone(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _pr_open(world, tmp_path)
    world.checks[101] = []
    world.all_checks[101] = {"pass": 0, "fail": 0, "pending": 3}
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: True)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]


def test_a_failing_check_warns_once_per_head_across_loop_passes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _pr_open(world, tmp_path)
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]
    sleeps: list[float] = []

    def _fix_after_two(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            world.checks[101] = [{"name": "lint", "bucket": "pass"}]
        assert len(sleeps) < 10, "the loop did not end"

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _fix_after_two)
    world.config = None
    code, out = _drive(tmp_path, "--yes", "--interval", "5")
    # said once: the plain runner has no session to message, so the recovery decides
    # needs-you once at that head (merge-train-safety §C) and the later pass is quiet
    (line,) = _lines(out, "warn")
    assert line.startswith("warn b1: PR #101 CI failing at sha-101: lint; ")
    assert world.merged == [(101, "sha-101", "squash")]
    assert sleeps[:2] == [5, 5]


def test_a_ci_none_declared_mid_drive_reaches_the_merge_too(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#880 review: the merge context outlives a pass, so the `ci none` its R4
    reads is the one each pass reads, not the one the first merge attempt saw."""
    _pr_open(world, tmp_path)
    world.refuse_merge = "protected"  # pass 1 builds the merge context, and stops
    sleeps: list[float] = []

    def _declare_ci_none(seconds: float) -> None:
        sleeps.append(seconds)
        world.refuse_merge = None
        world.checks[101] = []
        world.all_checks[101] = {"pass": 0, "fail": 0, "pending": 0}
        monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: True)
        assert len(sleeps) < 5, "the loop did not end"

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _declare_ci_none)
    world.config = None
    code, out = _drive(tmp_path, "--yes", "--interval", "5")
    assert world.merged == [(101, "sha-101", "squash")], out


@pytest.mark.parametrize(
    ("kw", "reason"),
    [
        (dict(cross_repo=True), "opened from a fork"),
        (dict(author="mallory"), "by mallory, not an allowed author"),
    ],
    ids=["fork", "foreign-author"],
)
def test_a_foreign_pr_on_the_batch_branch_is_never_merged_and_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, kw: dict[str, Any], reason: str,
) -> None:  # fmt: skip
    """gh#936: green, not a draft, on `feat/batch-b1` after the dispatch — and still
    never merged, because a branch name is not an identity."""
    _pr_open(world, tmp_path, **kw)
    sleeps: list[float] = []

    def _stop_after_three(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _stop_after_three)
    result = _drive_named(tmp_path, "--yes", "--interval", "5")
    assert isinstance(result.exception, _StopError), result.output
    assert len(world.passes) >= 3  # type: ignore[attr-defined]
    assert world.merged == [] and not [c for c in world.calls if c.startswith("pr_merge")]
    assert _lines(result.output, "foreign") == [
        f"foreign b1: PR #101 on feat/batch-b1 is not this batch's: {reason}; it is never merged"
    ]


def test_an_allow_listed_author_in_triage_yaml_is_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = {"pr_authors": ["fr-bot"]}
    _pr_open(world, tmp_path, author="fr-bot")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]


def test_an_untrusted_archive_pr_is_never_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"], cross_repo=True)
    world.pr(202, "chore/closeout-feat-batch-b1", [], author="mallory")
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    _drive(tmp_path, "--once", "--yes")
    assert world.merged == []


def test_a_pr_behind_its_base_is_updated_then_merged_on_a_later_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    checkout.behind.add("sha-101")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == []
    assert _lines(out, "merge") == [
        "merge b1: updated PR #101 to sha-updated; it merges on a later pass"
    ]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [(101, "sha-updated", "squash")]


# ------------------------------------------------- close-out and post_merge


def _merged(world: World, tmp_path: Path, *, events: str = "", skill: str = "goal") -> None:
    prefix = "fix" if skill == "debug" else "feat"
    world.issues[1] = "closed"
    world.pr(101, f"{prefix}/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    extra = {"skill": skill} if skill != "goal" else {}
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1", prefix) + events, **extra))


def _cursor(checkout: DriveCheckout, run: str, branch: str) -> None:
    runs = checkout.path / "docs" / "superpowers" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / f"{run}.yaml").write_text(
        yaml.safe_dump({"run": run, "branch": branch,
                        "steps": {"plan": {"emitted": {"plan": f"docs/superpowers/plans/{run}"}}}})
    )  # fmt: skip


def test_no_closeout_before_the_release_commit(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert runner.dispatched == []


def test_post_merge_then_one_closeout_through_the_runner(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    _cursor(checkout, "2026-10-01-b1", "feat/batch-b1")
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert checkout.forwarded == 1
    assert checkout.commands == [["./scripts/install.sh"]]
    (item,) = runner.dispatched
    assert item.id == f"{REPO}/run/closeout-b1"
    assert item.unit == "run" and item.payload["kind"] == "closeout"
    assert "fr pickup --run 2026-10-01-b1" in item.payload["brief"]
    assert item.payload["model"] == "claude-opus-5-5"
    assert item.payload["checkout"] == str(checkout.path)
    assert _events(tmp_path, "b1") == ["dispatch", "post_merge", "closeout"]
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    closeout = batch.events[-1]
    assert closeout.run == "2026-10-01-b1"  # type: ignore[union-attr]
    assert closeout.archive == "chore/archive-2026-10-01-b1"  # type: ignore[union-attr]
    assert _lines(out, "closeout") == [
        f"closeout b1: started {REPO}/run/closeout-b1 (fr pickup --run 2026-10-01-b1)"
    ]
    # a second pass starts nothing
    code, _ = _drive(tmp_path, "--once", "--yes")
    assert len(runner.dispatched) == 1 and checkout.commands == [["./scripts/install.sh"]]


def test_batches_closed_out_by_hand_are_not_closed_out_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Debug 2026-10-03: every batch merged before 5.2.0 has no close-out event, and
    an unnamed drive on a repo with no waves (so every batch is selected) planned a
    close-out for each — 50 on this repo. One whose run is archived is done; one
    whose run is still live is owed, wave or no wave."""
    world.issues.update({1: "closed", 2: "closed"})
    for n, bid in ((101, "done"), (102, "owed")):
        world.pr(n, f"feat/batch-{bid}", [n - 100], state="MERGED",
                 merged_at=(NOW - timedelta(days=3)).isoformat(), merge_commit=f"m{n}")  # fmt: skip
        checkout.added[f"m{n}"] = (f"docs/superpowers/journals/debug/{bid}.md",)
    checkout.live.add("docs/superpowers/journals/debug/owed.md")
    no_wave = [
        _batch(bid, n, events=_dispatch_event(bid)).replace("    wave: 1\n", "")
        for n, bid in ((1, "done"), (2, "owed"))
    ]
    _state(tmp_path, world, *no_wave)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/closeout-owed"]
    assert "m101" not in checkout.release_probes  # an archived batch probes no release


def test_a_named_batch_already_archived_by_hand_is_not_closed_out(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    journal = "docs/superpowers/journals/debug/2026-10-01-b1.md"
    _merged(world, tmp_path)
    world.prs[101]["merge_commit"] = "m101"
    checkout.added["m101"] = (journal, "packages/x.py")
    checkout.released = True
    checkout.live.add(journal)  # not archived yet: the close-out is owed
    code, out = _drive(tmp_path, "--once", "b1")
    assert _lines(out, "closeout") == [f"closeout b1: start {REPO}/run/closeout-b1"], out
    checkout.live.discard(journal)  # archived by hand
    code, out = _drive(tmp_path, "--once", "--yes", "b1")
    assert code == 0, out
    assert _lines(out, "closeout") == [] and runner.dispatched == []
    assert "closing 0" in out


def test_an_archived_batch_is_recorded_once_and_never_probed_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#900, gh#899: the first pass that finds a batch archived records a close-out
    event, so later passes read nothing for it, `batch list` shows it archived and
    the board drops its 'post_merge not done' row."""
    from fr.triage import views
    from fr.triage.batch import closeout_state

    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    world.prs[101].update(merge_commit="m101", merged_at=(NOW - timedelta(days=1)).isoformat())
    checkout.added["m101"] = ("docs/superpowers/journals/debug/2026-10-01-b1.md",)
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    before = views.needs_you(world.facts(), load_judgements(tmp_path / "judgements.yaml"))
    assert [n.kind for n in before] == ["post-merge"]  # the stale row, as filed
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert runner.dispatched == [] and checkout.commands == []
    assert _lines(out, "adopt") == ["adopt b1: archived on the default branch already"]
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    event = batch.events[-1]
    assert (event.kind, event.runner, event.archived) == ("closeout", "hand", 0)  # type: ignore[union-attr]
    assert closeout_state(batch) == "archived"
    assert views.needs_you(world.facts(), load_judgements(tmp_path / "judgements.yaml")) == []
    world.calls.clear()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "pr_view 101" not in world.calls and checkout.release_probes == []
    assert _lines(out, "adopt") == [] and _events(tmp_path, "b1") == [
        "dispatch",
        "closeout",
        "claims_released",
    ]


def test_a_hand_opened_closeout_pr_is_adopted_then_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#912: #895 was a close-out started by hand and left open. Naming its batch
    must not start a second close-out: the driver records the open PR as the
    close-out under way, and the archive step then merges it."""
    journal = "docs/superpowers/journals/debug/2026-10-01-b1.md"
    _merged(world, tmp_path)
    world.prs[101]["merge_commit"] = "m101"
    checkout.added["m101"] = (journal,)
    checkout.live.add(journal)  # the archive PR has not merged: still live on main
    checkout.released = True
    world.pr(895, "chore/closeout-feat-batch-b1", [], files=[journal])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes", "b1")
    assert runner.dispatched == [], out
    assert _lines(out, "adopt") == [
        "adopt b1: close-out PR #895 (chore/closeout-feat-batch-b1) is open"
    ]
    event = load_judgements(tmp_path / "judgements.yaml").batches[0].events[-1]
    assert (event.kind, event.runner, event.handle, event.archive, event.archived) == (  # type: ignore[union-attr]
        "closeout",
        "hand",
        "PR #895",
        "chore/closeout-feat-batch-b1",
        None,
    )
    code, out = _drive(tmp_path, "--once", "--yes", "b1")
    assert code == 0, out
    assert runner.dispatched == [] and [m[0] for m in world.merged] == [895]
    event = load_judgements(tmp_path / "judgements.yaml").batches[0].events[-1]
    assert event.archived == 895  # type: ignore[union-attr]


def test_a_merged_hand_opened_closeout_pr_finishes_the_batch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """A debug batch whose merge added no run artifact has no archived evidence in
    git; its merged hand close-out PR is the evidence."""
    _merged(world, tmp_path)
    checkout.released = True
    world.pr(895, "chore/closeout-feat-batch-b1", [], state="MERGED",
             merged_at=NOW.isoformat())  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert runner.dispatched == []
    assert _lines(out, "adopt") == ["adopt b1: close-out PR #895 merged"]
    event = load_judgements(tmp_path / "judgements.yaml").batches[0].events[-1]
    assert event.archived == 895  # type: ignore[union-attr]


def test_a_closed_hand_closeout_pr_leaves_the_closeout_owed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """An abandoned (closed, unmerged) close-out PR is no evidence of anything."""
    _merged(world, tmp_path)
    checkout.released = True
    world.pr(895, "chore/closeout-feat-batch-b1", [], state="CLOSED")
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert _lines(out, "adopt") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/closeout-b1"]


def test_a_forks_pr_on_the_closeout_head_is_never_adopted(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Batch branch names are predictable and `gh pr list --head` matches a fork's
    branch of the same name; an adopted open PR is merged by the archive step, so a
    fork's PR must never be adopted. The close-out stays owed and starts as usual."""
    _merged(world, tmp_path)
    checkout.released = True
    world.pr(895, "chore/closeout-feat-batch-b1", [], cross_repo=True)
    world.pr(896, "chore/closeout-feat-batch-b1", [], state="MERGED", cross_repo=True,
             merged_at=NOW.isoformat())  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert _lines(out, "adopt") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/closeout-b1"]


def test_plan_mode_reports_an_adoption_and_writes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    world.pr(895, "chore/closeout-feat-batch-b1", [])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once")
    assert _lines(out, "adopt") == [
        "adopt b1: close-out PR #895 (chore/closeout-feat-batch-b1) is open"
    ], out
    assert _events(tmp_path, "b1") == ["dispatch"]


def test_a_debug_batch_is_closed_out_with_branch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path, skill="debug")
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    (item,) = runner.dispatched
    assert "fr pickup --branch fix/batch-b1" in item.payload["brief"]
    assert checkout.commands == []  # no post_merge configured: nothing runs


def test_the_ten_minute_fallback_starts_the_closeout(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _merged(world, tmp_path)
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW + timedelta(minutes=8))
    code, _ = _drive(tmp_path, "--once", "--yes")
    assert code == 0 and len(runner.dispatched) == 1


def test_a_failing_post_merge_holds_the_closeout_every_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path)
    checkout.released = True
    checkout.command_fails = "install.sh: exit 1"
    for _ in range(2):
        code, out = _drive(tmp_path, "--once", "--yes")
        assert code == 3, out
        assert _lines(out, "closeout") == [
            "closeout b1: post_merge failed, close-out held: install.sh: exit 1"
        ]
    assert runner.dispatched == []
    assert _events(tmp_path, "b1") == ["dispatch"]


def test_a_kill_after_post_merge_does_not_rerun_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = {"post_merge": ["./scripts/install.sh"]}
    _merged(world, tmp_path, events="      - {kind: post_merge, at: 2026-10-02T11:59:00Z}\n")
    checkout.released = True
    code, _ = _drive(tmp_path, "--once", "--yes")
    assert code == 0
    assert checkout.commands == []
    assert len(runner.dispatched) == 1


def test_an_existing_closeout_tab_is_recorded_not_redispatched(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _merged(world, tmp_path)
    checkout.released = True
    runner.live.add(f"{REPO}/run/closeout-b1")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert runner.dispatched == []
    assert _events(tmp_path, "b1") == ["dispatch", "closeout"]
    assert _lines(out, "closeout") == [f"closeout b1: recorded the live {REPO}/run/closeout-b1"]


# ---------------------------------------------------------------- archive


def test_the_attributed_archive_pr_is_merged_and_the_batch_finishes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    world.pr(202, "chore/archive-someone-else", [])
    world.pr(203, "chore/archive-p1-lookalike", [])  # no run file: never attributed
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201]
    assert _lines(out, "archive") == ["archive b1: merged archive PR #201"]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0 and "closing 0" in out


def test_an_archive_pr_merged_by_hand_is_recorded_so_batch_list_reads_archived(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#882: the driver started the close-out, someone else merged its archive PR.
    One pass records it on the close-out event; `batch list` reads that, never
    `facts.prs`, which holds open PRs only."""
    from fr.triage.batch import closeout_state

    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-p1", [], state="MERGED", files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    listed = CliRunner().invoke(app, ["triage", "batch", "list", "--repo", REPO,
                                      "--dir", str(tmp_path)])  # fmt: skip
    assert "close-out started" in listed.output, listed.output
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == []
    assert _lines(out, "adopt") == ["adopt b1: archive PR #201 merged"]
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    event = batch.events[-1]
    assert (event.kind, event.runner, event.run, event.archived) == ("closeout", "fake", "r1", 201)  # type: ignore[union-attr]
    assert closeout_state(batch) == "archived"
    listed = CliRunner().invoke(app, ["triage", "batch", "list", "--repo", REPO,
                                      "--dir", str(tmp_path)])  # fmt: skip
    assert "close-out archived" in listed.output, listed.output
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0 and _lines(out, "adopt") == [], out


def test_a_wave_less_archived_batch_is_adopted_by_an_unnamed_drive(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#990: a waved batch makes the default selection drop every wave-less one, so
    a wave-less batch closed out by hand was never adopted. Adoption ignores the
    selection; nothing else is done for the wave-less batch."""
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(days=3)).isoformat(), merge_commit="m101")  # fmt: skip
    checkout.added["m101"] = ("docs/superpowers/journals/debug/b1.md",)
    loose = _batch("b1", 1, events=_dispatch_event("b1")).replace("    wave: 1\n", "")
    _state(tmp_path, world, loose, _batch("b2", 2))
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert _lines(out, "adopt") == ["adopt b1: archived on the default branch already"]
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]
    assert _events(tmp_path, "b1") == ["dispatch", "closeout"]


def test_a_wave_less_batch_still_owed_is_not_closed_out_outside_the_selection(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """The other half of gh#990: a close-out session is a real action, so it still
    follows the selection."""
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(days=3)).isoformat(), merge_commit="m101")  # fmt: skip
    journal = "docs/superpowers/journals/debug/b1.md"
    checkout.added["m101"] = (journal,)
    checkout.live.add(journal)
    checkout.released = True
    loose = _batch("b1", 1, events=_dispatch_event("b1")).replace("    wave: 1\n", "")
    _state(tmp_path, world, loose, _batch("b2", 2))
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert _lines(out, "adopt") == [] and _lines(out, "closeout") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]


def test_plan_mode_with_an_unreadable_clone_says_so_and_plans_no_closeout(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#991: plan mode read a failed clone read as "not archived" and planned a
    close-out for 37 batches that were archived already. A read it needs that fails
    is reported, and nothing is planned on it."""
    from fr.triage.gitseam import GitError

    def _fetch() -> None:
        raise GitError("not a git repository")

    _merged(world, tmp_path)
    # merged long enough ago that a close-out is due whatever the release reads
    world.prs[101].update(merge_commit="m101", merged_at=(NOW - timedelta(days=3)).isoformat())
    checkout.added["m101"] = ("docs/superpowers/journals/debug/2026-10-01-b1.md",)
    monkeypatch.setattr(checkout, "fetch", _fetch)
    before = (tmp_path / "judgements.yaml").read_text()
    code, out = _drive(tmp_path, "--once")
    assert _lines(out, "closeout") == [] and _lines(out, "adopt") == [], out
    assert f"cannot read {REPO}'s clone (not a git repository)" in out
    assert "b1" in out.split("cannot read", 1)[1].splitlines()[0]
    assert "closing 1" in out
    assert (tmp_path / "judgements.yaml").read_text() == before


def test_an_archive_pr_retargeted_off_the_default_branch_is_reported_and_never_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """gh#1004: the archive merge never read the PR's base, so a PR retargeted off
    the default branch would have merged into its new base. It is read fresh, as
    the export path reads it (p4-r15)."""
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"],
             base="release")  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [], out
    assert _lines(out, "blocked") == [
        "blocked b1: archive PR #201 (chore/archive-p1) is based on release, not main; "
        "it is never merged"
    ], out
    code, out = _drive(tmp_path, "--yes")  # the loop names the batch it stops on
    assert code == 3 and world.merged == [], out
    assert "only blocked batches remain (b1)" in out, out
    world.prs[201]["base"] = "main"  # retargeted back by the operator
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201]


_CLOSEOUT_R1 = (
    "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
    "run: r1, archive: chore/archive-p1}\n"
)


def _closing(world: World, tmp_path: Path, events: str = "") -> None:
    """b1 merged, its close-out started (run r1, archive head chore/archive-p1)."""
    _merged(world, tmp_path, events=_CLOSEOUT_R1 + events)
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1 + events))


def test_head_found_open_archive_pr_gets_live_checks_not_pending(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """merge-truth R7: an archive PR opened after the last full collect is found by
    its head alone. Its checks are read live, never assumed `pending`."""
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    world.hidden.add(201)
    world.checks[201] = [{"name": "test", "bucket": "pass"}]
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201], out
    assert _lines(out, "archive") == ["archive b1: merged archive PR #201"]


def test_head_found_open_archive_pr_with_red_live_checks_is_not_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    world.hidden.add(201)
    world.checks[201] = [{"name": "test", "bucket": "fail"}]
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [], out


def test_linked_archive_pr_in_issue_prs_gets_the_facts_verdict(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """merge-truth R7: an archive PR that closes an issue sits in `issue.prs`, never
    `facts.prs`. Path 1 scans both, so a head the close-out did not name is found."""
    _closing(world, tmp_path)
    world.issues[9] = "open"
    world.pr(201, "chore/closeout-r1", [9], files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201], out


def test_archive_of_a_draft_calls_pr_ready_before_pr_merge_and_says_so(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """merge-truth R11: under --yes a green draft archive PR is marked ready, then
    merged, and the line says so. No `approved-fr` label is read or written."""
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"],
             draft=True, labels=[])  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    world.calls.clear()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    acts = [c for c in world.calls if c.startswith(("pr_ready", "pr_merge"))]
    assert acts == ["pr_ready 201", "pr_merge 201"], world.calls
    assert _lines(out, "archive") == ["archive b1: marked ready, merged archive PR #201"]
    assert not [c for c in world.calls if "approved-fr" in c or c.startswith("label ")]


def test_a_refused_ready_on_a_draft_archive_is_worded_as_the_ready_step(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """p2-r9: the forge refusing `pr_ready` is not a refused merge: the line names the
    ready step, and nothing is merged."""
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"],
             draft=True, labels=[])  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    world.refuse_ready = "not permitted"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1 and world.merged == [], out
    (line,) = _lines(out, "archive")
    assert "refused to mark it ready: not permitted" in line, line
    assert "refused the merge" not in line
    assert "not permitted" in load_stops(tmp_path)["archive:b1"].reason


def test_plan_mode_never_marks_a_draft_archive_ready(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"], draft=True)
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    code, out = _drive(tmp_path, "--once")
    assert not [c for c in world.calls if c.startswith(("pr_ready", "pr_merge"))], out


# ------------------------------------------------- the board, every pass (R11)


def _page(tmp_path: Path) -> str:
    return (tmp_path / "board.html").read_text(encoding="utf-8")


def test_an_acting_once_pass_writes_the_board_and_shows_its_own_dispatch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    page = _page(tmp_path)
    start = page.index('data-column="running"')
    assert 'id="card-b1"' in page[start : page.index("</section>", start)]


def test_a_pass_that_acts_on_nothing_still_writes_the_board(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True, labels=[])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, _ = _drive(tmp_path, "--once", "--yes")
    assert code == 3
    assert 'id="card-b1"' in _page(tmp_path)


def test_plan_mode_writes_no_board(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path)
    assert code == 0, out
    assert not (tmp_path / "board.html").exists()


def test_the_board_copies_the_drives_repo_and_dir_only_when_given(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)
    _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert f"focus b1 --repo {REPO} --dir {tmp_path.resolve()}" in _page(tmp_path)
    seen: list[list[str]] = []

    def _spy(scope: Any, target: Path, *, scope_args: Any, **kw: Any) -> Any:
        seen.append(list(scope_args))
        return target / "board.html", 0

    monkeypatch.setattr(triage_kanban_cmd, "write_board", _spy)
    monkeypatch.setattr(triage_batch_cmd, "resolve_state_dir", lambda scope, override, ws: tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)  # no clone here: no --workspace to carry either
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    CliRunner().invoke(app, ["triage", "batch", "drive", "--once", "--yes", "--repo", REPO])
    assert seen == [["--repo", REPO]]


def test_a_board_that_cannot_be_written_warns_once_per_cause_and_changes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)

    def _boom(*a: Any, **kw: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(triage_kanban_cmd, "write_board", _boom)
    sleeps: list[float] = []

    def _stop(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise RuntimeError("end of the test loop")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _stop)
    _, out = _drive(tmp_path, "--yes", "--interval", "5")
    assert out.count("could not write the board") == 1 and "disk full" in out
    assert len(sleeps) == 3 and world.passes == [1, 1, 1]  # type: ignore[attr-defined]
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b1"]


# ------------------------------------------------------------ lock (R6)


def test_a_second_driver_on_the_same_state_directory_refuses(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    (tmp_path / "drive.lock").write_text(json.dumps({"pid": os.getpid(), "started": "x"}))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 2
    assert "drive.lock" in out and str(os.getpid()) in out
    assert runner.dispatched == [] and world.passes == []  # type: ignore[attr-defined]


def test_a_stale_lock_is_taken_over_and_released(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)
    (tmp_path / "drive.lock").write_text(json.dumps({"pid": 999_999_999, "started": "x"}))
    monkeypatch.setattr(drive_lock, "pid_alive", lambda pid: pid == os.getpid())
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert not (tmp_path / "drive.lock").exists()


# --------------------------------------------------------- --checkout map


def test_a_malformed_checkout_mapping_is_refused(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--checkout", "no-equals-sign")
    assert code == 2 and "REPO=PATH" in out
    code, out = _drive(tmp_path, "--once", "--checkout", f"other/repo={tmp_path}")
    assert code == 2 and "other/repo" in out


def test_the_checkout_map_reaches_dispatch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    seen: list[Path | None] = []
    monkeypatch.setattr(
        triage_batch_cmd, "make_checkout", lambda path: seen.append(path) or checkout
    )
    _proposed(world, tmp_path, 1)
    code, out = _drive(
        tmp_path, "--once", "--yes", "--single-pass", "--checkout", f"{REPO}={checkout.path}"
    )
    assert code == 0, out
    assert set(seen) == {checkout.path}


# ------------------------------------------------- re-collect (Forge seam)


def test_recollect_goes_through_the_forge_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.model import Scope, load_facts

    from tests.unit.triage_fixtures import FakeForge

    forge = FakeForge(issues={REPO: []}, prs={REPO: []})
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    triage_batch_cmd.recollect(Scope(kind="repo", target=REPO), tmp_path)
    assert forge.called("list_issues")
    assert load_facts(tmp_path / "facts.json").repos == [REPO]


def _closed_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.unit.triage_fixtures import FakeForge

    (tmp_path / "judgements.yaml").write_text(
        'schema: 1\ntiers: [{n: 1, title: T}]\nissues:\n  "super-fr#5": {tier: 1}\n',
        encoding="utf-8",
    )
    forge = FakeForge(
        issues={REPO: []},
        prs={REPO: []},
        closed={
            (REPO, 5): {
                "number": 5,
                "title": "done",
                "body": "",
                "labels": [],
                "state": "CLOSED",
                "url": f"https://github.com/{REPO}/issues/5",
                "closedAt": "2026-09-20T10:00:00Z",
            }
        },
    )
    monkeypatch.setattr(triage_cmd, "make_forge", lambda: forge)
    return forge


def test_recollect_carries_a_known_closed_issue_over(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from fr.triage.model import Scope, load_facts

    forge = _closed_world(tmp_path, monkeypatch)
    scope = Scope(kind="repo", target=REPO)
    triage_batch_cmd.recollect(scope, tmp_path)
    assert len(forge.called("view_issue")) == 1
    assert "collect: 1 issue viewed, 0 carried over" in capsys.readouterr().out

    triage_batch_cmd.recollect(scope, tmp_path)
    assert len(forge.called("view_issue")) == 1  # no second view
    assert "collect: 0 issues viewed, 1 carried over" in capsys.readouterr().out
    assert [i.state for i in load_facts(tmp_path / "facts.json").issues] == ["closed"]


def test_a_merged_batch_stays_merged_after_its_members_are_carried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.triage.batch import batch_pr, derive_batch_stage
    from fr.triage.model import Batch, DispatchEvent, Scope, load_facts

    from tests.unit.triage_fixtures import _pr_closing

    forge = _closed_world(tmp_path, monkeypatch)
    merged = _pr_closing(owner="derio-net", name="super-fr", number=5, pr_number=9)
    # A batch PR is attributed only from the repo itself by an allowed author
    # (gh#936): the captured record carries neither, so give it the collector's.
    merged.update(
        state="MERGED", headRefName="batch/b1", createdAt=NOW.isoformat(),
        mergedAt=NOW.isoformat(), author={"login": forge.viewer}, isCrossRepository=False,
    )  # fmt: skip
    forge.prs[REPO] = [merged]
    scope = Scope(kind="repo", target=REPO)
    triage_batch_cmd.recollect(scope, tmp_path)
    triage_batch_cmd.recollect(scope, tmp_path)
    assert len(forge.called("view_issue")) == 1  # the second pass carried #5
    facts = load_facts(tmp_path / "facts.json")
    dispatch = DispatchEvent(
        kind="dispatch", at=NOW - timedelta(days=1), runner="r", handle="h", branch="batch/b1"
    )
    batch = Batch(id="b1", title="t", ids=["super-fr#5"], events=[dispatch])

    assert [p.number for p in facts.issues[0].prs] == [9]  # its link recomputed this pass
    assert (pr := batch_pr(batch, facts)) is not None and pr.number == 9
    assert derive_batch_stage(batch, facts) == "merged"


# ------------------------------------------------- kill-safety (R6, Test Plan 5)


def test_a_second_run_after_a_pass_repeats_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 2)
    assert _drive(tmp_path, "--once", "--yes", "--single-pass")[0] == 0
    code, out = _drive(tmp_path, "--once", "--yes")  # nothing left to dispatch
    assert len(runner.dispatched) == 2
    assert _lines(out, "dispatch") == []
    assert code == 3  # both in flight, nothing to do


def test_a_kill_between_launch_and_event_never_launches_twice(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    runner.live.add(f"{REPO}/run/batch-b1")  # launched, event never written
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 2
    assert runner.dispatched == []
    assert "already holds" in out


# ---------------------------------------------- phase 2 review fixes (rg-*)


class _StopError(Exception):
    """Ends a loop-mode test from its sleep hook."""


def _drive_named(tmp_path: Path, *args: str) -> Any:
    return CliRunner().invoke(
        app, ["triage", "batch", "drive", *args, "--repo", REPO, "--dir", str(tmp_path)]
    )


def _unwaved(bid: str, n: int, *, events: str = "", **kw: Any) -> str:
    extra = "".join(f"    {k}: {v}\n" for k, v in kw.items())
    ev = f"    events:\n{events}" if events else ""
    return (
        f'  - id: {bid}\n    title: {bid}\n    ids: ["super-fr#{n}"]\n'
        f"    launch: {LAUNCH}\n{extra}{ev}"
    )


def test_a_dependent_is_not_dispatched_when_its_dependencys_merge_did_not_land(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-1: b1 is behind its base, so the pass updates it instead of merging it;
    b2 (`after: [b1]`) must not start, and the summary must not count b1 merged."""
    world.issues.update({1: "open", 2: "open"})
    world.pr(101, "feat/batch-b1", [1])
    checkout.behind.add("sha-101")
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")),
           _batch("b2", 2, after="[b1]"))  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out  # the update push is an act
    assert world.merged == [] and runner.dispatched == []
    assert _lines(out, "dispatch") == [
        "dispatch b2: held: waits on b1, whose merge did not land this pass"
    ]
    assert _summary(out) == "in flight 1, merged 0, pending 1, closing 0"


def test_a_merge_held_at_act_time_holds_its_dependent(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-1/rg-15: the snapshot judged b1 green, but at the merge a required check is
    pending again; b1 is held and b2 does not start."""
    world.issues.update({1: "open", 2: "open"})
    world.pr(101, "feat/batch-b1", [1])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")),
           _batch("b2", 2, after="[b1]"))  # fmt: skip
    seen: list[int] = []

    def _checks(repo: str, number: int) -> list[dict[str, Any]]:
        seen.append(number)
        bucket = "pass" if len(seen) == 1 else "pending"
        return [{"name": "test", "bucket": bucket}]

    monkeypatch.setattr(world, "pr_required_checks", _checks)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 3, out
    assert world.merged == [] and runner.dispatched == []
    assert _lines(out, "merge") == ["merge b1: held: PR #101 is pending: test"]
    assert "merged 0" in out


@pytest.mark.parametrize("required", [True, False], ids=["required-checks", "no-required"])
def test_a_head_that_moves_after_the_snapshot_is_not_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, required: bool,
) -> None:  # fmt: skip
    """rg-2: the merge is pinned to the head whose checks were judged. Here the move is
    fr's own update (recorded), so the train waits for it (p1-r10)."""
    _pr_open(world, tmp_path)
    _fr_moved(tmp_path, "b1", 101, "sha-101", "sha-pushed")
    if not required:
        world.checks[101] = []
    views: list[int] = []
    real_view = world.pr_view

    def _view(repo: str, number: int) -> dict[str, Any]:
        views.append(number)
        if len(views) == 3:  # after the approval settle and the snapshot: someone pushes
            world.prs[101]["head_oid"] = "sha-pushed"
        return real_view(repo, number)

    monkeypatch.setattr(world, "pr_view", _view)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [], out
    assert _lines(out, "merge") == [
        "merge b1: held: PR #101 head moved from sha-101 to sha-pushed since its checks "
        "were judged; it is judged again next pass"
    ]
    assert code == 3


def test_the_cap_counts_batches_outside_the_selection(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-3: `drive b5` with four other batches in flight dispatches nothing."""
    for n in range(1, 6):
        world.issues[n] = "open"
    others = [_batch(f"o{n}", n, events=_dispatch_event(f"o{n}")) for n in range(1, 5)]
    _state(tmp_path, world, *others, _batch("b5", 5))
    code, out = _drive(tmp_path, "--once", "--yes", "b5")
    assert code == 3, out
    assert runner.dispatched == []
    # gh#913: the summary counts only the selection, so the held line says why
    assert _lines(out, "held") == ["held b5: the in-flight cap (4) is full: o1, o2, o3, o4"]


def test_a_merged_dependency_outside_the_selection_is_not_blocking(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-3: `drive b2` where b1 (unselected) is merged dispatches b2."""
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], state="MERGED", merged_at=NOW.isoformat())
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")),
           _batch("b2", 2, after="[b1]"))  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass", "b2")
    assert code == 0, out
    assert _lines(out, "blocked") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]


def test_a_waved_batch_on_an_unwaved_merged_batch_is_not_blocked(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-3: the default selection (batches with a wave) still resolves its
    dependencies over every batch."""
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b0", [1], state="MERGED", merged_at=NOW.isoformat())
    _state(tmp_path, world, _unwaved("b0", 1, events=_dispatch_event("b0")),
           _batch("b2", 2, after="[b0]"))  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert _lines(out, "blocked") == []
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]


def test_zero_reported_checks_are_not_green(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-4: no required checks and no checks at all (CI not queued yet) waits."""
    _pr_open(world, tmp_path)
    world.checks[101] = []
    world.all_checks[101] = {"pass": 0, "fail": 0, "pending": 0}
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert world.merged == []


def test_a_merge_stop_does_not_end_the_loop_and_is_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-4: a repo with required checks the forge does not report (`--required`
    says none) gets a merge refusal; the loop reports it once and keeps going."""
    _pr_open(world, tmp_path)
    world.checks[101] = []
    world.refuse_merge = "required status check is expected"
    naps: list[float] = []

    def _nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == 3:
            raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _nap)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("required status check is expected") == 1
    assert world.calls.count("pr_merge 101") == 3


def test_ci_none_is_read_from_the_default_branch_not_the_working_tree(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-5: a clone on a feature branch whose tree declares `ci none` does not make
    the driver merge on non-draft alone; origin/main has CI."""
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", REAL_CI_IS_NONE)
    _pr_open(world, tmp_path)
    world.checks[101] = []
    world.all_checks[101] = {"pass": 0, "fail": 0, "pending": 2}
    profiles = "version: 2\nforge: {type: github}\nci: {type: none}\n"
    (checkout.path / ".devcontainer").mkdir()
    (checkout.path / ".devcontainer" / "fr-profiles.yaml").write_text(profiles)
    checkout.files[("origin/main", ".github/workflows/ci.yml")] = "on: push\njobs: {}\n"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert world.merged == []
    # and when origin/main itself declares it, the merge goes ahead
    checkout.files[("origin/main", ".devcontainer/fr-profiles.yaml")] = profiles
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]


def test_an_archive_merged_by_file_attribution_finishes_the_batch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-6: the archive PR's head is neither the close-out's own nor the recorded
    archive branch, so only its files attribute it; once the driver merged it, the
    next pass sees the batch archived and `--once` exits 0."""
    closeout = (
        "      - {kind: closeout, at: 2026-10-02T11:59:00Z, runner: fake, handle: h, "
        "run: r1, archive: chore/archive-p1}\n"
    )
    _merged(world, tmp_path, events=closeout)
    world.pr(201, "chore/archive-renamed", [], files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201]
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    assert batch.events[-1].archived == 201  # type: ignore[union-attr]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert out.rstrip().splitlines()[-1] == "in flight 0, merged 1, pending 0, closing 0"


def test_an_unparsable_lock_is_held_for_its_grace_period(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-7a: a lock another starter created but has not written yet is not stale."""
    _proposed(world, tmp_path, 1)
    (tmp_path / "drive.lock").write_text("")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 2, out
    assert world.passes == []  # type: ignore[attr-defined]
    assert (tmp_path / "drive.lock").read_text() == ""


def test_an_unparsable_lock_past_its_grace_period_is_taken_over(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    lock = tmp_path / "drive.lock"
    lock.write_text("")
    old = lock.stat().st_mtime - 3600
    os.utime(lock, (old, old))
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert not lock.exists()


def test_a_stale_lock_retaken_by_another_starter_is_not_removed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-7b: between reading the stale lock and taking it, another driver took it
    over; this starter must neither remove that lock nor run."""
    _proposed(world, tmp_path, 1)
    lock = tmp_path / "drive.lock"
    lock.write_text(json.dumps({"pid": 999_999_999, "started": "x"}))
    rival = json.dumps({"pid": 4242, "started": "rival"})

    def _alive(pid: int) -> bool:
        if pid == 999_999_999:
            lock.write_text(rival)  # the rival replaced the stale lock meanwhile
            return False
        return pid == 4242

    monkeypatch.setattr(drive_lock, "pid_alive", _alive)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 2, out
    assert lock.read_text() == rival
    assert world.passes == []  # type: ignore[attr-defined]


def test_a_driver_does_not_remove_a_lock_it_no_longer_owns(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-7c: the lock is released only when it is still this driver's."""
    _proposed(world, tmp_path, 1)
    lock = tmp_path / "drive.lock"
    rival = json.dumps({"pid": 4242, "started": "rival"})
    real = triage_batch_cmd.recollect

    def _recollect(scope: Any, target: Path, **_: Any) -> None:
        lock.write_text(rival)
        real(scope, target)

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    assert lock.read_text() == rival


def test_the_lock_is_written_whole_before_it_is_visible(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """rg-7a: the lock appears with its pid already in it (link of a written file),
    never as an empty O_EXCL file."""
    _proposed(world, tmp_path, 1)
    lock = tmp_path / "drive.lock"
    seen: list[str] = []
    real = triage_batch_cmd.recollect

    def _recollect(scope: Any, target: Path, **_: Any) -> None:
        seen.append(lock.read_text())
        real(scope, target)

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    assert _drive(tmp_path, "--once", "--yes", "--single-pass")[0] == 0
    assert json.loads(seen[0])["pid"] == os.getpid()
    assert sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("drive.lock")) == []


def test_closeout_and_batch_dispatch_resolve_the_same_model(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-8: the close-out reads the clone's models.yaml as `batch dispatch` does,
    also when no --checkout is given."""
    no_model = "{runner: fake, harness: claude}"
    models = checkout.path / "docs" / "superpowers" / "models.yaml"
    models.parent.mkdir(parents=True)
    models.write_text("claude-code:\n  orchestrator: repo-model\n")
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    b1 = _batch("b1", 1, events=_dispatch_event("b1")).replace(LAUNCH, no_model)
    b2 = _batch("b2", 2).replace(LAUNCH, no_model)
    _state(tmp_path, world, b1, b2)
    checkout.released = True
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, out
    models_by_item = {i.id: i.payload["model"] for i in runner.dispatched}
    assert models_by_item == {
        f"{REPO}/run/closeout-b1": "repo-model",
        f"{REPO}/run/batch-b2": "repo-model",
    }


def test_the_release_probe_names_the_batchs_merge_commit(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-9: the release must follow THIS merge, so the probe is by merge commit."""
    _merged(world, tmp_path)
    world.prs[101]["merge_commit"] = "c0ffee"
    _drive(tmp_path, "--once", "--yes")
    assert checkout.release_probes == ["c0ffee"]


def test_a_preflight_refusal_does_not_stop_a_merge_when_no_closeout_is_due(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-10: only a due close-out is probed through its runner."""
    world.issues.update({1: "closed", 2: "open"})
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    world.pr(102, "feat/batch-b2", [2])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")),
           _batch("b2", 2, events=_dispatch_event("b2")))  # fmt: skip
    runner.refusal = "HERDR_ENV is not set"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(102, "sha-102", "squash")]
    assert "HERDR_ENV" not in out


def _blocked_state(world: World, tmp_path: Path) -> None:
    world.issues.update({1: "open", 2: "open"})
    cancel = "      - {kind: cancel, at: 2026-10-01T11:00:00Z}\n"
    _state(tmp_path, world, _batch("b0", 1, events=_dispatch_event("b0") + cancel),
           _batch("b1", 2, after="[b0]"))  # fmt: skip


def test_once_with_only_blocked_work_left_exits_3(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """rg-11: blocked work needs the operator, so it is not `done`."""
    _blocked_state(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert _lines(out, "blocked") == ["blocked b1: waits on b0 is cancelled"]


def test_the_loop_ends_with_exit_3_naming_the_blocked_batches(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, sleeps: list[float]
) -> None:
    _blocked_state(world, tmp_path)
    code, out = _drive(tmp_path, "--yes")
    assert code == 3, out
    assert sleeps == []
    assert out.rstrip().splitlines()[-1] == (
        "stopped: only blocked batches remain (b1); they need the operator"
    )


@pytest.mark.parametrize(
    ("required", "all_checks", "merged"),
    [
        ([], {"pass": 2, "fail": 0, "pending": 0}, True),
        ([], {"pass": 2, "fail": 1, "pending": 0}, False),
        ([{"name": "test", "bucket": "pass"}], {"pass": 0, "fail": 3, "pending": 0}, True),
        ([{"name": "test", "bucket": "fail"}], {"pass": 5, "fail": 0, "pending": 0}, False),
    ],
    ids=["none-required-all-green", "none-required-one-failing", "required-passing",
         "required-failing"],
)  # fmt: skip
def test_required_checks_when_there_are_any_else_all_checks(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    required: list[dict[str, Any]], all_checks: dict[str, int], merged: bool,
) -> None:  # fmt: skip
    """rg-15: the World default (one passing required check) must not hide the
    all-checks fallback."""
    _pr_open(world, tmp_path)
    world.checks[101] = required
    world.all_checks[101] = all_checks
    code, out = _drive(tmp_path, "--once", "--yes")
    assert bool(world.merged) is merged, out


# ------------------------------------------- a degraded forge (gh#909, gh#910)


def _flaky_collect(
    monkeypatch: pytest.MonkeyPatch, world: World, failures: int, message: str
) -> list[int]:
    """The real `recollect` over a `collect_into` whose first *failures* calls fail
    as a stalled-then-dropped `gh` read does; later calls write the world's facts."""
    calls: list[int] = []

    def _collect_into(scope: Any, target: Path, **_: Any) -> Any:
        calls.append(1)
        if len(calls) <= failures:
            raise ForgeError(message)
        (target / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
        return world.facts(), target / "facts.json", CollectStats()

    monkeypatch.setattr(triage_batch_cmd, "recollect", REAL_RECOLLECT)
    monkeypatch.setattr(triage_batch_cmd, "collect_into", _collect_into)
    return calls


def _naps_until(monkeypatch: pytest.MonkeyPatch, n: int) -> list[float]:
    naps: list[float] = []

    def _nap(seconds: float) -> None:
        naps.append(seconds)
        if len(naps) == n:
            raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _nap)
    return naps


EOF_MSG = "Post https://api.github.com/graphql: unexpected EOF"


def test_a_failed_recollect_does_not_end_the_loop_and_is_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#910: loop mode skips the pass, waits --interval and reads again; the same
    cause twice in a row is reported once; the merge lands once the forge answers."""
    _pr_open(world, tmp_path)
    calls = _flaky_collect(monkeypatch, world, failures=2, message=EOF_MSG)
    naps = _naps_until(monkeypatch, 3)
    result = _drive_named(tmp_path, "--yes", "--interval", "7")
    assert isinstance(result.exception, _StopError), result.output
    assert len(calls) == 3
    assert naps[:2] == [7, 7]
    assert result.output.count("unexpected EOF") == 1
    assert world.merged == [(101, "sha-101", "squash")]


def test_a_failed_snapshot_read_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#910: a forge read inside the pass (the PR's live view) fails like the
    re-collect can; the pass is skipped and the next one merges."""
    _pr_open(world, tmp_path)
    real_view = world.pr_view
    failed: list[int] = []

    def _view(repo: str, number: int) -> dict[str, Any]:
        if not failed:
            failed.append(number)
            raise GhError(EOF_MSG, returncode=1)
        return real_view(repo, number)

    monkeypatch.setattr(world, "pr_view", _view)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("unexpected EOF") == 1
    assert world.merged == [(101, "sha-101", "squash")]


def test_once_still_exits_non_zero_on_a_failed_forge_read(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _pr_open(world, tmp_path)
    _flaky_collect(monkeypatch, world, failures=1, message=EOF_MSG)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 2, out
    assert "unexpected EOF" in out
    assert world.merged == []


def test_a_failed_merge_method_read_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#910: the repo's merge methods are read when the first merge is acted on;
    that read failing skips the pass like any other, and is read again next pass."""
    _pr_open(world, tmp_path)
    real = world.repo_merge_methods
    failed: list[str] = []

    def _methods(repo: str) -> dict[str, Any]:
        if not failed:
            failed.append(repo)
            raise GhError(EOF_MSG, returncode=1)
        return real(repo)

    monkeypatch.setattr(world, "repo_merge_methods", _methods)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("unexpected EOF") == 1
    assert world.merged == [(101, "sha-101", "squash")]


def test_a_failed_read_while_acting_on_a_merge_does_not_end_the_loop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """gh#910 (review): the merge re-reads the PR before acting (`plan_queue`); that
    read failing after the snapshot's succeeded skips the pass like any other."""
    _pr_open(world, tmp_path)
    real_view = world.pr_view
    calls: list[int] = []

    def _view(repo: str, number: int) -> dict[str, Any]:
        calls.append(number)
        if len(calls) == 2:  # the snapshot's read answered; the act-time one fails
            raise GhError(EOF_MSG, returncode=1)
        return real_view(repo, number)

    monkeypatch.setattr(world, "pr_view", _view)
    _naps_until(monkeypatch, 2)
    result = _drive_named(tmp_path, "--yes")
    assert isinstance(result.exception, _StopError), result.output
    assert result.output.count("unexpected EOF") == 1
    assert world.merged == [(101, "sha-101", "squash")]


# ------------------------------------- default branch unknown (merge-truth R13, gh#1176)


def _git(cwd: Path, *args: str) -> None:
    import subprocess

    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True,
    )  # fmt: skip


class GitHeadCheckout(DriveCheckout):
    """DriveCheckout whose fetch and default branch are a REAL clone's: a git fixture."""

    def __init__(self, path: Path, world: World, real: Checkout) -> None:
        super().__init__(path, world)
        self.real = real

    def default_branch(self) -> str:
        return self.real.default_branch()

    def fetch(self) -> None:
        self.real.fetch()


def _git_clone(tmp_path: Path, world: World, monkeypatch: pytest.MonkeyPatch) -> Path:
    """origin (bare, on main) and a clone of it with `origin/HEAD` removed, as a cloud
    session's clone has none. Returns the origin."""
    origin, clone = tmp_path / "origin.git", tmp_path / "gitclone"
    _git(tmp_path, "init", "--bare", "-b", "main", str(origin))
    _git(tmp_path, "clone", "-q", str(origin), str(clone))
    (clone / "f").write_text("x")
    _git(clone, "add", "f")
    _git(clone, "commit", "-qm", "init")
    _git(clone, "push", "-q", "origin", "HEAD:main")
    _git(clone, "remote", "set-head", "origin", "--auto")
    _git(clone, "remote", "set-head", "origin", "-d")
    fake = GitHeadCheckout(clone, world, Checkout.at(clone))
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    return origin


def test_yes_pass_over_a_clone_without_origin_head_heals_and_merges(
    tmp_path: Path, world: World, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    _git_clone(tmp_path, world, monkeypatch)
    _pr_open(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.merged == [(101, "sha-101", "squash")]
    assert "default branch unknown" not in out


def test_yes_pass_with_unreachable_origin_holds_the_repo_and_finishes(
    tmp_path: Path, world: World, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fetch fails with `origin/HEAD` set: the repo is held with ONE warning line,
    the pass ends without an error, and nothing is written to it."""
    import shutil

    origin = _git_clone(tmp_path, world, monkeypatch)
    _git(tmp_path / "gitclone", "remote", "set-head", "origin", "main")
    shutil.rmtree(origin)
    _pr_open(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out  # not an error: work remains, as for any held merge (exit 3)
    assert world.merged == []
    assert out.count(f"held: {REPO} default branch unknown (") == 1, out


def test_merge_methods_read_failure_still_fails_the_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """The unchanged gh#921 behaviour: only the default-branch read is held; any other
    forge read failure in the merge context still ends a `--once` pass non-zero."""
    _pr_open(world, tmp_path)

    def _methods(repo: str) -> dict[str, Any]:
        raise GhError(EOF_MSG, returncode=1)

    monkeypatch.setattr(world, "repo_merge_methods", _methods)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code != 0, out
    assert "default branch unknown" not in out
    assert world.merged == []


# ------------------------------------------------- closing finished sessions (#918)

BATCH_ITEM = f"{REPO}/run/batch-b1"
CLOSEOUT_ITEM = f"{REPO}/run/closeout-b1"


class CloserRunner(FakeRunner):
    """A runner that is a `SessionCloser`: records closes, answers a set outcome."""

    def __init__(self) -> None:
        super().__init__()
        self.closes: list[Any] = []
        self.outcome = "closed"
        self.outcomes: dict[str, str] = {}  # item id -> outcome, over `outcome`
        self.close_raises: Exception | None = None

    def close(self, item: Any) -> str:
        self.calls.append("close")
        self.closes.append(item)
        if self.close_raises is not None:
            raise self.close_raises
        return self.outcomes.get(item.id, self.outcome)


@pytest.fixture
def closer(monkeypatch: pytest.MonkeyPatch) -> CloserRunner:
    fake = CloserRunner()
    fake.live = {BATCH_ITEM, CLOSEOUT_ITEM}
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


def _finished(world: World, tmp_path: Path, *, runner_name: str = "fake", extra: str = "") -> None:
    closeout = (
        f"      - {{kind: closeout, at: 2026-10-02T11:59:00Z, runner: {runner_name}, "
        "handle: h, archived: 201}\n"
    )
    world.issues[1] = "closed"
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout), extra)


def test_a_finished_batchs_sessions_are_closed_on_the_runner_each_event_recorded(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [i.id for i in closer.closes] == [BATCH_ITEM, CLOSEOUT_ITEM]
    assert {i.payload["group"] for i in closer.closes} == {"drive-wave-1"}
    assert len(_lines(out, "close")) == 1
    assert "closed" in _lines(out, "close")[0]
    assert len(closer.preflighted) == 1  # one preflight and one probe for the one runner
    assert closer.calls.count("existing_dispatches") == 1


def test_only_the_sessions_the_runner_holds_are_closed(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    closer.live = {CLOSEOUT_ITEM}
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [i.id for i in closer.closes] == [CLOSEOUT_ITEM]


def test_a_hand_closeout_is_never_probed(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path, runner_name="hand")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    probed = {i.id for items in closer.preflighted for i in items}
    assert probed == {BATCH_ITEM}
    assert [i.id for i in closer.closes] == [BATCH_ITEM]


def test_keep_sessions_probes_and_closes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes", "--keep-sessions")
    assert code == 0, out
    assert closer.closes == [] and closer.preflighted == []
    assert "close " not in out


def test_without_yes_nothing_is_probed_or_closed(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    code, out = _drive(tmp_path)
    assert code == 0, out
    assert closer.closes == [] and closer.preflighted == []


def test_a_runner_that_cannot_close_is_never_asked(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _finished(world, tmp_path)
    runner.live = {BATCH_ITEM, CLOSEOUT_ITEM}
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert runner.calls == []
    assert _lines(out, "close") == []


def test_a_runner_that_will_not_load_is_skipped_without_exit_2(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    def refuse(name: str) -> Any:
        raise typer.Exit(code=2)

    monkeypatch.setattr(triage_batch_cmd, "load_runner", refuse)
    _finished(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert out.count("could not be loaded") == 1


@pytest.mark.parametrize(
    "error", [ImportError("no module named fr_herdr"), RuntimeError("bad env")]
)
def test_a_runner_whose_load_raises_is_skipped_with_one_warning(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
) -> None:
    # Review p2-r1: an adapter's own import or from_env() failure is not a typer.Exit.
    def broken(name: str) -> Any:
        raise error

    monkeypatch.setattr(triage_batch_cmd, "load_runner", broken)
    _finished(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert out.count("could not be loaded") == 1 and str(error) in out


def test_a_runner_load_refusal_prints_one_warning_not_an_error(
    tmp_path: Path, world: World, checkout: DriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Review p2-r1: `load_runner`'s refusal must not also print a red `error:` line.
    def refuse(name: str) -> Any:
        triage_batch_cmd._fail("runner `fake` is not installed")

    monkeypatch.setattr(triage_batch_cmd, "load_runner", refuse)
    _finished(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "error:" not in out
    assert out.count("is not installed") == 1


def test_a_preflight_refusal_skips_the_runner_and_is_reported_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    closer.refusal = "not inside a herdr session"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert out.count("not inside a herdr session") == 1
    assert closer.closes == []


def test_a_busy_session_is_reported_once_and_changes_no_exit_code(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    closer.outcome = "busy"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "busy, retried next pass" in out
    assert out.count("busy, retried next pass") == 1


def test_a_raised_close_is_printed_and_is_not_a_failed_write(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    _finished(world, tmp_path)
    closer.close_raises = RuntimeError("herdr went away")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "herdr went away" in out


def test_a_pass_whose_only_action_is_a_close_exits_as_it_would_without_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    cycle = _batch("b2", 2, after="[b3]") + _batch("b3", 3, after="[b2]")
    world.issues[2] = world.issues[3] = "open"
    _finished(world, tmp_path, extra=cycle)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert [i.id for i in closer.closes] == [BATCH_ITEM, CLOSEOUT_ITEM]
    assert code == 3, out  # work remains and nothing was done, as without the close


def test_a_repeated_busy_cause_is_reported_once_per_batch(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    from fr.triage.batch_drive import Action

    _finished(world, tmp_path)
    closer.outcome = "busy"
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={}, max_inflight=4,
        yes=True,
    )  # fmt: skip
    driver._probes = {BATCH_ITEM: (closer, _ProbeId(BATCH_ITEM))}  # type: ignore[dict-item]
    action = Action("close", "b1", "x", items=(BATCH_ITEM,))
    first = driver._close_sessions(action)
    assert "busy, retried next pass" in first
    assert driver._close_sessions(action) == ""
    assert driver.failed_write is False


def _close_driver(tmp_path: Path, closer: CloserRunner) -> Any:
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd._scope(REPO, None), tmp_path, named=None, checkouts={}, max_inflight=4,
        yes=True,
    )  # fmt: skip
    driver._probes = {i: (closer, _ProbeId(i)) for i in (BATCH_ITEM, CLOSEOUT_ITEM)}
    return driver


class _ProbeId:
    def __init__(self, item_id: str) -> None:
        self.id = item_id


def test_a_busy_cause_is_not_reported_again_when_a_sibling_closed(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    # Review p2-r2: pass 1 closes the batch tab while the close-out is busy; pass 2
    # sees only the close-out, still busy: the same cause, so no second report.
    from fr.triage.batch_drive import Action

    _finished(world, tmp_path)
    closer.outcomes = {CLOSEOUT_ITEM: "busy"}
    driver = _close_driver(tmp_path, closer)
    first = driver._close_sessions(Action("close", "b1", "x", items=(BATCH_ITEM, CLOSEOUT_ITEM)))
    assert f"closed {BATCH_ITEM}" in first and "busy, retried next pass" in first
    assert driver._close_sessions(Action("close", "b1", "x", items=(CLOSEOUT_ITEM,))) == ""


def test_a_failed_close_is_reported_once_whatever_its_message(
    tmp_path: Path, world: World, checkout: DriveCheckout, closer: CloserRunner
) -> None:
    from fr.triage.batch_drive import Action

    _finished(world, tmp_path)
    driver = _close_driver(tmp_path, closer)
    action = Action("close", "b1", "x", items=(CLOSEOUT_ITEM,))
    closer.close_raises = RuntimeError("socket timeout after 1.2s")
    assert "socket timeout" in driver._close_sessions(action)
    closer.close_raises = RuntimeError("socket timeout after 3.4s")
    assert driver._close_sessions(action) == ""
    assert driver.failed_write is False


# ------------------------------------------------ the merge train (spec §B, §C)


class ScriptedMerge:
    """A `merge_ready` that answers per PR number: an attempt, or an exception."""

    def __init__(self) -> None:
        self.script: dict[int, Any] = {}
        self.calls: list[int] = []

    def __call__(self, ctx: Any, slot: Any, previous: Any) -> Any:
        number = slot.step.pr.number
        self.calls.append(number)
        answer = self.script.get(number, MergeAttempt("merged", head=f"sha-{number}"))
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def train(monkeypatch: pytest.MonkeyPatch) -> ScriptedMerge:
    fake = ScriptedMerge()
    monkeypatch.setattr(triage_batch_cmd, "merge_ready", fake)
    return fake


def _fr_moved(tmp_path: Path, bid: str, pr: int, before: str, after: str) -> None:
    """Record, on *bid*, the operator's approval at *before* and fr's own update from it
    to *after* (merge-train-safety §B): a head that moves there is fr's move."""
    path = tmp_path / "judgements.yaml"
    text = path.read_text("utf-8").replace("schema: 3\n", "schema: 9\n", 1)
    marker = f"branch: feat/batch-{bid}}}\n"
    extra = (
        f"      - {{kind: approval, at: 2026-10-01T10:30:00Z, pr: {pr}, head: {before}}}\n"
        f"      - {{kind: update, at: 2026-10-01T10:40:00Z, pr: {pr}, head_before: {before}, "
        f"head_after: {after}, base: m1}}\n"
    )
    assert marker in text
    path.write_text(text.replace(marker, marker + extra, 1), "utf-8")


def _three_ready(world: World, tmp_path: Path) -> None:
    batches = []
    for i in (1, 2, 3):
        world.issues[i] = "open"
        world.pr(100 + i, f"feat/batch-b{i}", [i])
        batches.append(_batch(f"b{i}", i, events=_dispatch_event(f"b{i}")))
    _state(tmp_path, world, *batches)


def test_an_updated_head_queues_the_rest_without_attempting_them(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    _three_ready(world, tmp_path)
    train.script[101] = MergeAttempt("updated", head="sha-new")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101], out
    assert _lines(out, "merge")[1:] == [
        "merge b2: queued: behind b1",
        "merge b3: queued: behind b1",
    ]
    assert "queued 2" in out


def test_a_merged_head_lets_the_next_candidate_go_in_the_same_pass(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    _three_ready(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101, 102, 103], out


def test_a_refused_head_is_reported_and_stepped_over(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    _three_ready(world, tmp_path)
    train.script[101] = MergeStopError("PR #101: the forge refused the merge")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101, 102, 103]
    assert _lines(out, "merge")[0].startswith("merge b1: stopped: PR #101")
    assert code == 1


def test_a_stopped_merge_is_recorded_for_the_board_and_cleared_when_it_lands(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    """gh#987: the board read "merge ready" for a merge the driver had stopped on, because
    the stop lived only in the driver's memory. It is written down, at the head it stopped
    at, and the board says the driver needs you; a later pass that merges it clears it."""
    _three_ready(world, tmp_path)
    train.script[101] = MergeStopError("PR #101: conflicts with origin/main: a.py")
    _drive(tmp_path, "--once", "--yes")
    stop = load_stops(tmp_path)["b1"]
    assert (stop.head, stop.reason) == ("sha-101", "PR #101: conflicts with origin/main: a.py")
    assert "needs you: merge stopped: PR #101" in (tmp_path / "board.html").read_text("utf-8")
    del train.script[101]
    _drive(tmp_path, "--once", "--yes")
    assert "b1" not in load_stops(tmp_path)


def test_a_moved_head_is_not_recorded_as_a_stop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    """A moved head is a hold the next pass re-judges, not something the operator owes."""
    _three_ready(world, tmp_path)
    train.script[101] = HeadMovedError("PR #101: head moved since the plan was printed")
    _drive(tmp_path, "--once", "--yes")
    assert load_stops(tmp_path) == {}


@pytest.mark.parametrize(
    "answer",
    [
        HeadMovedError("PR #101: head moved since the plan was printed"),
        MergeAttempt("pending", head="sha-101", checks=("test",)),
    ],
    ids=["head-moved-error", "pending"],
)
def test_a_head_that_cannot_proceed_stops_the_train(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge,
    answer: Any,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    train.script[101] = answer
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101], out
    assert _lines(out, "merge")[1:] == [
        "merge b2: queued: behind b1",
        "merge b3: queued: behind b1",
    ]


def test_a_head_moved_since_the_checks_were_judged_stops_the_train(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    _fr_moved(tmp_path, "b1", 101, "sha-101", "sha-pushed")  # fr's own move (p1-r10)
    seen: list[int] = []
    real_view = world.pr_view

    def _view(repo: str, number: int) -> dict[str, Any]:
        seen.append(number)
        if number == 101 and seen.count(101) == 3:  # after the settle and the snapshot
            world.prs[101]["head_oid"] = "sha-pushed"
        return real_view(repo, number)

    monkeypatch.setattr(world, "pr_view", _view)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [], out
    assert _lines(out, "merge")[0].startswith("merge b1: held: PR #101 head moved")
    assert _lines(out, "merge")[1:] == [
        "merge b2: queued: behind b1",
        "merge b3: queued: behind b1",
    ]


@pytest.mark.parametrize("outcome", ["failing", "unapproved", "unready"])
def test_a_head_that_is_failing_or_draft_at_merge_time_is_stepped_over(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge,
    outcome: str,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    train.script[101] = MergeAttempt(outcome, head="sha-101")  # type: ignore[arg-type]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101, 102, 103], out


def test_a_stop_in_one_repo_does_not_stop_another(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    real = triage_batch_cmd.drive_pass

    def _two_repos(snap: Any) -> Any:
        got = real(snap)
        actions = tuple(
            replace(a, train="other/repo") if a.batch == "b3" else a for a in got.actions
        )
        return replace(got, actions=actions)

    monkeypatch.setattr(triage_batch_cmd, "drive_pass", _two_repos)
    train.script[101] = MergeAttempt("updated", head="sha-new")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert train.calls == [101, 103], out
    assert _lines(out, "merge")[1] == "merge b2: queued: behind b1"


# ---------------------------------------------------- the train line (§C, R6)


def test_the_train_line_comes_before_the_actions_in_plan_mode_and_with_yes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner, train: ScriptedMerge
) -> None:
    _three_ready(world, tmp_path)
    for args in ((), ("--once", "--yes")):
        code, out = _drive(tmp_path, *args)
        lines = out.splitlines()
        first_action = next(i for i, ln in enumerate(lines) if ln.startswith("merge "))
        trains = [i for i, ln in enumerate(lines) if ln.startswith(f"train {REPO}: head b1")]
        assert trains and trains[0] < first_action, out
        assert "then b2 (#102), b3 (#103)" in lines[trains[0]]


def test_no_train_line_without_a_ready_pr(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path)
    code, out = _drive(tmp_path)
    assert "train " not in out


# ------------------------------------------- dedupe wiring (triage-dedupe R10, sr-1, sr-5)


def test_the_driver_fills_the_dedupe_fields_and_carries_unfinished_waves(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    world.titles = {1: "deliver gate refuses X", 2: "deliver gate refuses X again"}
    _proposed(world, tmp_path)
    seen: list[Any] = []
    real = triage_batch_cmd.drive_pass

    def _spy(snap: Any) -> Any:
        seen.append(snap)
        return real(snap)

    scope_args = ["--repo", REPO, "--dir", str(tmp_path)]
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd.Scope(kind="repo", target=REPO), tmp_path, named=None,
        checkouts={}, max_inflight=4, yes=False, scope_args=scope_args,
    )  # fmt: skip
    monkeypatch.setattr(triage_batch_cmd, "drive_pass", _spy)
    driver.run_pass()
    driver.run_pass()

    first, second = seen
    assert first.unfinished_waves is None  # a first pass reports nothing
    assert second.unfinished_waves == {"1"}  # b1 and b2 are unfinished: carried forward
    assert first.duplicate_groups == 1
    assert first.dedupe_command == f"fr triage check --repo {REPO} --dir {tmp_path}"


def test_a_dedupe_action_is_reported_under_yes_and_acts_on_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    from fr.triage.batch_drive import Action

    _proposed(world, tmp_path)
    driver = triage_batch_cmd._Driver(
        triage_batch_cmd.Scope(kind="repo", target=REPO), tmp_path, named=None,
        checkouts={}, max_inflight=4, yes=True,
    )  # fmt: skip
    before = (tmp_path / "judgements.yaml").read_text()

    outcome = driver._act(Action("dedupe", "", "2 duplicate candidate groups after wave 1"),
                          world.facts(), 0)  # fmt: skip

    assert outcome == ("2 duplicate candidate groups after wave 1", False, 0)
    assert (tmp_path / "judgements.yaml").read_text() == before
    assert runner.dispatched == [] and world.calls == []


# ------------------------------------- per-wave state export (pages-goal R13, §I)

EXPORT_CONFIG = {"export": {"path": "docs/triage"}}
SCOPE_DIR = "docs/triage/derio-net--super-fr"


def _sid() -> str:
    """This scope's id under the suite's fixed host id."""
    from fr.triage.scope_config import scope_id

    return scope_id(REPO.replace("/", "--"))


def _head(wave: str = "1") -> str:
    """This scope's export head for *wave*: it names the scope id (gh#1101), which the
    suite's fixed host id makes stable."""
    from fr.triage.batch_drive import export_branch

    return export_branch(wave, _sid())


ARCHIVED = (
    "      - {kind: closeout, at: '2026-10-01T12:00:00Z', runner: fake, handle: h, archived: 7}\n"
)


def _git(cwd: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


class GitDriveCheckout(Checkout):
    """A real clone of a throwaway bare origin, whose origin reads as REPO."""

    def origin_repo(self) -> str | None:
        return REPO


@pytest.fixture(name="git_checkout")
def git_checkout_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: World
) -> GitDriveCheckout:
    world.config = EXPORT_CONFIG
    origin = tmp_path / "git" / "origin.git"
    origin.parent.mkdir()
    _git(origin.parent, "init", "--quiet", "--bare", "--initial-branch=main", str(origin))
    clone = tmp_path / "git" / "clone"
    _git(origin.parent, "clone", "--quiet", str(origin), str(clone))
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(clone, "config", k, v)
    _git(clone, "checkout", "--quiet", "-b", "main")
    (clone / ".fr").mkdir()
    (clone / ".fr" / "triage.yaml").write_text(yaml.safe_dump(EXPORT_CONFIG), encoding="utf-8")
    (clone / "README.md").write_text("r\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "seed")
    _git(clone, "push", "--quiet", "origin", "main")
    _git(clone, "remote", "set-head", "origin", "main")
    fake = GitDriveCheckout(clone)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    world.head_of = lambda branch: _git(origin, "rev-parse", f"refs/heads/{branch}").strip()
    world.create_files = [f"{SCOPE_DIR}/judgements.yaml"]
    return fake


def _finished_wave(
    tmp_path: Path,
    world: World,
    *,
    exports: str = "",
    waves: tuple[int, ...] = (1,),
    live: tuple[int, ...] = (),
) -> Path:
    """Each of *waves* is finished: its one batch merged, closed out and archived. Each
    of *live* has one merged batch still owed its close-out. Batch ids are `w<N>`."""
    batches = []
    for n in (*waves, *live):
        world.issues[n] = "closed"
        world.pr(10 + n, f"feat/batch-w{n}", [n], state="MERGED", merged_at=NOW.isoformat())
        events = _dispatch_event(f"w{n}") + (ARCHIVED if n in waves else "")
        batches.append(_batch(f"w{n}", n, wave=n, events=events))
    state = tmp_path / "state"
    state.mkdir()
    _state(state, world, *batches)
    (state / "board").mkdir()
    (state / "board" / "manifest.yaml").write_text("sections: []\n", encoding="utf-8")
    if exports:
        text = (state / "judgements.yaml").read_text(encoding="utf-8")
        text = text.replace("schema: 3\n", "schema: 4\n") + "exports:\n" + exports
        (state / "judgements.yaml").write_text(text, encoding="utf-8")
    return state


def _exports(state: Path) -> list[tuple[str, int | None, bool]]:
    return [(e.wave, e.pr, e.merged) for e in load_judgements(state / "judgements.yaml").exports]


def _heads(state: Path) -> list[str | None]:
    return [e.head for e in load_judgements(state / "judgements.yaml").exports]


def _recorded(head: str) -> str:
    return (
        "  - {wave: '1', repo: derio-net/super-fr, at: '2026-10-01T13:00:00Z', pr: 40, "
        f"head: '{head}'}}\n"
    )


def _export_pr(
    world: World,
    clone: Path,
    files: dict[str, str] | None = None,
    *,
    renames: tuple[tuple[str, str], ...] = (),
    **kw: Any,
) -> str:
    """PR #40 on the export head, whose head is a REAL commit on origin off main that
    writes *files* and makes *renames*. The forge's own `files` field always claims
    an in-directory file only: the driver must never believe it (p4-sec-file-list)."""
    _git(clone, "fetch", "--quiet", "origin")
    _git(clone, "checkout", "--quiet", "-B", "export-pr", "origin/main")
    for src, dst in renames:
        (clone / dst).parent.mkdir(parents=True, exist_ok=True)
        _git(clone, "mv", src, dst)
    for rel, text in (
        files if files is not None else {f"{SCOPE_DIR}/judgements.yaml": "x\n"}
    ).items():
        (clone / rel).parent.mkdir(parents=True, exist_ok=True)
        (clone / rel).write_text(text, encoding="utf-8")
    _git(clone, "add", "--all")
    _git(clone, "commit", "--quiet", "-m", "export pr")
    sha = _git(clone, "rev-parse", "HEAD").strip()
    _git(clone, "push", "--quiet", "--force", "origin", f"export-pr:{_head()}")
    _git(clone, "checkout", "--quiet", "main")
    world.pr(40, _head(), [], **{"head_oid": sha, "files": [f"{SCOPE_DIR}/j.yaml"], **kw})
    return sha


def _export_drive(state: Path, *args: str) -> tuple[int, str]:
    return _drive(state, "--keep-sessions", *args)


def test_plan_mode_prints_the_export_and_writes_nothing(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    state = _finished_wave(tmp_path, world)
    code, out = _export_drive(state)
    assert code == 0, out
    assert f"export wave 1 {REPO}: to {SCOPE_DIR} on {_head()}" in out
    assert _exports(state) == []
    assert not any(c.startswith("pr_create") for c in world.calls)


def test_export_commits_only_the_scope_dir_force_pushes_and_records_the_pr(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    clone = git_checkout.path
    # a stale export branch a dead pass left behind, diverged from main
    _git(clone, "checkout", "--quiet", "-b", "stale")
    (clone / "stale.txt").write_text("old\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "stale")
    _git(clone, "push", "--quiet", "origin", f"stale:{_head()}")
    _git(clone, "checkout", "--quiet", "main")
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    (number,) = [n for n, p in world.prs.items() if p["head_ref"] == _head()]
    assert f"export wave 1 {REPO}: opened PR #{number}" in out
    assert f"pr_create {_head()} -> main" in world.calls
    assert _exports(state) == [("1", number, False)]
    _git(clone, "fetch", "--quiet", "origin")
    tip = f"origin/{_head()}"
    assert _heads(state) == [_git(clone, "rev-parse", tip).strip()]  # the SHA it pushed
    assert _git(clone, "rev-parse", f"{tip}^") == _git(clone, "rev-parse", "origin/main")
    changed = _git(clone, "diff", "--name-only", "origin/main", tip).split()
    assert sorted(changed) == [
        f"{SCOPE_DIR}/board/manifest.yaml",
        f"{SCOPE_DIR}/exported-by",  # the scope id that exported it (gh#1101)
        f"{SCOPE_DIR}/judgements.yaml",
    ]
    assert not (state / "export" / "1").exists()  # the scratch worktree is gone


def test_a_directory_another_scope_exported_is_refused_and_nothing_is_pushed(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """gh#1101: another host's scope of this repo (same scope name, another scope id)
    exported the directory. This driver neither replaces it nor opens a PR, and records
    no export, so the wave stays owed until the operator decides."""
    from fr.triage.state_sync import OWNER_FILE, export_state

    state = _finished_wave(tmp_path, world)
    clone = git_checkout.path
    export_state(state, clone, SCOPE_DIR, owner="s-ffffffff")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "exported by another host's scope")
    _git(clone, "push", "--quiet", "origin", "main")

    code, out = _export_drive(state, "--once", "--yes")

    assert "refused, nothing committed or pushed" in out
    assert "s-ffffffff" in out and _sid() in out
    assert _exports(state) == []
    assert not any(c.startswith("pr_create") for c in world.calls)
    _git(clone, "fetch", "--quiet", "origin")
    assert _head() not in _git(clone, "branch", "-r")
    assert _git(clone, "show", f"origin/main:{SCOPE_DIR}/{OWNER_FILE}") == "s-ffffffff\n"


def test_an_export_that_changes_nothing_records_no_pr_and_opens_none(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    from fr.triage.state_sync import export_state

    state = _finished_wave(tmp_path, world)
    clone = git_checkout.path
    export_state(state, clone, SCOPE_DIR, owner=_sid())
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "already exported")
    _git(clone, "push", "--quiet", "origin", "main")

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert f"{SCOPE_DIR} is unchanged; recorded with no PR" in out
    assert _exports(state) == [("1", None, False)]
    assert not any(c.startswith("pr_create") for c in world.calls)
    _git(clone, "fetch", "--quiet", "origin")
    assert _head() not in _git(clone, "branch", "-r")


def test_an_orphan_is_reused_with_the_drivers_own_commit_never_its_foreign_one(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r12: PR #40 on the export branch carries a single commit nobody here wrote.
    The driver pushes ITS export over it, records #40 with that SHA, and the merge
    pins to it: the foreign commit can never reach main."""
    clone = git_checkout.path
    foreign = _export_pr(world, clone, {f"{SCOPE_DIR}/judgements.yaml": "planted\n"})
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert f"export wave 1 {REPO}: pushed" in out and "reused PR #40" in out
    assert not any(c.startswith("pr_create") for c in world.calls)
    _git(clone, "fetch", "--quiet", "origin")
    tip = _git(clone, "rev-parse", f"origin/{_head()}").strip()
    assert tip != foreign and _heads(state) == [tip]
    assert _exports(state) == [("1", 40, False)]
    assert "planted" not in _git(clone, "show", f"{tip}:{SCOPE_DIR}/judgements.yaml")

    world.prs[40]["head_oid"] = tip  # the forge follows the force-push
    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert world.merged == [(40, tip, "squash")]  # pinned to the driver's own commit


def test_a_green_recorded_export_pr_is_merged_at_its_recorded_head_and_recorded(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    sha = _export_pr(world, git_checkout.path)
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert world.merged == [(40, sha, "squash")]  # the recorded head
    assert f"export-merge wave 1 {REPO}: merged export PR #40" in out
    assert _exports(state) == [("1", 40, True)]
    assert _heads(state) == [sha]


def test_a_foreign_commit_on_the_export_branch_blocks_the_merge(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    sha = _export_pr(world, git_checkout.path)
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))
    world.prs[40]["head_oid"] = "sha-someone-else"

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert f"warn wave 1 {REPO}: export PR #40 head is sha-someone-" in out
    assert not any(c.startswith("pr_merge") for c in world.calls)
    assert world.merged == []
    assert _exports(state) == [("1", 40, False)]


def test_a_file_outside_the_export_dir_blocks_the_merge(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    files = {f"{SCOPE_DIR}/judgements.yaml": "x\n", ".github/workflows/ci.yml": "evil\n"}
    sha = _export_pr(world, git_checkout.path, files)
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert ".github/workflows/ci.yml" in out
    assert not any(c.startswith("pr_merge") for c in world.calls)


def test_a_rename_from_outside_into_the_export_dir_blocks_the_merge(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """gh's `files` names only a rename's new path; git names both (p4-sec-file-list)."""
    clone = git_checkout.path
    sha = _export_pr(world, clone, {}, renames=(("README.md", f"{SCOPE_DIR}/README.md"),))
    assert git_checkout.changed_paths("origin/main", sha) == frozenset(
        {"README.md", f"{SCOPE_DIR}/README.md"}
    )
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert "README.md, outside" in out
    assert not any(c.startswith("pr_merge") for c in world.calls)


def test_a_stray_file_past_the_forges_hundredth_is_still_seen(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    files = {f"{SCOPE_DIR}/snapshots/{i:03}.json": "{}\n" for i in range(120)}
    files["zzz/evil.sh"] = "evil\n"  # sorts last: past entry 100 of a truncated list
    sha = _export_pr(world, git_checkout.path, files)
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert "zzz/evil.sh" in out
    assert world.merged == []


def test_an_unreadable_export_head_is_never_merged(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    ghost = "0123456789abcdef0123456789abcdef01234567"
    state = _finished_wave(tmp_path, world, exports=_recorded(ghost))
    world.pr(40, _head(), [], head_oid=ghost, files=[f"{SCOPE_DIR}/j.yaml"])

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert "changed files are unknown" in out
    assert world.merged == []


def test_a_refused_export_merge_exits_1(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    sha = _export_pr(world, git_checkout.path)
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))
    world.refuse_merge = "protected branch"

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 1, out
    assert "protected branch" in out
    assert _exports(state) == [("1", 40, False)]


def test_a_refused_pr_create_exits_1_and_records_nothing(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    state = _finished_wave(tmp_path, world)
    world.refuse_create = "no permission"

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 1, out
    assert "no permission" in out
    assert _exports(state) == []


def test_a_closed_unmerged_export_pr_is_recorded_once_then_re_exported(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r6: a closed export PR never blocks the repo; its waves are exported again."""
    sha = _export_pr(world, git_checkout.path, state="CLOSED")
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert f"export-closed wave 1 {REPO}: recorded export PR #40 as closed" in out
    assert "warning:" in out and "closed without a merge" in out
    assert [e.closed for e in load_judgements(state / "judgements.yaml").exports] == [True]

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert "closed without a merge" not in out  # said once
    (new,) = [n for n, p in world.prs.items() if p["head_ref"] == _head() and n != 40]
    assert _exports(state) == [("1", new, False)]  # force-pushed onto the same branch


def test_an_export_pr_merged_outside_the_driver_is_recorded_and_the_next_wave_exports(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r1: a hand merge (or a crash after pr_merge) never pins the repo forever."""
    sha = _export_pr(world, git_checkout.path, state="MERGED")
    state = _finished_wave(tmp_path, world, exports=_recorded(sha), waves=(1,), live=(2,))
    _finish(state, 2)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert f"export-reconcile wave 1 {REPO}: recorded export PR #40 as merged" in out
    assert world.merged == []  # nothing merged by the driver
    assert _exports(state) == [("1", 40, True)]

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert [w for w, pr, _ in _exports(state) if pr not in (40,)] == ["2"]


def test_a_drive_loop_is_not_done_while_its_export_pr_is_open(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _finished_wave(tmp_path, world)
    naps: list[float] = []

    def _sleep(seconds: float) -> None:  # the export PR's checks go green on the 2nd nap
        naps.append(seconds)
        if len(naps) == 2:
            for n, p in world.prs.items():
                if p["head_ref"] == _head():
                    world.checks[n] = [{"name": "test", "bucket": "pass"}]
        if len(naps) > 6:
            raise AssertionError("the loop did not end")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _sleep)
    real_create = world.pr_create

    def _create(repo: str, **kw: Any) -> int:
        n = real_create(repo, **kw)
        world.checks[n] = [{"name": "test", "bucket": "pending"}]
        return n

    monkeypatch.setattr(world, "pr_create", _create)

    code, out = _export_drive(state, "--yes")

    assert code == 0, out
    assert len(naps) >= 2  # it kept passing while the PR's checks were pending
    (number,) = [n for n, p in world.prs.items() if p["head_ref"] == _head()]
    assert world.merged == [(number, _heads(state)[0], "squash")]
    assert _exports(state) == [("1", number, True)]


def test_a_symlinked_export_path_in_the_repo_is_refused_as_a_warn_with_nothing_written(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    clone = git_checkout.path
    outside = tmp_path / "outside"
    outside.mkdir()
    (clone / "docs").mkdir()
    (clone / "docs" / "triage").symlink_to(outside)
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "a planted symlink")
    _git(clone, "push", "--quiet", "origin", "main")
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert f"warn wave 1 {REPO}: refused, nothing committed or pushed" in out
    assert list(outside.iterdir()) == []
    assert _exports(state) == []
    assert not any(c.startswith("pr_create") for c in world.calls)
    assert _head() not in _git(clone, "ls-remote", "origin")


def test_a_group_scope_that_opts_in_is_warned_to_use_repo(
    tmp_path: Path, world: World, checkout: DriveCheckout
) -> None:
    from fr.triage.model import Scope

    world.config = EXPORT_CONFIG
    state = _finished_wave(tmp_path, world)
    facts = world.facts()
    driver = triage_batch_cmd._Driver(
        Scope.group([REPO, "derio-net/other"]), state, named=None, checkouts={},
        max_inflight=4, yes=False,
    )  # fmt: skip
    snap = driver.snapshot(facts, load_judgements(state / "judgements.yaml"), NOW)
    assert snap.export_path == {}
    assert snap.export_refused == frozenset({REPO})
    assert snap.finished == frozenset({"1"})


# --------------------------- one export PR covers every unexported finished wave (R13)


def _finish(state: Path, n: int) -> None:
    """Wave *n*'s batch is closed out and archived now. Read as YAML, not as text: an
    earlier pass may have rewritten the file (it records released claims)."""
    path = state / "judgements.yaml"
    doc = yaml.safe_load(path.read_text("utf-8"))
    batch = next(b for b in doc["batches"] if b["id"] == f"w{n}")
    batch["events"].append(yaml.safe_load(ARCHIVED.strip().removeprefix("- ")))
    path.write_text(yaml.safe_dump(doc), "utf-8")


def test_one_pr_covers_three_finished_waves_and_its_merge_marks_all_three(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    state = _finished_wave(tmp_path, world, waves=(1, 2, 3))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    prs = [n for n, p in world.prs.items() if p["head_ref"].startswith("chore/triage-state-")]
    assert len(prs) == 1 and world.prs[prs[0]]["head_ref"] == _head("3")
    assert _lines(out, "export") == [
        f"export wave 3 {REPO}: opened PR #{prs[0]} from {_head('3')} at "
        + world.prs[prs[0]]["head_oid"][:12]
    ]
    assert _exports(state) == [("1", prs[0], False), ("2", prs[0], False), ("3", prs[0], False)]
    assert len(set(_heads(state))) == 1 and _heads(state)[0] == world.prs[prs[0]]["head_oid"]

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert [m[0] for m in world.merged] == prs
    assert _exports(state) == [("1", prs[0], True), ("2", prs[0], True), ("3", prs[0], True)]


def test_a_wave_finishing_while_the_export_pr_is_open_waits_then_exports_alone(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _finished_wave(tmp_path, world, waves=(1, 2), live=(3,))
    real_create = world.pr_create

    def _pending(repo: str, **kw: Any) -> int:
        n = real_create(repo, **kw)
        world.checks[n] = [{"name": "test", "bucket": "pending"}]
        return n

    monkeypatch.setattr(world, "pr_create", _pending)
    assert _export_drive(state, "--once", "--yes")[0] == 0
    (first,) = [n for n, p in world.prs.items() if p["head_ref"] == _head("2")]
    _finish(state, 3)  # wave 3 finishes while PR `first` is open

    code, out = _export_drive(state, "--once", "--yes")

    assert _lines(out, "export") == [] and _lines(out, "export-merge") == []
    assert not [p for p in world.prs.values() if p["head_ref"] == _head("3")]
    assert _exports(state) == [("1", first, False), ("2", first, False)]

    world.checks[first] = [{"name": "test", "bucket": "pass"}]
    assert _export_drive(state, "--once", "--yes")[0] == 0  # merges `first`
    assert [m[0] for m in world.merged] == [first]
    code, out = _export_drive(state, "--once", "--yes")  # then wave 3, alone

    assert code == 0, out
    (second,) = [n for n, p in world.prs.items() if p["head_ref"] == _head("3")]
    assert _exports(state) == [("1", first, True), ("2", first, True), ("3", second, False)]


def test_files_the_target_repo_ignores_are_reported_never_force_added(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r9: the export lands in a (public) repo whose .gitignore says what must never
    be committed. Ignored durable files stay out, and are named three times: in the
    export's line, in a warn for the wave, and in the PR body."""
    clone = git_checkout.path
    (clone / ".gitignore").write_text("snapshots/\n", encoding="utf-8")
    _git(clone, "add", ".gitignore")
    _git(clone, "commit", "--quiet", "-m", "ignore snapshots")
    _git(clone, "push", "--quiet", "origin", "main")
    state = _finished_wave(tmp_path, world)
    (state / "snapshots").mkdir()
    (state / "snapshots" / "s.json").write_text("{}\n", encoding="utf-8")
    bodies: list[str] = []
    real_create = world.pr_create

    def _create(repo: str, **kw: Any) -> int:
        bodies.append(kw["body"])
        return real_create(repo, **kw)

    world.pr_create = _create  # type: ignore[method-assign]

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    _git(clone, "fetch", "--quiet", "origin")
    changed = _git(clone, "diff", "--name-only", "origin/main", f"origin/{_head()}").split()
    assert f"{SCOPE_DIR}/snapshots/s.json" not in changed
    assert f"{SCOPE_DIR}/judgements.yaml" in changed
    snap = f"{SCOPE_DIR}/snapshots/s.json"
    (export,) = _lines(out, "export")
    assert "1 durable file ignored by the target repo" in export and snap in export
    (warn,) = _lines(out, "warn")
    assert warn.startswith(f"warn wave 1 {REPO}: 1 durable file is ignored by the target repo")
    assert snap in warn
    assert snap not in bodies[0]  # p4-r14: file names never reach the public PR body
    assert "1 durable file is ignored by this repo and was not exported." in bodies[0]


def test_a_leftover_export_worktree_with_changes_is_replaced(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r10: a pass that died mid-export leaves a dirty worktree; it is fr's scratch."""
    state = _finished_wave(tmp_path, world)
    left = git_checkout.add_worktree(state / "export" / "1", "origin/main")
    (left.path / "half-written.yaml").write_text("x\n", encoding="utf-8")

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _exports(state)[0][1] is not None
    assert not (state / "export" / "1").exists()


def test_a_plain_directory_at_the_export_scratch_path_is_replaced(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r10: not a worktree, but still fr's own scratch: removed, never a per-pass failure."""
    state = _finished_wave(tmp_path, world)
    (state / "export" / "1").mkdir(parents=True)
    (state / "export" / "1" / "junk.txt").write_text("x\n", encoding="utf-8")

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _exports(state)[0][1] is not None


def test_a_filesystem_error_while_exporting_is_a_warn_for_the_wave(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r10: the repo holds a file where the export needs a directory."""
    clone = git_checkout.path
    (clone / SCOPE_DIR).mkdir(parents=True)
    (clone / SCOPE_DIR / "board").write_text("a file\n", encoding="utf-8")
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "a file in the way")
    _git(clone, "push", "--quiet", "origin", "main")
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert f"warn wave 1 {REPO}: refused, nothing committed or pushed" in out
    assert "board/manifest.yaml" in out
    assert _exports(state) == []


def test_a_crash_after_opening_then_a_new_wave_opens_exactly_one_pr(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r3, p4-r13: PR #40 on wave 1's branch was opened but never recorded; wave 2
    has finished since. #40 is reused for both waves; no second PR ever opens."""
    _export_pr(world, git_checkout.path)
    state = _finished_wave(tmp_path, world, waves=(1, 2))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _exports(state) == [("1", 40, False), ("2", 40, False)]
    assert not any(c.startswith("pr_create") for c in world.calls)
    world.checks[40] = [{"name": "test", "bucket": "pending"}]
    _export_drive(state, "--once", "--yes")
    assert not any(c.startswith("pr_create") for c in world.calls)
    assert [n for n, p in world.prs.items() if p["head_ref"].startswith("chore/triage")] == [40]


def test_a_fork_pr_on_the_export_branch_name_is_ignored(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r7: never adopted, never warned on; the driver exports as if it were not there."""
    state = _finished_wave(tmp_path, world)
    world.pr(40, _head(), [], cross_repo=True, author="someone", head_oid="f" * 40)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _lines(out, "warn") == []
    (mine,) = [n for n, p in world.prs.items() if p["head_ref"] == _head() and n != 40]
    assert _exports(state) == [("1", mine, False)]


def test_a_reopened_pr_recorded_closed_is_reused(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r13: closed (recorded `closed: true`), then reopened by someone: the export
    reuses it rather than calling pr_create, which would fail on the busy head."""
    _export_pr(world, git_checkout.path)
    closed = (
        "  - {wave: '1', repo: derio-net/super-fr, at: '2026-10-01T13:00:00Z', pr: 40, "
        "head: 'x', closed: true}\n"
    )
    state = _finished_wave(tmp_path, world, exports=closed)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert not any(c.startswith("pr_create") for c in world.calls)
    assert _exports(state) == [("1", 40, False)]
    assert [e.closed for e in load_judgements(state / "judgements.yaml").exports] == [False]


def test_a_reused_pr_with_nothing_to_export_is_left_open_with_one_stale_warn(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    from fr.triage.state_sync import export_state

    _export_pr(world, git_checkout.path)
    state = _finished_wave(tmp_path, world)
    clone = git_checkout.path
    export_state(state, clone, SCOPE_DIR, owner=_sid())
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "already exported")
    _git(clone, "push", "--quiet", "origin", "main")

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _exports(state) == [("1", None, False)]
    (warn,) = _lines(out, "warn")
    assert "PR #40" in warn and "stale" in warn
    assert world.prs[40]["state"] == "OPEN"
    code, out = _export_drive(state, "--once", "--yes")
    assert _lines(out, "warn") == []  # said once


# ---------------------------------- the base branch (p4-r15) and extra orphans (p4-r16)


def test_a_retargeted_recorded_export_pr_is_never_merged(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    """p4-r15: its base moved off the default branch; the driver warns and merges nothing."""
    sha = _export_pr(world, git_checkout.path, base="release/1.x")
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert "is based on release/1.x, not main" in out
    assert not any(c.startswith("pr_merge") for c in world.calls)
    assert world.merged == []


def test_an_orphan_based_on_another_branch_is_not_reused_and_nothing_is_pushed(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    clone = git_checkout.path
    sha = _export_pr(world, clone, base="release/1.x")
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 3, out
    assert "is based on release/1.x, not main" in out
    remote = _git(clone, "ls-remote", "origin", f"refs/heads/{_head()}")
    assert remote.split()[0] == sha  # nothing pushed over it
    assert _exports(state) == []
    assert not any(c.startswith("pr_create") for c in world.calls)


def test_extra_orphans_are_warned_stale_once_each(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout, sleeps: list[float]
) -> None:
    """p4-r16: PR #40 (wave 1) is reused; #45 on another wave's branch is named stale."""
    _export_pr(world, git_checkout.path)
    world.pr(45, _head("0"), [], head_oid="e" * 40)
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    (stale,) = [ln for ln in _lines(out, "warn") if "stale" in ln]
    assert "PR #45" in stale and "safe to close" in stale and "PR #40" in stale
    assert _exports(state) == [("1", 40, False)]


# ------------------------------------- conflict hand-back (spec 2026-10-06 §G, R19-R23)


class MessengerRunner(FakeRunner):
    """A runner that reports session state and takes messages (`SessionMessenger`)."""

    def __init__(self) -> None:
        super().__init__()
        self.status: dict[str, str] = {}
        self.messages: list[tuple[str, str]] = []

    def session_statuses(self, items: Any) -> dict[str, str]:
        self.calls.append("session_statuses")
        return {i.id: self.status.get(i.id, "absent") for i in items}

    def message(self, item: Any, text: str) -> None:
        self.messages.append((item.id, text))


@pytest.fixture
def messenger(monkeypatch: pytest.MonkeyPatch) -> MessengerRunner:
    fake = MessengerRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


BATCH_ITEM_B1 = f"{REPO}/run/batch-b1"


def _conflict_error(head: str = "sha-101", paths: tuple[str, ...] = ("src/a.py",), bid: str = "b1",
                    number: int = 101) -> Any:  # fmt: skip
    from fr.triage.batch_merge import MergeConflictError

    return MergeConflictError(
        f"PR #{number} (batch {bid}) conflicts with origin/main in a change merge will not "
        f"resolve: {', '.join(paths)}",
        batch=bid, head=head, paths=paths,
    )  # fmt: skip


def _conflict_yaml(head: str, delivered: str, minute: int) -> str:
    return (
        f"      - {{kind: conflict, at: '2026-10-01T11:{minute:02d}:00Z', head: {head}, "
        f"paths: [src/a.py], delivered: {delivered}}}\n"
    )


def _one_conflicted(world: World, tmp_path: Path, events: str = "") -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + events))
    if events:
        path = tmp_path / "judgements.yaml"
        path.write_text(path.read_text("utf-8").replace("schema: 3\n", "schema: 5\n"), "utf-8")


def _conflicts(tmp_path: Path, bid: str = "b1") -> list[Any]:
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)
    return [e for e in batch.events if e.kind == "conflict"]


def _needs(tmp_path: Path) -> list[Any]:
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    facts = load_facts(tmp_path / "facts.json")
    return [n for n in needs_you(facts, load_judgements(tmp_path / "judgements.yaml"))
            if n.kind == "merge-conflict"]  # fmt: skip


def test_a_conflict_is_messaged_to_the_idle_batch_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "idle"
    train.script[101] = _conflict_error()
    code, out = _drive(tmp_path, "--once", "--yes")
    ((target, text),) = messenger.messages
    assert target == BATCH_ITEM_B1, out
    assert "b1" in text and "PR #101" in text and "sha-101" in text and "src/a.py" in text
    (event,) = _conflicts(tmp_path)
    assert (event.head, event.paths, event.delivered) == ("sha-101", ["src/a.py"], "session")
    assert event.handle == BATCH_ITEM_B1
    assert messenger.dispatched == []
    (line,) = _lines(out, "merge")
    assert line.startswith("merge b1: stopped: PR #101") and "handed back to its session" in line
    assert load_judgements(tmp_path / "judgements.yaml").schema_ == 10


@pytest.mark.parametrize("status", ["idle", "absent", "working"])
def test_a_conflict_the_pass_handles_is_no_failed_write(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge, status: str,
) -> None:  # fmt: skip
    """gh#1099: a conflict handed back (or waiting on a busy session) is the train doing
    what it should; `--once` exits 1 only for a write that failed."""
    _one_conflicted(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = status
    train.script[101] = _conflict_error()

    code, out = _drive(tmp_path, "--once", "--yes")

    assert code != 1, out
    assert _lines(out, "merge")[0].startswith("merge b1: stopped: PR #101")


@pytest.mark.parametrize("status", ["absent", "done"])
def test_a_conflict_with_no_live_session_starts_a_fresh_one(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge, status: str,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = status
    train.script[101] = _conflict_error()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [], out
    (item,) = messenger.dispatched
    assert item.id == f"{REPO}/run/conflict-b1-1"
    assert item.unit == "run"
    payload = item.payload
    assert payload["kind"] == "conflict"
    assert payload["branch"] == "feat/batch-b1"
    assert (payload["harness"], payload["model"]) == ("claude", "claude-opus-5-5")
    assert payload["checkout"] == str(checkout.path)
    assert "src/a.py" in payload["brief"]
    (event,) = _conflicts(tmp_path)
    assert (event.delivered, event.handle) == ("fresh", "w2:p1K")


def test_a_runner_without_the_messenger_protocol_always_starts_a_fresh_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    (item,) = runner.dispatched
    assert item.id == f"{REPO}/run/conflict-b1-1" and item.payload["kind"] == "conflict"
    assert [e.delivered for e in _conflicts(tmp_path)] == ["fresh"]


@pytest.mark.parametrize("status", ["working", "blocked"])
def test_a_busy_session_gets_nothing_and_no_event(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge, status: str,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = status
    train.script[101] = _conflict_error()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [] and messenger.dispatched == []
    assert _conflicts(tmp_path) == []
    assert f"its session is {status}" in _lines(out, "merge")[0]
    messenger.status[BATCH_ITEM_B1] = "idle"  # a later pass delivers it
    _drive(tmp_path, "--once", "--yes")
    assert [t for t, _ in messenger.messages] == [BATCH_ITEM_B1]


def test_the_message_goes_to_the_latest_fresh_conflict_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path, _conflict_yaml("sha-old", "fresh", 1))
    conflict_item = f"{REPO}/run/conflict-b1-1"
    messenger.status.update({BATCH_ITEM_B1: "idle", conflict_item: "idle"})
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    assert [t for t, _ in messenger.messages] == [conflict_item]


def test_a_second_fresh_session_takes_the_next_number(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path, _conflict_yaml("sha-old", "fresh", 1))
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/conflict-b1-2"]


def test_a_restarted_driver_never_hands_the_same_head_back_twice(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "idle"
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    code, out = _drive(tmp_path, "--once", "--yes")  # a new process: no in-memory state
    assert len(messenger.messages) == 1, out
    assert len(_conflicts(tmp_path)) == 1
    assert "handed back" not in _lines(out, "merge")[0]


def test_a_live_fresh_session_from_a_killed_pass_is_recorded_not_restarted(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    runner.live.add(f"{REPO}/run/conflict-b1-1")
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    assert runner.dispatched == []
    assert [(e.delivered, e.handle) for e in _conflicts(tmp_path)] == [
        ("fresh", f"{REPO}/run/conflict-b1-1")
    ]


def test_the_third_conflict_is_held_and_needs_the_operator(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(
        world, tmp_path, _conflict_yaml("sha-1", "session", 1) + _conflict_yaml("sha-2", "fresh", 2)
    )
    messenger.status.update({BATCH_ITEM_B1: "idle", f"{REPO}/run/conflict-b1-1": "idle"})
    train.script[101] = _conflict_error()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [] and messenger.dispatched == [], out
    assert [e.delivered for e in _conflicts(tmp_path)] == ["session", "fresh", "held"]
    assert "held" in _lines(out, "merge")[0]
    (need,) = _needs(tmp_path)
    assert need.ref == "b1" and "sha-101" in need.text
    # a fourth pass at the same head is a skip: still one held event, still one need
    _drive(tmp_path, "--once", "--yes")
    assert len(_conflicts(tmp_path)) == 3 and len(_needs(tmp_path)) == 1


def test_a_held_conflict_is_cleared_by_a_merge_a_cancel_or_a_new_dispatch(
    tmp_path: Path,
    world: World,
    checkout: DriveCheckout,
    runner: FakeRunner,
) -> None:
    held = _conflict_yaml("sha-3", "held", 3)
    _one_conflicted(world, tmp_path, held)
    assert len(_needs(tmp_path)) == 1
    # a new dispatch resets the count
    redispatch = (
        "      - {kind: dispatch, at: '2026-10-01T12:00:00Z', runner: fake, handle: h, "
        "branch: feat/batch-b1}\n"
    )
    _one_conflicted(world, tmp_path, held + redispatch)
    assert _needs(tmp_path) == []
    # a cancel closes the batch
    _one_conflicted(world, tmp_path, held + "      - {kind: cancel, at: '2026-10-01T12:00:00Z'}\n")
    assert _needs(tmp_path) == []
    # a merge closes it too
    _one_conflicted(world, tmp_path, held)
    world.prs[101].update(state="MERGED", merged_at=NOW.isoformat())
    world.issues[1] = "closed"
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    assert _needs(tmp_path) == []


def test_a_conflict_sharing_a_path_with_an_earlier_one_this_pass_waits_behind_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    messenger.status.update({f"{REPO}/run/batch-b{i}": "idle" for i in (1, 2, 3)})
    train.script[101] = _conflict_error(paths=("src/a.py",))
    train.script[102] = _conflict_error(head="sha-102", paths=("src/a.py", "x.py"), bid="b2",
                                        number=102)  # fmt: skip
    train.script[103] = _conflict_error(head="sha-103", paths=("docs/c.md",), bid="b3",
                                        number=103)  # fmt: skip
    code, out = _drive(tmp_path, "--once", "--yes")
    assert [t for t, _ in messenger.messages] == [BATCH_ITEM_B1, f"{REPO}/run/batch-b3"], out
    assert _conflicts(tmp_path, "b2") == []
    assert "waits behind b1" in _lines(out, "merge")[1]


def test_a_batch_that_waited_behind_a_blocker_is_handed_back_once_the_blocker_merges(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _three_ready(world, tmp_path)
    messenger.status.update({f"{REPO}/run/batch-b{i}": "idle" for i in (1, 2, 3)})
    train.script[101] = _conflict_error(paths=("src/a.py",))
    train.script[102] = _conflict_error(head="sha-102", paths=("src/a.py", "x.py"), bid="b2",
                                        number=102)  # fmt: skip
    _drive(tmp_path, "--once", "--yes")
    assert _conflicts(tmp_path, "b2") == []  # waited, nothing recorded
    # b1's conflict is resolved and its PR merges; b2 is no longer behind anything
    del train.script[101]
    world.prs[101].update(state="MERGED", merged_at=NOW.isoformat())
    world.issues[1] = "closed"
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    messenger.messages.clear()
    _drive(tmp_path, "--once", "--yes")
    assert f"{REPO}/run/batch-b2" in [t for t, _ in messenger.messages]
    (event,) = _conflicts(tmp_path, "b2")
    assert (event.head, event.delivered) == ("sha-102", "session")


def test_conflict_brief_names_the_six_steps_and_the_declared_mirrors() -> None:
    from fr.triage.batch_dispatch import conflict_brief
    from fr.triage.model import Batch

    batch = Batch.model_validate({"id": "b1", "title": "Fix it", "ids": ["super-fr#1"]})
    text = conflict_brief(
        batch, pr=101, head="sha-101abcdef0123", paths=("src/a.py", "uv.lock"),
        branch="feat/batch-b1", base="origin/main",
        mirrors=(["uv", "run", "scripts/sync-opencode.py"],
                 ["uv", "run", "scripts/sync hermes.py"]),
    )  # fmt: skip
    for needle in ("b1", "PR #101", "sha-101abcdef0123", "src/a.py, uv.lock", "feat/batch-b1"):
        assert needle in text
    assert "git merge origin/main" in text
    assert "rebase" in text and "force-push" in text
    assert "regenerate" in text.lower() and "test suite" in text and "git push" in text
    assert "uv run scripts/sync-opencode.py" in text
    assert "uv run 'scripts/sync hermes.py'" in text
    bare = conflict_brief(
        batch, pr=101, head="sha-101", paths=("src/a.py",), branch="feat/batch-b1",
        base="origin/main", mirrors=(),
    )  # fmt: skip
    assert "sync-opencode" not in bare and "regenerate" in bare.lower()


def test_the_fresh_conflict_brief_enters_the_batch_workspace_before_it_merges(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    _one_conflicted(world, tmp_path)
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    (item,) = runner.dispatched
    brief = item.payload["brief"]
    enter = brief.index("fr isolation up --branch feat/batch-b1")
    assert enter < brief.index("git merge origin/main")
    assert brief.index("1. ") < enter < brief.index("2. ")
    # the session starts in the driver's clone, which the brief never moves off its branch
    assert "git checkout" not in brief and "git switch" not in brief


def test_triage_yaml_declares_mirrors_as_argument_lists() -> None:
    assert TriageConfig().mirrors == []
    got = TriageConfig.model_validate({"mirrors": [["uv", "run", "scripts/sync.py"]]})
    assert got.mirrors == [["uv", "run", "scripts/sync.py"]]
    from pydantic import ValidationError

    for bad in ("uv run x", ["uv run x"], [[]]):
        with pytest.raises(ValidationError):
            TriageConfig.model_validate({"mirrors": bad})


def test_the_conflict_brief_carries_the_repos_mirrors(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge,
) -> None:  # fmt: skip
    world.config = {"mirrors": [["uv", "run", "scripts/sync-opencode.py"]]}
    _one_conflicted(world, tmp_path)
    train.script[101] = _conflict_error()
    _drive(tmp_path, "--once", "--yes")
    (item,) = runner.dispatched
    assert "uv run scripts/sync-opencode.py" in item.payload["brief"]


@pytest.mark.parametrize(("unfinished", "passes"), [(frozenset({"1"}), 2), (frozenset(), 1)])
def test_a_finishing_loop_runs_one_observation_pass_only_when_a_wave_was_unfinished(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, unfinished: frozenset[str], passes: int,
) -> None:  # fmt: skip
    """Review p1-r4: the pass that ends the drive may finish the last wave itself (an
    adopt, an archive merge); only one more pass observes it, so the loop runs it once."""
    from fr.triage.batch_drive import Summary

    _proposed(world, tmp_path, 1)
    calls: list[int] = []

    def _done_pass(self: Any) -> tuple[bool, Summary, list[str]]:
        calls.append(1)
        self._unfinished = unfinished if len(calls) == 1 else frozenset()
        return False, Summary(in_flight=0, merged=1, pending=0, closing=0), []

    monkeypatch.setattr(triage_batch_cmd._Driver, "run_pass", _done_pass)
    code, _ = _drive(tmp_path, "--yes", "--checkout", f"{REPO}={checkout.path}")

    assert code == 0
    assert len(calls) == passes


# ------------------------------------------------- claims (triage-claims R3, R6, R8, R10, R11)


def _me() -> str:
    from fr.triage.scope_config import scope_id

    return scope_id("derio-net--super-fr")


def _markers(world: World, n: int) -> list[Any]:
    from fr.triage.claims import parse_marker

    found = (parse_marker(c["body"]) for c in world.comments.get(n, []))
    return [m for m in found if m is not None and m.released is None]


def _put(world: World, n: int, signer: str, bid: str, *, hours: float = 0, cid: int = 90) -> None:
    from fr.triage.claims import Marker, render_marker

    at = NOW - timedelta(hours=hours)
    m = Marker(signer=signer, batch=bid, claimed=at, heartbeat=at, expires=at + timedelta(hours=4))
    world.comments.setdefault(n, []).append(
        {"author": "operator", "body": render_marker(m), "created_at": at.isoformat(), "id": cid}
    )


def test_the_snapshot_reads_owed_claims_from_facts_and_prints_them_without_yes(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once")
    assert code == 0, out
    assert _lines(out, "claim") == ["claim super-fr#1 (b1): owed"]
    assert out.index("claim super-fr#1") < out.index("dispatch b1")
    assert world.comments == {}  # plan mode writes nothing


def test_the_scope_config_sets_when_a_refresh_is_owed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    _put(world, 1, _me(), "b1", hours=2)
    _state(tmp_path, world, _batch("b1", 1))  # facts now carry the claim
    code, out = _drive(tmp_path, "--once")
    assert code == 0, out
    assert not _lines(out, "refresh")  # 24 hours by default: a quarter is six
    (tmp_path / "scope.yaml").write_text("claim_expiry_hours: 4\n", encoding="utf-8")
    code, out = _drive(tmp_path, "--once")
    assert _lines(out, "refresh") == ["refresh super-fr#1 (b1): heartbeat due"]


def test_a_yes_pass_claims_before_dispatch_backfills_and_owes_nothing_after(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    _state(tmp_path, world, _batch("old", 1, events=_dispatch_event("old")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out  # a claim write is no progress: the batch is still in flight
    assert [m.batch for m in _markers(world, 1)] == ["old"]  # a pre-claims batch, backfilled
    assert _lines(out, "claim") == ["claim super-fr#1 (old): posted"]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert not _lines(out, "claim") and not _lines(out, "release")


def test_a_cancelled_batchs_claims_are_released_and_recorded_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    cancel = "      - {kind: cancel, at: 2026-10-01T12:00:00Z}\n"
    _put(world, 1, _me(), "gone")
    _state(tmp_path, world, _batch("gone", 1, events=_dispatch_event("gone") + cancel))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert _lines(out, "release") == ["release super-fr#1 (gone): released"]
    assert _markers(world, 1) == []  # the released form is no longer a claim
    assert _events(tmp_path, "gone")[-1] == "claims_released"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert not _lines(out, "release")
    assert _events(tmp_path, "gone").count("claims_released") == 1


def test_a_claim_that_turns_out_held_stops_the_pass_acting_on_that_batch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 2)
    # facts (read first) know nothing of the rival marker the forge shows at write time
    _put(world, 1, "s-22222222", "theirs", cid=5)
    original = world.facts

    def _stale() -> Facts:
        f = original()
        return f.model_copy(
            update={"issues": [i.model_copy(update={"claims": []}) for i in f.issues]}
        )

    world.facts = _stale  # type: ignore[method-assign]
    _state(tmp_path, world, _batch("b1", 1), _batch("b2", 2))
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert "super-fr#1 is claimed by triage scope s-22222222" in out
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]
    assert _events(tmp_path, "b1") == []


def _stale_claims(world: World) -> None:
    """Facts (read first) know nothing of a rival marker the forge shows at write time."""
    original = world.facts

    def _stale() -> Facts:
        f = original()
        return f.model_copy(
            update={"issues": [i.model_copy(update={"claims": []}) for i in f.issues]}
        )

    world.facts = _stale  # type: ignore[method-assign]


def test_a_dispatch_dropped_for_a_lost_claim_is_not_counted_in_flight(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Review p2-r1: the summary says what the pass did, not what it planned."""
    _proposed(world, tmp_path, 2)
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _stale_claims(world)
    _state(tmp_path, world, _batch("b1", 1), _batch("b2", 2))
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b2"]
    assert _summary(out) == "in flight 1, merged 0, pending 1, closing 0", out
    assert code == 0


def test_a_merge_dropped_for_a_lost_claim_is_not_counted_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Review p2-r1: a merge left alone because the batch turned out held did not land."""
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1])
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _stale_claims(world)
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [], out
    assert "merged 0" in out.rstrip().splitlines()[-1], out
    assert "in flight 1" in out.rstrip().splitlines()[-1], out


def test_after_a_lost_claim_the_batchs_other_members_are_not_claimed(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Review p2-r2: one lost claim stops the rest of that batch's claims in the pass."""
    world.issues.update({1: "open", 2: "open"})
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _stale_claims(world)
    two = (
        '  - id: b1\n    title: b1\n    ids: ["super-fr#1", "super-fr#2"]\n    wave: 1\n'
        f"    launch: {LAUNCH}\n"
    )
    _state(tmp_path, world, two)
    _drive(tmp_path, "--once", "--yes")
    assert _markers(world, 2) == []
    assert [m.signer for m in _markers(world, 1)] == ["s-22222222"]


def test_a_forge_error_in_a_claim_write_exits_1_and_the_pass_goes_on(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Review p2-r4: a failed write is reported per member, never a crash."""
    _proposed(world, tmp_path, 2)
    real = world.comment_issue

    def _flaky(repo: str, number: int, body: str) -> None:
        if number == 1:
            raise GhError("HTTP 502", returncode=1)
        real(repo, number, body)

    monkeypatch.setattr(world, "comment_issue", _flaky)
    result = _drive_named(tmp_path, "--once", "--yes", "--single-pass")
    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), result.exception  # an exit, not a crash
    assert "claim super-fr#1 (b1): failed:" in result.output
    assert [m.batch for m in _markers(world, 2)] == ["b2"]  # the rest of the pass went on


def test_a_failed_record_of_released_claims_is_reported_and_tried_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Review p2-r4: the release is idempotent at the forge, so the next pass records it."""
    from fr.triage.errors import TriageError

    world.issues[1] = "open"
    cancel = "      - {kind: cancel, at: 2026-10-01T12:00:00Z}\n"
    _put(world, 1, _me(), "gone")
    _state(tmp_path, world, _batch("gone", 1, events=_dispatch_event("gone") + cancel))
    real = triage_batch_cmd._save
    calls: list[int] = []

    def _save_once_refused(*a: Any, **kw: Any) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise TriageError("disk full")
        real(*a, **kw)

    monkeypatch.setattr(triage_batch_cmd, "_save", _save_once_refused)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "could not record the released claims (disk full)" in out, out
    assert "claims_released" not in _events(tmp_path, "gone")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert _events(tmp_path, "gone").count("claims_released") == 1, out
    code, out = _drive(tmp_path, "--once", "--yes")
    assert not _lines(out, "release")
    assert _events(tmp_path, "gone").count("claims_released") == 1


def test_a_merged_then_archived_batch_refreshes_then_releases_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Review p2-r4: the claim is kept (refreshed) while the batch is merged and its
    close-out runs, released and recorded once it is archived, and nothing is owed after."""
    from fr.triage.batch import closeout_state

    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], state="MERGED",
             merged_at=(NOW - timedelta(minutes=2)).isoformat())  # fmt: skip
    _put(world, 1, _me(), "b1", hours=7)  # past a quarter of the default expiry: due
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1")))
    _, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "refresh") == ["refresh super-fr#1 (b1): refreshed"], out
    assert not _lines(out, "release")
    assert "claims_released" not in _events(tmp_path, "b1")

    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + ARCHIVED))
    _, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "release") == ["release super-fr#1 (b1): released"], out
    assert _events(tmp_path, "b1").count("claims_released") == 1
    assert closeout_state(load_judgements(tmp_path / "judgements.yaml").batches[0]) == "archived"
    _, out = _drive(tmp_path, "--once", "--yes")
    assert not _lines(out, "release") and not _lines(out, "refresh")
    assert _events(tmp_path, "b1").count("claims_released") == 1


def test_a_held_batch_that_is_cancelled_gets_no_held_action(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """Review p2-r4: a cancelled batch is nothing to wait on."""
    world.issues[1] = "open"
    cancel = "      - {kind: cancel, at: 2026-10-01T12:00:00Z}\n"
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _state(tmp_path, world, _batch("gone", 1, events=_dispatch_event("gone") + cancel))
    code, out = _drive(tmp_path, "--once")
    assert not _lines(out, "held"), out


def test_a_loop_with_only_held_batches_stops_naming_who_holds_them(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    sleeps: list[float],
) -> None:  # fmt: skip
    """Review p2-r5: a batch another scope holds waits on that scope, not the operator."""
    world.issues.update({1: "open", 2: "open"})
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _state(tmp_path, world, _batch("b1", 1), _batch("b2", 2, after="[zz]"))
    code, out = _drive(tmp_path, "--yes")
    assert code == 3, out
    assert "held by another scope: b1 (s-22222222)" in out, out
    assert "need the operator: b2" in out, out
    assert "held 1" in out and "blocked 1" in out


def test_a_loop_with_only_held_batches_names_no_operator_need(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    sleeps: list[float],
) -> None:  # fmt: skip
    world.issues[1] = "open"
    _put(world, 1, "s-22222222", "theirs", cid=5)
    _state(tmp_path, world, _batch("b1", 1))
    code, out = _drive(tmp_path, "--yes")
    assert code == 3, out
    assert "held by another scope: b1 (s-22222222)" in out
    assert "need the operator" not in out
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out


# ------------------------------------------------------------ publishing (R14)


def _publish_config(tmp_path: Path, argv: list[str]) -> Path:
    out = tmp_path / "published.txt"
    code = "import sys; open(sys.argv[1], 'a').write(sys.argv[2] + '\\n')"
    cfg = {"publish": [sys.executable, "-c", code, str(out), *argv]}
    (tmp_path / "scope.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    return out


def test_a_drive_pass_publishes_the_board_it_rendered(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    out = _publish_config(tmp_path, ["{name}"])
    code, said = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0, said
    assert out.read_text(encoding="utf-8") == "super-fr batches\n"


def test_a_plan_pass_writes_no_board_and_publishes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    out = _publish_config(tmp_path, ["{name}"])
    assert _drive(tmp_path)[0] == 0 and not out.exists()


def test_a_failing_publish_warns_once_per_cause_and_changes_no_exit_code(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _proposed(world, tmp_path, 1)
    (tmp_path / "scope.yaml").write_text(yaml.safe_dump({"publish": ["/no/such"]}))
    sleeps: list[float] = []

    def _stop(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise RuntimeError("end of the test loop")

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _stop)
    _, out = _drive(tmp_path, "--yes", "--interval", "5")
    assert out.count("could not publish the board") == 1 and "/no/such" in out
    assert len(sleeps) == 3
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b1"]


def test_a_failing_publish_leaves_a_once_drive_exit_code_alone(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    (tmp_path / "scope.yaml").write_text(yaml.safe_dump({"publish": ["/no/such"]}))
    code, said = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert code == 0 and "could not publish the board" in said


# ------------------------------------------- the approval gate (merge-train-safety §A)


def _approvals(tmp_path: Path, bid: str) -> list[Any]:
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)
    return [e for e in batch.events if e.kind in ("approval", "update")]


def test_the_driver_holds_an_unlabelled_green_pr_and_says_it_awaits_approval(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path, labels=[])
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert world.merged == []
    assert "awaiting approval b1 (#101)" in out
    assert _approvals(tmp_path, "b1") == []


def test_the_driver_readies_and_merges_a_labelled_draft(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path, draft=True)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert "pr_ready 101" in world.calls
    assert world.merged == [(101, "sha-101", "squash")]
    (approval,) = _approvals(tmp_path, "b1")
    assert (approval.pr, approval.head, approval.voided_at) == (101, "sha-101", None)


def test_a_session_push_after_labelling_voids_the_approval(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]
    _drive(tmp_path, "--once", "--yes")  # records the approval at sha-101; CI is red
    world.prs[101]["head_oid"] = "sha-session"
    world.checks[101] = [{"name": "lint", "bucket": "pass"}]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "approval of PR #101 at sha-101 voided: head moved to sha-session" in out
    assert "label 101" in world.calls and world.prs[101]["labels"] == []
    assert world.merged == []
    assert _approvals(tmp_path, "b1")[-1].voided_at == "sha-session"


def test_a_driver_update_is_recorded_and_keeps_the_approval(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    checkout.behind.add("sha-101")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "updated PR #101 to sha-updated" in out, out
    approval, update = _approvals(tmp_path, "b1")
    assert (update.head_before, update.head_after, update.base) == (
        "sha-101",
        "sha-updated",
        "origin/main@fetched",
    )
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [(101, "sha-updated", "squash")], out
    assert "voided" not in out


def test_each_drive_pass_checks_the_label_once_per_repo_and_creates_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path, labels=[])
    world.labels_defined.clear()
    code, out = _drive(tmp_path, "--once", "--yes")
    assert f"created label approved-fr on {REPO}" in out
    assert world.calls.count("label_exists approved-fr") == 1
    _drive(tmp_path, "--once", "--yes")
    assert world.calls.count("label_exists approved-fr") == 2  # one per pass
    assert out.count("created label") == 1


def test_a_foreign_push_after_the_snapshot_is_stepped_over_not_a_stop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    train: ScriptedMerge, monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """p1-r10: a push fr did not make voids the approval, so the PR is stepped over like
    any unapproved one and the PRs behind it are tried."""
    _three_ready(world, tmp_path)
    seen: list[int] = []
    real_view = world.pr_view

    def _view(repo: str, number: int) -> dict[str, Any]:
        seen.append(number)
        if number == 101 and seen.count(101) == 3:  # after the settle and the snapshot
            world.prs[101]["head_oid"] = "sha-pushed"
        return real_view(repo, number)

    monkeypatch.setattr(world, "pr_view", _view)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "merge")[0] == (
        "merge b1: held: PR #101 head moved from sha-101 to sha-pushed by a push fr did "
        "not make; its approved-fr approval is void"
    )
    assert train.calls == [102, 103], out


def test_a_pass_dispatching_several_batches_checks_the_label_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """p1-r5 (R4: at most once per repo per pass), whatever the pass dispatches."""
    _proposed(world, tmp_path, 3)
    code, out = _drive(tmp_path, "--once", "--yes", "--single-pass")
    assert len(runner.dispatched) == 3, out
    assert world.calls.count("label_exists approved-fr") == 1


def test_the_pass_that_voids_an_approval_leaves_facts_and_board_without_the_label(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """p1-r9: the pass's facts were collected before it voided; the board it writes must
    not show the voided PR as approved."""
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    _pr_open(world, tmp_path)
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]
    _drive(tmp_path, "--once", "--yes")  # records the approval at sha-101
    world.prs[101]["head_oid"] = "sha-session"
    world.checks[101] = [{"name": "lint", "bucket": "pass"}]
    _drive(tmp_path, "--once", "--yes")  # voids it
    facts = load_facts(tmp_path / "facts.json")
    every = [*facts.prs, *facts.batch_prs, *(p for i in facts.issues for p in i.prs)]
    found = [p for p in every if p.number == 101]
    assert found and all("approved-fr" not in (p.labels or []) for p in found)
    rows = needs_you(facts, load_judgements(tmp_path / "judgements.yaml"))
    assert [r.text for r in rows if r.kind == "approve-pr"] == [
        "PR #101 changed since you approved it at sha-101: re-label to merge"
    ]


def test_the_drivers_board_asks_for_the_label_in_a_ci_none_repo(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """p1-r2: the driver holds a `ci none` repo's unlabelled PR, so its board says so."""
    _pr_open(world, tmp_path, labels=[])
    world.checks[101] = []
    world.all_checks[101] = {"pass": 0, "fail": 0, "pending": 0}
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: True)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "awaiting approval b1 (#101)" in out
    assert "awaiting approval" in _page(tmp_path)


def test_a_local_clone_tells_the_board_its_repo_is_ci_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fr.commands import triage_kanban_cmd

    class Clone:
        def origin_repo(self) -> str:
            return REPO.upper()

    monkeypatch.setattr(triage_kanban_cmd.Checkout, "at", classmethod(lambda cls, p: Clone()))
    monkeypatch.setattr(triage_batch_cmd, "ci_none_at", lambda checkout: True)
    facts = Facts(scope="s", kind="repo", collected_at="2026-10-11T00:00:00Z", repos=[REPO],
                  issues=[])  # fmt: skip
    assert triage_kanban_cmd.local_ci_none(facts) == frozenset({REPO})
    monkeypatch.setattr(triage_batch_cmd, "ci_none_at", lambda checkout: False)
    assert triage_kanban_cmd.local_ci_none(facts) == frozenset()


# --------------------------- red recovery (merge-train-safety §C, R9-R11)


def _red(world: World, tmp_path: Path) -> None:
    """PR #101 of b1 is red at sha-101 on `lint`."""
    _pr_open(world, tmp_path)
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]
    world.all_checks[101] = {"pass": 0, "fail": 1, "pending": 0}
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")


def _red_events(tmp_path: Path, bid: str = "b1") -> list[Any]:
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)
    return [e for e in batch.events if e.kind == "red_handback"]


def _red_needs(tmp_path: Path) -> list[str]:
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    facts = load_facts(tmp_path / "facts.json")
    needs = needs_you(facts, load_judgements(tmp_path / "judgements.yaml"))
    return [n.kind for n in needs if n.kind in ("failing-ci", "red-pr")]


def test_a_red_pr_is_handed_back_to_its_idle_session_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    ((target, text),) = messenger.messages
    assert target == BATCH_ITEM_B1, out
    assert "sha-101" in text and "lint" in text and "PR" in text
    (event,) = _red_events(tmp_path)
    assert (event.pr, event.head, event.checks, event.delivered) == (
        101,
        "sha-101",
        ["lint"],
        "session",
    )
    (line,) = _lines(out, "warn")
    assert "CI failing at sha-101: lint" in line and "handed back to its session" in line
    assert world.merged == []
    # the same red head again: nothing sent, nothing recorded, no warn line
    code, out = _drive(tmp_path, "--once", "--yes")
    assert len(messenger.messages) == 1 and len(_red_events(tmp_path)) == 1
    assert _lines(out, "warn") == []


def test_a_red_pr_whose_session_is_working_waits_and_records_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "working"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [] and _red_events(tmp_path) == []
    (line,) = _lines(out, "warn")
    assert "its session is working: nothing sent, retried next pass" in line


@pytest.mark.parametrize("status", ["absent", "done"])
def test_a_red_pr_with_no_session_to_take_it_needs_you_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner, status: str
) -> None:
    _red(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = status
    code, out = _drive(tmp_path, "--once", "--yes")
    (event,) = _red_events(tmp_path)
    assert event.delivered == "none" and event.head == "sha-101"
    assert messenger.messages == [] and messenger.dispatched == []  # no fresh session (§C)
    assert _red_needs(tmp_path) == ["red-pr"]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert len(_red_events(tmp_path)) == 1 and _lines(out, "warn") == []


def test_a_delivered_hand_back_suppresses_failing_ci_on_the_board(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    assert _red_needs(tmp_path) == ["failing-ci"]  # before anything was sent
    messenger.status[BATCH_ITEM_B1] = "idle"
    _drive(tmp_path, "--once", "--yes")
    assert _red_needs(tmp_path) == []
    world.prs[101]["head_oid"] = "sha-newer"  # a new red head is not covered
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    assert _red_needs(tmp_path) == ["failing-ci"]


def test_a_red_pr_at_an_fr_made_head_with_a_moved_base_is_updated_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    _fr_moved(tmp_path, "b1", 101, "sha-old", "sha-101")  # base m1; the clone now says otherwise
    checkout.behind.add("sha-101")
    messenger.status[BATCH_ITEM_B1] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [], out  # an update, not a hand-back
    assert world.prs[101]["head_oid"] == "sha-updated"
    updates = [
        e for b in load_judgements(tmp_path / "judgements.yaml").batches
        for e in b.events if e.kind == "update"
    ]  # fmt: skip
    assert [(e.head_before, e.head_after) for e in updates] == [
        ("sha-old", "sha-101"),
        ("sha-101", "sha-updated"),
    ]
    assert updates[-1].base == "origin/main@fetched"
    (line,) = _lines(out, "warn")
    assert "updated PR #101 to sha-updated" in line


def test_a_red_pr_at_an_fr_made_head_with_an_unmoved_base_is_handed_back(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _red(world, tmp_path)
    _fr_moved(tmp_path, "b1", 101, "sha-old", "sha-101")
    monkeypatch.setattr(checkout, "rev_parse", lambda ref: "m1")  # the base has not moved
    messenger.status[BATCH_ITEM_B1] = "idle"
    _drive(tmp_path, "--once", "--yes")
    assert len(messenger.messages) == 1 and world.prs[101]["head_oid"] == "sha-101"


def test_two_red_hand_backs_per_dispatch_then_the_third_needs_you(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "idle"
    for head in ("sha-a", "sha-b", "sha-c"):
        world.prs[101]["head_oid"] = head
        _drive(tmp_path, "--once", "--yes")
        (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    assert [e.delivered for e in _red_events(tmp_path)] == ["session", "session", "none"]
    assert len(messenger.messages) == 2


def test_the_base_rules_are_read_once_per_repo_per_pass_and_reach_the_merge_context(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """merge-train-safety §D: one read per pass; strict checks ride the context (R14)."""
    seen: list[bool] = []

    def _spy(ctx: Any, slot: Any, previous: Any) -> Any:
        seen.append(ctx.strict_checks)
        return MergeAttempt("merged", head="sha-101")

    monkeypatch.setattr(triage_batch_cmd, "merge_ready", _spy)
    world.rules = BaseRules(merge_queue=False, strict_checks=True)  # type: ignore[attr-defined]
    _pr_open(world, tmp_path)
    _drive(tmp_path, "--once", "--yes")
    assert seen == [True] and world.calls.count("base_rules") == 1


# ------------------- red recovery: no I/O for a decided head, deduped lines (p2-r2..r5)


def test_an_already_handed_back_red_head_builds_no_context_and_reads_no_base(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _red(world, tmp_path)
    messenger.status[BATCH_ITEM_B1] = "idle"
    _drive(tmp_path, "--once", "--yes")
    assert len(_red_events(tmp_path)) == 1
    built: list[str] = []
    fetched: list[int] = []
    real = triage_batch_cmd._Driver.merge_ctx

    def _spy(self: Any, facts: Any, repo: str) -> Any:
        built.append(repo)
        return real(self, facts, repo)

    monkeypatch.setattr(triage_batch_cmd._Driver, "merge_ctx", _spy)
    monkeypatch.setattr(checkout, "rev_parse", lambda ref: fetched.append(1) or "x")
    _drive(tmp_path, "--once", "--yes")
    assert built == [] and fetched == []


def test_a_red_pr_whose_runner_this_driver_lacks_says_so_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.driver import HOST

    _red(world, tmp_path)
    monkeypatch.setattr(type(HOST), "carries", lambda self, runner: False)
    sleeps: list[float] = []

    def _stop(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) == 2:
            raise _StopError

    monkeypatch.setattr(triage_batch_cmd, "_sleep", _stop)
    result = _drive_named(tmp_path, "--yes", "--interval", "5")
    lines = _lines(result.output, "warn")
    assert len(lines) == 1 and "left to that runner's driver" in lines[0]
    assert messenger.messages == [] and _red_events(tmp_path) == []


def test_a_failing_status_read_and_a_failing_send_are_each_said_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    _red(world, tmp_path)

    def _boom_status(items: Any) -> dict[str, str]:
        raise RuntimeError("socket down")

    monkeypatch.setattr(messenger, "session_statuses", _boom_status)

    def _two_passes() -> str:
        sleeps: list[float] = []

        def _stop(seconds: float) -> None:
            sleeps.append(seconds)
            if len(sleeps) == 2:
                raise _StopError

        monkeypatch.setattr(triage_batch_cmd, "_sleep", _stop)
        return str(_drive_named(tmp_path, "--yes", "--interval", "5").output)

    out = _two_passes()
    assert out.count("could not be read: socket down") == 1

    monkeypatch.setattr(messenger, "session_statuses", lambda items: {i.id: "idle" for i in items})

    def _boom_send(item: Any, text: str) -> None:
        raise RuntimeError("pane gone")

    monkeypatch.setattr(messenger, "message", _boom_send)
    out = _two_passes()
    assert out.count("failed, retried next pass: pane gone") == 1
    assert _red_events(tmp_path) == []


def test_a_reupdate_keeps_the_approval_and_leaves_draft_and_labels_alone(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _red(world, tmp_path)
    world.prs[101]["draft"] = True
    _fr_moved(tmp_path, "b1", 101, "sha-old", "sha-101")
    checkout.behind.add("sha-101")
    labels = list(world.prs[101]["labels"])
    _drive(tmp_path, "--once", "--yes")
    assert world.prs[101]["head_oid"] == "sha-updated"
    assert world.prs[101]["draft"] is True and world.prs[101]["labels"] == labels
    assert not any(c.startswith(("pr_ready", "label 101")) for c in world.calls)
    kinds = [e.kind for b in load_judgements(tmp_path / "judgements.yaml").batches
             for e in b.events]  # fmt: skip
    assert kinds.count("approval") == 1 and kinds.count("update") == 2  # none voided or re-recorded


# --------------------------- merge queues (merge-train-safety §D, R13)

QUEUE_CONFIG = {
    "version": {
        "source": {"file": "pyproject.toml", "key": "project.version"},
        "files": ["pyproject.toml"],
        "set": "python scripts/bump.py {version}",
    }
}


def _queue_repo(world: World, tmp_path: Path) -> None:
    """PR #101 of b1 is green and approved on a repo whose base requires a merge queue."""
    world.rules = BaseRules(merge_queue=True)  # type: ignore[attr-defined]
    _pr_open(world, tmp_path)


def _enqueued(tmp_path: Path, bid: str, pr: int, head: str, base: str, *outcomes: str) -> None:
    """Record, on *bid*, the driver's earlier enqueue of *pr* at *head* with the base at *base*."""
    path = tmp_path / "judgements.yaml"
    text = path.read_text("utf-8").replace("schema: 3\n", "schema: 9\n", 1)
    marker = f"branch: feat/batch-{bid}}}\n"
    extra = (
        f"      - {{kind: approval, at: 2026-10-01T10:30:00Z, pr: {pr}, head: {head}}}\n"
        f"      - {{kind: enqueue, at: 2026-10-01T10:40:00Z, pr: {pr}, head: {head}, "
        f"base: {base}}}\n"
        + "".join(
            f"      - {{kind: enqueue, at: 2026-10-01T10:50:00Z, pr: {pr}, head: {head}, "
            f"base: {base}, outcome: {o}, detail: not mergeable}}\n"
            for o in outcomes
        )
    )
    assert marker in text
    path.write_text(text.replace(marker, marker + extra, 1), "utf-8")


def test_a_queue_repo_enqueues_an_approved_green_pr_and_records_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.enqueued == [(101, "sha-101", "squash")] and world.merged == []  # type: ignore[attr-defined]
    assert _lines(out, "enqueue") == ["enqueue b1: enqueued PR #101 at sha-101"]
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == "b1")
    (event,) = [e for e in batch.events if e.kind == "enqueue"]
    assert (event.pr, event.head, event.base) == (101, "sha-101", "origin/main@fetched")
    # the next pass finds it in the queue and writes nothing
    code, out = _drive(tmp_path, "--once", "--yes")
    assert len(world.enqueued) == 1 and _lines(out, "enqueue") == []  # type: ignore[attr-defined]


def test_plan_mode_names_the_enqueue_and_writes_nothing(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    code, out = _drive(tmp_path)
    assert "enqueue b1: PR #101 at sha-101" in out and not hasattr(world, "enqueued")


def test_a_pr_ejected_with_the_base_moved_is_enqueued_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    _enqueued(tmp_path, "b1", 101, "sha-101", "old-base")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert len(world.enqueued) == 1  # type: ignore[attr-defined]
    assert "enqueue b1: enqueued PR #101 at sha-101" in out
    events = [e for e in _enqueue_events(tmp_path) if e.outcome == "enqueued"]
    assert [e.base for e in events] == ["old-base", "origin/main@fetched"]


def test_a_pr_ejected_with_the_base_unmoved_needs_you_and_is_not_enqueued_again(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    _enqueued(tmp_path, "b1", 101, "sha-101", "origin/main@fetched")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert not hasattr(world, "enqueued")
    assert "PR #101 left the merge queue unmerged" in out
    assert world.merged == []
    assert [e.outcome for e in _enqueue_events(tmp_path)] == ["enqueued", "ejected"]
    assert _queue_needs(tmp_path) == ["queue-ejected"]  # facts-only needs_you, from the events
    code, out = _drive(tmp_path, "--once", "--yes")  # recorded once per head: not again
    assert [e.outcome for e in _enqueue_events(tmp_path)] == ["enqueued", "ejected"]
    assert "left the merge queue" not in out


def test_a_pr_waiting_to_enter_the_queue_is_left_alone(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    _enqueued(tmp_path, "b1", 101, "sha-101", "old-base")
    world.queue_states[101] = QueueState(in_queue=False, auto_merge=True)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert not hasattr(world, "enqueued") and "left the merge queue" not in out


def test_a_refused_enqueue_is_a_held_line_and_records_only_the_refusal(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    world.refuse_enqueue = "gh: Pull request is not mergeable"  # type: ignore[attr-defined]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "held: PR #101 enqueue refused" in out
    assert [e.outcome for e in _enqueue_events(tmp_path)] == ["refused"]
    assert _queue_needs(tmp_path) == []  # one refusal is a retry, not yet a need


def test_a_version_block_holds_a_queue_repo(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.config = QUEUE_CONFIG
    _queue_repo(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "fr does not reserve versions through one" in out
    assert not hasattr(world, "enqueued") and world.merged == []


def test_forge_api_rest_holds_a_queue_repo(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    monkeypatch.setenv("FR_FORGE_API", "rest")
    _queue_repo(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "forge.api rest cannot enqueue" in out
    assert not hasattr(world, "enqueued") and world.merged == []


def test_a_repo_without_a_queue_merges_as_before(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _pr_open(world, tmp_path)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [(101, "sha-101", "squash")] and not hasattr(world, "enqueued")
    assert "pr_queue_state" not in " ".join(world.calls)


def test_a_clone_without_origin_head_does_not_abort_a_pass_that_has_nothing_to_enqueue(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """Queue reads are for repos with a candidate, and an unknowable default branch is no
    queue, never a failed pass (the cloud driver's clone has no origin/HEAD)."""
    from fr.triage.gitseam import GitError

    def _unset() -> str:
        raise GitError("cannot tell the default branch (origin/HEAD is unset)")

    _pr_open(world, tmp_path, draft=True, labels=[])
    world.checks[101] = [{"name": "lint", "bucket": "fail"}]
    world.all_checks[101] = {"pass": 0, "fail": 1, "pending": 0}
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    monkeypatch.setattr(checkout, "default_branch", _unset)
    code, out = _drive(tmp_path)  # plan mode: a failing PR is no candidate
    assert "base_rules" not in world.calls, out
    world.checks[101] = [{"name": "test", "bucket": "pass"}]
    world.all_checks[101] = {"pass": 1, "fail": 0, "pending": 0}
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    code, out = _drive(tmp_path)  # a candidate, but the branch is unknowable: read as no queue
    assert code == 0 and "Traceback" not in out, out


def _enqueue_events(tmp_path: Path, bid: str = "b1") -> list[Any]:
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == bid)
    return [e for e in batch.events if e.kind == "enqueue"]


def _queue_needs(tmp_path: Path) -> list[str]:
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    facts = load_facts(tmp_path / "facts.json")
    needs = needs_you(facts, load_judgements(tmp_path / "judgements.yaml"))
    return [n.kind for n in needs if n.kind in ("queue-ejected", "enqueue-refused")]


def test_an_approved_draft_is_readied_then_enqueued(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.rules = BaseRules(merge_queue=True)  # type: ignore[attr-defined]
    _pr_open(world, tmp_path, draft=True)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert world.prs[101]["draft"] is False
    assert world.calls.index("pr_ready 101") < world.calls.index("pr_enqueue 101")
    assert world.enqueued == [(101, "sha-101", "squash")]  # type: ignore[attr-defined]


def test_a_draft_whose_label_is_gone_is_not_enqueued(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.rules = BaseRules(merge_queue=True)  # type: ignore[attr-defined]
    _pr_open(world, tmp_path, draft=True, labels=[])
    _drive(tmp_path, "--once", "--yes")
    assert "pr_enqueue 101" not in world.calls


def test_two_refusals_at_one_head_become_a_need_and_stop_the_retries(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    world.refuse_enqueue = "gh: Pull request is not mergeable"  # type: ignore[attr-defined]
    for _ in range(3):
        _drive(tmp_path, "--once", "--yes")
        (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    assert world.calls.count("pr_enqueue 101") == 2  # the third pass does not try
    assert [e.outcome for e in _enqueue_events(tmp_path)] == ["refused", "refused"]
    assert _queue_needs(tmp_path) == ["enqueue-refused"]


def test_an_unknown_default_branch_holds_the_candidate_repo_and_says_so_once(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    from fr.triage.gitseam import GitError

    def _unset() -> str:
        raise GitError("origin/HEAD is unset")

    _pr_open(world, tmp_path)
    monkeypatch.setattr(checkout, "default_branch", _unset)
    code, out = _drive(tmp_path)
    assert "cannot tell derio-net/super-fr's default branch: queue mode unknown" in out
    assert out.count("queue mode unknown") >= 1 and world.merged == []


def test_removing_the_label_after_the_enqueue_dequeues_the_pr_and_a_relabel_enqueues_it(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _queue_repo(world, tmp_path)
    _drive(tmp_path, "--once", "--yes")
    assert len(world.enqueued) == 1  # type: ignore[attr-defined]
    world.prs[101]["labels"] = []  # the operator un-approves it
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    code, out = _drive(tmp_path, "--once", "--yes")
    assert "dequeued PR #101: its approved-fr approval is gone" in out
    assert world.dequeued == [101]  # type: ignore[attr-defined]
    assert [e.outcome for e in _enqueue_events(tmp_path)] == ["enqueued", "dequeued"]
    world.prs[101]["labels"] = ["approved-fr"]
    (tmp_path / "facts.json").write_text(json.dumps(world.facts().to_json()), "utf-8")
    _drive(tmp_path, "--once", "--yes")
    assert len(world.enqueued) == 2 and _queue_needs(tmp_path) == []  # type: ignore[attr-defined]


def test_a_queue_repo_red_pr_is_never_re_updated(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # fmt: skip
    """p3-r7: a pre-queue update event does not make fr push an update in a queue repo."""
    world.rules = BaseRules(merge_queue=True)  # type: ignore[attr-defined]
    _red(world, tmp_path)
    _fr_moved(tmp_path, "b1", 101, "sha-old", "sha-101")
    messenger.status[BATCH_ITEM_B1] = "idle"
    _drive(tmp_path, "--once", "--yes")
    assert world.prs[101]["head_oid"] == "sha-101" and len(messenger.messages) == 1


def test_settle_of_a_carried_repo_waits_by_the_keys_repo() -> None:
    from fr.triage.batch_drive import Action
    from fr.triage.claim_sync import ClaimEnv
    from fr.triage.scope_config import ScopeConfig

    facts = Facts(
        viewer="operator", scope="derio-net--super-fr", kind="repo",
        collected_at=NOW.isoformat(), repos=[REPO], issues=[],
    )  # fmt: skip
    env = ClaimEnv(me="s-me", config=ScopeConfig(), facts=facts, client_for=lambda r: None)  # type: ignore[arg-type,return-value]
    settle = Action("settle", "", "closed", key="super-fr#4")  # names no batch
    assert triage_batch_cmd.read_repo(settle, {}, env) == REPO
    assert triage_batch_cmd.read_repo(settle, {}, None) is None
    merge = Action("merge", "b1", "x")
    assert triage_batch_cmd.read_repo(merge, {"b1": REPO}, env) == REPO
    assert "settle" in triage_batch_cmd._LIVE_READ_ACTIONS


def test_a_yes_pass_settles_a_closed_hit_no_batch_holds(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    from fr.triage.model import StaleInProgress

    world.issues[1] = "closed"
    world.stale_in_progress = [
        StaleInProgress(key="super-fr#1", title="t", url="https://example.com/1", state="stale")
    ]
    _state(tmp_path, world)
    code, out = _drive(tmp_path, "--once")
    assert _lines(out, "settle") == ["settle super-fr#1: closed"]
    assert "label 1" not in world.calls  # plan mode writes nothing
    code, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "settle") == ["settle super-fr#1: unlabelled"]
    assert "label 1" in world.calls


def test_a_yes_pass_leaves_a_closed_hit_of_a_skipped_repo_alone(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """p1-r6: the carried-repo filter holds at pass level, not only in `read_repo`."""
    from fr.triage.model import Skipped, StaleInProgress

    world.issues[1] = "closed"
    world.stale_in_progress = [
        StaleInProgress(key="super-fr#1", title="t", url="https://example.com/1", state="stale")
    ]
    world.skipped = [Skipped(repo=REPO, reason="collect could not read it")]
    _state(tmp_path, world)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "settle") == []
    assert "label 1" not in world.calls


def test_a_yes_pass_clears_a_release_pending_member(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    """p1-r5: a closed member whose own marker stands (release-pending) is settled by
    `--once --yes`: its marker is released and its labels removed."""
    from fr.triage.claims import Marker, parse_marker, render_marker
    from fr.triage.model import Scope, StaleInProgress
    from fr.triage.scope_config import scope_id

    me = scope_id(Scope(kind="repo", target=REPO))
    marker = Marker(signer=me, batch="b1", claimed=NOW, heartbeat=NOW, expires=NOW + timedelta(1))
    world.comments[1] = [
        {
            "author": "operator",
            "body": render_marker(marker),
            "created_at": NOW.isoformat(),
            "id": 7,
        }
    ]
    world.issues[1] = "closed"
    world.stale_in_progress = [
        StaleInProgress(
            key="super-fr#1", title="t", url="https://example.com/1", state="release-pending"
        )
    ]
    _state(tmp_path, world)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert _lines(out, "settle") == ["settle super-fr#1: released"]
    assert "label 1" in world.calls
    released = parse_marker(world.comments[1][0]["body"])
    assert released is not None and released.released is not None


# ---------------------- conflicting archive and export PRs (merge-truth R12, §E)

CLOSEOUT_B1 = f"{REPO}/run/closeout-b1"


def _archive_conflict_yaml(head: str, delivered: str, minute: int) -> str:
    return (
        f"      - {{kind: archive_conflict, at: '2026-10-02T11:59:{minute:02d}Z', head: {head}, "
        f"pr: 201, delivered: {delivered}}}\n"
    )


def _conflicting_archive(world: World, tmp_path: Path, events: str = "") -> None:
    """b1 closing (run r1), its archive PR #201 green and conflicting at sha-201."""
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"],
             mergeable="CONFLICTING")  # fmt: skip
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1 + events))
    path = tmp_path / "judgements.yaml"
    path.write_text(path.read_text("utf-8").replace("schema: 3\n", "schema: 10\n"), "utf-8")


def _archive_conflicts(tmp_path: Path) -> list[Any]:
    batch = load_judgements(tmp_path / "judgements.yaml").batches[0]
    return [e for e in batch.events if e.kind == "archive_conflict"]


def test_archive_conflict_messages_an_idle_closeout_session(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    _conflicting_archive(world, tmp_path)
    messenger.status[CLOSEOUT_B1] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [] and not [c for c in world.calls if c.startswith("pr_merge")], out
    ((target, text),) = messenger.messages
    assert target == CLOSEOUT_B1
    assert "PR #201" in text and "chore/archive-p1" in text and "sha-201" in text
    assert "main" in text and "push" in text
    (event,) = _archive_conflicts(tmp_path)
    assert (event.head, event.pr, event.delivered, event.handle) == (
        "sha-201", 201, "session", CLOSEOUT_B1)  # fmt: skip
    assert _lines(out, "archive-conflict") == [
        f"archive-conflict b1: handed back to its close-out session {CLOSEOUT_B1}"
    ], out
    _drive(tmp_path, "--once", "--yes")  # the same head is never handed back twice
    assert len(messenger.messages) == 1 and len(_archive_conflicts(tmp_path)) == 1


def test_archive_conflict_brief_enters_isolation_on_the_archive_branch() -> None:
    """p2-r1: a fresh session starts in the driver's base clone, so step 1 enters the
    archive branch's workspace as `conflict_brief` does, never `git switch` there."""
    from fr.triage.batch_dispatch import archive_conflict_brief
    from fr.triage.model import Batch

    batch = Batch.model_validate({"id": "b1", "title": "Fix it", "ids": ["super-fr#1"]})
    text = archive_conflict_brief(
        batch, pr=201, head="sha-201", branch="chore/archive-p1", base="origin/main"
    )
    assert text.startswith("Archive PR conflict on batch b1 ")
    step1 = next(line for line in text.splitlines() if line.startswith("1. "))
    assert "`fr isolation up --branch chore/archive-p1`" in step1
    assert "git switch" not in text
    assert "at head sha-201, conflicts with" in text


@pytest.mark.parametrize("status", ["working", "blocked"])
def test_archive_conflict_waits_while_the_closeout_session_works(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    status: str,
) -> None:  # fmt: skip
    _conflicting_archive(world, tmp_path)
    messenger.status[CLOSEOUT_B1] = status
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [] and messenger.dispatched == [], out
    assert _archive_conflicts(tmp_path) == []
    assert "nothing sent, retried next pass" in out


@pytest.mark.parametrize("status", ["done", "absent"])
def test_archive_conflict_starts_a_fresh_item_when_the_closeout_is_done(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner,
    status: str,
) -> None:  # fmt: skip
    _conflicting_archive(world, tmp_path)
    messenger.status[CLOSEOUT_B1] = status
    code, out = _drive(tmp_path, "--once", "--yes")
    (item,) = messenger.dispatched
    assert item.id == f"{REPO}/run/archive-conflict-b1-1", out
    assert item.unit == "run" and item.payload["branch"] == "chore/archive-p1"
    assert "PR #201" in item.payload["brief"] and "sha-201" in item.payload["brief"]
    (event,) = _archive_conflicts(tmp_path)
    assert event.delivered == "fresh" and messenger.messages == []


def test_archive_conflict_held_records_a_stop_and_raises_the_need(
    tmp_path: Path, world: World, checkout: DriveCheckout, messenger: MessengerRunner
) -> None:
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    earlier = _archive_conflict_yaml("sha-a", "session", 1) + _archive_conflict_yaml(
        "sha-b", "fresh", 2
    )
    _conflicting_archive(world, tmp_path, earlier)
    messenger.status[CLOSEOUT_B1] = "idle"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert messenger.messages == [] and messenger.dispatched == [], out
    held = _archive_conflicts(tmp_path)[-1]
    assert (held.head, held.delivered, held.handle) == ("sha-201", "held", None)
    stop = load_stops(tmp_path)["archive:b1"]
    assert (stop.head, stop.reason) == ("sha-201", "archive PR #201 conflicts")
    assert "b1" not in load_stops(tmp_path)  # never the batch PR's key (p2-r2)
    facts = load_facts(tmp_path / "facts.json")
    rows = needs_you(facts, load_judgements(tmp_path / "judgements.yaml"))
    (need,) = [r for r in rows if r.kind == "archive-conflict"]
    assert need.ref == "b1" and "PR #201" in need.text
    assert not [r for r in rows if r.kind in ("failing-ci", "merge-conflict")]
    code, out = _drive(tmp_path, "--yes")  # the loop ends on it: only the operator can act
    assert code == 3 and "only blocked batches remain (b1)" in out, out


def test_merged_archive_pr_clears_its_stop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    from fr.triage.merge_stops import MergeStop, record_stop

    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    record_stop(tmp_path, "archive:b1", MergeStop("sha-old", "archive PR #201 conflicts", "t"))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert [m[0] for m in world.merged] == [201], out
    assert "archive:b1" not in load_stops(tmp_path)


def test_forge_refused_archive_merge_records_a_stop(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + _CLOSEOUT_R1))
    world.refuse_merge = "protected branch"
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 1 and world.merged == [], out
    stop = load_stops(tmp_path)["archive:b1"]
    assert stop.head == "sha-201" and "protected branch" in stop.reason


def test_conflicting_export_pr_goes_straight_to_needs_you_with_stop_key_export_repo(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    from fr.triage.model import load_facts
    from fr.triage.views import needs_you

    sha = _export_pr(world, git_checkout.path, mergeable="CONFLICTING")
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))

    code, out = _export_drive(state, "--once", "--yes")

    assert world.merged == [], out
    assert _exports(state) == [("1", 40, False)]
    (line,) = _lines(out, "export-conflict")  # p2-r5: its own kind, not archive-conflict
    assert line.startswith(f"export-conflict wave 1 {REPO}: export PR #40 conflicts"), out
    assert _lines(out, "archive-conflict") == []
    stop = load_stops(state)[f"export:{REPO}"]
    assert (stop.head, stop.reason) == (sha, "export PR #40 conflicts")
    facts = load_facts(state / "facts.json")
    rows = needs_you(facts, load_judgements(state / "judgements.yaml"), stops=load_stops(state))
    (need,) = [r for r in rows if r.kind == "archive-conflict"]
    assert need.ref == REPO and "export PR #40" in need.text
    # once the export PR merges, its stop clears
    world.prs[40]["mergeable"] = "MERGEABLE"
    code, out = _export_drive(state, "--once", "--yes")
    assert world.merged == [(40, sha, "squash")], out
    assert f"export:{REPO}" not in load_stops(state)


@pytest.mark.parametrize(("state_", "line"), [
    ("MERGED", "recorded export PR #40 as merged"),
    ("CLOSED", "recorded export PR #40 as closed"),
])  # fmt: skip
def test_an_export_pr_merged_or_closed_by_hand_clears_its_conflict_stop(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout, state_: str, line: str
) -> None:
    """p2-r3: the export conflict's stop is over once the PR is merged by hand
    (export-reconcile) or closed (export-closed), not only when the driver merges it."""
    sha = _export_pr(world, git_checkout.path, mergeable="CONFLICTING")
    state = _finished_wave(tmp_path, world, exports=_recorded(sha))
    _export_drive(state, "--once", "--yes")
    assert f"export:{REPO}" in load_stops(state)
    world.prs[40]["state"] = state_
    code, out = _export_drive(state, "--once", "--yes")
    assert line in out, out
    assert f"export:{REPO}" not in load_stops(state)


def test_viewed_takes_head_and_mergeable_from_the_same_fresh_read() -> None:
    """p2-r6: a fresh `pr_view`'s `mergeable` describes its own head; pairing it with
    the facts' older head would pin a merge to a head the verdict never saw."""
    from fr.commands.triage_batch_cmd import _viewed
    from fr.triage.batch_drive import LivePr

    old = LivePr(number=201, state="OPEN", draft=False, head="sha-old", checks="green")
    view = {"head_oid": "sha-new", "mergeable": "MERGEABLE", "base_ref": "main"}
    got = _viewed(old, view)
    assert (got.head, got.mergeable, got.base) == ("sha-new", "MERGEABLE", "main")
    assert _viewed(old, {"mergeable": "CONFLICTING"}).head == "sha-old"  # no head: kept


@pytest.mark.parametrize("found_by", ["facts", "head"])
def test_an_archive_pr_pushed_between_its_view_and_its_checks_is_never_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, found_by: str,
) -> None:  # fmt: skip
    """p2-r6 (security): the merge is pinned to a head, so the green verdict must be
    for that head. The head is read, then the checks, then the head again; a push in
    between makes the verdict pending this pass: no archive, no `pr_merge`."""
    _closing(world, tmp_path)
    world.pr(201, "chore/archive-p1", [], files=["docs/superpowers/runs/r1.yaml"])
    events = _dispatch_event("b1") + _CLOSEOUT_R1
    _state(tmp_path, world, _batch("b1", 1, events=events))
    if found_by == "head":  # opened after the collect: found by its head alone
        facts = json.loads((tmp_path / "facts.json").read_text("utf-8"))
        facts["prs"] = [p for p in facts["prs"] if p["number"] != 201]
        (tmp_path / "facts.json").write_text(json.dumps(facts), "utf-8")
    real_view = world.pr_view
    views: list[int] = []

    def _pushed_after_first_view(repo: str, number: int) -> dict[str, Any]:
        got = real_view(repo, number)
        if number == 201:
            views.append(number)
            if len(views) == 1:  # a push lands right after the first read of the head
                world.prs[201]["head_oid"] = "sha-pushed"
        return got

    monkeypatch.setattr(world, "pr_view", _pushed_after_first_view)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert world.merged == [] and not [c for c in world.calls if c.startswith("pr_merge")], out
    assert _lines(out, "archive") == [], out
    assert len(views) >= 2  # the head was read on both sides of the checks

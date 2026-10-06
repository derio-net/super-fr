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
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd, triage_kanban_cmd
from fr.gh import GhError
from fr.triage import drive_lock
from fr.triage.batch_merge import HeadMovedError, MergeAttempt, MergeStopError
from fr.triage.collect import CollectStats
from fr.triage.errors import ForgeError
from fr.triage.gitseam import Checkout
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
        self.refuse_create: str | None = None
        self.create_files: list[str] = []  # what a PR pr_create opens changes
        self.head_of: Any = lambda branch: "sha-created"  # the head a pushed branch has
        self.calls: list[str] = []
        self.comments: dict[int, list[dict[str, Any]]] = {}
        self.config: dict[str, Any] | None = None

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
            **kw,
        }

    def facts(self) -> Facts:
        prs = {n: self._pr(n) for n in self.prs}
        linked = {i: [prs[n] for n, p in self.prs.items() if i in p["closes"]] for i in self.issues}
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
                    title=f"issue {i}",
                    state=s,  # type: ignore[arg-type]
                    url=f"https://github.com/{REPO}/issues/{i}",
                    prs=linked[i],
                )
                for i, s in self.issues.items()
            ],  # fmt: skip
            prs=[prs[n] for n, p in self.prs.items() if not p["closes"] and p["state"] == "OPEN"],
            config={REPO: TriageConfig.model_validate(self.config)} if self.config else {},
            viewer="operator",
        )

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
        )

    # -- the GhClient adapter
    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(f"pr_view {number}")
        p = self.prs[number]
        view = {k: p[k] for k in ("state", "draft", "head_oid", "head_ref")}
        merge = p.get("merge_commit", f"merge-{number}")
        return {**view, "base_ref": p.get("base", "main"), "merge_commit": merge}

    def pr_required_checks(self, repo: str, number: int) -> list[dict[str, Any]]:
        return list(self.checks.get(number, [{"name": "test", "bucket": "pass"}]))

    def wait_required_checks(self, repo: str, number: int, **kw: Any) -> list[dict[str, Any]]:
        raise AssertionError("the driver never waits for checks")

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
        return list(self.comments.get(number, []))

    def ensure_labels(self, repo: str, labels: list[Any]) -> None:
        self.calls.append("ensure_labels")

    def edit_issue_labels(self, repo: str, number: int, **kw: Any) -> None:
        self.calls.append(f"label {number}")

    def comment_issue(self, repo: str, number: int, body: str) -> None:
        self.comments.setdefault(number, []).append({"author": "fr", "body": body})


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
        self.files: dict[tuple[str, str], str] = {}
        self.release_probes: list[str] = []
        self.added: dict[str, tuple[str, ...]] = {}  # merge commit -> paths it added
        self.live: set[str] = set()  # paths still on origin/main

    def origin_repo(self) -> str | None:
        return REPO

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

    def fast_forward(self) -> None:
        self.forwarded += 1

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


@pytest.fixture(autouse=True)
def _sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "home" / ".config"))
    monkeypatch.setattr(triage_batch_cmd, "_now", lambda: NOW)
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: False)


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> World:
    w = World()
    passes: list[int] = []

    def _recollect(scope: Any, target: Path) -> None:
        passes.append(1)
        (target / "facts.json").write_text(json.dumps(w.facts().to_json()), "utf-8")

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: w)
    w.passes = passes  # type: ignore[attr-defined]
    return w


@pytest.fixture
def checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: World) -> DriveCheckout:
    fake = DriveCheckout(tmp_path / "clone", world)
    fake.path.mkdir()
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: fake)
    return fake


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> FakeRunner:
    fake = FakeRunner()
    monkeypatch.setattr(triage_batch_cmd, "load_runner", lambda name: fake)
    return fake


@pytest.fixture
def sleeps(monkeypatch: pytest.MonkeyPatch) -> list[float]:
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
    code, out = _drive(tmp_path, "--once", "--yes", "--max-inflight", "2")
    assert code == 0, out
    assert [i.id for i in runner.dispatched] == [f"{REPO}/run/batch-b1", f"{REPO}/run/batch-b2"]
    assert _lines(out, "dispatch") == [
        f"dispatch b1: dispatched to fake as {REPO}/run/batch-b1",
        f"dispatch b2: dispatched to fake as {REPO}/run/batch-b2",
    ]
    assert "brief:" not in out  # dispatch_batch's own plan is not echoed
    assert _events(tmp_path, "b1") == ["dispatch"]
    assert _events(tmp_path, "b3") == []
    assert out.rstrip().splitlines()[-1] == "in flight 2, merged 0, pending 1, closing 0"


def test_a_driven_dispatch_carries_its_waves_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    (item,) = runner.dispatched
    assert item.payload["group"] == "drive-wave-1"


def test_workspace_prefix_renames_the_group(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes", "--workspace-prefix", "bugfix")
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
    code, out = _drive(tmp_path, "--once", "--yes", "b1", "--workspace-prefix", "bugfix")
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
    world.pr(101, "feat/batch-b1", [1], draft=True)
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
    code, out = _drive(tmp_path, "--once", "--yes")
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
        lambda w: w.prs[101].update(draft=True),
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
    assert not any(c.startswith(("ready", "approve")) for c in world.calls)


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
    assert _lines(out, "warn") == ["warn b1: PR #101 CI failing at sha-101: lint"]
    assert world.merged == [(101, "sha-101", "squash")]
    assert sleeps[:2] == [5, 5]


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
    assert _lines(out, "adopt") == [] and _events(tmp_path, "b1") == ["dispatch", "closeout"]


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


# ------------------------------------------------- the board, every pass (R11)


def _page(tmp_path: Path) -> str:
    return (tmp_path / "board.html").read_text(encoding="utf-8")


def test_an_acting_once_pass_writes_the_board_and_shows_its_own_dispatch(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    page = _page(tmp_path)
    start = page.index('data-column="running"')
    assert 'id="card-b1"' in page[start : page.index("</section>", start)]


def test_a_pass_that_acts_on_nothing_still_writes_the_board(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    world.issues[1] = "open"
    world.pr(101, "feat/batch-b1", [1], draft=True)
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
    _drive(tmp_path, "--once", "--yes")
    assert f"focus b1 --repo {REPO} --dir {tmp_path.resolve()}" in _page(tmp_path)
    seen: list[list[str]] = []

    def _spy(scope: Any, target: Path, *, scope_args: Any, **kw: Any) -> Any:
        seen.append(list(scope_args))
        return target / "board.html", 0

    monkeypatch.setattr(triage_kanban_cmd, "write_board", _spy)
    monkeypatch.setattr(triage_batch_cmd, "state_dir", lambda scope, override: tmp_path)
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
    code, out = _drive(tmp_path, "--once", "--yes")
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
    code, out = _drive(tmp_path, "--once", "--yes", "--checkout", f"{REPO}={checkout.path}")
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
    assert _drive(tmp_path, "--once", "--yes")[0] == 0
    code, out = _drive(tmp_path, "--once", "--yes")
    assert len(runner.dispatched) == 2
    assert _lines(out, "dispatch") == []
    assert code == 3  # both in flight, nothing to do


def test_a_kill_between_launch_and_event_never_launches_twice(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner
) -> None:
    _proposed(world, tmp_path, 1)
    runner.live.add(f"{REPO}/run/batch-b1")  # launched, event never written
    code, out = _drive(tmp_path, "--once", "--yes")
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
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out  # the update push is an act
    assert world.merged == [] and runner.dispatched == []
    assert _lines(out, "dispatch") == [
        "dispatch b2: held: waits on b1, whose merge did not land this pass"
    ]
    assert out.rstrip().splitlines()[-1] == "in flight 1, merged 0, pending 1, closing 0"


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
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 3, out
    assert world.merged == [] and runner.dispatched == []
    assert _lines(out, "merge") == ["merge b1: held: PR #101 is pending: test"]
    assert "merged 0" in out


@pytest.mark.parametrize("required", [True, False], ids=["required-checks", "no-required"])
def test_a_head_that_moves_after_the_snapshot_is_not_merged(
    tmp_path: Path, world: World, checkout: DriveCheckout, runner: FakeRunner,
    monkeypatch: pytest.MonkeyPatch, required: bool,
) -> None:  # fmt: skip
    """rg-2: the merge is pinned to the head whose checks were judged."""
    _pr_open(world, tmp_path)
    if not required:
        world.checks[101] = []
    views: list[int] = []
    real_view = world.pr_view

    def _view(repo: str, number: int) -> dict[str, Any]:
        views.append(number)
        if len(views) == 2:  # after the snapshot read it: someone pushes
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
    code, out = _drive(tmp_path, "--once", "--yes", "b2")
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
    code, out = _drive(tmp_path, "--once", "--yes")
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
    code, out = _drive(tmp_path, "--once", "--yes")
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

    def _recollect(scope: Any, target: Path) -> None:
        lock.write_text(rival)
        real(scope, target)

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    code, out = _drive(tmp_path, "--once", "--yes")
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

    def _recollect(scope: Any, target: Path) -> None:
        seen.append(lock.read_text())
        real(scope, target)

    monkeypatch.setattr(triage_batch_cmd, "recollect", _recollect)
    assert _drive(tmp_path, "--once", "--yes")[0] == 0
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
    code, out = _drive(tmp_path, "--once", "--yes")
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
        return None, target / "facts.json", CollectStats()

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
    seen: list[int] = []
    real_view = world.pr_view

    def _view(repo: str, number: int) -> dict[str, Any]:
        seen.append(number)
        if number == 101 and seen.count(101) == 2:
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


@pytest.mark.parametrize("outcome", ["failing", "draft"])
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


# ------------------------------------- per-wave state export (pages-goal R13, §I)

EXPORT_CONFIG = {"export": {"path": "docs/triage"}}
SCOPE_DIR = "docs/triage/derio-net--super-fr"
EXPORT_HEAD = "chore/triage-state-wave-1"
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


@pytest.fixture
def git_checkout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, world: World) -> GitDriveCheckout:
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
    _git(clone, "push", "--quiet", "--force", "origin", f"export-pr:{EXPORT_HEAD}")
    _git(clone, "checkout", "--quiet", "main")
    world.pr(40, EXPORT_HEAD, [], **{"head_oid": sha, "files": [f"{SCOPE_DIR}/j.yaml"], **kw})
    return sha


def _export_drive(state: Path, *args: str) -> tuple[int, str]:
    return _drive(state, "--keep-sessions", *args)


def test_plan_mode_prints_the_export_and_writes_nothing(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    state = _finished_wave(tmp_path, world)
    code, out = _export_drive(state)
    assert code == 0, out
    assert f"export wave 1 {REPO}: to {SCOPE_DIR} on {EXPORT_HEAD}" in out
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
    _git(clone, "push", "--quiet", "origin", f"stale:{EXPORT_HEAD}")
    _git(clone, "checkout", "--quiet", "main")
    state = _finished_wave(tmp_path, world)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    (number,) = [n for n, p in world.prs.items() if p["head_ref"] == EXPORT_HEAD]
    assert f"export wave 1 {REPO}: opened PR #{number}" in out
    assert f"pr_create {EXPORT_HEAD} -> main" in world.calls
    assert _exports(state) == [("1", number, False)]
    _git(clone, "fetch", "--quiet", "origin")
    tip = f"origin/{EXPORT_HEAD}"
    assert _heads(state) == [_git(clone, "rev-parse", tip).strip()]  # the SHA it pushed
    assert _git(clone, "rev-parse", f"{tip}^") == _git(clone, "rev-parse", "origin/main")
    changed = _git(clone, "diff", "--name-only", "origin/main", tip).split()
    assert sorted(changed) == [f"{SCOPE_DIR}/board/manifest.yaml", f"{SCOPE_DIR}/judgements.yaml"]
    assert not (state / "export" / "1").exists()  # the scratch worktree is gone


def test_an_export_that_changes_nothing_records_no_pr_and_opens_none(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    from fr.triage.state_sync import export_state

    state = _finished_wave(tmp_path, world)
    clone = git_checkout.path
    export_state(state, clone, SCOPE_DIR)
    _git(clone, "add", ".")
    _git(clone, "commit", "--quiet", "-m", "already exported")
    _git(clone, "push", "--quiet", "origin", "main")

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert f"{SCOPE_DIR} is unchanged; recorded with no PR" in out
    assert _exports(state) == [("1", None, False)]
    assert not any(c.startswith("pr_create") for c in world.calls)
    _git(clone, "fetch", "--quiet", "origin")
    assert EXPORT_HEAD not in _git(clone, "branch", "-r")


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
    tip = _git(clone, "rev-parse", f"origin/{EXPORT_HEAD}").strip()
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
    world.pr(40, EXPORT_HEAD, [], head_oid=ghost, files=[f"{SCOPE_DIR}/j.yaml"])

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
    (new,) = [n for n, p in world.prs.items() if p["head_ref"] == EXPORT_HEAD and n != 40]
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
                if p["head_ref"] == EXPORT_HEAD:
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
    (number,) = [n for n, p in world.prs.items() if p["head_ref"] == EXPORT_HEAD]
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
    assert EXPORT_HEAD not in _git(clone, "ls-remote", "origin")


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
    """Wave *n*'s batch is closed out and archived now."""
    path = state / "judgements.yaml"
    line = _dispatch_event(f"w{n}")
    path.write_text(path.read_text("utf-8").replace(line, line + ARCHIVED), "utf-8")


def test_one_pr_covers_three_finished_waves_and_its_merge_marks_all_three(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout
) -> None:
    state = _finished_wave(tmp_path, world, waves=(1, 2, 3))

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    prs = [n for n, p in world.prs.items() if p["head_ref"].startswith("chore/triage-state-")]
    assert len(prs) == 1 and world.prs[prs[0]]["head_ref"] == "chore/triage-state-wave-3"
    assert _lines(out, "export") == [
        f"export wave 3 {REPO}: opened PR #{prs[0]} from chore/triage-state-wave-3 at "
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
    (first,) = [n for n, p in world.prs.items() if p["head_ref"] == "chore/triage-state-wave-2"]
    _finish(state, 3)  # wave 3 finishes while PR `first` is open

    code, out = _export_drive(state, "--once", "--yes")

    assert _lines(out, "export") == [] and _lines(out, "export-merge") == []
    assert not [p for p in world.prs.values() if p["head_ref"] == "chore/triage-state-wave-3"]
    assert _exports(state) == [("1", first, False), ("2", first, False)]

    world.checks[first] = [{"name": "test", "bucket": "pass"}]
    assert _export_drive(state, "--once", "--yes")[0] == 0  # merges `first`
    assert [m[0] for m in world.merged] == [first]
    code, out = _export_drive(state, "--once", "--yes")  # then wave 3, alone

    assert code == 0, out
    (second,) = [n for n, p in world.prs.items() if p["head_ref"] == "chore/triage-state-wave-3"]
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
    changed = _git(clone, "diff", "--name-only", "origin/main", f"origin/{EXPORT_HEAD}").split()
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
    world.pr(40, EXPORT_HEAD, [], cross_repo=True, author="someone", head_oid="f" * 40)

    code, out = _export_drive(state, "--once", "--yes")

    assert code == 0, out
    assert _lines(out, "warn") == []
    (mine,) = [n for n, p in world.prs.items() if p["head_ref"] == EXPORT_HEAD and n != 40]
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
    export_state(state, clone, SCOPE_DIR)
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
    remote = _git(clone, "ls-remote", "origin", f"refs/heads/{EXPORT_HEAD}")
    assert remote.split()[0] == sha  # nothing pushed over it
    assert _exports(state) == []
    assert not any(c.startswith("pr_create") for c in world.calls)


def test_extra_orphans_are_warned_stale_once_each(
    tmp_path: Path, world: World, git_checkout: GitDriveCheckout, sleeps: list[float]
) -> None:
    """p4-r16: PR #40 (wave 1) is reused; #45 on another wave's branch is named stale."""
    _export_pr(world, git_checkout.path)
    world.pr(45, "chore/triage-state-wave-0", [], head_oid="e" * 40)
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
    assert load_judgements(tmp_path / "judgements.yaml").schema_ == 5


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

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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.cli import app
from fr.commands import triage_batch_cmd, triage_cmd
from fr.gh import GhError
from fr.triage.model import Facts, Issue, PullRequest, TriageConfig, load_judgements
from typer.testing import CliRunner

from tests.unit.test_triage_batch_dispatch import FakeRunner

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
        )

    # -- the GhClient adapter
    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(f"pr_view {number}")
        p = self.prs[number]
        return {k: p[k] for k in ("state", "draft", "head_oid", "head_ref")}

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
             "headRefOid": p["head_oid"]}
            for n, p in self.prs.items() if p["head_ref"] == branch
        ]  # fmt: skip

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

    def add_worktree(self, where: Path, ref: str) -> Any:
        return _Worktree(self, where)

    def remove_worktree(self, where: Path) -> None:
        pass

    def fast_forward(self) -> None:
        self.forwarded += 1

    def released_since(self, when: datetime) -> bool:
        return self.released

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
    world.pr(201, "chore/archive-p1", [])
    world.pr(202, "chore/archive-someone-else", [])
    _state(tmp_path, world, _batch("b1", 1, events=_dispatch_event("b1") + closeout))
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0, out
    assert [m[0] for m in world.merged] == [201]
    assert _lines(out, "archive") == ["archive b1: merged archive PR #201"]
    code, out = _drive(tmp_path, "--once", "--yes")
    assert code == 0 and "closing 0" in out


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
    monkeypatch.setattr(triage_batch_cmd, "_pid_alive", lambda pid: pid == os.getpid())
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

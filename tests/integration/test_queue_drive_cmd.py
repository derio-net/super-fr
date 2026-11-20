"""The wave merge queue through `fr triage batch drive` itself (spec
2026-11-19-wave-merge-queue §A, R4, R10, R12, R24, R33, R35; review p3-r4, p3-r5).

The forge is the drive tests' in-memory `World`, but its PR heads, and whether a PR reads
`MERGED`, come from a real bare origin (a head reachable from `main` is merged, as GitHub
decides after a push); the clone is a real `gitseam.Checkout` of it. Every pass is the
real command, `--once --yes`: it resumes, builds into the slot branches, lands by ONE
atomic push and runs the repo's `post_merge` once per landing.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from fr.commands import triage_batch_cmd
from fr.triage.gitseam import Checkout
from fr.triage.model import QueueBuiltEvent, QueueLandEvent, load_judgements
from fr.triage.queue_exec import slot_ref

from tests.unit.test_triage_batch_dispatch import FakeRunner
from tests.unit.test_triage_batch_drive_cmd import (  # noqa: F401 - fixtures
    REPO,
    World,
    _batch,
    _dispatch_event,
    _lines,
    _sandbox,
    _state,
    runner_fixture,
    world_fixture,
)


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _ident(repo: Path) -> None:
    for k, v in (("user.name", "t"), ("user.email", "t@example.com"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)


class Origin:
    """A bare origin with `main` and one branch per batch PR, and a seed clone to push
    from."""

    def __init__(self, tmp_path: Path, config: dict[str, Any]) -> None:
        self.bare = tmp_path / "git" / "origin.git"
        self.bare.parent.mkdir()
        _git(self.bare.parent, "init", "--quiet", "--bare", "--initial-branch=main", str(self.bare))
        self.seed = tmp_path / "git" / "seed"
        _git(self.bare.parent, "clone", "--quiet", str(self.bare), str(self.seed))
        _ident(self.seed)
        _git(self.seed, "checkout", "--quiet", "-b", "main")
        (self.seed / ".fr").mkdir()
        (self.seed / ".fr" / "triage.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        (self.seed / "a.txt").write_text("alpha\n", encoding="utf-8")
        _git(self.seed, "add", ".")
        _git(self.seed, "commit", "--quiet", "-m", "seed")
        _git(self.seed, "push", "--quiet", "origin", "main")
        self.clone = tmp_path / "git" / "clone"
        _git(self.bare.parent, "clone", "--quiet", str(self.bare), str(self.clone))
        _ident(self.clone)
        _git(self.clone, "remote", "set-head", "origin", "main")

    def sha(self, ref: str) -> str:
        return _git(self.bare, "rev-parse", ref)

    def branch(self, name: str, files: dict[str, str]) -> str:
        _git(self.seed, "fetch", "--quiet", "origin")
        _git(self.seed, "checkout", "--quiet", "-B", name, "origin/main")
        for path, text in files.items():
            (self.seed / path).write_text(text, encoding="utf-8")
        _git(self.seed, "add", "--all")
        _git(self.seed, "commit", "--quiet", "-m", f"work on {name}")
        _git(self.seed, "push", "--quiet", "--force", "origin", f"{name}:{name}")
        _git(self.seed, "checkout", "--quiet", "--detach")
        return self.sha(f"refs/heads/{name}")

    def configure(self, config: dict[str, Any]) -> None:
        """`.fr/triage.yaml` on main now *config*: the operator's commit."""
        _git(self.seed, "fetch", "--quiet", "origin")
        _git(self.seed, "checkout", "--quiet", "-B", "main", "origin/main")
        (self.seed / ".fr" / "triage.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        _git(self.seed, "commit", "--quiet", "-am", "configure")
        _git(self.seed, "push", "--quiet", "origin", "main")
        _git(self.seed, "checkout", "--quiet", "--detach")

    def merged(self, head: str) -> bool:
        probe = ["git", "merge-base", "--is-ancestor", head, "refs/heads/main"]
        return subprocess.run(probe, cwd=self.bare).returncode == 0


class QueueWorld(World):
    """`World` whose PRs follow the bare origin: each read takes the head its branch has
    and reads MERGED once that head is reachable from `main`, so the next pass's collect
    sees what the queue's push did. `sticky` PRs keep reading OPEN (R35's lagging forge)."""

    def __init__(self, origin: Origin) -> None:
        super().__init__()
        self.origin = origin
        self.sticky: set[int] = set()

    def sync(self) -> None:
        for n, p in self.prs.items():
            if p["state"] != "OPEN":
                continue
            head = self.origin.sha(f"refs/heads/{p['head_ref']}")
            p["head_oid"] = head
            if self.origin.merged(head) and n not in self.sticky:
                p.update(state="MERGED", merged_at="2026-10-02T12:00:00+00:00")
                for i in p["closes"]:
                    self.issues[i] = "closed"

    def facts(self) -> Any:
        self.sync()
        return super().facts()

    def pr_view(self, repo: str, number: int) -> dict[str, Any]:
        self.sync()
        view = super().pr_view(repo, number)
        return {**view, "merge_commit": self.origin.sha("refs/heads/main")}

    def commit_checks(self, repo: str, sha: str) -> list[dict[str, Any]]:
        return []

    def required_check_names(self, repo: str, base: str) -> list[str]:
        return []


class QueueCheckout(Checkout):
    def origin_repo(self) -> str | None:
        return REPO


@pytest.fixture(name="queue")
def queue_fixture(
    tmp_path: Path, world: World, runner: FakeRunner, monkeypatch: pytest.MonkeyPatch
) -> tuple[Origin, QueueWorld, Path]:
    log = tmp_path / "post_merge.log"
    command = [sys.executable, "-c", f"open({str(log)!r}, 'a').write('ran\\n')"]
    config = {"queue": {"ci": "none", "depth": 2}, "post_merge": command}
    origin = Origin(tmp_path, config)
    qw = QueueWorld(origin)
    qw.config = config
    monkeypatch.setattr(triage_batch_cmd, "make_client", lambda url: qw)

    def recollect(scope: Any, target: Path, **_: Any) -> None:
        (target / "facts.json").write_text(json.dumps(qw.facts().to_json()), "utf-8")

    monkeypatch.setattr(triage_batch_cmd, "recollect", recollect)
    monkeypatch.setattr(triage_batch_cmd, "ci_is_none", lambda path: True)
    checkout = QueueCheckout(origin.clone)
    monkeypatch.setattr(triage_batch_cmd, "make_checkout", lambda path: checkout)
    for n, bid in ((1, "b1"), (2, "b2")):
        qw.issues[n] = "open"
        head = origin.branch(f"feat/batch-{bid}", {f"{bid}.txt": f"{bid}\n"})
        qw.pr(100 + n, f"feat/batch-{bid}", [n], head_oid=head)
    events = {bid: _dispatch_event(bid) for bid in ("b1", "b2")}
    _state(tmp_path, qw, *(_batch(bid, n, events=events[bid]) for n, bid in ((1, "b1"), (2, "b2"))))
    return origin, qw, log


def _drive(tmp_path: Path, *args: str) -> tuple[int, str]:
    """One `fr triage batch drive` run; an exception it raised is raised here."""
    from fr.cli import app
    from typer.testing import CliRunner

    argv = ["triage", "batch", "drive", *args, "--repo", REPO, "--dir", str(tmp_path)]
    result = CliRunner().invoke(app, argv)
    if result.exception is not None and not isinstance(result.exception, SystemExit):
        raise result.exception
    return result.exit_code, result.output


def _queue(tmp_path: Path) -> Any:
    (record,) = load_judgements(tmp_path / "judgements.yaml").queues
    return record


def _passes(tmp_path: Path, n: int) -> list[str]:
    outs = []
    for _ in range(n):
        code, out = _drive(tmp_path, "--once", "--yes")
        assert code in (0, 3), out
        outs.append(out)
    return outs


def test_the_drive_builds_lands_by_one_push_and_runs_post_merge_once(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    """p3-r5: under --yes the command opens the queue, builds both combinations into
    their slots, lands them by ONE push (main is the tested tip) and runs `post_merge`
    once for the landing; the per-batch `post-merge` actions are not the queue repo's."""
    origin, qw, log = queue
    base = origin.sha("refs/heads/main")
    outs = _passes(tmp_path, 4)
    record = _queue(tmp_path)
    built = [e for e in record.events if isinstance(e, QueueBuiltEvent)]
    lands = [e for e in record.events if isinstance(e, QueueLandEvent)]
    assert [e.slot for e in built] == [1, 2] and all(e.base == base for e in built)
    assert origin.sha(slot_ref(_queue(tmp_path).scope, 2)) == built[-1].sha
    assert len(lands) == 1 and [e.batch for e in lands[0].entries] == ["b1", "b2"]
    assert origin.sha("refs/heads/main") == built[-1].sha == lands[0].main  # the tested tip
    assert log.read_text().splitlines() == ["ran"]  # once per landing (R33)
    joined = "\n".join(outs)
    assert any("landed at" in line and "post_merge ran" in line
               for line in _lines(joined, "queue-land")), joined  # fmt: skip
    assert _lines(joined, "post-merge") == []  # no per-batch post_merge for a queue repo
    assert qw.merged == []  # nothing merged through the forge API under `land: push`
    kinds = {b.id: [e.kind for e in b.events]
             for b in load_judgements(tmp_path / "judgements.yaml").batches}  # fmt: skip
    assert all(k.count("post_merge") == 1 for k in kinds.values()), kinds


def test_a_resumed_landing_is_reloaded_before_the_pass_plans(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """p3-r5: a landing a killed driver pushed and never recorded is recorded by
    `_queue_resume`, and the pass then plans from the reloaded judgements: it lands nothing
    again and runs the landing's `post_merge` once."""
    origin, qw, log = queue
    _passes(tmp_path, 2)  # open, build
    from fr.triage import queue_exec

    real = queue_exec.land_push

    def push_then_die(*a: Any, **kw: Any) -> Any:
        kw["record"] = None  # the push lands; the event never reaches the file
        result = real(*a, **kw)
        raise KeyboardInterrupt(result.outcome)

    monkeypatch.setattr(queue_exec, "land_push", push_then_die)
    with pytest.raises(BaseException):  # noqa: B017, PT011 - the driver is killed
        code, out = _drive(tmp_path, "--once", "--yes")
        if code != 0:
            raise RuntimeError(out)
    monkeypatch.setattr(queue_exec, "land_push", real)
    landed = origin.sha("refs/heads/main")
    assert [e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)] == []
    (out,) = _passes(tmp_path, 1)
    assert "recorded, not pushed again" in out, out
    lands = [e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]
    assert len(lands) == 1 and lands[0].main == landed
    _passes(tmp_path, 2)
    assert origin.sha("refs/heads/main") == landed
    assert len([e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]) == 1
    assert log.read_text().splitlines() == ["ran"]  # the gate ran it once, after the reload


def test_a_landed_pr_the_forge_still_reads_open_keeps_its_approval(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    """p3-r4, R12, R35: after the landing the forge still reads #101 open; its patch-id
    against the new main is empty, but the driver never settles a landed PR, so the
    approval stays and the label is never removed."""
    origin, qw, _ = queue
    qw.sticky.add(101)
    outs = _passes(tmp_path, 5)
    assert len([e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]) == 1
    batch = next(b for b in load_judgements(tmp_path / "judgements.yaml").batches if b.id == "b1")
    approvals = [e for e in batch.events if e.kind == "approval"]
    assert approvals and all(getattr(e, "voided_at", None) is None for e in approvals)
    assert "approved-fr" in qw.prs[101]["labels"]
    assert not any(c == "label 101" for c in qw.calls)
    assert any("did not mark #101 merged" in out for out in outs), outs


def test_a_failed_post_merge_pauses_the_next_landing_and_runs_once_a_pass(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    """p3-r5, R33: `_queue_post_merge` maps a failed run to the failure (an unconfigured or
    foreign one to none), so the landing's line says it failed and the next landing waits.
    Each pass runs it once, from the queue's gate: the batches' own `post-merge` actions,
    which a merged batch with no `post_merge` event would plan, are dropped for a queue
    repo."""
    origin, qw, log = queue
    fail = [sys.executable, "-c", f"open({str(log)!r}, 'a').write('ran\\n'); raise SystemExit(4)"]
    qw.config = {"queue": {"ci": "none", "depth": 1}, "post_merge": fail}
    origin.configure(qw.config)
    outs = _passes(tmp_path, 3)  # open, build b1, land b1: post_merge fails
    joined = "\n".join(outs)
    assert any("post_merge failed" in line for line in _lines(joined, "queue-land")), joined
    assert log.read_text().splitlines() == ["ran"]
    more = _passes(tmp_path, 2)
    lands = [e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]
    assert len(lands) == 1  # b2 is built, but nothing lands behind the failed post_merge
    assert any("lands nothing until this clears" in out and "post_merge failed" in out
               for out in more), more  # fmt: skip
    assert log.read_text().splitlines() == ["ran"] * 3  # once a pass, never twice
    assert _lines("\n".join(more), "post-merge") == []
    qw.config = {"queue": {"ci": "none", "depth": 1},
                 "post_merge": [sys.executable, "-c", "pass"]}  # fmt: skip
    origin.configure(qw.config)  # a move of main the queue did not make: it rebuilds
    _passes(tmp_path, 3)
    assert len([e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]) == 2


def test_with_no_post_merge_the_queue_lands_on_without_a_pause(
    tmp_path: Path, queue: tuple[Origin, QueueWorld, Path]
) -> None:
    origin, qw, log = queue
    qw.config = {"queue": {"ci": "none", "depth": 1}}
    origin.configure(qw.config)
    _passes(tmp_path, 6)
    lands = [e for e in _queue(tmp_path).events if isinstance(e, QueueLandEvent)]
    assert [[e.batch for e in x.entries] for x in lands] == [["b1"], ["b2"]]
    assert not log.exists()

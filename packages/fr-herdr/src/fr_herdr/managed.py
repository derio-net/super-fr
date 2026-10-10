"""Local managed launch state, fail-closed reconstruction and nonblocking pane locks.

No triage imports: the item supplies identity; recovery reads the branch's durable
cursor, or asks the existing pickup gate. Initial batch goals are never replayed.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

import yaml
from fr.artifacts.atomic import write_text_atomic
from fr.git import git_answer
from fr.hostclient import client_for
from pydantic import BaseModel, ConfigDict, ValidationError


class ManagedError(Exception):
    """Missing/uncertain managed state is not permission to send input."""


class Descriptor(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    server: str
    pane: str
    name: str
    item: str
    role: Literal["batch", "conflict", "closeout"]
    branch: str
    checkout: str
    model: str
    harness: Literal["opencode", "claude"] = "opencode"
    brief: str = ""
    conflict_head: str | None = None
    conflict_brief: str | None = None
    attempt: str | None = None
    old_harness: Literal["opencode", "claude"] | None = None
    old_model: str | None = None
    checkpoint: Literal[
        "prepared",
        "source-exited",
        "target-ready",
        "submission-started",
        "submission-uncertain",
        "uptake-confirmed",
        "batch-committed",
        "active",
        "aborted",
    ] = "active"


def server_identity() -> str:
    socket = os.environ.get("HERDR_SOCKET_PATH")
    if not socket:
        raise ManagedError("HERDR_SOCKET_PATH is missing; server identity is unknown")
    return str(Path(socket).resolve())


def cache_dir() -> Path:
    return Path(os.environ.get("FR_HERDR_CACHE_DIR", Path.home() / ".cache/fr/herdr"))


def _key(pane: str) -> str:
    return hashlib.sha256(f"{server_identity()}\0{pane}".encode()).hexdigest()


def path_for(pane: str) -> Path:
    return cache_dir() / f"{_key(pane)}.json"


def save(d: Descriptor) -> None:
    if d.server != server_identity() or not all(
        (d.pane, d.name, d.item, d.branch, d.checkout, d.model)
    ):
        raise ManagedError("invalid managed descriptor identity")
    if not Path(d.checkout).is_absolute():
        raise ManagedError("managed checkout must be absolute")
    path = path_for(d.pane)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, d.model_dump_json(indent=2) + "\n")


def load(pane: str) -> Descriptor | None:
    path = path_for(pane)
    try:
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict) or "checkpoint" not in raw:
            raise ManagedError("managed operation checkpoint is missing")
        d = Descriptor.model_validate(raw)
    except FileNotFoundError:
        return None
    except (OSError, ValueError, ValidationError) as exc:
        raise ManagedError(f"unreadable managed descriptor: {path}") from exc
    if (
        d.server != server_identity()
        or d.pane != pane
        or not all((d.name, d.item, d.branch, d.checkout, d.model))
        or not Path(d.checkout).is_absolute()
    ):
        raise ManagedError("managed descriptor identity mismatch")
    return d


@contextmanager
def pane_lock(pane: str) -> Iterator[None]:
    """Shared restart/replacement lock. A loser sends/writes nothing, never waits."""
    path = cache_dir() / f"{_key(pane)}.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ManagedError(f"pane {pane} is locked") from exc
        try:
            # Virtual/shared filesystems can acknowledge flock without excluding
            # another process. Verify that OS contract before allowing any input.
            probe = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "import fcntl,sys\n"
                    "with open(sys.argv[1], 'a') as f:\n"
                    " try: fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)\n"
                    " except BlockingIOError: sys.exit(3)\n"
                    " sys.exit(0)\n",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if probe.returncode != 3:
                raise ManagedError(
                    "filesystem does not enforce pane lock; use a reliable local cache"
                )
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _git(d: Descriptor, *args: str) -> str:
    result = git_answer(Path(d.checkout), *args)
    if result.returncode:
        raise ManagedError(f"cannot inspect branch {d.branch}: {result.stderr.strip()}")
    return result.stdout.strip()


def branch_workspace(d: Descriptor) -> Path:
    where = None
    for line in _git(d, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            where = Path(line.removeprefix("worktree "))
        if line == f"branch refs/heads/{d.branch}" and where and where.is_dir():
            return where
    raise ManagedError(f"existing workspace for {d.branch} is unavailable; do not create another")


def conflict_current(d: Descriptor) -> bool:
    """A saved handback only survives a matching head AND live conflicting open PR."""
    if _git(d, "rev-parse", d.branch) != d.conflict_head:
        return False
    repo, separator, _ = d.item.partition("/run/")
    if not separator:
        raise ManagedError("managed item has no repo/run identity")
    client = client_for(Path(d.checkout))
    prs = [
        pr
        for pr in client.list_prs_by_head(repo, d.branch)
        if not pr.get("isCrossRepository", False)
    ]
    if not isinstance(prs, list) or len(prs) != 1:
        raise ManagedError("cannot establish the handback's live PR identity")
    pr = client.pr_view(repo, int(prs[0]["number"]))
    if pr["state"] != "OPEN":
        return False
    if pr["mergeable"] not in ("MERGEABLE", "CONFLICTING"):
        raise ManagedError("live mergeability is unknown; inspect before recovery")
    return bool(pr["head_oid"] == d.conflict_head and pr["mergeable"] == "CONFLICTING")


def pickup(d: Descriptor) -> str:
    """The existing pickup implementation owns delivery/merge gates."""
    run = re.search(r"\bfr pickup --run ([a-zA-Z0-9_-]+)", d.brief)
    args = ["--run", run[1]] if run else ["--branch", d.branch]
    done = subprocess.run(
        ["fr", "pickup", *args],
        cwd=d.checkout,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if done.returncode:
        raise ManagedError(f"close-out pickup refused: {done.stderr or done.stdout}")
    return done.stdout


def reconstruct(d: Descriptor) -> str:
    if d.role == "closeout":
        return pickup(d)
    if d.conflict_head and d.conflict_brief and conflict_current(d):
        return d.conflict_brief
    workspace = branch_workspace(d)
    runs = []
    for path in sorted((workspace / "docs/superpowers/runs").glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            raise ManagedError(f"unreadable cursor {path}")
        if data.get("branch") == d.branch:
            runs.append(data)
    intro = (
        f"Fresh recovery of {d.item} in the EXISTING workspace {workspace}. "
        "Inspect committed and in-progress step records and journal handoff first. "
        "Never replay the original goal or start a second run/worktree.\n"
    )
    if not runs:
        return (
            intro
            + "HOLD: no durable run cursor found; inspect fr status and current PR before acting."
        )
    if len(runs) != 1 or not isinstance(runs[0].get("steps"), dict):
        raise ManagedError("ambiguous or unreadable branch cursor")
    run = runs[0]
    steps = run["steps"]
    if steps.get("deliver", {}).get("state") == "done":
        return (
            intro
            + "HOLD for operator review/Ready/merge. Delivery is done; do not merge or close out."
        )
    return (
        intro + f"Run {run.get('run')} is at {run.get('cursor')}. Read `fr run status` and "
        "reconcile any running unit and its dead source holder explicitly BEFORE redispatch. "
        "Use fr's claim/abandoned reconciliation, preserving attempts and records; never "
        "dispatch the same running unit twice. Resume the actual unfinished cursor only."
    )


def handback(d: Descriptor, text: str) -> Descriptor:
    """Save the engine's existing six-step brief under the ORIGINAL item identity."""
    match = re.search(r"\bhead ([0-9a-f]+), conflicts with", text)
    if text.startswith("Merge conflict on batch ") and match:
        return d.model_copy(update={"conflict_head": match[1], "conflict_brief": text})
    return d

"""A scope's durable copy: the git ref `refs/fr/triage/<scope-id>` (spec
2026-10-07-cloud-triage R5, §B).

The ref points at a commit whose tree is the explicit list `REF_FILES`, not the export
set: the authored state `fr.triage.state_sync` exports (asserted a subset by the tests),
plus the merge stops, the lease, the scope's durable settings and the cloud runner's
mailbox. `facts.json`, the rendered pages, the host-only `scope.yaml` and the host id
never ride on it: fr rebuilds the first two, and the last two are this host's.

A push is a compare-and-swap (`--force-with-lease=<ref>:<old>`): a second writer, or a
lost lease, fails the push (`StateRefConflict`) rather than overwriting. The commit is
built in a temporary index, so the workspace's index, HEAD and files never move, and a
ref outside `refs/heads/` is no branch: no branch list, no protection rule, no PR.

Every git process starts in `fr.triage.gitseam`. The clone that holds the objects is
the git toplevel of the state directory (it lives in the workspace, R4), or *repo*.

`read_base` / the `.state-ref` file: the sha this state directory was last fetched
from or pushed to, the `expected_old` of its next push.
"""

from __future__ import annotations

import contextlib
import os
import re
import tempfile
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from fr.triage import gitseam, state_sync
from fr.triage.errors import TriageError
from fr.triage.model import Scope

REF_FILES: tuple[str, ...] = (
    "judgements.yaml",
    "origins.yaml",
    "subsystems.yaml",
    "board/",
    "origins/",
    "architecture/",
    "history/",
    "snapshots/",
    "authored-src/",
    "merge-stops.json",
    "lease.yaml",
    "scope-durable.yaml",
    "requests.yaml",
    "sessions.yaml",
    "rehomes.yaml",
)
"""THE list of what the state ref carries: a name ending in `/` is a directory, taken
whole (every regular file under it, never through a symlink)."""

REF_PREFIX = "refs/fr/triage/"
BASE_FILE = ".state-ref"


class StateRefConflict(TriageError):  # noqa: N818 - the name the plan and spec use
    """The remote's ref is not the one this push was based on: someone else wrote it."""


def ref_name(scope_id: str) -> str:
    """`refs/fr/triage/<scope-id>`."""
    if not scope_id or "/" in scope_id or scope_id.startswith("."):
        raise TriageError(f"{scope_id!r} is not a scope id")
    return f"{REF_PREFIX}{scope_id}"


def _allowed(rel: str) -> bool:
    """Whether *rel* (POSIX, relative) is a `REF_FILES` entry or lies under one."""
    parts = PurePosixPath(rel).parts
    if not parts or any(p in ("", ".", "..") for p in parts) or rel.startswith("/"):
        return False
    for entry in REF_FILES:
        if entry.endswith("/"):
            if len(parts) > 1 and parts[0] == entry[:-1]:
                return True
        elif rel == entry:
            return True
    return False


def ref_entries(state_dir: Path) -> list[str]:
    """The `REF_FILES` entries that exist in *state_dir* as regular files, sorted; a
    symlink is never followed and never carried, at any depth."""
    out: list[str] = []
    for entry in REF_FILES:
        name = entry.rstrip("/")
        path = state_dir / name
        if path.is_symlink():
            continue
        if entry.endswith("/"):
            if path.is_dir():
                out += [rel for rel, link in state_sync._walk(state_dir, PurePosixPath(name))
                        if not link]  # fmt: skip
        elif path.is_file():
            out.append(name)
    return sorted(out)


def _repo(state_dir: Path, repo: Path | None) -> Path:
    if repo is not None:
        return repo
    probe = state_dir
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    root = gitseam.toplevel(probe)
    if root is None:
        raise TriageError(
            f"{state_dir} is in no git clone: the state ref is written from the workspace "
            "that holds the state (--workspace)"
        )
    return root


def read_base(state_dir: Path) -> str | None:
    """The sha *state_dir* was last fetched from or pushed to; None when never."""
    try:
        value = (state_dir / BASE_FILE).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    return value or None


def _write_base(state_dir: Path, sha: str) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / BASE_FILE).write_text(f"{sha}\n", encoding="utf-8")


def _write_bytes(state_dir: Path, rel: str, content: bytes) -> None:
    """Write *content* to `state_dir/rel` atomically, refusing any path through a symlink
    or outside *state_dir* (`state_sync.contained`)."""
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_sync.contained(state_dir, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    state_sync.contained(state_dir, rel)  # again, now that the parents exist
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".fr-ref-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def fetch_state(
    state_dir: Path, remote_repo: str, scope_id: str, *, repo: Path | None = None
) -> str | None:
    """Fetch the scope's ref from *remote_repo* (a URL or path git can push to) and write
    every `REF_FILES` entry it carries into *state_dir*, byte for byte; its sha, or None
    (nothing written) when the remote has no such ref. An entry the ref does not carry is
    left alone; a path in the ref outside `REF_FILES` is ignored."""
    cwd = _repo(state_dir, repo)
    ref = ref_name(scope_id)
    sha = gitseam.fetch_ref(cwd, remote_repo, ref)
    if sha is None:
        return None
    for _mode, blob, rel in gitseam.tree_files(cwd, sha):
        if _allowed(rel):
            _write_bytes(state_dir, rel, gitseam.blob_bytes(cwd, blob))
    _write_base(state_dir, sha)
    apply_durable(state_dir)
    return sha


def apply_durable(state_dir: Path) -> None:
    """Carry the restored `scope-durable.yaml` to where this host reads it (cloud-triage
    §B, R11): `state_repo` mirrored into `scope.yaml`, and `forge_api` written to
    `~/.config/fr/forge.yaml` only when that file is absent (the host file always wins)."""
    from fr import forgeapi
    from fr.triage.scope_config import load_durable, load_scope_config, mirror_state_repo

    durable = load_durable(state_dir)
    if durable.state_repo and load_scope_config(state_dir).state_repo != durable.state_repo:
        mirror_state_repo(state_dir, durable.state_repo)
    if durable.forge_api is not None:
        forgeapi.write_default(durable.forge_api)


def push_state(
    state_dir: Path,
    remote_repo: str,
    scope_id: str,
    *,
    expected_old: str | None,
    scope: Scope,
    state_repo: str,
    client: Any,
    repo: Path | None = None,
) -> str:
    """Commit *state_dir*'s `REF_FILES` entries and push them to the scope's ref on
    *remote_repo* (the git URL or path of *state_repo*), only if the remote's ref is still
    *expected_old* (None: it must not exist yet). The new sha; `StateRefConflict` when the
    remote moved, and then nothing on the remote changed.

    First, the privacy guard (R8): *state_repo*'s visibility is read from the forge through
    *client* (`GET repos/{state_repo}`), and the push is refused (`PrivacyError`, nothing
    written) when it cannot be read, or when it is public and the state names a private
    repo's issue."""
    from fr.triage.privacy import guard_state

    guard_state(state_dir, scope=scope, state_repo=state_repo, client_for=lambda _r: client)
    cwd = _repo(state_dir, repo)
    ref = ref_name(scope_id)
    parent = expected_old if expected_old and gitseam.has_commit(cwd, expected_old) else None
    sha = gitseam.commit_tree_from_paths(
        cwd, state_dir, ref_entries(state_dir), parent=parent, message=f"fr triage state {ref}"
    )
    if not gitseam.push_ref_cas(cwd, remote_repo, sha, ref, expected_old=expected_old):
        raise StateRefConflict(
            f"{ref} on {remote_repo} is no longer {expected_old or 'absent'}: another writer "
            "pushed it; fetch the state again before pushing"
        )
    _write_base(state_dir, sha)
    return sha


# ------------------------------------------------------------ where it lives

NEW_REPO = "a new repo for the refs"
"""The choice offered beside the public repos when no repo of the scope is private (R7);
the prompt then asks for its OWNER/REPO."""

LEAK_WARNING = (
    "every repo in this scope is public: if a private repo's issue is later added to a "
    "batch or a wave, keeping the state ref in a public repo would leak it (fr refuses "
    "that add, R8). A new repo just for the refs, made private, avoids the refusal."
)

Ask = Callable[[str, list[str], str | None], str | None]
"""`(question, choices, warning) -> answer`: the operator's prompt, injected; None when
nothing was answered."""

_SLUG = re.compile(r"[A-Za-z0-9._-]+/[A-Za-z0-9._-]+")


def is_private(visibility: str | None) -> bool:
    """`private` or `internal`: anything a public reader cannot see."""
    return visibility in ("private", "internal")


def decide_state_repo(
    repos: Iterable[str], visibility: Mapping[str, str], ask: Ask | None
) -> str | None:
    """Where a scope's state ref lives (R6, R7). Pure; the prompt is *ask*.

    One repo: that repo, and no question. Several, at least one private: the operator
    picks one of the private ones. All public (a repo whose visibility is unknown counts
    as public here: it is never offered as the safe choice): the operator picks between
    a new repo for the refs and each public repo, warned of the leak. None when *ask*
    is None (non-interactive) or gives no answer: the state then stays local. An answer
    outside the choices is refused (`TriageError`)."""
    ordered = sorted(set(repos))
    if len(ordered) == 1:
        return ordered[0]
    if not ordered or ask is None:
        return None
    private = [r for r in ordered if is_private(visibility.get(r))]
    if private:
        choices, warning = private, None
        question = "Which private repo of this scope keeps its state ref?"
    else:
        choices, warning = [NEW_REPO, *ordered], LEAK_WARNING
        question = "Where does this scope keep its state ref?"
    answer = ask(question, choices, warning)
    if answer is None:
        return None
    if answer in choices and answer != NEW_REPO:
        return answer
    if warning is not None and _SLUG.fullmatch(answer) and answer != NEW_REPO:
        return answer  # the new repo's name
    raise TriageError(f"{answer!r} is not one of {', '.join(c for c in choices if c != NEW_REPO)}")

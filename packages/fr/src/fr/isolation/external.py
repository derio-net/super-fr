"""ExternalTarget — adopt a preparer-built containment (spec §A, Type 1).

Mode `external`: another process (a k8s run pod, an image build, an attach
script) stood the container up — the checkout, the authenticated agent, and the
secrets are already inside, and it signals "this environment is contained and
prepared for fr" by writing the `.fr-isolation` marker itself at the checkout
toplevel with `mode="external"`. The marker is the hand-off artifact; there is no
probing, so an unprepared container is never silently treated as isolated.

fr adopts that containment instead of isolating a second time: `up` validates the
marker, ensures the requested feature branch in place (the preparer chose the
base, fr names the branch), records `IsolationState`, and fills the branch into
the marker. `exec` is a plain subprocess in the checkout with the inherited env —
the exec-bridge stays the uniform surface skills call, it just stops crossing a
container boundary. The checkout and container belong to the preparer: `down`
retires fr's state file and the marker's branch claim ONLY (never the marker
file, the checkout, or the container), and `restart`/`stats` refuse outright.
Implements the `Target` protocol directly — no devcontainer inheritance.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fr.isolation.local import Runner, subprocess_runner
from fr.isolation.types import (
    IsolationError,
    IsolationState,
    _git_common_dir,
    delete_state,
    save_state,
)

_MARKER = ".fr-isolation"
_EXTERNAL = "externally managed — restart/inspect the container via its owner, not fr"


def _container_evidence() -> bool:
    """Corroboration that we really are inside a container (spec §C) — any of the
    docker/podman sentinel files or the k8s service-host env var."""
    import os

    return (
        Path("/.dockerenv").exists()
        or Path("/run/.containerenv").exists()
        or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
    )


class ExternalTarget:
    def __init__(self, repo_root: Path, runner: Runner = subprocess_runner) -> None:
        # The checkout IS the isolation boundary — resolve to match the realpath
        # the marker records, but do NOT normalize to a main-worktree root: an
        # external checkout is a primary checkout, not a linked worktree.
        self.repo_root = Path(repo_root).resolve()
        self.run = runner

    @classmethod
    def detect(cls, repo: Path, runner: Runner = subprocess_runner) -> ExternalTarget | None:
        """Cheap marker probe for `_target` selection: a valid `external` marker
        at the CWD'S git toplevel → an instance that owns every subcommand;
        otherwise None (fall through to `FR_ISOLATION_TARGET` / the default).
        Never raises — an absent/foreign marker, a non-repo dir, or a bare host
        with no container evidence is a routing signal, not an error.

        Resolves `git rev-parse --show-toplevel` first (spec §A Selection), so a
        command issued from a SUBDIRECTORY of the prepared checkout still finds
        the marker at the toplevel instead of falling through to devcontainer.
        And it requires live container evidence (spec §A hardening / §C): a
        forged marker on a bare host never routes here — the preparer's claim is
        only adopted when corroborated by /.dockerenv, /run/.containerenv, or
        $KUBERNETES_SERVICE_HOST (not probe-based auto-detection — the marker is
        still the trigger; evidence is corroboration)."""
        top = runner(["git", "rev-parse", "--show-toplevel"], cwd=repo)
        toplevel = (top.stdout or "").strip()
        if top.returncode != 0 or not toplevel:
            return None  # not a git repo — nothing to adopt
        target = cls(Path(toplevel), runner)
        try:
            target._load_marker()
        except IsolationError:
            return None
        if not _container_evidence():
            return None  # forged marker on a bare host — never adopt
        return target

    # ---------- marker ----------

    def _marker_path(self) -> Path:
        return self.repo_root / _MARKER

    def _load_marker(self) -> dict[str, Any]:
        """Read + validate the preparer's marker: present, `mode="external"`, and
        recorded toplevel == actual toplevel (defeats a marker copied elsewhere)."""
        p = self._marker_path()
        if not p.is_file():
            raise IsolationError(
                f"no {_MARKER} marker at {self.repo_root} — external mode requires the "
                "preparer to write one (the containment hand-off artifact). See spec §A."
            )
        try:
            data: dict[str, Any] = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise IsolationError(f"unreadable {_MARKER} marker at {self.repo_root}: {e}") from e
        if data.get("mode") != "external":
            raise IsolationError(
                f"{_MARKER} marker at {self.repo_root} is not mode 'external' "
                f"(got {data.get('mode')!r}) — not an externally prepared containment."
            )
        recorded = Path(str(data.get("toplevel", ""))).resolve()
        if recorded != self.repo_root:
            raise IsolationError(
                f"{_MARKER} marker records toplevel {recorded} but the actual toplevel is "
                f"{self.repo_root} — a stale or copied marker. Refusing to adopt."
            )
        return data

    def _set_marker_branch(self, branch: str) -> None:
        """Rewrite the marker's `branch` claim in place, preserving every other
        preparer-written field. Never unlinks the file — it is the preparer's.

        Parses defensively: `down` calls this AFTER `delete_state`, so a marker
        that turned corrupt must surface a clear IsolationError, not a raw
        JSONDecodeError traceback (mirrors `_load_marker`'s guarded parse)."""
        p = self._marker_path()
        if not p.is_file():
            return
        try:
            data = json.loads(p.read_text())
        except (OSError, json.JSONDecodeError) as e:
            raise IsolationError(f"unreadable {_MARKER} marker at {self.repo_root}: {e}") from e
        data["branch"] = branch
        p.write_text(json.dumps(data, indent=2) + "\n")

    def _exclude_marker(self) -> None:
        """Git-exclude the adopted marker so an in-container agent can't commit
        it in a repo that lacks a `.gitignore` entry (mirrors the local target's
        `_write_isolation_marker` info/exclude append). The marker is the
        preparer's file — fr never stages it."""
        exclude = _git_common_dir(self.repo_root) / "info" / "exclude"
        exclude.parent.mkdir(parents=True, exist_ok=True)
        existing = exclude.read_text().splitlines() if exclude.is_file() else []
        if _MARKER not in existing:
            with exclude.open("a") as fh:
                fh.write(f"{_MARKER}\n")

    # ---------- lifecycle ----------

    def up(
        self,
        profile: str | None,
        branch: str,
        path: Path | None = None,
        base: str | None = None,
        no_fetch: bool = False,
    ) -> IsolationState:
        self._load_marker()  # validate before touching anything
        if profile is not None:
            print(
                f"[fr] note: --profile {profile!r} ignored in external mode — the "
                "environment is not fr's to select (spec §A).",
                file=sys.stderr,
            )
        self._ensure_branch(branch)
        state = IsolationState(
            repo_root=self.repo_root,
            branch=branch,
            worktree=self.repo_root,
            profile="external",
            created_at=datetime.now(UTC).isoformat(),
        )
        save_state(state)
        self._set_marker_branch(branch)
        self._exclude_marker()
        return state

    def _ensure_branch(self, branch: str) -> None:
        """Put the requested feature branch in place, without ever cutting a new
        base — the preparer chose the base (spec §A). HEAD already the branch →
        no-op (idempotent); the branch exists → `git switch <branch>`; otherwise
        `git switch -c <branch>` from current HEAD."""
        head = self.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=self.repo_root)
        if (head.stdout or "").strip() == branch:
            return
        listed = self.run(["git", "branch", "--list", branch], cwd=self.repo_root)
        argv = (
            ["git", "switch", branch]
            if (listed.stdout or "").strip()
            else ["git", "switch", "-c", branch]
        )
        result = self.run(argv, cwd=self.repo_root)
        if result.returncode != 0:
            raise IsolationError(f"git switch failed: {result.stderr}")

    def exec(self, state: IsolationState, argv: list[str]) -> int:
        """Plain subprocess in the checkout, inherited env — no container boundary
        crossed. capture=False streams output live, matching exec passthrough."""
        return self.run(argv, cwd=state.worktree, capture=False).returncode

    def restart(self, state: IsolationState, force: bool = False) -> str:
        raise IsolationError(_EXTERNAL)

    def stats(self, state: IsolationState) -> dict[str, str] | None:
        raise IsolationError(_EXTERNAL)

    def status(self, state: IsolationState) -> dict[str, Any]:
        """Mode/toplevel/branch + the keys the shared CLI text renderer reads
        (`profile`, `worktree`, `pr`) so `fr isolation status` renders an
        external workspace without a KeyError. The checkout IS the workspace
        (worktree == toplevel); `profile` is the sentinel "external"; `pr` is
        None — a PR is the preparer's/operator's concern, not fr's to probe
        from inside an adopted containment."""
        return {
            "mode": "external",
            "repo": str(self.repo_root),
            "toplevel": str(self.repo_root),
            "worktree": str(self.repo_root),
            "branch": state.branch,
            "profile": "external",
            "container": _container_evidence(),
            "pr": None,
        }

    def down(self, state: IsolationState, force: bool = False) -> None:
        """Retire fr's state file and the marker's branch claim ONLY. The checkout
        and container belong to the preparer — no worktree removal, no docker, and
        the marker file itself is never unlinked."""
        delete_state(state.repo_root, state.branch)
        self._set_marker_branch("")

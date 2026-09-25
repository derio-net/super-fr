"""Where `fr run` and `fr usage` execute: on the harness host (spec
`2026-09-25-lean-cost-aware-process-design.md` §5.B.6, decision d10).

Both read the harness's own session store (transcripts, SQLite databases) and
the workspace's session bindings, which live where the HARNESS runs. In
devcontainer mode that is the host, while `fr isolation exec` runs commands in
the container — where none of that data exists, so a capture there records
nothing and a transcript gate observes nothing.

| mode          | harness runs | `fr run` runs          | refused |
|---------------|--------------|------------------------|---------|
| host-worktree | host         | host                   | no      |
| devcontainer  | host         | host: `cd <wt> && fr …`| yes     |
| external      | container    | container (= harness)  | no      |

Two layers enforce it:

- **the bridge** — `fr isolation exec` inspects its argv (and, best effort,
  a `bash -c` string) for an inner `fr run` / `fr usage` and, in devcontainer
  mode, refuses with the exact host-side command;
- **in process** — `require_harness_host`, called by the `run` and `usage`
  groups, refuses when the OPERATED repo carries a `.fr-isolation` marker
  with `target: devcontainer` AND container evidence exists. `mode` cannot
  discriminate — devcontainer and host-worktree both write `mode: worktree`,
  and a host-worktree pod or CI container shows container evidence too — so
  `fr isolation up` records the chosen `target`; a legacy marker without one
  is never refused (p2-r20). It keys on the repo's marker, not on the
  environment, so a test suite driving `fr run` against temp repos inside a
  container is unaffected, and external mode is never refused.
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

HOST_SIDE_GROUPS = ("run", "usage")
_SEPARATORS = {"&&", "||", ";", "|", "&"}
_SHELLS = {"bash", "sh", "zsh", "dash"}


class HostSideError(Exception):
    """A host-side command asked to run inside a devcontainer."""


def container_evidence() -> bool:
    """`/.dockerenv`, `/run/.containerenv` or `$KUBERNETES_SERVICE_HOST` —
    the same corroboration `fr.isolation.external` and the edit gate use."""
    return (
        Path("/.dockerenv").exists()
        or Path("/run/.containerenv").exists()
        or bool(os.environ.get("KUBERNETES_SERVICE_HOST"))
    )


def _tokens(argv: Sequence[str]) -> list[str]:
    """argv, with a shell's `-c` string split into words (best effort)."""
    args = list(argv)
    for i, tok in enumerate(args):
        if Path(tok).name in _SHELLS and "-c" in args[i + 1 :]:
            at = args.index("-c", i + 1) + 1
            script = args[at] if at < len(args) else ""
            try:
                lexer = shlex.shlex(script, posix=True, punctuation_chars=";&|")
                lexer.whitespace_split = True
                return args[:i] + list(lexer)
            except ValueError:
                return args[:i] + script.split()
    return args


def inner_fr_command(argv: Sequence[str]) -> list[str] | None:
    """The `fr` arguments (from the group on) of an `fr run`/`fr usage` that
    `argv` would invoke — `fr …`, `uv run fr …`, `python -m fr …`, or inside a
    shell's `-c` string — else `None`. Best effort, and it errs strict: a
    word `fr` followed by a host-side group counts wherever it appears."""
    tokens = _tokens(argv)
    for i, tok in enumerate(tokens):
        if Path(tok).name != "fr" or i + 1 >= len(tokens) or tokens[i + 1] not in HOST_SIDE_GROUPS:
            continue
        tail: list[str] = []
        for word in tokens[i + 1 :]:
            if word in _SEPARATORS:
                break
            tail.append(word)
        return tail
    return None


def host_command(worktree: Path, fr_args: Sequence[str]) -> str:
    """`cd <worktree> && [uv run] fr <args>` — `uv run fr` when the worktree
    holds fr's own source (this repo), so the host runs the worktree's fr."""
    prefix = "uv run fr" if (worktree / "packages" / "fr").is_dir() else "fr"
    return f"cd {shlex.quote(str(worktree))} && {prefix} {shlex.join(list(fr_args))}"


def refusal(worktree: Path, fr_args: Sequence[str]) -> str:
    group = fr_args[0] if fr_args else "run"
    return (
        f"fr {group} runs on the harness host, not inside the devcontainer: it reads the "
        "harness's session store and the workspace's bindings, which live on the host "
        "(spec 2026-09-25-lean-cost-aware-process §5.B.6). Run it from the host:\n"
        f"  {host_command(worktree, fr_args)}"
    )


def _marker(repo_root: Path) -> dict[str, object] | None:
    try:
        data = json.loads((repo_root / ".fr-isolation").read_text())
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def require_harness_host(repo_root: Path, group: str, argv: Sequence[str] | None = None) -> None:
    """Raise `HostSideError` when `repo_root` is a devcontainer-mode workspace
    seen from inside its container: a `target: devcontainer` marker plus
    container evidence. Host-worktree, external, legacy (no `target`) and
    unmarked repos pass."""
    marker = _marker(repo_root)
    if marker is None or marker.get("target") != "devcontainer" or not container_evidence():
        return
    args = list(sys.argv[1:] if argv is None else argv)
    fr_args = args[args.index(group) :] if group in args else [group, "…"]
    toplevel = marker.get("toplevel")
    worktree = Path(toplevel) if isinstance(toplevel, str) and toplevel else repo_root
    raise HostSideError(refusal(worktree, fr_args))


__all__ = [
    "HOST_SIDE_GROUPS",
    "HostSideError",
    "container_evidence",
    "host_command",
    "inner_fr_command",
    "refusal",
    "require_harness_host",
]

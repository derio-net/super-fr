"""The `--checkout REPO=PATH` map `fr triage batch drive` reads (moved out of
`commands/triage_batch_cmd.py`, which is at its module line budget)."""

from __future__ import annotations

from pathlib import Path

from fr.triage.errors import TriageError
from fr.triage.model import Scope


def checkout_map(values: list[str] | None, scope: Scope, repos: set[str]) -> dict[str, Path | None]:
    """`--checkout REPO=PATH`, repeatable, keyed by lower-cased OWNER/REPO.

    A single-repo scope defaults to the current git toplevel (None), as `batch
    dispatch` does; any other scope needs a mapping for every repo with a batch to
    drive, refused before anything runs."""
    out: dict[str, Path | None] = {}
    for value in values or []:
        name, sep, where = value.partition("=")
        if not sep or name.count("/") != 1 or not where:
            raise TriageError(
                f"--checkout takes REPO=PATH (OWNER/REPO=/path/to/clone), got {value!r}"
            )
        out[name.lower()] = Path(where).expanduser()
    if scope.kind == "repo":
        stray = sorted(set(out) - {scope.target.lower()})
        if stray:
            raise TriageError(
                f"--checkout names {', '.join(stray)}, which is not this scope's repo "
                f"{scope.target}"
            )
        out.setdefault(scope.target.lower(), None)
        return out
    if scope.kind == "group":
        stray = sorted(set(out) - {r.lower() for r in scope.repos})
        if stray:
            raise TriageError(
                f"--checkout names {', '.join(stray)}, which is not in this scope's group"
            )
        repos = set(
            scope.repos
        )  # a group needs a clone for EVERY repo, not only those with batches
    missing = sorted(r for r in repos if r.lower() not in out)
    if missing:
        raise TriageError(
            f"give --checkout REPO=PATH for {', '.join(missing)}: no clone is known for it"
        )
    return out

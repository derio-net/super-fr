"""`deliver`'s derived `settle` witness (spec 2026-11-23-pr-readiness-wait R8, §D).

Evaluated with no wait, after every other witness, and never through run_cmd's `derive()`,
which turns every exit into a refusal. The recorded value is
`<conflicts mode>/<ci mode>:<conflict state>/<ci state>@<head sha>`, `off` when both keys
are `off` (nothing is read), and `managed` for a driver-managed branch. A failing `fix`
concern refuses (exit 2, naming `settle`); an unknown or pending one, or a transient forge
failure, holds the unit (exit 75) and records nothing. An `unsupported` state is recorded
and refuses nothing.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from fr._hosts import origin_slug
from fr.hostclient import client_for
from fr.settle.model import EXIT_FAILING, EXIT_PENDING, SettlePending, SettleRefused


def _branch(repo_root: Path) -> str:
    done = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    branch = done.stdout.strip()
    if done.returncode != 0 or not branch:
        raise SettleRefused("HEAD is detached: fr settles a run's feature branch")
    return branch


def settle_witness(repo_root: Path, state: Any, client: Any = None) -> str:
    """The witness value, or `SettleRefused` / `SettlePending`. *client* is the repo's
    forge client (`fr.hostclient.client_for` when None, resolved only once a read is due);
    `SettingsError` when the setting is unreadable."""
    from fr.settle.managed import driver_managed
    from fr.settle.modes import run_modes
    from fr.settle.read import read_verdict

    branch = _branch(repo_root)
    if driver_managed(branch):
        return "managed"
    modes = run_modes(repo_root, state)
    if modes.both_off:
        return "off"
    repo = origin_slug(repo_root)
    if repo is None:
        raise SettleRefused("cannot read the forge repository from the origin remote")
    if client is None:
        client = client_for(repo_root)
    verdict = read_verdict(
        repo_root, client, repo, branch, getattr(state, "pr", None), modes,
        wait=0, clock=time.time, sleep=time.sleep,
    )  # fmt: skip
    said = "; ".join(verdict.lines)
    if verdict.exit_code == EXIT_FAILING:
        raise SettleRefused(f"the PR has not settled: {said}")
    if verdict.exit_code == EXIT_PENDING:
        raise SettlePending(f"the PR is still settling: {said}")
    return verdict.witness


def deliver_witness(key: str, repo_root: Path, state: Any, console: Any) -> str:
    """`settle_witness` for `fr run resolve`: the value, or a printed line and
    `typer.Exit` (75 for a hold, 2 for a refusal), both before any write."""
    import typer
    from rich.markup import escape

    from fr.settings import SettingsError

    try:
        return settle_witness(repo_root, state)
    except SettlePending as e:
        console.print(
            f"[yellow]{key}: settle — {escape(str(e))}. Nothing was recorded: run "
            "`fr pr settle --wait <s>`, then resolve again.[/yellow]",
            soft_wrap=True,
        )
        raise typer.Exit(EXIT_PENDING) from e
    except (SettleRefused, SettingsError) as e:
        console.print(
            f"[red]{key}: refused — settle: {escape(str(e))}. Fix it and push with "
            "`fr push`, or record an override with its reason in the spec's "
            "`## Verification` (`settle.<key>: <mode> — <reason>`).[/red]",
            soft_wrap=True,
        )
        raise typer.Exit(2) from e

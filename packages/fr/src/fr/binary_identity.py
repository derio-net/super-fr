"""Which `fr` is this — and is it the one the harness's integrations run? (super-fr#746)

A harness's shell tool runs each command as `zsh -c`, and zsh re-reads
`~/.zshenv` on every start; a dotfiles PATH rebuild there pushes whatever the
harness put first (a wrapper running a worktree's `fr`) behind `~/.local/bin`.
The harness's hooks and plugin spawn `fr` with no shell and never read it. So
PATH order does not choose `fr`, and the two sides can run different binaries
in one session with nothing saying so.

fr does not fight PATH order. The integrations PIN the `fr` they resolved in
`FR_HARNESS_FR` (Claude Code: the `fr-binary-pin.sh` SessionStart hook writes
`$CLAUDE_ENV_FILE`; OpenCode: the plugin's `shell.env`). An env var other than
PATH survives `.zshenv`, so the shell sees the pin. At CLI entry `fr` compares
itself to it:

- no pin, or a pin naming this `fr`: nothing happens;
- a pin naming this package directory at another version — the install was
  upgraded under a live session, one binary still: warn, suggest a restart;
- a disagreeing pin, and this `fr` runs from no project venv — it was reached
  through PATH, which is the skew: REFUSE, naming both;
- a disagreeing pin, and this `fr` runs from a venv (`uv run fr`, a `uv run`
  wrapper) — a deliberate choice, which is what AGENTS.md tells an agent in a
  worktree to make: one warning line, then run.

`FR_SKIP_IDENTITY=1` bypasses. The identity is the version AND the package
directory: a branch's `fr` and the global one share a version number until
`main` releases, so a version alone cannot tell them apart.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import typer

import fr
from fr import __version__
from fr.artifacts.trigger import _asks_for_help

PIN_ENV = "FR_HARNESS_FR"
SKIP_ENV = "FR_SKIP_IDENTITY"

Action = Literal["ok", "warn", "refuse"]


@dataclass(frozen=True)
class Verdict:
    action: Action
    message: str = ""


def current_identity() -> str:
    """`<version> <package directory>` — what `fr --identity` prints."""
    return f"{__version__} {Path(fr.__file__).resolve().parent}"


def runs_from_venv(env: Mapping[str, str], prefix: str) -> bool:
    """True when this `fr` runs from the venv the caller activated or `uv run`
    chose. A uv tool's shim sets no `VIRTUAL_ENV`, and a venv activated in the
    shell for something else is not the one this interpreter belongs to."""
    venv = env.get("VIRTUAL_ENV", "")
    if not venv:
        return False
    try:
        return Path(venv).resolve() == Path(prefix).resolve()
    except OSError:
        return False


def judge(env: Mapping[str, str], *, identity: str, from_venv: bool) -> Verdict:
    pin = env.get(PIN_ENV, "")
    if not pin or pin == identity or env.get(SKIP_ENV) == "1":
        return Verdict("ok")
    if pin.partition(" ")[2] == identity.partition(" ")[2]:
        # Same package directory, another version: the one install was
        # upgraded under a live session (install.sh runs mid-flight), not a
        # second binary on PATH.
        return Verdict(
            "warn",
            f"fr: this fr was upgraded to {identity.partition(' ')[0]} after the session "
            f"pinned {pin.partition(' ')[0]}; restart the session to re-pin it.",
        )
    if from_venv:
        return Verdict(
            "warn",
            f"fr: this fr ({identity}) is not the one this session's hooks run "
            f"({pin}); running it because it was chosen from a venv.",
        )
    return Verdict(
        "refuse",
        "fr: refusing — two fr binaries serve this session (super-fr#746).\n"
        f"  this shell ran:            {identity}\n"
        f"  the harness's hooks run:   {pin}\n"
        "  PATH reached a different fr than the hooks did (a shell profile such as\n"
        "  ~/.zshenv can reorder PATH). Run the intended fr through its venv —\n"
        "  `uv run fr` in a worktree, `uv run --project <worktree> fr` elsewhere —\n"
        "  restart the session if the hooks' fr was the one replaced, or set\n"
        f"  {SKIP_ENV}=1 to run this one anyway.",
    )


def enforce(argv: Sequence[str] | None = None) -> None:
    """The CLI-entry check: warn on stderr, or exit 2. A subcommand's `--help`
    reaches the root callback too, and is answered whatever the pin says —
    detected exactly as the migration gate detects it."""
    if _asks_for_help(sys.argv[1:] if argv is None else argv):
        return
    verdict = judge(
        os.environ, identity=current_identity(), from_venv=runs_from_venv(os.environ, sys.prefix)
    )
    if verdict.action == "ok":
        return
    typer.echo(verdict.message, err=True)
    if verdict.action == "refuse":
        raise typer.Exit(2)

"""`tests: ci` — the forge's CI on the pushed head as `tests` evidence (spec
2026-11-27-run-verdict R7).

Moved from `fr.commands.run_cmd` in slice 5. `ci_tests_witness` returns a `Verdict[str]`;
a gate check that has not finished, or a forge read that failed, refuses with
`ci_evidence.CI_PENDING_EXIT` (75), and any other refusal with 2.

Engine code: no `typer`, no `rich` but `rich.markup`, no `fr.commands`
(`tests/unit/test_run_writes_layering.py`).
"""

from __future__ import annotations

from pathlib import Path

from rich.markup import escape

from fr.run.evidence import refusal
from fr.run.evidence.suite import TESTS_CI
from fr.run.verdict import Verdict


def ci_tests_witness(key: str, repo_root: Path, *, done: bool) -> Verdict[str]:
    """`tests: ci`: on a `done` resolve the `verify_ci` witness, else the bare
    claim (a failed unit vouches for no tree, and asks no forge). A pending gate
    refuses with `CI_PENDING_EXIT` and any other refusal with 2, both before any write.

    gh#1395: a failed forge read (`FORGE_ERRORS`: a timeout, an EOF, a 5xx) exits
    `CI_PENDING_EXIT` too, in one line naming it — never a traceback and exit 1,
    which fr-goal reads as "the record applied and a chained step failed". A host
    trust refusal does not answer on a retry, so it exits 2."""
    from fr.ghclient import HostRefusedError
    from fr.hostclient import FORGE_ERRORS
    from fr.run import ci_evidence

    if not done:
        return Verdict(TESTS_CI)
    try:
        return Verdict(ci_evidence.verify_ci(repo_root))
    except HostRefusedError as e:
        return Verdict(
            None,
            refusal=refusal(
                f"[red]{key}: tests: ci — the forge refused the host: {escape(str(e))}. "
                "Nothing was recorded.[/red]"
            ),
        )
    except FORGE_ERRORS as e:
        stderr = str(getattr(e, "stderr", "") or "")
        detail = " ".join(f"{e} {stderr if stderr not in str(e) else ''}".split())
        return Verdict(
            None,
            refusal=refusal(
                f"[yellow]{key}: tests: ci — could not read CI from the forge ({escape(detail)}). "
                "Nothing was recorded: resolve again.[/yellow]"
            ),
            exit_code=ci_evidence.CI_PENDING_EXIT,
        )
    except ci_evidence.CiPending as e:
        return Verdict(
            None,
            refusal=refusal(
                f"[yellow]{key}: tests: ci — {escape(str(e))}. Nothing was recorded: "
                "resolve again when CI finishes.[/yellow]"
            ),
            exit_code=ci_evidence.CI_PENDING_EXIT,
        )
    except ci_evidence.CiEvidenceRefused as e:
        return Verdict(None, refusal=refusal(f"[red]{key}: {escape(str(e))}[/red]"))

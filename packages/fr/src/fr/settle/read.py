"""One settle read of a branch's PR, shared by `fr pr settle` and the `deliver` witness
(spec 2026-11-23-pr-readiness-wait R2-R4, R8, R11).

PR discovery, the first `pr_view`, the gate set and the bounded poll, with the forge-error
rule stated once: only a `warn` or `rate_limit` forge error is transient (`SettlePending`,
exit 75); a host refusal, a 404 or an auth failure refuses (`SettleRefused`, exit 2). A
read the forge cannot make (`UnsupportedForgeOperation`) is the `unsupported` verdict, and
it takes effect before the no-open-PR refusal.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Final

from fr.settle.model import Modes, SettlePending, SettleRefused, Verdict

TRANSIENT_FORGE_KINDS: Final = frozenset({"warn", "rate_limit"})
"""`forge_error_kind`s a retry may answer: exit 75 on them, 2 on the rest."""


def forge_repo(slug: str | None, client: Any) -> str:
    """The forge repo to read: *slug* (the origin's `owner/repo`). With none, a backend
    that cannot read PRs (glab, tea: `UnsupportedBatchOps`) gets `""` and answers with
    R11's `unsupported` when asked; any other refuses (review p2-r3)."""
    from fr.ghclient import UnsupportedBatchOps

    if slug is not None:
        return slug
    if isinstance(client, UnsupportedBatchOps):
        return ""
    raise SettleRefused("cannot read the forge repository from the origin remote")


def read_verdict(
    repo_root: Path,
    client: Any,
    repo: str,
    branch: str,
    recorded: str | None,
    modes: Modes,
    *,
    wait: float,
    clock: Callable[[], float],
    sleep: Callable[[float], None],
) -> Verdict:
    """The verdict for *branch*'s PR (the run's *recorded* url first) after a poll of up
    to *wait* seconds. `SettleRefused` or `SettlePending` on a failure, as above."""
    from fr.ghclient import HostRefusedError, UnsupportedForgeOperation
    from fr.hostclient import FORGE_ERRORS, forge_error_kind
    from fr.settle import poll, target
    from fr.settle.evaluate import merged_verdict, unsupported_verdict

    no_ci = target.ci_none(repo_root)
    view: dict[str, Any] = {}
    try:
        found = target.open_pr(client, repo, branch, recorded)
        if isinstance(found, str):
            return merged_verdict(found, target.local_head(repo_root))
        pr, view = found
        gates = None
        if modes.ci.mode != "off" and not no_ci:
            gates = target.gate_names(repo_root, client, repo, str(view.get("base_ref") or ""))
        return poll.settle(
            client,
            repo,
            pr,
            gate_names=gates,
            modes=modes,
            ci_none=no_ci,
            wait=wait,
            clock=clock,
            sleep=sleep,
            committed_at=lambda sha: target.committed_at(repo_root, sha),
            first_view=view,
        )
    except UnsupportedForgeOperation as e:
        # Review p2-r2: with no head from the forge, the local HEAD, never an empty `@`.
        head = str(view.get("head_oid") or "") or target.local_head(repo_root)
        return unsupported_verdict(modes, backend=e.backend, op=e.op, head=head)
    except HostRefusedError as e:
        # A host trust refusal does not answer on a retry (run_cmd._ci_tests_witness).
        raise SettleRefused(f"the forge refused the host: {e}") from e
    except FORGE_ERRORS as e:
        if forge_error_kind(e) in TRANSIENT_FORGE_KINDS:
            raise SettlePending(f"the forge read failed, try again: {e}") from e
        raise SettleRefused(f"the forge refused the read: {e}") from e

"""What `fr pr settle` reads before it polls (spec 2026-11-23-pr-readiness-wait §B).

The PR (the run cursor's `pr`, else the open PR whose head is the branch), the gate set
(`declared_gates`, else the base's required checks, else every check: unlike
`ci_evidence._gate_names`, the last fallback never refuses), `ci none` from `fr services`,
and a head's commit time.
"""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path
from typing import Any

from fr.settle.model import SettleRefused

_PULL = re.compile(r"/pull/(\d+)/?$")


def pr_number(url: str | None) -> int | None:
    """The number in a recorded PR url (`.../pull/<n>`), None when it names none."""
    m = _PULL.search(url or "")
    return int(m.group(1)) if m else None


def open_pr(
    client: Any, repo: str, branch: str, recorded_url: str | None
) -> tuple[int, dict[str, Any]] | str:
    """`(number, view)` of the PR to settle: the run cursor's recorded PR (*recorded_url*,
    which the caller reads) while it is open, else the open PR whose head is *branch*.
    With none open: the recorded url when that PR merged (nothing to settle), else a
    `SettleRefused` naming what to do (l-errors-r5)."""
    recorded = pr_number(recorded_url)
    view: dict[str, Any] = {}
    if recorded is not None:
        view = client.pr_view(repo, recorded)
        if str(view.get("state") or "OPEN") == "OPEN":
            return recorded, view
    found = client.open_pr_for_head(repo, branch)
    if found:
        number = int(found["number"])
        return number, client.pr_view(repo, number)
    if recorded is None:
        raise SettleRefused(
            f"no open pull request for {branch}: open one with `fr pr create` first"
        )
    state = str(view.get("state"))
    if state == "MERGED":
        return str(recorded_url)
    raise SettleRefused(
        f"the run's PR {recorded_url} is {state} and no PR is open for {branch}: reopen it "
        "or open a new PR with `fr pr create`"
    )


def gate_names(repo_root: Path, client: Any, repo: str, base: str) -> list[str] | None:
    """The gate set, or None to read every check on the head. A `.fr/ci.yaml` fr
    cannot read (malformed, or git unavailable) is a refusal."""
    from fr.run.ci_evidence import CiEvidenceRefused, declared_gates

    try:
        declared = declared_gates(repo_root, base or None)
    except CiEvidenceRefused as e:
        raise SettleRefused(str(e)) from e
    if declared:
        return declared
    required = list(client.required_check_names(repo, base)) if base else []
    return required or None


def ci_none(repo_root: Path) -> bool:
    """`fr services` says this repo has no CI (a resolution failure is not none)."""
    from fr.services.resolve import resolve_services

    return resolve_services(repo_root, lenient=True).ci.type == "none"


def _commit_time(repo_root: Path, rev: str) -> float | None:
    done = subprocess.run(
        ["git", "log", "-1", "--format=%ct", rev, "--"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    out = done.stdout.strip()
    return float(out) if done.returncode == 0 and out.isdigit() else None


def local_head(repo_root: Path) -> str:
    """The checkout's HEAD sha, or empty when git cannot say."""
    done = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def committed_at(repo_root: Path, sha: str) -> float:
    """*sha*'s commit time; HEAD's when *sha* is not local; now when neither reads."""
    for rev in (sha, "HEAD"):
        found = _commit_time(repo_root, rev) if rev else None
        if found is not None:
            return found
    return time.time()

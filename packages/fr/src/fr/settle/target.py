"""What `fr pr settle` reads before it polls (spec 2026-11-23-pr-readiness-wait §B).

The PR (the run cursor's `pr`, else the open PR whose head is the branch), the gate set
(`declared_gates`, else the base's required checks, else every check: unlike
`ci_evidence._gate_names`, the last fallback never refuses), `ci none` from `fr services`,
and a head's commit time.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fr.settle.model import SettleRefused

_PULL = re.compile(r"/pull/(\d+)/?$")
_SHA = re.compile(r"[0-9a-f]{40}([0-9a-f]{24})?")
"""A full SHA-1 or SHA-256 object id: anything else a forge says never reaches git."""


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
        ["git", "log", "-1", "--format=%ct", "--end-of-options", rev, "--"],
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


@dataclass(frozen=True)
class HeadTime:
    """A PR head's commit time: `at` None when nothing could be read (age unknown), and
    `estimated` when it is local HEAD's because the PR head is not in this clone."""

    at: float | None
    estimated: bool = False


def _fetch(repo_root: Path, sha: str) -> bool:
    try:
        done = subprocess.run(
            ["git", "fetch", "--quiet", "--no-tags", "origin", "--end-of-options", sha],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.TimeoutExpired:
        return False
    return done.returncode == 0


def committed_at(repo_root: Path, sha: str) -> HeadTime:
    """*sha*'s commit time: local, else after one quiet fetch of it; else local HEAD's,
    marked estimated; else unknown. Never the clock (l-errors-r7). No forge client offers
    a commit's time today, so the forge is not asked. A *sha* that is not a full object id
    is unknown with no git call at all (sec-r1)."""
    if sha and not _SHA.fullmatch(sha):
        return HeadTime(None)
    if sha:
        found = _commit_time(repo_root, sha)
        if found is None and _fetch(repo_root, sha):
            found = _commit_time(repo_root, sha)
        if found is not None:
            return HeadTime(found)
    head = _commit_time(repo_root, "HEAD")
    return HeadTime(head, estimated=True) if head is not None else HeadTime(None)

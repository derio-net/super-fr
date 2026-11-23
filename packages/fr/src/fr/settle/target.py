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

_PULL = re.compile(r"/pull/(\d+)/?$")


def recorded_pr(repo_root: Path) -> int | None:
    """The PR number the branch's one run records, None without one."""
    from fr.commands import push_cmd

    runs = push_cmd.branch_runs(repo_root)
    url = runs[0].pr if len(runs) == 1 else None
    m = _PULL.search(url or "")
    return int(m.group(1)) if m else None


def find_pr(repo_root: Path, client: Any, repo: str, branch: str) -> int | None:
    recorded = recorded_pr(repo_root)
    if recorded is not None:
        return recorded
    found = client.open_pr_for_head(repo, branch)
    return int(found["number"]) if found else None


def gate_names(repo_root: Path, client: Any, repo: str, base: str) -> list[str] | None:
    """The gate set, or None to read every check on the head."""
    from fr.run.ci_evidence import declared_gates

    declared = declared_gates(repo_root, base or None)
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


def committed_at(repo_root: Path, sha: str) -> float:
    """*sha*'s commit time; HEAD's when *sha* is not local; now when neither reads."""
    for rev in (sha, "HEAD"):
        found = _commit_time(repo_root, rev) if rev else None
        if found is not None:
            return found
    return time.time()

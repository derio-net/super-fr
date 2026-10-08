"""CI as test evidence — spec 2026-10-07-cloud-triage R22, §I.

A phase unit or `deliver` may offer `evidence: {tests: ci}`: the forge's CI on
the pushed head instead of a local suite log. `verify_ci` decides whether that
claim holds and returns the witness `ci:<ci sha>+<base sha>;tree=<code tree>`,
or raises: `CiPending` (exit `CI_PENDING_EXIT`, the cursor unmoved — resolve
again when CI finishes) or `CiEvidenceRefused` (exit 2). Every refusal fires
before any write; the only writes are the caller's, after a witness.

What a green gate proves is narrower than a local log: a `pull_request`
workflow tests the synthetic merge of the head into the base, so the witness
names both shas. `;tree=` is HEAD's code tree, which is what `tests: reuse`
reads (`run_cmd._latest_tests_witness`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from fr.git import GitUnavailableError, git_answer

CI_PENDING_EXIT = 75
"""`fr run resolve`'s exit while a gate check has not finished (EX_TEMPFAIL):
not idle, not refused — the unit stays held until CI ends."""

CI_CONFIG = ".fr/ci.yaml"
"""The repo's gate-check declaration, read from HEAD: `gate_checks: [<name>, ...]`."""

WALK_LIMIT = 50
"""How many first-parent ancestors of HEAD (HEAD included) may stand in as the
CI sha while their code tree equals HEAD's (§I step 3)."""

UNKNOWN_BASE = "unknown"
"""The witness's base sha when GitHub names no PR on the gate's run."""


class CiEvidenceRefused(Exception):  # noqa: N818 — the name the plan (P2.T2) fixes
    """`tests: ci` cannot be accepted; the message says why (exit 2)."""


class CiPending(Exception):  # noqa: N818 — the name the plan (P2.T2) fixes
    """A gate check on the CI sha has not finished (exit `CI_PENDING_EXIT`)."""

    def __init__(self, sha: str, detail: str = "") -> None:
        self.sha = sha
        more = f" ({detail})" if detail else ""
        super().__init__(f"CI has not finished for {sha}{more}; resolve again when it does")


def _git(repo_root: Path, *args: str) -> str:
    try:
        res = git_answer(repo_root, *args)
    except GitUnavailableError as e:
        raise CiEvidenceRefused(f"tests: ci — git could not answer: {e}") from e
    if res.returncode != 0:
        raise CiEvidenceRefused(
            f"tests: ci — `git {' '.join(args)}` failed: {res.stderr.strip() or res.returncode}"
        )
    return res.stdout


def load_gate_checks(repo_root: Path) -> list[str] | None:
    """The gate-check names `.fr/ci.yaml` declares at HEAD; None when HEAD has
    no such file. A file that is not `gate_checks:` with a non-empty list of
    names is refused, never read as "no gates"."""
    try:
        res = git_answer(repo_root, "show", f"HEAD:{CI_CONFIG}")
    except GitUnavailableError as e:
        raise CiEvidenceRefused(f"tests: ci — git could not read {CI_CONFIG}: {e}") from e
    if res.returncode != 0:
        return None
    try:
        data = yaml.safe_load(res.stdout)
    except yaml.YAMLError as e:
        raise CiEvidenceRefused(f"{CI_CONFIG} at HEAD is not YAML: {e}") from e
    names = data.get("gate_checks") if isinstance(data, dict) else None
    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(n, str) and n.strip() for n in names)
    ):
        raise CiEvidenceRefused(
            f"{CI_CONFIG} at HEAD must be `gate_checks: [<check name>, ...]` with at least one name"
        )
    return [n.strip() for n in names]


def _check_services(repo_root: Path) -> None:
    """§I step 1: the forge is GitHub and `fr services` CI is not `none`."""
    from fr.services.model import ServicesError
    from fr.services.resolve import resolve_services

    try:
        services = resolve_services(repo_root)
    except ServicesError as e:
        raise CiEvidenceRefused(f"tests: ci — fr services cannot be resolved: {e}") from e
    if services.forge.type != "github":
        raise CiEvidenceRefused(
            f"tests: ci — the forge is {services.forge.type}; CI evidence is read from "
            "GitHub only. Run the full suite into a log and name it."
        )
    if services.ci.type == "none":
        raise CiEvidenceRefused(
            "tests: ci — `fr services` says this repo's CI is none, so no CI run can "
            "vouch for it. Run the full suite into a log and name it."
        )


def _check_pushed(repo_root: Path) -> tuple[str, str]:
    """§I step 2: `(branch, head)` when HEAD is the remote branch's head and no
    code path is uncommitted."""
    from fr.run.code_tree import dirty_code_paths

    branch = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    head = _git(repo_root, "rev-parse", "HEAD").strip()
    try:
        dirty = dirty_code_paths(repo_root)
    except GitUnavailableError as e:
        raise CiEvidenceRefused(f"tests: ci — git could not answer: {e}") from e
    if dirty:
        n = len(dirty)
        raise CiEvidenceRefused(
            f"tests: ci — {n} code path{'' if n == 1 else 's'} uncommitted "
            f"({', '.join(dirty[:5])}); CI tested none of it. Commit and push, then resolve."
        )
    listed = _git(repo_root, "ls-remote", "origin", f"refs/heads/{branch}").split()
    remote = listed[0] if listed else ""
    if remote != head:
        where = f"origin/{branch} is {remote[:12]}" if remote else f"origin has no {branch}"
        raise CiEvidenceRefused(
            f"tests: ci — HEAD {head[:12]} is not pushed ({where}); "
            f"push it (`git push origin {branch}`), wait for CI, then resolve."
        )
    return branch, head


def _open_pr(client: Any, repo: str, branch: str) -> int:
    """§I step 4: the number of the branch's open PR, refused when none or conflicting."""
    prs = [p for p in client.list_prs_by_head(repo, branch) if p.get("state") == "OPEN"]
    if not prs:
        raise CiEvidenceRefused(
            f"tests: ci — no open pull request for {branch}; CI runs on a pull request, "
            "so open one (a draft is enough)."
        )
    number = int(prs[0]["number"])
    mergeable = str(client.pr_view(repo, number).get("mergeable") or "UNKNOWN")
    if mergeable == "CONFLICTING":
        raise CiEvidenceRefused(
            f"tests: ci — PR #{number} conflicts with its base; GitHub runs no "
            "pull_request workflow for a conflicting PR. Resolve the conflict and push."
        )
    return number


def _gate_names(repo_root: Path, client: Any, repo: str, pr: int) -> list[str]:
    declared = load_gate_checks(repo_root)
    if declared is not None:
        return declared
    required = sorted({str(r["name"]) for r in client.pr_required_checks(repo, pr)})
    if not required:
        raise CiEvidenceRefused(
            f"tests: ci — no gate checks: HEAD has no {CI_CONFIG} and the base branch "
            f"requires no status check. Declare them in {CI_CONFIG} "
            "(`gate_checks: [<check name>]`) or as required checks on the base branch."
        )
    return required


def _ci_sha(
    repo_root: Path, client: Any, repo: str, head: str, gates: list[str]
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    """§I step 3: `(ci sha, its checks, HEAD's checks)` — the first of HEAD's
    first-parent ancestors (HEAD first, at most `WALK_LIMIT`) whose code tree is
    HEAD's and on which CI reported a gate check. `ci sha` is "" when none is."""
    from fr.run.code_tree import code_tree

    try:
        tree = code_tree(repo_root)
        revs = _git(
            repo_root, "rev-list", "--first-parent", f"--max-count={WALK_LIMIT}", "HEAD"
        ).split()
        head_checks: list[dict[str, Any]] = []
        for rev in revs:
            if code_tree(repo_root, rev) != tree:
                break
            checks = client.commit_checks(repo, rev)
            if rev == head:
                head_checks = checks
            if any(c.get("name") in gates for c in checks):
                return rev, checks, head_checks
    except GitUnavailableError as e:
        raise CiEvidenceRefused(f"tests: ci — git could not answer: {e}") from e
    return "", [], head_checks


def _finished(check: dict[str, Any]) -> bool:
    return check.get("status") == "completed"


def verify_ci(repo_root: Path, client: Any = None) -> str:
    """The `tests: ci` witness for a `done` resolve, or raise (§I steps 1-6).

    *client* is the repo's `GhClient` (`fr.hostclient.client_for` when None,
    resolved only after the checks that need no forge)."""
    from fr._hosts import origin_slug
    from fr.run.code_tree import code_tree

    _check_services(repo_root)
    branch, head = _check_pushed(repo_root)
    repo = origin_slug(repo_root)
    if not repo:
        raise CiEvidenceRefused("tests: ci — cannot tell the GitHub repo (no `origin` remote)")
    if client is None:
        from fr.hostclient import client_for

        client = client_for(repo_root)
    pr = _open_pr(client, repo, branch)
    gates = _gate_names(repo_root, client, repo, pr)
    ci_sha, checks, head_checks = _ci_sha(repo_root, client, repo, head, gates)
    if not ci_sha:
        # No same-tree commit carries a gate yet. While HEAD's CI is still
        # running (or has not reported at all), a gate whose job waits on
        # others has no check run yet: pending, not absent.
        if not head_checks or not all(_finished(c) for c in head_checks):
            raise CiPending(head, f"no {', '.join(gates)} reported yet")
        raise CiEvidenceRefused(
            f"tests: ci — gate check{'' if len(gates) == 1 else 's'} "
            f"{', '.join(gates)} absent on {head[:12]}: CI finished without "
            f"reporting {'it' if len(gates) == 1 else 'them'}."
        )
    by_gate = {g: [c for c in checks if c.get("name") == g] for g in gates}
    failed = [
        f"{g} {c.get('conclusion') or 'failure'} ({c.get('url') or 'no url'})"
        for g, cs in by_gate.items()
        for c in cs
        if _finished(c) and c.get("conclusion") != "success"
    ]
    if failed:
        raise CiEvidenceRefused(
            f"tests: ci — on {ci_sha[:12]}, gate check(s) did not succeed: {'; '.join(failed)}"
        )
    running = [g for g, cs in by_gate.items() if any(not _finished(c) for c in cs)]
    absent = [g for g, cs in by_gate.items() if not cs]
    if running or (absent and not all(_finished(c) for c in checks)):
        raise CiPending(ci_sha, f"waiting on {', '.join(running + absent)}")
    if absent:
        raise CiEvidenceRefused(
            f"tests: ci — gate check(s) {', '.join(absent)} absent on {ci_sha[:12]}: "
            "CI finished without reporting them."
        )
    base = next((c.get("base_sha") for g in gates for c in by_gate[g] if c.get("base_sha")), "")
    try:
        tree = code_tree(repo_root)
    except GitUnavailableError as e:
        raise CiEvidenceRefused(f"tests: ci — git could not answer: {e}") from e
    return f"ci:{ci_sha}+{base or UNKNOWN_BASE};tree={tree}"

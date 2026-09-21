"""Collect the facts a triage board is built from (spec §3.B–C).

Pure: every function returns data. No Typer, no printing, no filesystem writes
— the command layer (`fr.commands.triage_cmd`) owns I/O.

`Forge` is the whole of decision d2's seam. `GhForge` is its one
implementation and the ONLY place `fr.triage` touches a forge; a second forge
is a second class, not an edit to the collector.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from fr import gh
from fr.isolation.types import _home

SCHEMA = 1
ISSUE_LIMIT = 1000
PR_LIMIT = 200

ScopeKind = Literal["repo", "org"]


class Forge(Protocol):
    """The forge calls triage needs — nothing more."""

    def list_repos(self, *, owner: str) -> list[dict[str, Any]]: ...

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]: ...

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]: ...


class GhForge:
    """`Forge` backed by `fr.gh` (the `gh` CLI)."""

    def list_repos(self, *, owner: str) -> list[dict[str, Any]]:
        return gh.list_repos(owner=owner)

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        return gh.list_issues(repo=repo, state=state, limit=limit)

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        return gh.list_prs(repo=repo, state=state, limit=limit)

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        return gh.view_issue(repo, number)


@dataclass(frozen=True)
class Scope:
    """What is being triaged: one repo, or every non-archived repo of an owner."""

    kind: ScopeKind
    target: str  # "OWNER/REPO" for a repo, "OWNER" for an org

    @property
    def name(self) -> str:
        """Directory-safe scope name: `<owner>--<repo>` or `<owner>` (spec §3.B)."""
        return self.target.replace("/", "--")

    @property
    def owner(self) -> str:
        return self.target.split("/", 1)[0]


def default_state_dir(scope: Scope) -> Path:
    """`$HOME/.cache/fr/triage/<scope>/` — fr's existing cache root."""
    return _home() / ".cache" / "fr" / "triage" / scope.name


def scope_repos(forge: Forge, scope: Scope) -> list[str]:
    """The `OWNER/REPO` slugs in *scope*, sorted."""
    if scope.kind == "repo":
        return [scope.target]
    return sorted(f"{scope.owner}/{r['name']}" for r in forge.list_repos(owner=scope.owner))


def collect_facts(forge: Forge, scope: Scope, *, now: datetime) -> dict[str, Any]:
    """Build the `facts.json` document for *scope*."""
    repos = scope_repos(forge, scope)
    issues: list[dict[str, Any]] = []
    for repo in repos:
        for issue in forge.list_issues(repo=repo, state="open", limit=ISSUE_LIMIT):
            issues.append({"repo": repo, "number": issue["number"], "title": issue["title"]})
    return {
        "schema": SCHEMA,
        "scope": scope.name,
        "kind": scope.kind,
        "collected_at": now.isoformat(timespec="seconds"),
        "repos": repos,
        "issues": issues,
    }

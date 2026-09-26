"""Shared fixtures for the `fr triage` tests (the `tests.unit.fakes` pattern).

Imported as a package module — `from tests.unit.triage_fixtures import ...` —
never through a `sys.path` insert (review r-p3-syspath).

- `NOW`, `SUPER_FR`, `ISSUES`, `PRS`: the CAPTURED super-fr `gh` fixtures and
  the scope they were captured for;
- `FakeForge` / `_super_fr_forge`: a Forge serving canned per-repo data;
- `forbidden_imports`: the AST import walker behind both the forge seam test
  (review r-p2-seam-ast) and the render-reads-no-clock test (review
  r-p3-clock-regex). One walker, so both checks catch the same spellings.
"""

from __future__ import annotations

import ast
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fr.triage.errors import ForgeError
from fr.triage.model import Scope

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "triage"
NOW = datetime(2026, 9, 21, 12, 0, tzinfo=UTC)
SUPER_FR = Scope(kind="repo", target="derio-net/super-fr")


def _load(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return data


ISSUES = _load("super-fr-issues.json")
PRS = _load("super-fr-prs.json")


class FakeForge:
    """A Forge serving per-repo canned data and recording every call."""

    def __init__(
        self,
        *,
        issues: dict[str, list[dict[str, Any]]],
        prs: dict[str, list[dict[str, Any]]],
        repos: list[dict[str, Any]] | None = None,
        failing: dict[str, str] | None = None,
        closed: dict[tuple[str, int], dict[str, Any]] | None = None,
        file_bodies: dict[tuple[str, str, str], str | Exception] | None = None,
        comments: dict[tuple[str, int], list[dict[str, Any]]] | None = None,
        head_prs: dict[tuple[str, str], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.issues = issues
        self.prs = prs
        self.repos = repos or []
        self.failing = failing or {}
        self.closed = closed or {}
        self.file_bodies = file_bodies or {}
        self.comments = comments or {}
        self.head_prs = head_prs or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def list_repos(self, *, owner: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_repos", {"owner": owner, "limit": limit}))
        return self.repos

    def list_issues(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_issues", {"repo": repo, "state": state, "limit": limit}))
        if repo in self.failing:
            raise ForgeError(self.failing[repo])
        return self.issues[repo]

    def list_prs(self, *, repo: str, state: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_prs", {"repo": repo, "state": state, "limit": limit}))
        return self.prs[repo]

    def list_open_prs(self, *, repo: str, limit: int) -> list[dict[str, Any]]:
        self.calls.append(("list_open_prs", {"repo": repo, "limit": limit}))
        return [p for p in self.prs[repo] if p.get("state") == "OPEN"]

    def view_issue(self, *, repo: str, number: int) -> dict[str, Any]:
        self.calls.append(("view_issue", {"repo": repo, "number": number}))
        return self.closed[(repo, number)]

    def read_file_at_ref(self, *, repo: str, path: str, ref: str) -> str:
        self.calls.append(("read_file_at_ref", {"repo": repo, "path": path, "ref": ref}))
        if (repo, path, ref) not in self.file_bodies:
            # What the contents API answers for an absent file (captured live
            # 2026-09-25, `gh api repos/derio-net/super-fr/contents/.fr/triage.yaml`).
            raise ForgeError("Not Found (HTTP 404)")
        body = self.file_bodies[(repo, path, ref)]
        if isinstance(body, Exception):
            raise body
        return body

    def list_issue_comments(self, *, repo: str, number: int) -> list[dict[str, Any]]:
        self.calls.append(("list_issue_comments", {"repo": repo, "number": number}))
        return self.comments.get((repo, number), [])

    def list_prs_by_head(self, *, repo: str, branch: str) -> list[dict[str, Any]]:
        self.calls.append(("list_prs_by_head", {"repo": repo, "branch": branch}))
        return self.head_prs.get((repo, branch), [])

    def anchor_reads(self) -> list[dict[str, Any]]:
        """`read_file_at_ref` calls other than collect's one config read per repo."""
        return [kw for kw in self.called("read_file_at_ref") if kw["path"] != ".fr/triage.yaml"]

    def called(self, name: str) -> list[dict[str, Any]]:
        return [kw for n, kw in self.calls if n == name]


def _super_fr_forge() -> FakeForge:
    return FakeForge(
        issues={"derio-net/super-fr": ISSUES},
        prs={"derio-net/super-fr": PRS},
        closed={},
    )


FORGE_MODULES = ("fr.gh", "subprocess")


def forbidden_imports(
    path: Path, package: str, modules: Iterable[str] = FORGE_MODULES
) -> list[str]:
    """Every import of one of *modules* in *path*, a module of *package*.

    Caught: `import m` (any alias), `from <parent> import <leaf>` (any alias,
    any grouping, or its relative spelling), `from m import ...`, submodules of
    `m`, imports nested in a function, and the same names through
    `importlib.import_module` / `__import__`. By default *modules* is the forge
    seam's pair (review r-p2-seam-ast).
    """
    banned = tuple(modules)

    def hit(name: str) -> bool:
        return any(name == m or name.startswith(m + ".") for m in banned)

    def absolute(node: ast.ImportFrom) -> str:
        if node.level == 0:
            return node.module or ""
        parts = package.split(".")
        base = parts[: len(parts) - (node.level - 1)]
        return ".".join([*base, *([node.module] if node.module else [])])

    found: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.Import):
            found += [f"import {a.name}" for a in node.names if hit(a.name)]
        elif isinstance(node, ast.ImportFrom):
            module = absolute(node)
            found += [
                f"from {module} import {a.name}"
                for a in node.names
                if hit(module) or hit(f"{module}.{a.name}")
            ]
        elif (
            isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "__import__")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
            )
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and hit(node.args[0].value)
        ):
            found.append(f"dynamic import of {node.args[0].value}")
    return found

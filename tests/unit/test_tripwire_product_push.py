"""Tripwire: every product-branch push goes through ONE function (review pr1431-r1).

`fr.git_policy.product.push_product_branch` runs the placement's guards (stealth's scan
of the paths and messages a push adds, quiet's R23 check and atomic push). A second
place that runs `git push` against a product branch is how `fr placement migrate-branch`
pushed fr's files to a stealth target around that scan. So the git push sites under
`packages/*/src` are pinned here, by exact module and function: a new one fails until it
is either routed through the one pusher or argued into the allowlist in a diff to this
file.

A "git push site" is a call to a git runner (a callee whose name holds `git`) with the
literal `"push"` among its positional arguments (`_git(root, "push", ...)`), or a list
literal starting `["push", ...]` or `["git", "push", ...]` (an argv).
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

PRODUCT_PUSHER = {("fr.git_policy.product", "push_product_branch")}
"""The one function that pushes a product branch."""

FR_BRANCH_PUSHERS = {
    # quiet's `fr` branch (with the product branch only when product calls it, code=True)
    ("fr.git_policy.push", "_atomic_push"),
    ("fr.placement.move", "_push_fr_branch"),
    ("fr.commands.settings_cmd", "init_quiet"),
}
TRACKING_REPO_PUSHERS = {
    # compare-and-swap ref pushes: the stealth tracking repo and triage's state refs
    ("fr.triage.gitseam", "push_ref_cas"),
}
FR_OWNED_BOT_BRANCH_PUSHERS = {
    # branches fr itself owns, outside any run workspace: the debt sweep's archive branch,
    # the DevOps gate's ops branch, and the triage driver's batch and export branches
    ("fr.commands.debt_cmd", "_push"),
    ("fr.commands.ops_gate_cmd", "OpsWorkspace.push"),
    ("fr.triage.gitseam", "Checkout.publish_branch"),
    ("fr.triage.gitseam", "Worktree.push"),
}
QUEUE_PUSHERS = {
    # the wave merge queue (spec 2026-11-19-wave-merge-queue R4, R10): its fr-owned slot
    # branches, and its landing, ONE atomic push leased on the base and every built-from
    # head that moves the default branch to a tested combination of approved PRs. That
    # is the forge merge's job done by push, not a write of fr's own files, so it is not
    # the placement's product pusher (which scans what fr adds to a product branch).
    ("fr.triage.gitseam", "Checkout.push_leased"),
}
ALLOWED = (
    PRODUCT_PUSHER | FR_BRANCH_PUSHERS | TRACKING_REPO_PUSHERS | FR_OWNED_BOT_BRANCH_PUSHERS
    | QUEUE_PUSHERS
)  # fmt: skip


def _module(path: Path) -> str:
    parts = path.relative_to(path.parents[len(path.parts) - path.parts.index("src") - 2])
    return ".".join(parts.with_suffix("").parts)


class _Sites(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.found: set[str] = set()
        self.atomic_calls: list[tuple[str, ast.Call]] = []

    def _scoped(self, node: ast.AST, name: str) -> None:
        self.stack.append(name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._scoped(node, node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._scoped(node, node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._scoped(node, node.name)

    def _here(self) -> str:
        return ".".join(self.stack) or "<module>"

    def visit_Call(self, node: ast.Call) -> None:
        name = (
            node.func.attr
            if isinstance(node.func, ast.Attribute)
            else getattr(node.func, "id", None)
        )
        runner = isinstance(name, str) and "git" in name.lower()
        if runner and any(isinstance(a, ast.Constant) and a.value == "push" for a in node.args):
            self.found.add(self._here())
        if name == "atomic_push":
            self.atomic_calls.append((self._here(), node))
        self.generic_visit(node)

    def visit_List(self, node: ast.List) -> None:
        words = [e.value for e in node.elts[:2] if isinstance(e, ast.Constant)]
        if words[:1] == ["push"] or words == ["git", "push"]:
            self.found.add(self._here())
        self.generic_visit(node)


def _scan() -> tuple[set[tuple[str, str]], list[tuple[str, str, ast.Call]]]:
    sites: set[tuple[str, str]] = set()
    atomic: list[tuple[str, str, ast.Call]] = []
    for path in sorted((REPO / "packages").glob("*/src/**/*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        visitor = _Sites()
        visitor.visit(tree)
        module = _module(path)
        sites |= {(module, where) for where in visitor.found}
        atomic += [(module, where, call) for where, call in visitor.atomic_calls]
    return sites, atomic


def test_every_git_push_site_is_pinned() -> None:
    sites, _ = _scan()
    unexpected = sorted(sites - ALLOWED)
    assert not unexpected, (
        f"a new `git push` site: {unexpected}. A product branch is pushed only through "
        "fr.git_policy.product.push_product_branch; route it there, or argue the new site "
        "into this file's allowlist"
    )
    stale = sorted(ALLOWED - sites)
    assert not stale, f"pinned push sites that no longer push (update the list): {stale}"


def test_atomic_push_carries_a_product_branch_only_from_the_one_pusher() -> None:
    """`atomic_push(..., code=True)` pushes the product branch with `fr`: only the one
    pusher may ask for that. Every other caller passes the literal `code=False`."""
    _, atomic = _scan()
    assert atomic, "the scan found no atomic_push call: the tripwire is blind"
    for module, where, call in atomic:
        if (module, where) in PRODUCT_PUSHER or (module, where) == ("fr.git_policy.push",
                                                                     "atomic_push"):  # fmt: skip
            continue
        code = next((k.value for k in call.keywords if k.arg == "code"), None)
        assert isinstance(code, ast.Constant) and code.value is False, (
            f"{module}.{where} calls atomic_push without the literal code=False: a product "
            "branch push belongs to fr.git_policy.product.push_product_branch"
        )


def test_the_scanner_sees_a_raw_push() -> None:
    visitor = _Sites()
    visitor.visit(ast.parse('def f():\n    _git(root, "push", "origin", "x")\n'))
    visitor.visit(ast.parse('def g():\n    run(["push", "-u", "origin"])\n'))
    visitor.visit(ast.parse('def h():\n    subprocess.run(["git", "push"])\n'))
    visitor.visit(ast.parse('def i():\n    stored(git_dir, "push", branch)\n'))
    assert visitor.found == {"f", "g", "h"}


QUEUE_LEASED_PUSH_CALLERS = {
    # the slot pushes (R4) and the one atomic landing (R10): the queue's executor alone
    ("fr.triage.queue_exec", "build"),
    ("fr.triage.queue_exec", "land_push"),
    ("fr.triage.queue_exec", "QueueExecutor.resume"),
}
QUEUE_ATOMIC_PUSH_CALLERS = {("fr.triage.queue_exec", "land_push")}


class _LeasedCalls(_Sites):
    """Every call of a `push_leased` attribute, with its `atomic=` keyword."""

    def __init__(self) -> None:
        super().__init__()
        self.leased: list[tuple[str, ast.Call]] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Attribute) and node.func.attr == "push_leased":
            self.leased.append((self._here(), node))
        super().visit_Call(node)


def _leased_calls() -> list[tuple[str, str, ast.Call]]:
    out: list[tuple[str, str, ast.Call]] = []
    for path in sorted((REPO / "packages").glob("*/src/**/*.py")):
        visitor = _LeasedCalls()
        visitor.visit(ast.parse(path.read_text(), filename=str(path)))
        out += [(_module(path), where, call) for where, call in visitor.leased]
    return out


def test_only_the_queue_executor_calls_the_leased_push() -> None:
    """p3-r6: `Checkout.push_leased` moves the default branch and PR branches by a leased
    push (R10), which no placement scan sees; pinned by caller, so any new one fails until
    it is argued into this list. Only the landing asks for `--atomic`; every other caller
    passes the literal `atomic=False`."""
    calls = _leased_calls()
    callers = {(module, where) for module, where, _ in calls}
    assert callers == QUEUE_LEASED_PUSH_CALLERS, (
        f"Checkout.push_leased callers changed: {sorted(callers ^ QUEUE_LEASED_PUSH_CALLERS)}. "
        "Only the wave merge queue's executor pushes leased; argue a new caller here"
    )
    for module, where, call in calls:
        atomic = next((k.value for k in call.keywords if k.arg == "atomic"), None)
        if (module, where) in QUEUE_ATOMIC_PUSH_CALLERS:
            assert isinstance(atomic, ast.Constant) and atomic.value is True
        else:
            assert isinstance(atomic, ast.Constant) and atomic.value is False, (
                f"{module}.{where} pushes leased without the literal atomic=False"
            )


def test_the_leased_push_scanner_sees_a_call() -> None:
    visitor = _LeasedCalls()
    visitor.visit(ast.parse("def f():\n    c.push_leased([], {}, atomic=True)\n"))
    assert [where for where, _ in visitor.leased] == ["f"]

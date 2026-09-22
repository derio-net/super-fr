"""The retired bare `derio-net` marketplace name must not reach a user.

AGENTS.md: super-fr installs as `derio-net--super-fr`; the bare org name was
retired after super-fr and blog-craft evicted each other from it, and both
installers purge it. An error message pointing at
`~/.claude/plugins/marketplaces/derio-net/…` sends the reader to a directory
that no longer exists.

One such message survived the rename in `fr.isolation.local` because its path
was split across two implicitly concatenated literals (`…/marketplaces/` then
`derio-net/scripts/…`), so no whole-path grep could match it. Python's parser
joins implicit concatenation into ONE constant, so an AST scan sees what grep
cannot — that is the whole reason this tripwire walks the AST.

The single legitimate occurrence is `plan_validator_wrapper._DELEGATE_PATHS`:
every fr-enabled repo has a COMMITTED wrapper carrying the old path, so the
recognizer must keep accepting it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fr.isolation.local import IsolationError, LocalWorktreeDevcontainerTarget
from fr.plan_validator_wrapper import REPAIR_COMMAND

REPO = Path(__file__).resolve().parents[2]
RETIRED = "marketplaces/derio-net/"
ALLOWED = {("packages/fr/src/fr/plan_validator_wrapper.py", "_DELEGATE_PATHS")}


def retired_name_sites(source: str, rel: str) -> list[int]:
    """Line numbers of string constants in *source* naming the retired path.

    Constants inside an allowed assignment (`ALLOWED`) are skipped.
    """
    tree = ast.parse(source)
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            if any((rel, n) in ALLOWED for n in names):
                skip.update(id(c) for c in ast.walk(node.value))
    return sorted(
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and RETIRED in node.value
        and id(node) not in skip
    )


def test_no_source_string_names_the_retired_bare_marketplace() -> None:
    hits = [
        f"{rel}:{line}"
        for path in sorted(REPO.glob("packages/*/src/**/*.py"))
        for rel in [path.relative_to(REPO).as_posix()]
        for line in retired_name_sites(path.read_text(), rel)
    ]
    assert not hits, (
        f"source strings name the retired bare marketplace ({RETIRED}): {hits}. "
        "Use fr.plan_validator_wrapper.REPAIR_COMMAND or the derio-net--super-fr path."
    )


@pytest.mark.parametrize(
    "source",
    [
        'x = "~/.claude/plugins/marketplaces/derio-net/scripts/a.sh"',
        # The shape that survived the rename: split across two literals.
        'x = ("run `bash ~/.claude/plugins/marketplaces/"\n     "derio-net/scripts/a.sh`")',
        'x = f"{y} ~/.claude/plugins/marketplaces/" "derio-net/scripts/a.sh"',
    ],
)
def test_the_scan_sees_through_split_literals(source: str) -> None:
    """Non-vacuity: every spelling is caught, including the split one grep misses."""
    assert retired_name_sites(source, "packages/x/src/x/m.py")


def test_the_scan_allows_only_the_recognizer_tuple() -> None:
    legacy = '_DELEGATE_PATHS = (".claude/plugins/marketplaces/derio-net/scripts/v.sh",)'
    assert retired_name_sites(legacy, "packages/fr/src/fr/plan_validator_wrapper.py") == []
    # The same assignment anywhere else is not the recognizer, so it is flagged.
    assert retired_name_sites(legacy, "packages/fr/src/fr/elsewhere.py")


def test_a_worktree_missing_its_wrapper_names_the_real_repair_command(tmp_path: Path) -> None:
    worktree = tmp_path / "wt"
    (worktree / "docs" / "superpowers" / "plans").mkdir(parents=True)

    with pytest.raises(IsolationError) as exc:
        LocalWorktreeDevcontainerTarget(tmp_path)._ensure_validator_wrapper_in_worktree(worktree)

    assert REPAIR_COMMAND in str(exc.value)

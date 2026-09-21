"""THE structural tripwire for the harness-parity matrix — #436 acceptance
criterion 2: *a test fails when a hook adds a surface without declaring its
per-harness state*. 2026-09-18 harness-parity-matrix spec §3.B, Phase 2.

Three things are pinned, and they are different claims:

1. **Every shipped hook script has a row.** This is the criterion. Ship a
   new `plugins/super-fr/hooks/*.sh` and forget `parity.yaml`, and this
   fails with the row you owe.
2. **Every hook row names a script that exists.** The other direction —
   a deleted or renamed script leaves a row declaring states for nothing,
   which reads as coverage the repo no longer has.
3. **This repo's own matrix agrees with its own registration files.** So
   the matrix cannot merge stale: `check()` over the REAL repo must be
   empty. (1) and (2) are about the row/script pairing; this is about the
   cells' contents.

The pairing in (1)+(2) is what makes the criterion true *by construction*
rather than by diligence: there is no path that adds a hook and leaves the
matrix silent about it.
"""

from __future__ import annotations

import re
from pathlib import Path

from fr.harness import load_matrix
from fr.harness.check import check, pairing
from fr.harness.model import HarnessState, Matrix, parse_matrix
from fr.harness.observe import HOOKS_RELPATH, observe, shipped_scripts

REPO_ROOT = Path(__file__).resolve().parents[2]

PARITY_FILE = "packages/fr/src/fr/harness/parity.yaml"


# The pairing logic itself lives in `fr.harness.check.pairing` and is called
# from `fr harness parity --check` too (review r2-i1). These read it back out
# by direction, so the tests below keep their two distinct claims while there
# stays exactly ONE implementation — before r2-i1 the pairing existed only
# here, and the operator-facing command reported "agrees with the registration
# files" on a repo this file called drifted.


def _scripts_with_no_row(matrix: Matrix, shipped: set[str]) -> list[str]:
    return sorted(
        f.surface_id for f in pairing(matrix, frozenset(shipped)) if f.declared == "(no row)"
    )


def _rows_with_no_script(matrix: Matrix, shipped: set[str]) -> list[str]:
    by_id = {s.id: s.script for s in matrix.surfaces}
    return sorted(
        by_id[f.surface_id]
        for f in pairing(matrix, frozenset(shipped))
        if f.declared == "(row)" and by_id.get(f.surface_id)
    )


# --- (1) every shipped hook script has a row -------------------------------


def test_every_shipped_hook_script_has_a_parity_row() -> None:
    shipped = set(shipped_scripts(REPO_ROOT))
    assert shipped, f"no hook scripts found under {HOOKS_RELPATH}"
    missing = _scripts_with_no_row(load_matrix(), shipped)
    assert not missing, (
        f"shipped hook script(s) with no harness-parity row: {missing}. Add a "
        f"`kind: hook` row naming each one to {PARITY_FILE}, declaring its state on "
        "every harness — a hook that ships without saying which harnesses enforce it "
        "is exactly the gap this matrix exists to close (#436)."
    )


# --- (2) every hook row names a script that exists -------------------------


def test_every_hook_row_names_a_script_that_exists_on_disk() -> None:
    shipped = set(shipped_scripts(REPO_ROOT))
    dangling = _rows_with_no_script(load_matrix(), shipped)
    assert not dangling, (
        f"harness-parity row(s) naming a script that does not exist under "
        f"{HOOKS_RELPATH}/: {dangling}. Remove the row from {PARITY_FILE}, or fix its "
        "`script:` — a row for a script nobody ships declares coverage the repo "
        "does not have."
    )


# --- the detectors actually detect -----------------------------------------


def _one_row_matrix(script: str) -> Matrix:
    return parse_matrix(
        {
            "schema": 1,
            "surfaces": [
                {
                    "id": "only",
                    "kind": "hook",
                    "script": script,
                    "summary": "s",
                    "harnesses": {
                        "claude-code": {"state": "absent"},
                        "opencode": {"state": "absent"},
                        "hermes": {"state": "absent"},
                        "codex": {"state": "unsupported"},
                        "copilot-cli": {"state": "unsupported"},
                    },
                }
            ],
        }
    )


def test_the_missing_row_detector_fires_on_an_undeclared_script() -> None:
    """A green tripwire that cannot go red is not a tripwire."""
    assert _scripts_with_no_row(_one_row_matrix("only.sh"), {"only.sh", "new-hook.sh"}) == [
        "new-hook.sh"
    ]


def test_the_dangling_row_detector_fires_on_a_row_for_a_deleted_script() -> None:
    assert _rows_with_no_script(_one_row_matrix("deleted.sh"), {"other.sh"}) == ["deleted.sh"]


# --- (3) this repo's own matrix is not stale -------------------------------


def test_this_repos_matrix_agrees_with_its_own_registration_files() -> None:
    findings = check(load_matrix(), observe(REPO_ROOT))
    assert not findings, "harness-parity drift:\n" + "\n".join(f.message for f in findings)


# --- subagent-dispatch on OpenCode: the row #493 says was wrong ------------


def _cell(surface_id: str, harness: str) -> HarnessState:
    row = next(s for s in load_matrix().surfaces if s.id == surface_id)
    return row.harnesses[harness]


def test_subagent_dispatch_is_enforced_on_opencode() -> None:
    """2026-09-19 opencode-subagent-dispatch spec §3.E. Both halves of the
    surface now ship — the tier agents are defined and installed (phases 1-3)
    and fr-goal §5 dispatches to them (phase 4) — so the row says `enforced`,
    not `absent`."""
    assert _cell("subagent-dispatch", "opencode").state == "enforced"


def test_subagent_dispatch_on_opencode_carries_no_scope_note() -> None:
    """The retired note read "no isolation-argument dispatch primitive on
    OpenCode". That cannot be the discriminator (#493): Hermes has no
    isolation argument either and is `enforced`, and the fr-phase-executor
    carve-out positively FORBIDS one for this agent (fr-goal §6 runs executors
    inside the workspace that already exists; `fr-phase-executor-guard.sh`
    refuses the combination). A note that names a requirement of the surface
    as the reason it is missing is worse than no note — and `enforced` is a
    state the schema requires no note for, so silence here is the honest
    declaration rather than an omission."""
    assert _cell("subagent-dispatch", "opencode").scope_note is None


def test_the_subagent_dispatch_summary_carries_the_cost_policy() -> None:
    """A reader meets the claim and its price in the same place (spec §3.E).
    Asserted as a multiple and a direction, not a sentence, so rewording the
    summary does not fail this — dropping the policy does. The measured
    numbers live in fr-goal §5's clause, not here (P4.T2.S3)."""
    summary = next(s for s in load_matrix().surfaces if s.id == "subagent-dispatch").summary
    assert re.search(r"(?<![\w.])7\s*(?:[x×]|times)", summary), (
        f"the dispatch default's cost multiple is not in the row summary: {summary!r}"
    )
    assert "inline" in summary, (
        f"the multiple is stated with no baseline to be a multiple OF: {summary!r}"
    )


# --- M-4: the invariant that makes `shipped_scripts()` non-recursive safe ---


def test_every_hermes_port_has_a_top_level_sibling() -> None:
    """`shipped_scripts()` globs `hooks/*.sh` only, on the stated ground that
    `hooks/hermes/*.sh` are PORTS of those same surfaces rather than surfaces
    of their own. True today — but nothing made it stay true, and a
    Hermes-only hook would then be registered in the snippet, observed
    `present`, own no parity row, and be invisible to the tripwire above
    (review r2-m4). Pin the assumption rather than the conclusion."""
    hooks = REPO_ROOT / HOOKS_RELPATH
    ports = {p.name for p in (hooks / "hermes").glob("*.sh")}
    orphans = sorted(ports - shipped_scripts(REPO_ROOT))
    assert not orphans, (
        f"hermes-only hook script(s) with no top-level sibling: {orphans}. "
        f"`shipped_scripts()` is non-recursive, so these own no parity row and "
        f"the tripwire above cannot see them. Either add a top-level surface "
        f"script, or make `shipped_scripts()` recursive and give them rows."
    )

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

from pathlib import Path

from fr.harness import load_matrix
from fr.harness.check import check
from fr.harness.model import Matrix, parse_matrix
from fr.harness.observe import HOOKS_RELPATH, observe, shipped_scripts

REPO_ROOT = Path(__file__).resolve().parents[2]

PARITY_FILE = "packages/fr/src/fr/harness/parity.yaml"


def _hook_rows(matrix: Matrix) -> dict[str, str]:
    """`{script filename: surface id}` for every `kind: hook` row."""
    return {s.script: s.id for s in matrix.surfaces if s.kind == "hook" and s.script}


def _scripts_with_no_row(matrix: Matrix, shipped: set[str]) -> list[str]:
    return sorted(shipped - set(_hook_rows(matrix)))


def _rows_with_no_script(matrix: Matrix, shipped: set[str]) -> list[str]:
    return sorted(script for script in _hook_rows(matrix) if script not in shipped)


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

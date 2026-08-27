"""CI tripwire: every shipped workflow manifest must pass `check_workflow`
(spec §4.A, Phase 6) — a malformed shipped shape fails CI, not a consumer's
run.

Deliberately requires the glob to be NON-empty (Phase 6 dispatch brief:
"a tripwire that passes vacuously over an empty glob is exactly the kind of
test that reads as coverage and provides none"). Phase 6 lands a minimal,
valid `fr-goal.yaml` **stub** — schema-valid but not yet the real pipeline —
so this test is green from the moment it exists; Phase 11 fleshes the stub
out into the spec §4.A example manifest and this test starts covering that
real content for free, no test-file change needed.
"""

from __future__ import annotations

from pathlib import Path

from fr.workflow.check import check_workflow
from fr.workflow.model import WorkflowError, parse_manifest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_WORKFLOWS_DIR = REPO_ROOT / "plugins" / "super-fr" / "workflows"


def test_at_least_one_shipped_workflow_manifest_exists() -> None:
    manifests = sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml"))
    assert manifests, (
        f"no manifests under {SHIPPED_WORKFLOWS_DIR} — this test intentionally requires "
        "at least one (see module docstring); ship at least a minimal, valid stub"
    )


def test_every_shipped_workflow_manifest_passes_check_workflow() -> None:
    manifests = sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml"))
    for path in manifests:
        try:
            manifest = parse_manifest(path.read_text())
        except WorkflowError as e:
            raise AssertionError(f"{path}: failed to parse: {e}") from e
        errors = check_workflow(manifest)
        assert not errors, f"{path}: {errors}"

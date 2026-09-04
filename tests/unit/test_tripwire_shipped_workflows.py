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


# ── the wheel-internal copy must match the plugin copy (review r5-b5) ──
#
# `plugins/super-fr/workflows/` is canonical; `packages/fr/src/fr/workflows/`
# is the same bytes shipped INSIDE the `fr` wheel, so a host with no Claude
# Code marketplace clone (a hermes pod, an OpenCode consumer, a bare
# `uv tool install fr`) can still resolve a shipped shape. Two copies need a
# tripwire, or the packaged one silently rots into the version everyone
# without Claude Code actually runs.

PACKAGED_WORKFLOWS_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "workflows"

_SYNC_HINT = (
    "run: cp plugins/super-fr/workflows/*.yaml packages/fr/src/fr/workflows/  "
    "(the plugin directory is canonical)"
)


def test_the_packaged_copy_holds_exactly_the_shipped_manifests() -> None:
    plugin = {p.name for p in SHIPPED_WORKFLOWS_DIR.glob("*.yaml")}
    packaged = {p.name for p in PACKAGED_WORKFLOWS_DIR.glob("*.yaml")}

    assert plugin == packaged, (
        f"shipped manifests differ: plugin-only={sorted(plugin - packaged)}, "
        f"packaged-only={sorted(packaged - plugin)} — {_SYNC_HINT}"
    )


def test_the_packaged_copy_is_byte_identical() -> None:
    for path in sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml")):
        mirror = PACKAGED_WORKFLOWS_DIR / path.name
        assert mirror.read_bytes() == path.read_bytes(), f"{mirror} drifted — {_SYNC_HINT}"


def test_the_packaged_dir_is_reachable_through_importlib_resources() -> None:
    """The wheel copy is only worth having if `resolve_workflow` can find it
    the way an INSTALLED fr does — through `importlib.resources`, not through
    a path relative to this checkout."""
    from fr.workflow.resolve import packaged_shipped_workflows_dir

    found = packaged_shipped_workflows_dir()

    assert found is not None
    assert {p.name for p in found.glob("*.yaml")} == {
        p.name for p in SHIPPED_WORKFLOWS_DIR.glob("*.yaml")
    }

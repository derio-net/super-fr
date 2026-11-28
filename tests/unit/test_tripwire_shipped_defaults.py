"""CI tripwire: super-fr's shipped defaults have one home (spec
2026-11-19-event-driven-a-la-carte R15).

`plugins/super-fr/defaults/<kind>/` (`workflows`, `verifications`, `lenses`) is
canonical; `packages/fr/src/fr/defaults/<kind>/` is the generated wheel copy,
written by `scripts/sync-defaults-data.py`. This file replaces the three per-kind
tripwires (`test_tripwire_shipped_{workflows,verifications,lenses}.py`) and keeps
their assertions: each workflow passes `check_workflow`, the four strategies keep
their `when` and `driver`, the four lenses exist, the copy is byte-equal and
reachable through `importlib.resources`.

Every glob is required to be NON-empty: a tripwire that passes vacuously over an
empty glob reads as coverage and provides none.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fr.lenses.model import Lens, parse_lens
from fr.verification.model import StrategyManifest, parse_strategy
from fr.workflow.check import check_workflow
from fr.workflow.model import WorkflowError, parse_manifest

pytestmark = pytest.mark.own_artifacts

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULTS_DIR = REPO_ROOT / "plugins" / "super-fr" / "defaults"
PACKAGED_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "defaults"
KINDS = ("workflows", "verifications", "lenses")

SHIPPED_WORKFLOWS_DIR = DEFAULTS_DIR / "workflows"
PACKAGED_WORKFLOWS_DIR = PACKAGED_DIR / "workflows"
SHIPPED_VERIFICATIONS_DIR = DEFAULTS_DIR / "verifications"
SHIPPED_LENSES_DIR = DEFAULTS_DIR / "lenses"

_SYNC_HINT = (
    "run: uv run --no-project python scripts/sync-defaults-data.py "
    "(plugins/super-fr/defaults/ is canonical)"
)


# ── the one tree ────────────────────────────────────────────────────────────


def test_the_defaults_tree_holds_exactly_the_three_kinds() -> None:
    assert sorted(p.name for p in DEFAULTS_DIR.iterdir()) == sorted(KINDS)


@pytest.mark.parametrize("old", ["workflows", "verifications", "lenses"])
def test_the_old_plugin_homes_are_gone(old: str) -> None:
    assert not (REPO_ROOT / "plugins" / "super-fr" / old).exists()


@pytest.mark.parametrize("old", ["workflows", "verifications", "lens_manifests"])
def test_the_old_wheel_homes_are_gone(old: str) -> None:
    assert not (REPO_ROOT / "packages" / "fr" / "src" / "fr" / old).exists()


def test_the_old_sync_script_is_gone() -> None:
    assert not (REPO_ROOT / "scripts" / "sync-lenses-data.py").exists()


@pytest.mark.parametrize("kind", KINDS)
def test_each_kind_ships_at_least_one_manifest(kind: str) -> None:
    assert sorted((DEFAULTS_DIR / kind).glob("*.yaml")), f"no manifests under {DEFAULTS_DIR / kind}"


@pytest.mark.parametrize("kind", KINDS)
def test_the_packaged_copy_holds_exactly_the_shipped_manifests(kind: str) -> None:
    plugin = {p.name for p in (DEFAULTS_DIR / kind).glob("*.yaml")}
    packaged = {p.name for p in (PACKAGED_DIR / kind).glob("*.yaml")}

    assert plugin == packaged, (
        f"{kind}: plugin-only={sorted(plugin - packaged)}, "
        f"packaged-only={sorted(packaged - plugin)} — {_SYNC_HINT}"
    )


@pytest.mark.parametrize("kind", KINDS)
def test_the_packaged_copy_is_byte_identical(kind: str) -> None:
    for path in sorted((DEFAULTS_DIR / kind).glob("*.yaml")):
        mirror = PACKAGED_DIR / kind / path.name
        assert mirror.read_bytes() == path.read_bytes(), f"{mirror} drifted — {_SYNC_HINT}"


@pytest.mark.parametrize("kind", KINDS)
def test_the_packaged_dir_is_reachable_through_importlib_resources(kind: str) -> None:
    """The wheel copy is only worth having if an INSTALLED fr finds it the way it
    will — through `importlib.resources`, not a path relative to this checkout."""
    from fr._shipped import packaged_kind_dir

    found = packaged_kind_dir(kind)

    assert found is not None
    assert {p.name for p in found.glob("*.yaml")} == {
        p.name for p in (DEFAULTS_DIR / kind).glob("*.yaml")
    }


def test_the_sync_script_check_exits_zero() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync-defaults-data.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr


def _copy_tree(tmp_path: Path) -> tuple[Path, Path]:
    import shutil

    root = tmp_path / "repo"
    shutil.copytree(
        REPO_ROOT / "plugins" / "super-fr" / "defaults", root / "plugins/super-fr/defaults"
    )
    shutil.copytree(PACKAGED_DIR, root / "packages/fr/src/fr/defaults")
    (root / "scripts").mkdir()
    shutil.copy(REPO_ROOT / "scripts" / "sync-defaults-data.py", root / "scripts")
    return root, root / "packages/fr/src/fr/defaults"


def _sync(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "sync-defaults-data.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_sync_script_check_exits_one_on_drift_and_the_write_repairs_it(
    tmp_path: Path,
) -> None:
    root, wheel = _copy_tree(tmp_path)
    (wheel / "lenses" / "tests.yaml").write_text("drifted\n")
    (wheel / "workflows" / "stale.yaml").write_text("stale\n")
    (root / "plugins/super-fr/defaults/verifications/new.yaml").write_text("new\n")

    checked = _sync(root, "--check")
    assert checked.returncode == 1
    for name in ("lenses/tests.yaml", "workflows/stale.yaml", "verifications/new.yaml"):
        assert name in checked.stderr

    written = _sync(root)
    assert written.returncode == 0
    assert "removed packages/fr/src/fr/defaults/workflows/stale.yaml" in written.stdout
    assert "wrote packages/fr/src/fr/defaults/verifications/new.yaml" in written.stdout
    assert "wrote packages/fr/src/fr/defaults/workflows/stale.yaml" not in written.stdout
    assert _sync(root, "--check").returncode == 0
    assert not (wheel / "workflows" / "stale.yaml").exists()
    assert (wheel / "verifications" / "new.yaml").read_text() == "new\n"


# ── workflows (was test_tripwire_shipped_workflows.py) ──────────────────────


def test_every_shipped_workflow_manifest_passes_check_workflow() -> None:
    for path in sorted(SHIPPED_WORKFLOWS_DIR.glob("*.yaml")):
        try:
            manifest = parse_manifest(path.read_text())
        except WorkflowError as e:
            raise AssertionError(f"{path}: failed to parse: {e}") from e
        assert not check_workflow(manifest, None), path


def _shipped_fr_goal():
    return parse_manifest((SHIPPED_WORKFLOWS_DIR / "fr-goal.yaml").read_text())


def _step(manifest, step_id: str):
    return next(s for s in manifest.steps if s.id == step_id)


def _both_copies(name: str):
    return [
        parse_manifest((d / f"{name}.yaml").read_text())
        for d in (SHIPPED_WORKFLOWS_DIR, PACKAGED_WORKFLOWS_DIR)
    ]


def test_shipped_fr_goal_reviews_inside_the_phase_iteration() -> None:
    manifest = _shipped_fr_goal()

    assert check_workflow(manifest, None) == []
    group = _step(manifest, "implement")
    assert group.for_each == "phase"
    assert [m.id for m in group.steps] == ["implement-phase", "review-phase"]
    assert group.steps[1].needs == ("spec", "plan", "journal:plan")
    assert "review" not in [s.id for s in manifest.steps]


def test_shipped_fr_goal_runs_journal_check_between_implement_and_deliver() -> None:
    manifest = _shipped_fr_goal()
    step_ids = [s.id for s in manifest.steps]
    assert "journal-check" in step_ids

    step = _step(manifest, "journal-check")
    assert step.kind == "cli"
    assert step.run is not None
    assert "{{ artifacts.plan }}" in step.run
    assert "--require-reviews" in step.run
    assert (
        step_ids.index("implement") < step_ids.index("journal-check") < step_ids.index("deliver")
    ), step_ids


_DELIVER_EVIDENCE = ("tests", "proportionality", "docs", "visual", "walk", "settle")
_INPUT_GATES = ("requirements", "coverage", "fidelity", "requirement-rows")


def test_shipped_fr_goal_evidence_is_the_4_28_lists_plus_visual() -> None:
    for manifest in _both_copies("fr-goal"):
        assert check_workflow(manifest, None) == []
        assert _step(manifest, "brainstorm").evidence == ()
        assert _step(manifest, "spec-review").evidence == ("review", "reviewer", "findings")
        assert _step(manifest, "deliver").evidence == _DELIVER_EVIDENCE
        members = {m.id: m for m in _step(manifest, "implement").steps}
        assert members["review-phase"].agent is None


def test_shipped_fr_goal_light_evidence_carries_no_input_gate() -> None:
    for manifest in _both_copies("fr-goal-light"):
        assert check_workflow(manifest, None) == []
        assert _step(manifest, "brainstorm").evidence == ()
        assert _step(manifest, "plan").evidence == ("single-phase",)
        assert _step(manifest, "spec-plan-review").evidence == ("review", "reviewer", "findings")
        assert _step(manifest, "deliver").evidence == _DELIVER_EVIDENCE


def test_run_resolve_knows_no_input_gate() -> None:
    from fr.run.evidence import target
    from fr.workflow.artifacts import DERIVED_EVIDENCE

    for name in _INPUT_GATES:
        assert name not in target.VERIFIABLE_EVIDENCE
        assert name not in DERIVED_EVIDENCE
        assert name not in target.DERIVED_FROM


# The removals, undone — the 4.29–4.40 shape an in-flight cursor was started against.
_WITH_THE_GATES = (
    (
        "    emits: [spec, journal:spec, acceptance]\n",
        "    emits: [spec, journal:spec, acceptance]\n    evidence: [requirements]\n",
    ),
    (
        "    evidence: [review, reviewer, findings]\n\n  - id: plan\n",
        "    evidence: [review, reviewer, findings, requirements, coverage, fidelity]\n"
        "\n  - id: plan\n",
    ),
    (
        "    evidence: [tests, proportionality, docs, visual, walk, settle]\n",
        "    evidence: [tests, proportionality, requirement-rows, visual]\n",
    ),
)


def test_a_cursor_started_with_the_input_gates_does_not_drift(tmp_path: Path) -> None:
    """Drift compares step and member ids only: every removal is a field, so a run
    started on the 4.29–4.40 shape keeps advancing on this one (R8)."""
    from fr.run.model import load_run_state
    from fr.run.steps import check_step_drift

    from tests.unit.test_run_cli import _invoke, _repo

    text = (SHIPPED_WORKFLOWS_DIR / "fr-goal.yaml").read_text()
    for new, old in _WITH_THE_GATES:
        assert new in text, new
        text = text.replace(new, old, 1)
    old_shipped = tmp_path / "old"
    old_shipped.mkdir()
    (old_shipped / "fr-goal.yaml").write_text(text)
    repo = _repo(tmp_path)
    started = _invoke(
        repo, old_shipped, ["run", "start", "fr-goal", "--branch", "b", "--run-id", "r1"]
    )
    assert started.exit_code == 0, started.output

    check_step_drift(load_run_state(repo, "r1"), _shipped_fr_goal())  # raises on drift


def test_shipped_fr_goal_declares_visual_on_the_three_ui_stages() -> None:
    manifest = _shipped_fr_goal()
    members = {m.id: m for m in _step(manifest, "implement").steps}

    assert members["implement-phase"].evidence == ("visual",)
    assert members["review-phase"].evidence == ("review", "reviewer", "findings", "visual")
    assert "visual" in _step(manifest, "deliver").evidence


# ── verifications (was test_tripwire_shipped_verifications.py) ──────────────

SPEC_TABLE = {
    "candidate": ("pre-merge", "agent"),
    "client-live": ("pre-merge", "operator"),
    "prerelease": ("pre-merge", "operator"),
    "live": ("post-merge", "operator"),
}


def _strategies() -> dict[str, StrategyManifest]:
    return {
        p.stem: parse_strategy(p.read_text(), source=str(p))
        for p in SHIPPED_VERIFICATIONS_DIR.glob("*.yaml")
    }


def test_the_shipped_strategies_are_exactly_the_four_of_the_spec() -> None:
    manifests = _strategies()

    assert set(manifests) == set(SPEC_TABLE)
    for name, (when, driver) in SPEC_TABLE.items():
        m = manifests[name]
        assert (m.when, m.driver) == (when, driver), name
        assert m.verification == name


def test_the_install_contract_and_scenario_shape_of_each_strategy() -> None:
    m = _strategies()

    for name in ("candidate", "client-live"):
        assert m[name].install == (".fr/candidate-install", "{prefix}", "{worktree}")
        assert m[name].scenario == ("{scenario}",)
    assert m["prerelease"].install == (".fr/candidate-install", "{prefix}", "{source}")
    assert m["prerelease"].source == "prerelease"
    assert m["live"].install is None
    assert m["live"].scenario is None


def test_every_shipped_strategy_passes_check() -> None:
    from fr.verification.check import check_strategy

    for name, manifest in _strategies().items():
        assert check_strategy(manifest) == [], name


# ── lenses (was test_tripwire_shipped_lenses.py) ────────────────────────────

SHIPPED_LENSES = {"security", "tests", "simplicity", "errors"}
CLOSING = "A problem you see outside this lens is still reported, as an ordinary finding."


def _lenses() -> dict[str, Lens]:
    return {
        p.stem: parse_lens(p.read_text(), source=str(p)) for p in SHIPPED_LENSES_DIR.glob("*.yaml")
    }


def test_the_shipped_lenses_are_exactly_the_four_of_the_spec() -> None:
    assert {p.name for p in SHIPPED_LENSES_DIR.glob("*")} == {f"{n}.yaml" for n in SHIPPED_LENSES}


def test_each_lens_parses_and_its_stem_is_its_id() -> None:
    for stem, lens in _lenses().items():
        assert lens.id == stem


def test_each_brief_ends_with_the_outside_the_lens_sentence() -> None:
    for stem, lens in _lenses().items():
        assert lens.brief.rstrip().endswith(CLOSING), stem

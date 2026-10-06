"""CI tripwire: every shipped verification strategy parses, the set is the four
spec §A names, and the wheel copy is byte-identical (spec 2026-10-06 R2/R3).

Mirrors `test_tripwire_shipped_workflows.py`: the plugin directory is
canonical, `packages/fr/src/fr/verifications/` is the generated wheel copy.
"""

from __future__ import annotations

from pathlib import Path

from fr.verification.model import StrategyManifest, parse_strategy

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIR = REPO_ROOT / "plugins" / "super-fr" / "verifications"
PACKAGED_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "verifications"

_SYNC_HINT = (
    "run: cp plugins/super-fr/verifications/*.yaml packages/fr/src/fr/verifications/  "
    "(the plugin directory is canonical)"
)

SPEC_TABLE = {
    "candidate": ("pre-merge", "agent"),
    "client-live": ("pre-merge", "operator"),
    "prerelease": ("pre-merge", "operator"),
    "live": ("post-merge", "operator"),
}


def _manifests() -> dict[str, StrategyManifest]:
    return {
        p.stem: parse_strategy(p.read_text(), source=str(p)) for p in SHIPPED_DIR.glob("*.yaml")
    }


def test_the_shipped_set_is_exactly_the_four_of_the_spec() -> None:
    manifests = _manifests()

    assert set(manifests) == set(SPEC_TABLE)
    for name, (when, driver) in SPEC_TABLE.items():
        m = manifests[name]
        assert (m.when, m.driver) == (when, driver), name
        assert m.verification == name


def test_the_install_contract_and_scenario_shape_of_each_strategy() -> None:
    m = _manifests()

    for name in ("candidate", "client-live"):
        assert m[name].install == (".fr/candidate-install", "{prefix}", "{worktree}")
        assert m[name].scenario == ("{scenario}",)
    assert m["prerelease"].install == (".fr/candidate-install", "{prefix}", "{source}")
    assert m["prerelease"].source == "prerelease"
    assert m["live"].install is None
    assert m["live"].scenario is None


def test_every_shipped_strategy_passes_check() -> None:
    from fr.verification.check import check_strategy

    for name, manifest in _manifests().items():
        assert check_strategy(manifest) == [], name


def test_the_packaged_copy_holds_exactly_the_shipped_manifests() -> None:
    plugin = {p.name for p in SHIPPED_DIR.glob("*.yaml")}
    packaged = {p.name for p in PACKAGED_DIR.glob("*.yaml")}

    assert plugin == packaged, (
        f"plugin-only={sorted(plugin - packaged)}, packaged-only={sorted(packaged - plugin)} "
        f"— {_SYNC_HINT}"
    )


def test_the_packaged_copy_is_byte_identical() -> None:
    for path in sorted(SHIPPED_DIR.glob("*.yaml")):
        mirror = PACKAGED_DIR / path.name
        assert mirror.read_bytes() == path.read_bytes(), f"{mirror} drifted — {_SYNC_HINT}"


def test_the_packaged_dir_is_reachable_through_importlib_resources() -> None:
    from fr.verification.resolve import packaged_shipped_verifications_dir

    found = packaged_shipped_verifications_dir()

    assert found is not None
    assert {p.name for p in found.glob("*.yaml")} == {p.name for p in SHIPPED_DIR.glob("*.yaml")}

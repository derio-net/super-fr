"""CI tripwire: the shipped review lenses parse, the set is the four the spec names,
and the wheel copy is byte-identical (spec 2026-11-12-review-lenses R1).

Mirrors `test_tripwire_shipped_verifications.py`: `plugins/super-fr/lenses/` is
canonical, `packages/fr/src/fr/lens_manifests/` is the generated wheel copy
(`scripts/sync-lenses-data.py`).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fr.lenses.model import Lens, parse_lens

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIPPED_DIR = REPO_ROOT / "plugins" / "super-fr" / "lenses"
PACKAGED_DIR = REPO_ROOT / "packages" / "fr" / "src" / "fr" / "lens_manifests"

SHIPPED = {"security", "tests", "simplicity", "errors"}
CLOSING = "A problem you see outside this lens is still reported, as an ordinary finding."


def _lenses() -> dict[str, Lens]:
    return {p.stem: parse_lens(p.read_text(), source=str(p)) for p in SHIPPED_DIR.glob("*.yaml")}


def test_the_shipped_set_is_exactly_the_four_of_the_spec() -> None:
    assert {p.name for p in SHIPPED_DIR.glob("*")} == {f"{n}.yaml" for n in SHIPPED}


def test_each_lens_parses_and_its_stem_is_its_id() -> None:
    for stem, lens in _lenses().items():
        assert lens.id == stem


def test_each_brief_ends_with_the_outside_the_lens_sentence() -> None:
    for stem, lens in _lenses().items():
        assert lens.brief.rstrip().endswith(CLOSING), stem


def test_the_packaged_copy_holds_exactly_the_shipped_manifests() -> None:
    plugin = {p.name for p in SHIPPED_DIR.glob("*.yaml")}
    packaged = {p.name for p in PACKAGED_DIR.glob("*.yaml")}

    assert plugin == packaged, (
        f"plugin-only={sorted(plugin - packaged)}, packaged-only={sorted(packaged - plugin)} "
        "— run scripts/sync-lenses-data.py (the plugin directory is canonical)"
    )


def test_the_packaged_copy_is_byte_identical() -> None:
    for path in sorted(SHIPPED_DIR.glob("*.yaml")):
        mirror = PACKAGED_DIR / path.name
        assert mirror.read_bytes() == path.read_bytes(), f"{mirror} drifted"


def test_the_sync_script_check_exits_zero() -> None:
    done = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "sync-lenses-data.py"), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert done.returncode == 0, done.stderr

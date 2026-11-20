"""The OpenCode plugin's lock holds no version a known advisory names (super-fr#1510).

`@opencode/plugin` (a dev dependency: the plugin imports only its types, and delivery
copies `src/` alone) pulls glob and minimatch in at exact versions inside the ranges
below, through `@opencode/util` and `rimraf`. `package.json`'s `overrides` lift them to
the first patched releases; this pins that the lock still says so after any relock.
Ranges are the advisories' own, read from the GitHub advisory database on 2026-11-19.
"""

from __future__ import annotations

import re
from pathlib import Path

LOCK = Path(__file__).resolve().parents[2] / "packages" / "fr-opencode-plugin" / "bun.lock"

# package -> (advisory, first patched version); every version below it is affected
# back to the range's floor, which no locked version is below.
ADVISORIES = {
    "glob": ("GHSA-3g3m-2fjr-6pw4", (14, 0, 2)),  # >= 9.0.0, <= 14.0.1
    "minimatch": ("GHSA-g3hv-75wg-m249", (11, 0, 1)),  # >= 7.0.0, < 11.0.1
}

_ENTRY = re.compile(r'\["(glob|minimatch)@(\d+)\.(\d+)\.(\d+)"')


def test_the_lock_names_both_packages() -> None:
    names = {m.group(1) for m in _ENTRY.finditer(LOCK.read_text())}
    assert names == set(ADVISORIES), "the check below would pass vacuously"


def test_no_locked_version_is_inside_an_advisory_range() -> None:
    affected = []
    for m in _ENTRY.finditer(LOCK.read_text()):
        name, version = m.group(1), tuple(int(x) for x in m.groups()[1:])
        ghsa, patched = ADVISORIES[name]
        if version < patched:
            affected.append(f"{name}@{'.'.join(map(str, version))} ({ghsa})")
    assert affected == []

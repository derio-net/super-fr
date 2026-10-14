"""Version-floor probes: does an `fr_version` constraint let an older fr load a plan?

One answer for both callers — `fr plan create`'s refusal and `fr plan
self-review`'s floor error (review p3-f3: the two had drifted, each with its own
comparator, and each missed a different constraint shape).

`SpecifierSet` has no "minimum version" accessor, so the question is answered
by probing: a dense list of real-looking versions below the floor. A probe list
only answers for the versions in it, though, and the shape it misses is the one
most likely to be hand-written — an exact pin (`==4.19.3`) falling between two
probes. So exact, non-wildcard pins are compared directly as well.
"""

from __future__ import annotations

import importlib.metadata

from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.version import InvalidVersion, Version


def ceiling_for(version: str) -> str:
    """The exclusive `fr_version` ceiling that admits `version`'s whole major: `X+1.0.0`.

    The ONE place that formula lives. It used to be a literal (`<5.0.0`) written
    at 4.0.0 and copied to ten sites, so the 5.0.0 release refused every plan it
    wrote. The repair that widens EXISTING plans (`fr.artifacts.fr_version`)
    calls this too, so the two can no longer drift.
    """
    return f"{Version(version).major + 1}.0.0"


def admits(constraint: str | SpecifierSet, version: str | Version) -> bool:
    """Does `constraint` admit `version`, pre-releases included?

    The ONE membership test for an `fr_version`. A bare `in` against a
    `SpecifierSet` leaves pre-release handling to the library default, which
    moved: before packaging 26 a dev install (`5.0.1.dev0`) fell outside a range
    spanning it, and the parser then told it to upgrade (gh#855). fr declares `packaging>=24`, so
    either default can be installed; asking explicitly makes the answer one.
    """
    spec = constraint if isinstance(constraint, SpecifierSet) else SpecifierSet(constraint)
    v = version if isinstance(version, Version) else Version(str(version))
    if v.pre is None or v.pre[0] != "rc" or v.dev is not None or v.post is not None:
        return spec.contains(v, prereleases=True)
    # R26 (spec 2026-10-14-exit-gates): an RC of X.Y.Z passes wherever X.Y.Z does, so a
    # release candidate never refuses artifacts written for the final it precedes. Only
    # a specifier naming exactly X.Y.Z judges the final; every other one (a floor naming
    # another release, a ceiling) still compares the RC itself, by PEP 440.
    final = Version(v.base_version)
    return all(s.contains(final if _names(s, final) else v, prereleases=True) for s in spec)


def _names(spec: Specifier, version: Version) -> bool:
    """Does *spec* name exactly *version* (a final; a wildcard names nothing)?"""
    try:
        named = Version(spec.version)
    except InvalidVersion:
        return False
    return not named.is_prerelease and named == version


CEILING_VERSION = ceiling_for(importlib.metadata.version("fr"))
"""The ceiling a NEW plan carries, derived from the installed fr at import.

Write a default as `f">=4.20.0,<{CEILING_VERSION}"`: the lower bound stays a
literal so `scripts/floors.py` keeps checking it against the release it names,
and only the ceiling — the part that goes stale — is derived.
"""

PRE_4_PROBES: tuple[str, ...] = (
    "0.1.0",
    "1.0.0",
    "2.0.0",
    "2.5.0",
    "3.0.0",
    "3.0.1",
    "3.1.0",
    "3.5.0",
    "3.10.0",
    "3.19.0",
    "3.20.0",
    "3.999.999",
)
"""Versions probed for "would some real fr 3.x load this plan?" (review r5-b6:
the original five missed `==3.5.0`; includes a 0.x, a 1.x, a 2.x, several
3.minor values and both ends of 3.x)."""

PRE_4_20_PROBES: tuple[str, ...] = PRE_4_PROBES + tuple(
    f"4.{minor}.{patch}" for minor in range(20) for patch in (0, 1, 2, 99, 999)
)
"""`PRE_4_PROBES` plus every 4.x minor below 4.20, each at several patches."""


def admits_below(constraint: str, floor: str, probes: tuple[str, ...]) -> bool:
    """Does `constraint` admit some version below `floor`?

    An unparseable constraint answers False: `fr.parser` fails it loudly at
    parse time, and duplicating that error here would only mask it.
    """
    try:
        spec = SpecifierSet(constraint)
    except InvalidSpecifier:
        return False
    ceiling = Version(floor)
    # Only probes below the floor count, so a caller may pass a superset.
    below = [p for p in probes if Version(p) < ceiling]
    # `filter` rather than `contains`: it applies the specifier's own
    # prerelease semantics uniformly, which is the question `pip` asks.
    if any(spec.filter(below)):
        return True
    for s in spec:
        if s.operator not in ("==", "===") or s.version.endswith(".*"):
            continue
        try:
            pinned = Version(s.version)
        except InvalidVersion:
            continue
        if pinned < ceiling and spec.contains(pinned, prereleases=True):
            return True
    return False

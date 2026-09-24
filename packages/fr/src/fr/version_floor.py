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

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

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

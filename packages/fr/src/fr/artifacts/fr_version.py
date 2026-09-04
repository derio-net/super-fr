"""4.0.0's registered migration: widen plan `fr_version` ceilings (spec §3.B).

`fr_version` is enforced at parse (`fr/parser.py`), so a plan written under 3.x
carrying `>=3.x,<4.0.0` raises `PlanSchemaError` the moment 4.0.0 is installed —
and `discover_plans` catches that, logs a warning and continues, so dispatch
stops for every pre-4.0.0 plan while the daemon reports a healthy tick. This is
the repair for that.

It is a **repair**, not a schema migration. A plan's artifact stamp *is* its
`_meta.yaml schema_version` (forced: `PlanMeta` is `extra="forbid"`, so a second
version key would make every stamped plan unparseable), which welds "bump the
plan stamp" to "declare a new plan-folder schema". Widening a ceiling declares
no such thing — it changes a constraint, not a shape — so it is guarded by its
own predicate and leaves the stamp at 2.

Two rules the widening obeys:

- It only ever moves the **ceiling**, and only when the ceiling is spelled
  `<` or `<=`, to `<{installed major + 1}.0.0`. A constraint that excludes the
  installed version because of its *floor* is a plan asking for a newer `fr`
  than this one; widening would not admit us anyway, and downgrades are a
  non-goal (spec §2), so that case is silent.
- A constraint it cannot parse — or one whose exclusion comes from a bound it
  will not guess at, like `~=3.19` or `==3.*` — is **reported, never
  rewritten**. The predicate raises, the runner records that one artifact as
  failed, and every other plan still migrates. What must never happen is the
  third outcome: no rewrite AND no report, which leaves `parse()` raising and
  dispatch silently stopped for that plan — the exact failure this repair
  exists to end.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from packaging.specifiers import InvalidSpecifier, Specifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.runner import MIGRATIONS, ArtifactMigrationError, Repair

FR_VERSION_KEY = "fr_version"
REPAIR_NAME = "widen-fr-version-ceiling"

_UPPER_BOUND_OPERATORS = ("<", "<=")
"""The only ceilings this repair rewrites; anything else it reports."""

_LOWER_BOUND_OPERATORS = (">", ">=")
"""An exclusion caused only by these is a floor problem — silent by design."""

# `fr_version` is a top-level scalar in `_meta.yaml`, so it owns a whole line
# and the quoting style (usually `'`, sometimes none) is the operator's. The
# value cannot contain a quote or a `#`, which is what makes line surgery safe
# here — see `registry.py` on why nothing round-trips through `yaml.safe_dump`.
_LINE_RE = re.compile(
    rf"^(?P<lead>{re.escape(FR_VERSION_KEY)}\s*:\s*)(?P<q>['\"]?)(?P<value>[^'\"#\n]*)(?P=q)"
    r"(?P<trail>[ \t]*)$",
    re.MULTILINE,
)


class MalformedConstraintError(ArtifactMigrationError):
    """An `fr_version` this repair refuses to guess at."""


class UnwidenableConstraintError(ArtifactMigrationError):
    """A well-formed `fr_version` that excludes this `fr` through a bound the
    repair will not rewrite (`~=`, `==X.*`, `!=`, an exact pin).

    Reported rather than widened: widening those means guessing what the author
    meant. Reported rather than ignored: an unadmitted plan never parses, so
    silence stops dispatch with no trace."""


def installed_fr_version() -> Version:
    """The running `fr`'s version. A function so tests can pin it."""
    from fr.parser import INSTALLED_FR_VERSION

    try:
        return Version(INSTALLED_FR_VERSION)
    except InvalidVersion as e:  # pragma: no cover — comes from packaging metadata
        raise MalformedConstraintError(
            f"installed fr version {INSTALLED_FR_VERSION!r} is not a valid PEP 440 version: {e}"
        ) from e


def widen_ceiling(constraint: str, installed: Version) -> str | None:
    """The widened constraint, or `None` when `constraint` needs no widening.

    `None` means exactly two things, and nothing else:

    - the constraint already admits `installed`;
    - it excludes `installed` **only** through a lower bound — a plan asking
      for a newer `fr` than this one. Widening a ceiling would not admit us and
      downgrades are a non-goal (spec §2), so there is nothing to do and
      nothing to say.

    Raises `MalformedConstraintError` if `constraint` is not a valid PEP 440
    specifier set, and `UnwidenableConstraintError` if it excludes `installed`
    through a bound this repair will not rewrite. Returning `None` for that
    third case is what made an un-dispatchable plan invisible.
    """
    # Split by hand rather than iterating a `SpecifierSet`: that iterates a
    # frozenset, so rebuilding from it would silently reorder the operator's
    # text. Order is part of what "rewrites nothing else" means.
    pieces = [p.strip() for p in constraint.split(",") if p.strip()]
    try:
        specifiers = [Specifier(p) for p in pieces]
        if installed in SpecifierSet(constraint):
            return None
    except InvalidSpecifier as e:
        raise MalformedConstraintError(f"invalid {FR_VERSION_KEY} {constraint!r}: {e}") from e

    excluding = [s for s in specifiers if installed not in SpecifierSet(str(s))]
    if excluding and all(s.operator in _LOWER_BOUND_OPERATORS for s in excluding):
        return None  # a floor problem; see the docstring

    new_ceiling = f"<{installed.major + 1}.0.0"
    widened = [new_ceiling if s.operator in _UPPER_BOUND_OPERATORS else str(s) for s in specifiers]
    candidate = ",".join(widened)
    if candidate != constraint and installed in SpecifierSet(candidate):
        return candidate
    raise UnwidenableConstraintError(
        f"{FR_VERSION_KEY} {constraint!r} excludes the installed fr {installed}, but not "
        f"through a `<` or `<=` ceiling this repair can widen "
        f"({', '.join(f'`{s}`' for s in excluding)}). fr will not guess at what it should "
        f"become — edit it by hand to admit {installed.major}.x."
    )


def _constraint_of(path: Path) -> str | None:
    """The `fr_version` `path` declares, or `None` when it declares none."""
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise MalformedConstraintError(f"{path}: not valid YAML: {e}") from e
    if not isinstance(data, dict):
        return None
    value = data.get(FR_VERSION_KEY)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MalformedConstraintError(f"{path}: {FR_VERSION_KEY} must be a string, got {value!r}")
    return value


def needs_widening(path: Path) -> bool:
    """Does `path`'s ceiling exclude the installed major?

    Raises (and so is reported as that one artifact's failure) when the
    constraint is unparseable, or excludes this `fr` through a bound the repair
    will not rewrite.
    """
    constraint = _constraint_of(path)
    if constraint is None:
        return False
    return widen_ceiling(constraint, installed_fr_version()) is not None


def widen(path: Path) -> None:
    """Rewrite `path`'s `fr_version` line in place.

    Re-reads the file here rather than trusting the predicate's parse: an agent
    may have written it in between (spec §4).
    """
    constraint = _constraint_of(path)
    if constraint is None:
        return
    widened = widen_ceiling(constraint, installed_fr_version())
    if widened is None:
        return
    text = path.read_text()
    match = _LINE_RE.search(text)
    if match is None or match.group("value").strip() != constraint:
        # The value is there (we parsed it) but not on a line we can rewrite
        # without re-serialising the document — a block scalar, say. Refuse
        # rather than reformat someone's file.
        raise MalformedConstraintError(
            f"{path}: cannot rewrite {FR_VERSION_KEY} in place; edit it by hand to {widened!r}"
        )
    q = match.group("q")
    replacement = f"{match.group('lead')}{q}{widened}{q}{match.group('trail')}"
    write_text_atomic(path, text[: match.start()] + replacement + text[match.end() :])


CEILING_REPAIR = Repair(
    kind="plan",
    name=REPAIR_NAME,
    applies=needs_widening,
    fn=widen,
    description="widen the plan's fr_version ceiling to admit the installed major",
)

MIGRATIONS.register(CEILING_REPAIR)

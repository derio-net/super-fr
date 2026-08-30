"""The artifact registry — the ONE place that enumerates artifact kinds.

Spec: `docs/superpowers/specs/2026-08-30-artifact-migration-framework-design.md`
§3.A. A node's installed `fr` changes whenever the plugin updates, mid-flight;
the artifacts on disk do not change with it. So every generated artifact
declares the version it was written for, and the migration runner (Phase 2),
the trigger (Phase 3) and the validator (Phase 7) all read that declaration
through this module.

Three properties this module exists to guarantee:

1. **An absent stamp means version 1.** Not an error, not "unknown". Every
   artifact in the wild today predates this framework, so absence *is* the
   pre-framework era — and is itself information. No flag day.
2. **Archived artifacts are excluded.** No locator reaches
   `docs/superpowers/implemented/**`: those record what shipped, and rewriting
   them would falsify history (spec §2 non-goals). The live locators are
   rooted at the live directories, so the archive is unreachable by
   construction; `iter_artifact_paths` re-checks anyway, because a future
   locator edit is exactly the mistake that would go unnoticed.
3. **Writing a stamp disturbs nothing else.** These run against files an
   operator has open. Every writer edits the carrier line *textually* and
   leaves every other byte — comments, key order, blank lines — alone. A
   round-trip through `yaml.safe_dump` would silently normalise all three, so
   no writer here re-serialises a parsed document.

Adding a kind means adding one entry to `ARTIFACT_KINDS`. Nothing outside this
module may enumerate kinds (Phase 7 adds a tripwire that asserts it).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

PRE_FRAMEWORK_VERSION = 1
"""What an artifact with no stamp reads as (spec §3.A)."""

ARCHIVE_SEGMENT = "implemented"
"""Path segment marking the frozen archive; no locator may reach it."""


class ArtifactError(Exception):
    """Base for every artifact-registry failure."""


class UnknownArtifactKindError(ArtifactError):
    """Raised for a kind name the registry does not carry."""


class ArtifactStampError(ArtifactError):
    """Raised when an artifact's stamp is present but unreadable."""


@dataclass(frozen=True)
class ArtifactKind:
    """One artifact kind: what it is, where it lives, how it is stamped."""

    name: str
    current_version: int
    """The version this `fr` writes. An artifact below it is stale."""
    locator: str
    """Glob relative to the repo root. Never reaches the archive."""
    stamp: str
    """Human description of the carrier, for messages and `--dry-run` output."""
    read_version: Callable[[Path], int]
    write_version: Callable[[Path, int], None]


# --- YAML-carried stamps (plan / run / matrix) ---------------------------
#
# Read through `yaml.safe_load` (correct for any scalar style); write by line
# surgery (byte-stable). The two halves deliberately do not share a code path:
# reading wants a parser, writing must not use one.

_TOP_LEVEL_KEY = "schema_version"


def _yaml_read_key(path: Path, key: str) -> int:
    text = path.read_text()
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ArtifactStampError(f"{path}: not valid YAML, cannot read `{key}`: {e}") from e
    if not isinstance(data, dict) or key not in data:
        return PRE_FRAMEWORK_VERSION
    return _coerce_version(data[key], path, key)


def _coerce_version(value: object, path: Path, carrier: str) -> int:
    # `isinstance(True, int)` is True in Python; a YAML `yes` must not read as 1.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactStampError(f"{path}: `{carrier}` must be an integer, got {value!r}")
    if value < 1:
        raise ArtifactStampError(f"{path}: `{carrier}` must be >= 1, got {value!r}")
    return value


def _insertion_index(lines: list[str]) -> int:
    """Where a new top-level key goes: after a `---` document start and after
    any leading comment/blank block, so a file's header comment stays on top."""
    i = 0
    if i < len(lines) and lines[i].rstrip() == "---":
        i += 1
    while i < len(lines) and (not lines[i].strip() or lines[i].lstrip().startswith("#")):
        i += 1
    return i


def _yaml_write_key(path: Path, key: str, version: int) -> None:
    text = path.read_text()
    lines = text.splitlines(keepends=True)
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for i, line in enumerate(lines):
        if pattern.match(line):
            # Preserve the original line ending; replace only the key's line.
            newline = "\n" if line.endswith("\n") else ""
            lines[i] = f"{key}: {version}{newline}"
            path.write_text("".join(lines))
            return
    at = _insertion_index(lines)
    lines.insert(at, f"{key}: {version}\n")
    path.write_text("".join(lines))


def _read_yaml_stamp(path: Path) -> int:
    return _yaml_read_key(path, _TOP_LEVEL_KEY)


def _write_yaml_stamp(path: Path, version: int) -> None:
    _yaml_write_key(path, _TOP_LEVEL_KEY, version)


# --- journal: an HTML comment on the first line --------------------------
#
# NOT the spec table's literal `<!-- fr:journal schema=N -->`: that string
# starts with `fr.journal.model._DELIM_PREFIX` (`"<!-- fr:journal "`), so
# `parse_journal` would read it as an ENTRY delimiter and raise
# `JournalParseError: missing required field: 'kind'` on every stamped journal.
# One character moves it out of the way (space -> hyphen) while keeping the
# spec's shape: a header comment, invisible in rendered Markdown, on line 1.

_JOURNAL_STAMP_RE = re.compile(r"^<!--\s*fr:journal-schema=(\d+)\s*-->\s*$", re.MULTILINE)


def _journal_stamp_line(version: int) -> str:
    return f"<!-- fr:journal-schema={version} -->"


def _read_journal_stamp(path: Path) -> int:
    m = _JOURNAL_STAMP_RE.search(path.read_text())
    if m is None:
        return PRE_FRAMEWORK_VERSION
    return _coerce_version(int(m.group(1)), path, "fr:journal-schema")


def _write_journal_stamp(path: Path, version: int) -> None:
    text = path.read_text()
    m = _JOURNAL_STAMP_RE.search(text)
    if m is not None:
        path.write_text(text[: m.start()] + _journal_stamp_line(version) + text[m.end() :])
        return
    path.write_text(_journal_stamp_line(version) + "\n" + text)


# --- spec: YAML front matter ---------------------------------------------
#
# Specs are hand-written Markdown that starts at `# Title`. Front matter is
# added only when stamping, and only at the very top: a `---` further down is
# a horizontal rule, not a delimiter.

_SPEC_KEY = "fr_schema"
_FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def _read_spec_stamp(path: Path) -> int:
    text = path.read_text()
    m = _FRONT_MATTER_RE.match(text)
    if m is None:
        return PRE_FRAMEWORK_VERSION
    try:
        data: Any = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise ArtifactStampError(f"{path}: front matter is not valid YAML: {e}") from e
    if not isinstance(data, dict) or _SPEC_KEY not in data:
        return PRE_FRAMEWORK_VERSION
    return _coerce_version(data[_SPEC_KEY], path, _SPEC_KEY)


def _write_spec_stamp(path: Path, version: int) -> None:
    text = path.read_text()
    m = _FRONT_MATTER_RE.match(text)
    if m is None:
        path.write_text(f"---\n{_SPEC_KEY}: {version}\n---\n" + text)
        return
    block = m.group(1)
    pattern = re.compile(rf"^{re.escape(_SPEC_KEY)}\s*:.*$", re.MULTILINE)
    if pattern.search(block):
        new_block = pattern.sub(f"{_SPEC_KEY}: {version}", block, count=1)
    else:
        new_block = f"{_SPEC_KEY}: {version}\n{block}"
    path.write_text(text[: m.start(1)] + new_block + text[m.end(1) :])


# --- the registry --------------------------------------------------------

ARTIFACT_KINDS: Mapping[str, ArtifactKind] = {
    kind.name: kind
    for kind in (
        ArtifactKind(
            name="plan",
            # The plan-folder schema version, which ALREADY means "the version
            # this artifact was written for" and already owns a migration chain
            # (`fr migrate v1-to-v2`). The framework reads that field rather
            # than adding a second one: `PlanMeta` is `extra="forbid"`, so a
            # new key would make every stamped plan unparseable.
            current_version=2,
            locator="docs/superpowers/plans/*/_meta.yaml",
            stamp="`schema_version` in `_meta.yaml`",
            read_version=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
        ),
        ArtifactKind(
            name="journal",
            current_version=1,
            locator="docs/superpowers/journals/**/*.md",
            stamp="`<!-- fr:journal-schema=N -->` header comment",
            read_version=_read_journal_stamp,
            write_version=_write_journal_stamp,
        ),
        ArtifactKind(
            name="run",
            current_version=1,
            locator="docs/superpowers/runs/*.yaml",
            stamp="`schema_version` in the run yaml",
            read_version=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
        ),
        ArtifactKind(
            name="matrix",
            current_version=1,
            locator="docs/acceptance/matrix.yaml",
            stamp="`schema_version` in `matrix.yaml`",
            read_version=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
        ),
        ArtifactKind(
            name="spec",
            current_version=1,
            locator="docs/superpowers/specs/*.md",
            stamp="`fr_schema:` in the front matter",
            read_version=_read_spec_stamp,
            write_version=_write_spec_stamp,
        ),
    )
}


def artifact_kind(name: str) -> ArtifactKind:
    """The registered kind called `name`. Raises `UnknownArtifactKindError`."""
    try:
        return ARTIFACT_KINDS[name]
    except KeyError:
        raise UnknownArtifactKindError(
            f"unknown artifact kind {name!r} (known: {', '.join(sorted(ARTIFACT_KINDS))})"
        ) from None


def iter_artifact_paths(repo_root: Path, name: str) -> Iterator[Path]:
    """Every live artifact of kind `name` under `repo_root`, sorted.

    Archived artifacts are never yielded — the locators cannot reach
    `implemented/`, and this re-checks so a future locator edit cannot quietly
    start rewriting shipped history.
    """
    kind = artifact_kind(name)
    for path in sorted(repo_root.glob(kind.locator)):
        if ARCHIVE_SEGMENT in path.relative_to(repo_root).parts:
            continue
        if path.is_file():
            yield path


def iter_all_artifacts(repo_root: Path) -> Iterator[tuple[ArtifactKind, Path]]:
    """`(kind, path)` for every live artifact of every registered kind."""
    for name, kind in ARTIFACT_KINDS.items():
        for path in iter_artifact_paths(repo_root, name):
            yield kind, path


def read_version(name: str, path: Path) -> int:
    """The version `path` declares — `PRE_FRAMEWORK_VERSION` when unstamped."""
    return artifact_kind(name).read_version(path)


def write_version(name: str, path: Path, version: int) -> None:
    """Stamp `path` with `version`, disturbing nothing else in the file."""
    artifact_kind(name).write_version(path, version)

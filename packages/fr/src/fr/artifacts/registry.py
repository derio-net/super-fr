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

Adding a kind means adding one entry to `ARTIFACT_KINDS` — including its
structure validator (spec §3.F), so a kind cannot be registered without one.
Nothing outside this module may enumerate kinds
(`tests/unit/test_tripwire_artifact_kinds.py`).
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from fr.artifacts.atomic import write_text_atomic
from fr.artifacts.structure import (
    validate_journal,
    validate_matrix,
    validate_plan,
    validate_run,
    validate_spec,
)

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
    read_stamp: Callable[[Path], int | None]
    """The version the artifact DECLARES, or `None` when it declares none.

    `None` is not an error and not "unknown" — it is the pre-framework era
    (property 1), and `read_version` below turns it into
    `PRE_FRAMEWORK_VERSION`. The two are kept distinct because the migration
    runner needs the distinction: a chain gap over a version an artifact
    *declared* is a bug in the registry, while a gap over a version nobody ever
    wrote is a data problem with one file (runner invariant 3)."""
    write_version: Callable[[Path, int], None]
    validate: Callable[[Path], list[str]]
    """Structural validation for this kind (spec §3.F), from
    `fr.artifacts.structure`: returns one human-readable message per problem
    and an empty list when the artifact is valid. Every kind carries one —
    "every version ships a structure validator" is only true if a new kind
    cannot be registered without one."""

    def read_version(self, path: Path) -> int:
        """The version `path` is on — `PRE_FRAMEWORK_VERSION` when unstamped."""
        declared = self.read_stamp(path)
        return PRE_FRAMEWORK_VERSION if declared is None else declared


# --- YAML-carried stamps (plan / run / matrix) ---------------------------
#
# Read through `yaml.safe_load` (correct for any scalar style); write by line
# surgery (byte-stable). The two halves deliberately do not share a code path:
# reading wants a parser, writing must not use one.

_TOP_LEVEL_KEY = "schema_version"

_BOM = "\ufeff"


def read_verbatim(path: Path) -> tuple[str, str]:
    """`(bom, body)` — the file's bytes as text, with NOTHING normalised.

    `Path.read_text()` is wrong for every writer in this module (review
    r5-e10). It opens in universal-newline mode, so a CRLF artifact comes back
    with `\n` and the writer then rewrites the WHOLE file with LF endings — a
    diff the operator never made, in a commit that says "migrate". It also
    leaves a UTF-8 BOM as an invisible first character, which made
    `^schema_version:` fail to match line 1, so the stamp was inserted a second
    time above the BOM.

    Splitting the BOM off explicitly lets every reader parse clean text and
    every writer put the mark back exactly where it was.
    """
    text = path.read_bytes().decode("utf-8")
    if text.startswith(_BOM):
        return _BOM, text[len(_BOM) :]
    return "", text


def _dominant_newline(text: str) -> str:
    """The line ending to give a line this module ADDS. CRLF only when the
    file is already CRLF, so a mixed file is not made more mixed."""
    return "\r\n" if "\r\n" in text else "\n"


def _yaml_read_key(path: Path, key: str) -> int | None:
    _, text = read_verbatim(path)
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ArtifactStampError(f"{path}: not valid YAML, cannot read `{key}`: {e}") from e
    if not isinstance(data, dict) or key not in data:
        return None
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
    bom, text = read_verbatim(path)
    lines = text.splitlines(keepends=True)
    pattern = re.compile(rf"^{re.escape(key)}\s*:")
    for i, line in enumerate(lines):
        if pattern.match(line):
            # Preserve the original line ending EXACTLY — `\r\n` stays `\r\n`,
            # and a final line with none stays without one.
            newline = line[len(line.rstrip("\r\n")) :]
            lines[i] = f"{key}: {version}{newline}"
            write_text_atomic(path, bom + "".join(lines))
            return
    at = _insertion_index(lines)
    lines.insert(at, f"{key}: {version}{_dominant_newline(text)}")
    write_text_atomic(path, bom + "".join(lines))


def _read_yaml_stamp(path: Path) -> int | None:
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

# `[ \t]*`, never `\s*`: under `re.MULTILINE` a `\s` matches `\n` too, so a
# trailing `\s*$` runs past the stamp's own line and the re-stamping writer
# below then deletes every blank line that followed it — silently, and against
# this module's property 3 ("writing a stamp disturbs nothing else").
#
# Anchored to the FIRST NON-BLANK LINE (review r5-c5). `re.MULTILINE` matched
# the stamp anywhere in the file, including inside a fenced code block — and a
# journal entry that QUOTES a stamp (this framework's own journal does exactly
# that) was then read as declaring that version, and the writer rewrote the
# quoted line instead of the real header. The stamp is a header comment on line
# 1 by definition; anything further down is prose about a stamp, not a stamp.
# No `^`: this pattern is applied with `Pattern.match(text, start, end)`, which
# already anchors at `start`. `^` would additionally require `start == 0` (it
# is not a MULTILINE pattern), so a journal with a blank line before its stamp
# read as unstamped.
_JOURNAL_STAMP_RE = re.compile(r"<!--[ \t]*fr:journal-schema=(\d+)[ \t]*-->[ \t]*$")


def _first_non_blank(text: str) -> tuple[int, int] | None:
    """`(start, end)` of the first non-blank line, or `None` for a blank file."""
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if stripped.strip():
            return offset, offset + len(stripped)
        offset += len(line)
    return None


def _journal_stamp_match(text: str) -> re.Match[str] | None:
    span = _first_non_blank(text)
    if span is None:
        return None
    start, end = span
    return _JOURNAL_STAMP_RE.match(text, start, end)


def _journal_stamp_line(version: int) -> str:
    return f"<!-- fr:journal-schema={version} -->"


def _read_journal_stamp(path: Path) -> int | None:
    _, text = read_verbatim(path)
    m = _journal_stamp_match(text)
    if m is None:
        return None
    return _coerce_version(int(m.group(1)), path, "fr:journal-schema")


def _write_journal_stamp(path: Path, version: int) -> None:
    # `read_verbatim`, not `read_text` (review r5-e10). The reader already used
    # it, so a BOM'd journal READ its stamp fine while this writer saw the BOM
    # as the first character, failed to match the stamp behind it, and prepended
    # a SECOND one — leaving a file with two stamps declaring two versions. And
    # `read_text` normalises CRLF, so writing one line rewrote every line ending
    # in the file.
    bom, text = read_verbatim(path)
    m = _journal_stamp_match(text)
    if m is not None:
        write_text_atomic(
            path, bom + text[: m.start()] + _journal_stamp_line(version) + text[m.end() :]
        )
        return
    write_text_atomic(path, bom + _journal_stamp_line(version) + _dominant_newline(text) + text)


# --- spec: YAML front matter ---------------------------------------------
#
# Specs are hand-written Markdown that starts at `# Title`. Front matter is
# added only when stamping, and only at the very top: a `---` further down is
# a horizontal rule, not a delimiter.

_SPEC_KEY = "fr_schema"
# `\r?\n`, not `\n` (review r5-e10). A CRLF spec's front matter did not match
# at all, so `_read_spec_stamp` reported "unstamped" for a file that plainly
# carried `fr_schema:` — and `_write_spec_stamp` then prepended a SECOND front
# matter block above the first. The artifact stayed "stale" forever, gaining
# one more block per migration.
_FRONT_MATTER_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)


def _read_spec_stamp(path: Path) -> int | None:
    _, text = read_verbatim(path)
    m = _FRONT_MATTER_RE.match(text)
    if m is None:
        return None
    try:
        data: Any = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        raise ArtifactStampError(f"{path}: front matter is not valid YAML: {e}") from e
    if not isinstance(data, dict) or _SPEC_KEY not in data:
        return None
    return _coerce_version(data[_SPEC_KEY], path, _SPEC_KEY)


def _write_spec_stamp(path: Path, version: int) -> None:
    bom, text = read_verbatim(path)
    m = _FRONT_MATTER_RE.match(text)
    if m is None:
        nl = _dominant_newline(text)
        write_text_atomic(path, f"{bom}---{nl}{_SPEC_KEY}: {version}{nl}---{nl}" + text)
        return
    block = m.group(1)
    # `[^\r\n]*` rather than `.*$`: `.` matches `\r`, so on a CRLF spec the
    # substitution swallowed the carriage return and left ONE line of the block
    # with a bare LF (review r5-e10).
    pattern = re.compile(rf"^{re.escape(_SPEC_KEY)}\s*:[^\r\n]*", re.MULTILINE)
    if pattern.search(block):
        new_block = pattern.sub(f"{_SPEC_KEY}: {version}", block, count=1)
    else:
        new_block = f"{_SPEC_KEY}: {version}{_dominant_newline(text)}{block}"
    write_text_atomic(path, bom + text[: m.start(1)] + new_block + text[m.end(1) :])


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
            read_stamp=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
            validate=validate_plan,
        ),
        ArtifactKind(
            name="journal",
            current_version=1,
            locator="docs/superpowers/journals/**/*.md",
            stamp="`<!-- fr:journal-schema=N -->` header comment",
            read_stamp=_read_journal_stamp,
            write_version=_write_journal_stamp,
            validate=validate_journal,
        ),
        ArtifactKind(
            name="run",
            current_version=1,
            locator="docs/superpowers/runs/*.yaml",
            stamp="`schema_version` in the run yaml",
            read_stamp=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
            validate=validate_run,
        ),
        ArtifactKind(
            name="matrix",
            current_version=1,
            locator="docs/acceptance/matrix.yaml",
            stamp="`schema_version` in `matrix.yaml`",
            read_stamp=_read_yaml_stamp,
            write_version=_write_yaml_stamp,
            validate=validate_matrix,
        ),
        ArtifactKind(
            name="spec",
            current_version=1,
            locator="docs/superpowers/specs/*.md",
            stamp="`fr_schema:` in the front matter",
            read_stamp=_read_spec_stamp,
            write_version=_write_spec_stamp,
            validate=validate_spec,
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


def iter_paths_of(repo_root: Path, kind: ArtifactKind) -> Iterator[Path]:
    """Every live artifact of `kind` under `repo_root`, sorted.

    Archived artifacts are never yielded — the locators cannot reach
    `implemented/`, and this re-checks so a future locator edit cannot quietly
    start rewriting shipped history.

    Takes the kind rather than its name so the migration runner can walk the
    kinds it was handed without re-entering the global mapping (the runner's
    registry is injectable in tests); `iter_artifact_paths` is the by-name
    front door and the archive check lives here, once, for both.
    """
    for path in sorted(repo_root.glob(kind.locator)):
        if ARCHIVE_SEGMENT in path.relative_to(repo_root).parts:
            continue
        if path.is_file():
            yield path


def iter_artifact_paths(repo_root: Path, name: str) -> Iterator[Path]:
    """Every live artifact of kind `name` under `repo_root`, sorted."""
    yield from iter_paths_of(repo_root, artifact_kind(name))


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

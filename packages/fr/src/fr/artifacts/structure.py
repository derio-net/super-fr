"""Per-kind structure validators — what `fr validate artifacts` checks (spec §3.F).

One function per artifact kind, each `(path) -> list[str]` of human-readable
problems ("" is never a problem; an empty list means valid). They are attached
to their kind in `fr.artifacts.registry`, so the registry stays the ONE place
that enumerates kinds and a new kind cannot appear here without appearing there.

Three rules the functions obey:

1. **Name the field.** "invalid" without a field name is a validator nobody
   uses. Every message either names the missing/invalid field or quotes the
   offending line with its number.
2. **Reuse the canonical schema.** The closed-world kinds already have a
   pydantic model (`PlanMeta`, `RunState`, `Matrix`) and the open ones a
   parser (`parse_journal`, `fr.parser.parse`); validation goes through those
   rather than growing a second definition of "valid" that can drift.
3. **Read only.** These run against files an operator has open. Nothing here
   writes, and nothing re-serialises.

The YAML kinds are parsed with `_StrictLoader`, not `yaml.safe_load`: a
duplicate key is the one corruption a schema check cannot see, because PyYAML
resolves it before the model ever runs (see the class docstring).

Imports of the heavier `fr` modules are deliberately *inside* the functions:
`fr.artifacts.registry` is imported at CLI entry by the migration trigger,
before every command, and must not drag the plan parser and pydantic models in
with it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# --- shared helpers ------------------------------------------------------


class _StrictLoader(yaml.SafeLoader):
    """`SafeLoader` that refuses a mapping with a repeated key.

    PyYAML keeps the LAST occurrence and says nothing, which makes a duplicate
    key a *silent drop* — the shape still validates, and everything the earlier
    block declared is simply gone. This repo shipped exactly that: a row of
    `docs/acceptance/matrix.yaml` carried `levels:` twice, so one of its two
    test refs disappeared from the matrix, from the generated reports and from
    `fr acceptance check`, with nothing anywhere reporting a problem.

    Structure validation is the layer that can see it, because it is the only
    one that reads the artifact as *text* rather than as whatever the parser
    already decided it meant.
    """

    def construct_mapping(self, node: Any, deep: bool = False) -> dict[Any, Any]:
        seen: set[Any] = set()
        for key_node, _ in node.value:
            # PyYAML ships no stubs for its constructor API, hence the cast.
            key: Any = self.construct_object(key_node, deep=deep)  # type: ignore[no-untyped-call]
            try:
                duplicate = key in seen
            except TypeError:  # pragma: no cover — an unhashable YAML key
                continue
            if duplicate:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key!r}",
                    key_node.start_mark,
                )
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


def _load_mapping(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """`(mapping, problems)` — a non-mapping, unparseable, or duplicate-keyed
    file is a problem."""
    try:
        data: Any = yaml.load(path.read_text(), Loader=_StrictLoader)  # noqa: S506
    except yaml.YAMLError as e:
        return None, [f"not valid YAML: {e}"]
    if data is None:
        return None, ["file is empty"]
    if not isinstance(data, dict):
        return None, [f"top level must be a mapping, got {type(data).__name__}"]
    return data, []


def _loc(parts: tuple[Any, ...]) -> str:
    """A pydantic error location as a field path: `rows[3].status`."""
    out = ""
    for part in parts:
        if isinstance(part, int):
            out += f"[{part}]"
        else:
            out += f".{part}" if out else str(part)
    return out or "<root>"


def _model_problems(model: Any, data: dict[str, Any]) -> list[str]:
    """Validate `data` against a pydantic model, one message per error."""
    from pydantic import ValidationError

    try:
        model.model_validate(data)
    except ValidationError as e:
        problems = []
        for err in e.errors():
            field = _loc(tuple(err["loc"]))
            if err["type"] == "missing":
                problems.append(f"missing required field `{field}`")
            else:
                problems.append(f"invalid field `{field}`: {err['msg']}")
        return problems
    return []


# --- plan ----------------------------------------------------------------


def validate_plan(path: Path) -> list[str]:
    """`_meta.yaml` against `PlanMeta`, then the whole folder through the parser.

    The folder parse is what catches a malformed `NN.yaml`, and it passes
    `enforce_fr_version=False`: a ceiling that excludes this fr is a *migration*
    question (the stamp check and `fr migrate artifacts` own it), not a
    structural one, and reporting it twice in different words helps nobody.
    """
    from fr.parser import PlanSchemaError, parse
    from fr.types import PlanMeta

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    problems = _model_problems(PlanMeta, data)
    if problems:
        return problems
    try:
        parse(path.parent, enforce_fr_version=False)
    except PlanSchemaError as e:
        return [f"plan folder does not parse: {e}"]
    return []


# --- journal -------------------------------------------------------------


def validate_journal(path: Path) -> list[str]:
    """Every entry parses, and no entry id appears twice.

    `fr journal add` is idempotent on `--id`, so two entries sharing one id can
    only come from a hand edit or a bad splice — and `fr journal render
    --entry` would then silently show the first.
    """
    from fr.journal.model import JournalParseError, parse_journal

    try:
        entries = parse_journal(path.read_text())
    except JournalParseError as e:
        return [str(e)]

    problems: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if entry.id in seen:
            problems.append(f"duplicate journal entry id `{entry.id}` — the entry appears twice")
        seen.add(entry.id)
    return problems


# --- run -----------------------------------------------------------------


def validate_run(path: Path) -> list[str]:
    """`RunState`, plus the one cross-reference it does not encode: the cursor
    must name a step the run actually records."""
    from fr.run.model import RunState

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    problems = _model_problems(RunState, data)
    if problems:
        return problems

    state = RunState.model_validate(data)
    if state.cursor not in state.steps:
        known = ", ".join(state.steps) or "none"
        problems.append(
            f"`cursor` names `{state.cursor}`, which is not a recorded step (recorded: {known})"
        )
    return problems


# --- matrix --------------------------------------------------------------


def validate_matrix(path: Path) -> list[str]:
    """The acceptance matrix against `Matrix`.

    Ref resolution and staleness are `fr acceptance check`'s job and stay
    there; this is the shape only, so the two gates cannot disagree.
    """
    from fr.acceptance.model import Matrix

    data, problems = _load_mapping(path)
    if problems or data is None:
        return problems
    return _model_problems(Matrix, data)


# --- spec ----------------------------------------------------------------
#
# Specs are hand-written Markdown with no schema, so the checks target the
# corruption this repo has actually produced: commit 7ece5a9 spliced a spec
# with `end = text.index("## Implementation Plans")`, matched an inline mention
# of that heading sitting BEFORE the replaced section, and re-appended the tail
# — ~640 duplicated lines and one heading fused mid-sentence. Nothing caught
# it. Both signals are checked below; measured against every spec in this repo,
# both are silent on all of them and both fire on the damaged file.

_FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*?)\s*$")

_SECTION_LEVEL = 3
"""Headings at this level or shallower name a *section*; deeper ones (`####`
notes, per-item headings) legitimately repeat and are not compared."""


def validate_spec(path: Path) -> list[str]:
    problems: list[str] = []
    seen: dict[tuple[int, str], int] = {}
    in_fence = False
    has_title = False

    for number, line in enumerate(path.read_text().splitlines(), start=1):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if m is None:
            continue
        level, text = len(m.group(1)), m.group(2)
        if level == 1:
            has_title = True

        # An inline-code span that never closes on a heading line: the heading
        # ran on into prose it was spliced into. A legitimate heading quoting
        # code (`### The `--yes` flag`) balances its backticks.
        if line.count("`") % 2:
            problems.append(
                f"line {number}: heading has an unclosed `` ` `` — a heading fused "
                f"mid-sentence? {line.strip()[:90]!r}"
            )

        if level <= _SECTION_LEVEL:
            key = (level, text)
            first = seen.get(key)
            if first is not None:
                problems.append(
                    f"line {number}: duplicated section heading {line.strip()[:90]!r} "
                    f"(already at line {first}) — a section block appears twice"
                )
            else:
                seen[key] = number

    if not has_title:
        problems.append("missing required `# ` title heading on the first heading level")
    return problems

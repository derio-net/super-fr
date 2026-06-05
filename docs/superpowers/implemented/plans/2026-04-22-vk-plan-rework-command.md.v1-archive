# `vk plan rework` Command Surface Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-22-vk-plan-rework-design.md`
**Status:** Complete

**Goal:** Ship the `vk plan rework`, `vk plan rework-add`, and `vk plan rework-list` commands — plus the supporting `**Track:**` phase body-field — so agents can defer surfaced-but-unrealised work into durable, vk-execute-compatible rework plans without reopening the parent.

**Architecture:** Layered. Phase 1 lands the generic plumbing — `Phase.track_label` on the model, parser extraction, and writer emission — that any phased plan will benefit from. Phase 2 delivers `src/vk/plan/rework.py` with the scaffold template, next-rework-number scan, and Origin-table helpers; it has no CLI surface yet. Phases 3-5 each wire one typer subcommand that delegates to `rework.py`, matching the thin-wrapper pattern already in `plan_cmd.py`. Phase 6 extends `vk plan self-review` with the canonical-Track-token lint. Phase 7 bumps the three version-source files in lockstep, updates `skills/vk-plan/SKILL.md`, and runs the full CI sweep.

**Tech stack:** Python 3.11+, typer, pyyaml, rich, pytest, typer.testing.CliRunner. Extends existing modules under `src/vk/`; no new dependencies.

**Canonical fixture directory:** `tests/fixtures/rework/` (new) — six committed `.md` files per spec §8.3.

---

## Phase 1: `**Track:**` parser, model, and writer plumbing [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/37 -->

**Depends on:** —

Generic plan-AST work. No CLI surface yet. Must stay backwards-compatible with every existing test fixture.

### Task 1: `Phase.track_label` model field

**Files:**
- Modify: `src/vk/plan/models.py`
- Modify: `tests/unit/test_models.py`

- [x] **Step 1: Write a failing test pinning the default-None behaviour**

Append to `tests/unit/test_models.py`:

```python
def test_phase_track_label_defaults_to_none() -> None:
    """Positional-constructor callers that predate **Track:** must still
    build a Phase without supplying the new field."""
    from vk.plan.models import Phase
    p = Phase(
        number=1,
        title="First",
        tag="agentic",
        depends_on=(),
        tasks=(),
        tracking_url=None,
    )
    assert p.track_label is None


def test_phase_track_label_accepts_string() -> None:
    from vk.plan.models import Phase
    p = Phase(
        number=1,
        title="First",
        tag="agentic",
        depends_on=(),
        tasks=(),
        tracking_url=None,
        track_label="development",
    )
    assert p.track_label == "development"
```

Run: `uv run pytest tests/unit/test_models.py -x -q` — expect 2 failures naming `track_label`.

- [x] **Step 2: Add `track_label` to `Phase` with default `None`**

In `src/vk/plan/models.py`, inside the `Phase` dataclass, add below `tracking_url`:

```python
    track_label: str | None = None
```

Default `None` preserves positional-constructor compatibility per spec D9 / §5.2.

Run: `uv run pytest tests/unit/test_models.py -x -q` — expect green.

- [x] **Step 3: Sweep for existing fixtures that build `Phase` positionally**

```bash
uv run rg -n "Phase\(" tests/ src/
```

Expected: every call-site either (a) uses keyword args, or (b) stops at `tracking_url`. If any positional call passes a 7th arg, it now collides with `track_label` and needs updating. Fix by converting to kwargs.

Run: `uv run pytest -q --no-cov` — expect full green suite (baseline preserved).

### Task 2: Parser extraction of `**Track:**` body line

**Files:**
- Modify: `src/vk/plan/parser.py`
- Modify: `tests/unit/test_plan_parser.py`

- [x] **Step 1: Write failing parser tests for `**Track:**`**

Append to `tests/unit/test_plan_parser.py`:

```python
class TestTrackParsing:
    """Parser extracts a phase **Track:** body-line into Phase.track_label."""

    def _phase(self, extra_line: str) -> str:
        return (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: First [agentic]\n"
            "**Depends on:** —\n"
            f"{extra_line}"
            "\n### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_absent_line_yields_none(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase(""))
        plan = parse_plan(p)
        assert plan.phases[0].track_label is None

    def test_single_canonical_value(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** development\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "development"

    def test_transition_syntax_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** decision → development\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "decision → development"

    def test_compound_syntax_preserved(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** development (future-triggered)\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "development (future-triggered)"

    def test_multiple_track_lines_first_wins(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._phase("**Track:** operations\n**Track:** decision\n"))
        plan = parse_plan(p)
        assert plan.phases[0].track_label == "operations"
```

Run: `uv run pytest tests/unit/test_plan_parser.py::TestTrackParsing -x -q` — expect 5 failures.

- [x] **Step 2: Add `_TRACK_RE` adjacent to `_DEPENDS_ON_RE`**

In `src/vk/plan/parser.py`, after `_DEPENDS_ON_RE` (line ~43):

```python
_TRACK_RE = re.compile(
    r"^\*\*Track:\*\*\s+(.+?)\s*$",
    re.MULTILINE,
)
```

- [x] **Step 3: Extract track in `_parse_phases` prelude slice**

In `_parse_phases`, after the `depends_on = _parse_depends_on(prelude, phase_number)` assignment, add:

```python
track_match = _TRACK_RE.search(prelude)
track_label = track_match.group(1).strip() if track_match else None
```

Pass `track_label=track_label` to the `Phase(...)` constructor call further down.

Run: `uv run pytest tests/unit/test_plan_parser.py::TestTrackParsing -x -q` — expect green.

- [x] **Step 4: Re-run full parser suite to prove no regressions**

```bash
uv run pytest tests/unit/test_plan_parser.py tests/unit/test_plan_validate.py -q
```

Expect all green. The new regex is scoped to the prelude slice, so it cannot leak into task bodies.

### Task 3: Writer emits `**Track:**` after `**Depends on:**`

**Files:**
- Modify: `src/vk/plan/writer.py`
- Modify: `tests/unit/test_plan_writer.py`

- [x] **Step 1: Write failing writer tests for Track emission**

Append to `tests/unit/test_plan_writer.py`:

```python
class TestTrackWriterEmission:
    def _one_phase_plan(self, track: str | None) -> Plan:
        return Plan(
            title="T",
            spec="s.md",
            status="Not Started",
            goal="g",
            format=PlanFormat.PHASED,
            phases=(
                Phase(
                    number=1,
                    title="First",
                    tag="agentic",
                    depends_on=(),
                    tasks=(),
                    tracking_url=None,
                    track_label=track,
                ),
            ),
            tasks=(),
        )

    def test_track_line_absent_when_none(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        write_plan(self._one_phase_plan(None), p)
        text = p.read_text()
        assert "**Track:**" not in text

    def test_track_line_emitted_after_depends_on(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        write_plan(self._one_phase_plan("development"), p)
        text = p.read_text()
        assert "**Depends on:** —\n**Track:** development" in text

    def test_round_trip_preserves_track_label(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        write_plan(self._one_phase_plan("decision → development"), p)
        reparsed = parse_plan(p)
        assert reparsed.phases[0].track_label == "decision → development"
```

Run: `uv run pytest tests/unit/test_plan_writer.py::TestTrackWriterEmission -x -q` — expect 2 failures (absence test passes trivially).

- [x] **Step 2: Emit `**Track:**` in `_write_phases`**

In `src/vk/plan/writer.py`, inside `_write_phases`, after `lines.append(_format_depends_on(phase))` and BEFORE the blank-line append that separates header from tasks:

```python
        if phase.track_label is not None:
            lines.append(f"**Track:** {phase.track_label}")
```

Run: `uv run pytest tests/unit/test_plan_writer.py -x -q` — expect green.

- [x] **Step 3: Full plan suite regression check**

```bash
uv run pytest -q --no-cov
```

All green. Every existing round-trip fixture still parses → writes → parses identically (no Track line emitted when `track_label is None`).

---

## Phase 2: `rework.py` core — template, numbering, Origin helpers [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/38 -->

**Depends on:** —

Pure library code under `src/vk/plan/rework.py`. No typer imports, no CLI surface. All three upcoming commands delegate their business logic here per spec §1.

### Task 1: `next_rework_number` with cross-dir collision guard

**Files:**
- Create: `src/vk/plan/rework.py`
- Create: `tests/unit/test_rework.py`

- [x] **Step 1: Write failing tests for `next_rework_number`**

Create `tests/unit/test_rework.py`:

```python
"""Unit tests for src/vk/plan/rework.py."""

from __future__ import annotations

from pathlib import Path

import pytest

from vk.plan.rework import next_rework_number


def _touch(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# placeholder\n")


class TestNextReworkNumber:
    def test_no_existing_reworks_returns_1(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        assert next_rework_number(parent, repo_root=tmp_path) == 1

    def test_active_rework_1_returns_2(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 2

    def test_archived_rework_1_returns_2(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 2

    def test_gaps_tolerated(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-3.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 4

    def test_collision_across_dirs_raises(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md")
        with pytest.raises(ValueError, match="ambiguous rework state"):
            next_rework_number(parent, repo_root=tmp_path)

    def test_concurrent_active_reworks_allowed(self, tmp_path: Path) -> None:
        parent = tmp_path / "docs/superpowers/plans/2026-04-08-foo.md"
        _touch(parent)
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md")
        _touch(tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-2.md")
        assert next_rework_number(parent, repo_root=tmp_path) == 3
```

Run: `uv run pytest tests/unit/test_rework.py -x -q` — expect import failure (file doesn't exist yet).

- [x] **Step 2: Create `src/vk/plan/rework.py` with `next_rework_number`**

```python
"""Rework-plan scaffolding, Origin-table I/O, and numbering helpers.

Sister module to ``src/vk/plan/convert.py`` and ``src/vk/plan/format.py``. The
command-level wrappers in ``src/vk/commands/plan_cmd.py`` delegate here; this
module has no typer dependency.
"""

from __future__ import annotations

import re
from pathlib import Path

from vk.plan.filename import derive_slug

_REWORK_NUM_RE = re.compile(r"-rework-(\d+)\.md$")


def next_rework_number(parent_path: Path, *, repo_root: Path) -> int:
    """Return the next available rework number for ``parent_path``.

    Scans ``docs/superpowers/plans/`` and ``docs/superpowers/archived-plans/``
    for files matching ``<date>-<slug>-rework-<N>.md``. Raises ``ValueError``
    on the same ``N`` appearing in both directories (spec D10 / §4).
    Tolerates gaps — returns ``max(N) + 1`` over the combined set.
    """
    slug = derive_slug(parent_path)
    date_prefix = parent_path.stem[:10]  # YYYY-MM-DD
    prefix = f"{date_prefix}-{slug}"

    plans_dir = repo_root / "docs/superpowers/plans"
    archived_dir = repo_root / "docs/superpowers/archived-plans"

    def _scan(dir_: Path) -> set[int]:
        if not dir_.is_dir():
            return set()
        out: set[int] = set()
        for p in dir_.iterdir():
            if not p.is_file() or not p.name.startswith(prefix):
                continue
            m = _REWORK_NUM_RE.search(p.name)
            if m:
                out.add(int(m.group(1)))
        return out

    in_plans = _scan(plans_dir)
    in_archived = _scan(archived_dir)

    collision = in_plans & in_archived
    if collision:
        n = sorted(collision)[0]
        raise ValueError(
            f"ambiguous rework state: rework-{n} exists in both plans/ and "
            f"archived-plans/. Resolve manually before scaffolding."
        )

    combined = in_plans | in_archived
    return max(combined) + 1 if combined else 1
```

Run: `uv run pytest tests/unit/test_rework.py -x -q` — expect green.

### Task 2: Template constant and `render_scaffold()`

**Files:**
- Modify: `src/vk/plan/rework.py`
- Modify: `tests/unit/test_rework.py`

- [x] **Step 1: Write failing tests for `render_scaffold`**

Append to `tests/unit/test_rework.py`:

```python
from vk.plan.rework import render_scaffold


class TestRenderScaffold:
    def test_archived_parent_with_spec_and_title(self) -> None:
        out = render_scaffold(
            parent_title="Parental Controls Plan",
            parent_slug_date="2026-04-08-kid-laptops-5-parental-controls",
            spec="docs/superpowers/specs/2026-04-07-kid-laptops-design.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-kid-laptops-5-parental-controls.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert out.startswith("# Parental Controls Plan — Rework 1\n")
        assert "**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`" in out
        assert "(merged + archived)" in out
        assert "**Prior rework:**" not in out
        assert "## Origin" in out
        assert "| # | Item | Source | Track |" in out
        assert "## Definition of Done" in out

    def test_unarchived_parent_annotation(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/plans/2026-04-08-foo.md",
            parent_archived=False,
            n=1,
            prior_rework_rel_path=None,
        )
        assert "(not yet archived)" in out

    def test_prior_rework_rendered(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=2,
            prior_rework_rel_path="docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md",
        )
        assert "**Prior rework:** `docs/superpowers/archived-plans/2026-04-08-foo-rework-1.md`" in out
        assert out.split("# Foo — Rework 2")[0] == ""

    def test_no_spec_line_when_spec_none(self) -> None:
        out = render_scaffold(
            parent_title="Foo",
            parent_slug_date="2026-04-08-foo",
            spec=None,
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert "**Spec:**" not in out
```

Run tests — expect import failure on `render_scaffold`.

- [x] **Step 2: Add the template literal and `render_scaffold()` to `rework.py`**

Append to `src/vk/plan/rework.py`:

```python
_SCAFFOLD_TEMPLATE = """\
# {title}

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

{spec_line}**Parent plan:** `{parent_rel_path}` {parent_annotation}
{prior_rework_line}**Status:** Not Started

**Goal:** [Address rework items on {parent_slug_date} without reopening the parent.]

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|

---

## Definition of Done

- [ ] TODO: echo each resolved origin item here when the rework completes.
"""


def render_scaffold(
    *,
    parent_title: str,
    parent_slug_date: str,
    spec: str | None,
    parent_rel_path: str,
    parent_archived: bool,
    n: int,
    prior_rework_rel_path: str | None,
) -> str:
    """Render the rework scaffold per spec §3.

    Interpolation rules (spec §3):
    - ``spec``: if ``None``, the whole ``**Spec:** ...`` line is omitted.
    - ``parent_annotation``: ``(merged + archived)`` or ``(not yet archived)``.
    - ``prior_rework_rel_path``: if ``None``, the line is omitted entirely
      (not rendered with ``—``).
    - ``title``: caller is responsible for passing ``"<parent_title> — Rework N"``
      or the fallback ``"Rework N for <slug>"``.
    """
    title = f"{parent_title} — Rework {n}" if parent_title else f"Rework {n} for {parent_slug_date}"
    annotation = "(merged + archived)" if parent_archived else "(not yet archived)"
    spec_line = f"**Spec:** `{spec}`\n" if spec else ""
    prior_line = (
        f"**Prior rework:** `{prior_rework_rel_path}`\n" if prior_rework_rel_path else ""
    )
    return _SCAFFOLD_TEMPLATE.format(
        title=title,
        spec_line=spec_line,
        parent_rel_path=parent_rel_path,
        parent_annotation=annotation,
        prior_rework_line=prior_line,
        parent_slug_date=parent_slug_date,
    )
```

Run `uv run pytest tests/unit/test_rework.py::TestRenderScaffold -x -q` — expect green.

- [x] **Step 3: Pin the no-H1-fallback title path**

Append to `TestRenderScaffold`:

```python
    def test_fallback_title_when_parent_title_empty(self) -> None:
        out = render_scaffold(
            parent_title="",
            parent_slug_date="2026-04-08-foo",
            spec="s.md",
            parent_rel_path="docs/superpowers/archived-plans/2026-04-08-foo.md",
            parent_archived=True,
            n=1,
            prior_rework_rel_path=None,
        )
        assert out.startswith("# Rework 1 for 2026-04-08-foo\n")
```

Run — expect green. This locks the spec §3 fallback-title rule.

### Task 3: `OriginRow` + `parse_origin_table`

**Files:**
- Modify: `src/vk/plan/rework.py`
- Modify: `tests/unit/test_rework.py`
- Create: `tests/fixtures/rework/rework_empty.md`
- Create: `tests/fixtures/rework/rework_with_rows.md`
- Create: `tests/fixtures/rework/rework_malformed_origin.md`

- [x] **Step 1: Write the three Origin-table fixtures**

Create `tests/fixtures/rework/rework_empty.md`:

```markdown
# Foo — Rework 1

**Spec:** `s.md`
**Parent plan:** `docs/superpowers/archived-plans/2026-04-08-foo.md` (merged + archived)
**Status:** Not Started

**Goal:** placeholder.

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|

---

## Definition of Done

- [ ] TODO.
```

Create `tests/fixtures/rework/rework_with_rows.md`:

```markdown
# Foo — Rework 1

**Spec:** `s.md`
**Parent plan:** `docs/superpowers/archived-plans/2026-04-08-foo.md` (merged + archived)
**Status:** Not Started

**Goal:** placeholder.

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|
| 1 | Wire \| pipe in item | PR #42 | development |
| 2 | Smoke test the deploy | demo | operations |
| 3 | Decide on theme palette | design review | decision |

---

## Definition of Done

- [ ] TODO.
```

Create `tests/fixtures/rework/rework_malformed_origin.md`:

```markdown
# Foo — Rework 1

**Status:** Not Started

**Goal:** placeholder.

---

## Origin

| # | Description | Source |
|---|-------------|--------|

---

## Definition of Done

- [ ] TODO.
```

- [x] **Step 2: Write failing tests for `parse_origin_table`**

Append to `tests/unit/test_rework.py`:

```python
from vk.plan.rework import OriginRow, parse_origin_table

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


class TestParseOriginTable:
    def test_empty_table(self) -> None:
        rows = parse_origin_table(FIXTURES / "rework_empty.md")
        assert rows == []

    def test_three_rows_with_pipe_escape_unescaped(self) -> None:
        rows = parse_origin_table(FIXTURES / "rework_with_rows.md")
        assert rows == [
            OriginRow(number=1, item="Wire | pipe in item", source="PR #42", track="development"),
            OriginRow(number=2, item="Smoke test the deploy", source="demo", track="operations"),
            OriginRow(number=3, item="Decide on theme palette", source="design review", track="decision"),
        ]

    def test_malformed_header_raises(self) -> None:
        with pytest.raises(ValueError, match="Origin table header malformed"):
            parse_origin_table(FIXTURES / "rework_malformed_origin.md")

    def test_missing_origin_section_raises(self, tmp_path: Path) -> None:
        p = tmp_path / "no_origin.md"
        p.write_text("# T\n\n**Status:** Not Started\n\n**Goal:** g\n")
        with pytest.raises(ValueError, match="no ## Origin section"):
            parse_origin_table(p)
```

Run — expect import failure on `OriginRow`, `parse_origin_table`.

- [x] **Step 3: Implement `OriginRow` and `parse_origin_table`**

Append to `src/vk/plan/rework.py`:

```python
from dataclasses import dataclass

_EXPECTED_ORIGIN_HEADER = "| # | Item | Source | Track |"
_ORIGIN_HEADING_RE = re.compile(r"^## Origin\s*$", re.MULTILINE)


@dataclass(frozen=True)
class OriginRow:
    number: int
    item: str
    source: str
    track: str


def parse_origin_table(path: Path) -> list[OriginRow]:
    """Parse the Origin table from a rework plan file.

    Raises ValueError on: missing ``## Origin`` heading, malformed header row.
    Empty table (header + separator, no data rows) returns ``[]``. Unescapes
    ``\\|`` back to ``|`` per spec §6.1.
    """
    text = path.read_text(encoding="utf-8")
    heading_match = _ORIGIN_HEADING_RE.search(text)
    if not heading_match:
        raise ValueError(
            f"plan has no ## Origin section. Was this scaffolded via 'vk plan rework'? ({path})"
        )
    after = text[heading_match.end() :]
    lines = after.splitlines()

    # Locate the header row (first non-blank, non-divider line).
    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1
    if idx >= len(lines) or lines[idx].strip() != _EXPECTED_ORIGIN_HEADER:
        raise ValueError(
            f"Origin table header malformed. Expected: {_EXPECTED_ORIGIN_HEADER}"
        )
    idx += 1
    # Separator row (| --- | --- | --- | --- |). Skip whatever is there.
    idx += 1

    rows: list[OriginRow] = []
    while idx < len(lines):
        line = lines[idx].rstrip()
        if not line.startswith("|"):
            break  # end of table
        # Split on non-escaped pipes: first replace \| with a sentinel.
        sentinel = "\x00"
        encoded = line.replace(r"\|", sentinel)
        parts = [p.strip().replace(sentinel, "|") for p in encoded.strip("|").split("|")]
        if len(parts) != 4:
            raise ValueError(f"Origin table row has {len(parts)} cells, expected 4: {line!r}")
        try:
            n = int(parts[0])
        except ValueError:
            raise ValueError(f"Origin table row # column is not an int: {line!r}")
        rows.append(OriginRow(number=n, item=parts[1], source=parts[2], track=parts[3]))
        idx += 1
    return rows
```

Run `uv run pytest tests/unit/test_rework.py::TestParseOriginTable -x -q` — expect green.

### Task 4: `append_origin_row`

**Files:**
- Modify: `src/vk/plan/rework.py`
- Modify: `tests/unit/test_rework.py`

- [x] **Step 1: Write failing round-trip tests for `append_origin_row`**

Append to `tests/unit/test_rework.py`:

```python
from vk.plan.rework import append_origin_row


class TestAppendOriginRow:
    def test_append_to_empty_table(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        row = OriginRow(number=1, item="Ship docs", source="PR #42", track="development")
        append_origin_row(p, row)
        rows = parse_origin_table(p)
        assert rows == [row]

    def test_append_preserves_dod(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        append_origin_row(p, OriginRow(1, "x", "y", "development"))
        text = p.read_text()
        assert "## Definition of Done" in text
        assert "- [ ] TODO." in text

    def test_append_escapes_pipes(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_empty.md").read_text())
        append_origin_row(p, OriginRow(1, "wire | pipe", "src | with pipe", "development"))
        text = p.read_text()
        assert r"wire \| pipe" in text
        assert r"src \| with pipe" in text
        # Round-trip unescapes.
        rows = parse_origin_table(p)
        assert rows[0].item == "wire | pipe"
        assert rows[0].source == "src | with pipe"

    def test_append_after_existing_rows(self, tmp_path: Path) -> None:
        p = tmp_path / "r.md"
        p.write_text((FIXTURES / "rework_with_rows.md").read_text())
        append_origin_row(p, OriginRow(4, "new item", "PR #99", "operations"))
        rows = parse_origin_table(p)
        assert len(rows) == 4
        assert rows[3] == OriginRow(4, "new item", "PR #99", "operations")
```

Run — expect import failure on `append_origin_row`.

- [x] **Step 2: Implement `append_origin_row`**

Append to `src/vk/plan/rework.py`:

```python
def append_origin_row(path: Path, row: OriginRow) -> None:
    """Append a single row to the Origin table in ``path``.

    Preserves every byte outside the Origin table. Escapes ``|`` in ``item``
    and ``source`` by replacing with ``\\|``. Writes the file back atomically
    via ``path.write_text`` (good enough — single-file scaffolds, no reader
    concurrency concern in CLI contexts).
    """
    text = path.read_text(encoding="utf-8")
    heading_match = _ORIGIN_HEADING_RE.search(text)
    if not heading_match:
        raise ValueError(
            f"plan has no ## Origin section. Was this scaffolded via 'vk plan rework'? ({path})"
        )
    after_heading = heading_match.end()
    lines = text[after_heading:].splitlines(keepends=True)

    # Walk forward to the header; then past separator; then past any data rows.
    abs_offset = after_heading
    idx = 0
    # Skip blanks.
    while idx < len(lines) and lines[idx].strip() == "":
        abs_offset += len(lines[idx])
        idx += 1
    if idx >= len(lines) or lines[idx].strip() != _EXPECTED_ORIGIN_HEADER:
        raise ValueError(
            f"Origin table header malformed. Expected: {_EXPECTED_ORIGIN_HEADER}"
        )
    abs_offset += len(lines[idx])  # consume header
    idx += 1
    if idx >= len(lines):
        raise ValueError("Origin table truncated after header.")
    abs_offset += len(lines[idx])  # consume separator
    idx += 1
    # Advance past any existing data rows.
    while idx < len(lines) and lines[idx].startswith("|"):
        abs_offset += len(lines[idx])
        idx += 1

    # Build the new row, escaping pipes.
    def _esc(s: str) -> str:
        return s.replace("|", r"\|")

    new_line = f"| {row.number} | {_esc(row.item)} | {_esc(row.source)} | {row.track} |\n"

    new_text = text[:abs_offset] + new_line + text[abs_offset:]
    path.write_text(new_text, encoding="utf-8")
```

Run `uv run pytest tests/unit/test_rework.py::TestAppendOriginRow -x -q` — expect green.

- [x] **Step 3: Full `test_rework.py` suite + whole-tree regression**

```bash
uv run pytest tests/unit/test_rework.py -q
uv run pytest -q --no-cov
```

Both green. No existing test touches rework.py, so the regression sweep is cheap but mandatory.

---

## Phase 3: `vk plan rework` scaffold CLI [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/39 -->

**Depends on:** Phase 2

Thin typer wrapper around `rework.py`. Every exit-code case in spec §7 for this command must have a test.

### Task 1: Typer command + happy-path integration test

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `src/vk/plan/rework.py` (add `scaffold_rework` orchestrator)
- Create: `tests/integration/test_plan_rework.py`
- Create: `tests/fixtures/rework/parent_archived.md`
- Create: `tests/fixtures/rework/parent_no_spec.md`

- [x] **Step 1: Write the parent fixtures**

Create `tests/fixtures/rework/parent_archived.md`:

```markdown
# Kid Laptops Plan 5

**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`
**Status:** Complete

**Goal:** Parental controls for kid laptops.

---

## Phase 1: First [agentic]
**Depends on:** —

### Task 1: Setup

- [x] **Step 1:** Do thing
```

Create `tests/fixtures/rework/parent_no_spec.md`:

```markdown
# Spec-less Parent

**Status:** Complete

**Goal:** A parent without a spec line.

---

## Phase 1: First [agentic]
**Depends on:** —

### Task 1: Setup

- [x] **Step 1:** Do thing
```

- [x] **Step 2: Write a failing happy-path integration test**

Create `tests/integration/test_plan_rework.py`:

```python
"""Integration tests for ``vk plan rework <parent>``."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _setup_repo(tmp_path: Path, parent_fixture: str, *, archived: bool = True) -> Path:
    """Build a minimal repo with a parent plan in plans/ or archived-plans/."""
    target_dir = tmp_path / (
        "docs/superpowers/archived-plans" if archived else "docs/superpowers/plans"
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    parent_dest = target_dir / "2026-04-08-kid-laptops-5-parental-controls.md"
    shutil.copy(FIXTURES / parent_fixture, parent_dest)
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True, exist_ok=True)
    return parent_dest


def test_rework_archived_parent_happy_path(tmp_path: Path) -> None:
    parent = _setup_repo(tmp_path, "parent_archived.md")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework", str(parent)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    out_path = tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    assert out_path.exists()
    text = out_path.read_text()
    assert "# Kid Laptops Plan 5 — Rework 1" in text
    assert "**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`" in text
    assert "(merged + archived)" in text
    assert "## Origin" in text
```

Run `uv run pytest tests/integration/test_plan_rework.py -x -q` — expect failure (command not registered).

- [x] **Step 3: Add `scaffold_rework` orchestrator in `rework.py`**

Append to `src/vk/plan/rework.py`:

```python
from vk.plan.parser import parse_plan


def scaffold_rework(parent_path: Path, *, repo_root: Path) -> tuple[Path, list[str]]:
    """Scaffold a rework plan for ``parent_path``. Returns (output_path, warnings).

    Raises ValueError on structural refusals (spec §7). Callers translate to
    typer.Exit(2). Warnings are stderr-destined strings — caller emits them.
    """
    parent_path = parent_path.resolve()
    if not parent_path.exists():
        raise ValueError(f"parent plan not found: {parent_path}")

    plans_dir = (repo_root / "docs/superpowers/plans").resolve()
    archived_dir = (repo_root / "docs/superpowers/archived-plans").resolve()
    is_in_plans = parent_path.is_relative_to(plans_dir)
    is_in_archived = parent_path.is_relative_to(archived_dir)
    if not (is_in_plans or is_in_archived):
        raise ValueError(
            "parent plan must live in docs/superpowers/plans/ or "
            f"docs/superpowers/archived-plans/. Got: {parent_path}"
        )

    warnings: list[str] = []
    parent = parse_plan(parent_path)
    title = parent.title if parent.title != "Untitled Plan" else ""
    if not title:
        warnings.append("parent has no H1 title; using slug-derived fallback.")

    n = next_rework_number(parent_path, repo_root=repo_root)

    slug = derive_slug(parent_path)
    date_prefix = parent_path.stem[:10]
    parent_slug_date = f"{date_prefix}-{slug}"

    # Prior rework: highest archived N lower than the new N.
    prior = _highest_archived_prior(
        repo_root=repo_root, prefix=parent_slug_date, below=n
    )

    if is_in_plans:
        warnings.append(
            "parent is not yet archived; Parent plan header points at plans/. "
            "Update when parent is moved."
        )

    rendered = render_scaffold(
        parent_title=title,
        parent_slug_date=parent_slug_date,
        spec=parent.spec,
        parent_rel_path=str(parent_path.relative_to(repo_root)),
        parent_archived=is_in_archived,
        n=n,
        prior_rework_rel_path=str(prior.relative_to(repo_root)) if prior else None,
    )

    out_path = plans_dir / f"{parent_slug_date}-rework-{n}.md"
    if out_path.exists():
        raise ValueError(f"output path already exists: {out_path}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(rendered, encoding="utf-8")
    return out_path, warnings


def _highest_archived_prior(
    *, repo_root: Path, prefix: str, below: int
) -> Path | None:
    archived_dir = repo_root / "docs/superpowers/archived-plans"
    if not archived_dir.is_dir():
        return None
    best_n = -1
    best_path: Path | None = None
    for p in archived_dir.iterdir():
        if not p.is_file() or not p.name.startswith(prefix):
            continue
        m = _REWORK_NUM_RE.search(p.name)
        if not m:
            continue
        n = int(m.group(1))
        if n < below and n > best_n:
            best_n = n
            best_path = p
    return best_path
```

- [x] **Step 4: Register `vk plan rework` in `plan_cmd.py`**

In `src/vk/commands/plan_cmd.py`, after `plan_convert`, add:

```python
@plan_app.command(name="rework")
def plan_rework(
    parent_path: Path = typer.Argument(..., help="Path to the parent plan file."),
) -> None:
    """Scaffold a rework plan against a parent."""
    import subprocess
    from vk.plan.rework import scaffold_rework

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        repo_root = Path.cwd()

    try:
        out_path, warnings = scaffold_rework(parent_path, repo_root=repo_root)
    except ValueError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)

    for w in warnings:
        err_console.print(f"warn: {w}")
    console.print(f"Created: {out_path}")
```

Run the happy-path test — expect green.

> Note: `CliRunner` invokes the typer app within the test's `tmp_path`, but
> `subprocess.run(["git", "rev-parse", ...])` will return the actual repo
> root. Integration tests set CWD via the `test_plan_execute.py` pattern —
> each test either `monkeypatch.chdir(tmp_path)` or invokes via a subprocess
> that we already use elsewhere. See Step 5.

- [x] **Step 5: Stabilise repo_root discovery under tmp_path**

Replace the `git rev-parse` block in `plan_rework` with:

```python
    repo_root = _resolve_repo_root()
```

Add a helper near the top of `plan_cmd.py`:

```python
def _resolve_repo_root() -> Path:
    """Resolve repo root for a plan command.

    Honors ``$VK_REPO_ROOT`` first (so integration tests can point the
    command at ``tmp_path`` without spawning a fake git repo), then falls
    back to ``git rev-parse``, then to ``Path.cwd()``.
    """
    import os
    import subprocess
    override = os.environ.get("VK_REPO_ROOT")
    if override:
        return Path(override)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()
```

Refactor `plan_new`, `plan_spec_index`, and `plan_rework` to call `_resolve_repo_root()`.

Update `test_rework_archived_parent_happy_path` to set `env={"VK_REPO_ROOT": str(tmp_path)}` on the `CliRunner.invoke` call. Keep in mind CliRunner does not pass `env` — set `monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))` instead.

Run the test — expect green.

### Task 2: Exit-code and warning matrix

**Files:**
- Modify: `tests/integration/test_plan_rework.py`
- Modify: `src/vk/plan/rework.py` (refinements as tests drive them)

- [x] **Step 1: Test — parent missing returns exit 2**

Append to `tests/integration/test_plan_rework.py`:

```python
def test_rework_missing_parent_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework", str(tmp_path / "nope.md")],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "parent plan not found" in result.stderr
```

Run — expect green if orchestrator raises correctly; otherwise fix.

- [x] **Step 2: Test — mis-located parent returns exit 2**

```python
def test_rework_parent_outside_plans_dirs_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    rogue = tmp_path / "not-a-plan-dir" / "2026-04-08-foo.md"
    rogue.parent.mkdir(parents=True)
    rogue.write_text("# Foo\n**Status:** Complete\n**Goal:** g\n")
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework", str(rogue)], catch_exceptions=False
    )
    assert result.exit_code == 2
    assert "must live in docs/superpowers/plans/" in result.stderr
```

Run — expect green.

- [x] **Step 3: Test — unarchived parent emits warning, proceeds**

```python
def test_rework_unarchived_parent_warns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md", archived=False)
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework", str(parent)], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert "not yet archived" in result.stderr
    out = tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    assert out.exists()
    text = out.read_text()
    assert "(not yet archived)" in text
```

Run — expect green.

- [x] **Step 4: Test — rework-1 archived, rework-2 gets Prior rework line**

```python
def test_rework_chains_prior_rework(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md")
    # Seed an archived rework-1.
    (tmp_path / "docs/superpowers/archived-plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md").write_text(
        "# Stub — Rework 1\n**Status:** Complete\n**Goal:** done.\n"
    )
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework", str(parent)], catch_exceptions=False
    )
    assert result.exit_code == 0
    out = tmp_path / "docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-2.md"
    assert out.exists()
    assert "# Kid Laptops Plan 5 — Rework 2" in out.read_text()
    assert "**Prior rework:** `docs/superpowers/archived-plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md`" in out.read_text()
```

Run — expect green.

- [x] **Step 5: Test — cross-dir collision exits 2**

```python
def test_rework_cross_dir_collision_exits_2(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    parent = _setup_repo(tmp_path, "parent_archived.md")
    slug = "2026-04-08-kid-laptops-5-parental-controls-rework-1.md"
    (tmp_path / "docs/superpowers/plans" / slug).write_text("# x\n")
    (tmp_path / "docs/superpowers/archived-plans" / slug).write_text("# x\n")
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework", str(parent)], catch_exceptions=False
    )
    assert result.exit_code == 2
    assert "ambiguous rework state" in result.stderr
```

Run — expect green.

- [x] **Step 6: Test — no-H1 parent warns, uses fallback title**

```python
def test_rework_no_h1_title_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    target_dir = tmp_path / "docs/superpowers/archived-plans"
    target_dir.mkdir(parents=True)
    parent = target_dir / "2026-04-08-no-title.md"
    parent.write_text("**Status:** Complete\n\n**Goal:** g\n")
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework", str(parent)], catch_exceptions=False
    )
    assert result.exit_code == 0
    assert "no H1 title" in result.stderr
    out_text = (tmp_path / "docs/superpowers/plans/2026-04-08-no-title-rework-1.md").read_text()
    assert out_text.startswith("# Rework 1 for 2026-04-08-no-title\n")
```

Run — expect green.

- [x] **Step 7: Full integration + unit regression**

```bash
uv run pytest -q --no-cov
```

All green.

---

## Phase 4: `vk plan rework-add` CLI [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/40 -->

**Depends on:** Phase 2

### Task 1: Typer command with required flags

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Create: `tests/integration/test_plan_rework_add.py`

- [x] **Step 1: Write failing happy-path integration test**

```python
"""Integration tests for ``vk plan rework-add``."""

from __future__ import annotations

import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app
from vk.plan.rework import parse_origin_table

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def _rework_file(tmp_path: Path, fixture: str = "rework_empty.md") -> Path:
    target = tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES / fixture, target)
    return target


def test_rework_add_happy_path(tmp_path: Path) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "plan", "rework-add", str(path),
            "--item", "Ship the docs",
            "--source", "PR #42",
            "--track", "development",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    assert "Added Origin row #1" in result.stdout
    rows = parse_origin_table(path)
    assert len(rows) == 1
    assert rows[0].item == "Ship the docs"
    assert rows[0].track == "development"
```

Run — expect failure (command missing).

- [x] **Step 2: Register `vk plan rework-add`**

In `plan_cmd.py`:

```python
@plan_app.command(name="rework-add")
def plan_rework_add(
    rework_path: Path = typer.Argument(..., help="Path to the rework plan file."),
    item: str = typer.Option(..., "--item", help="Origin item text."),
    source: str = typer.Option(..., "--source", help="Where the item came from."),
    track: str = typer.Option(..., "--track", help="Work-category label."),
) -> None:
    """Append a row to a rework plan's Origin table."""
    # ``OriginRow``, ``append_origin_row``, and ``parse_origin_table`` are
    # imported at the top of ``plan_cmd.py`` alongside the other
    # ``vk.plan.*`` helpers (no circular-import concern; rework.py has no
    # dependency on plan_cmd).
    if not rework_path.exists():
        err_console.print(f"Error: rework plan not found: {rework_path}")
        raise typer.Exit(2)

    for name, value in (("--item", item), ("--source", source), ("--track", track)):
        if not value.strip():
            err_console.print(f"Error: {name} is required and must be non-empty.")
            raise typer.Exit(2)
        if "\n" in value or "\r" in value:
            err_console.print(f"Error: {name} must not contain newlines.")
            raise typer.Exit(2)

    first_token = track.strip().split()[0].lower()
    if first_token not in {"development", "operations", "decision"}:
        err_console.print(
            f"warn: --track value '{track}' is not a canonical token "
            "(development / operations / decision). Accepted as free-form."
        )

    try:
        existing = parse_origin_table(rework_path)
    except ValueError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)
    next_n = (max((r.number for r in existing), default=0)) + 1
    try:
        append_origin_row(
            rework_path,
            OriginRow(number=next_n, item=item.strip(), source=source.strip(), track=track.strip()),
        )
    except ValueError as exc:
        err_console.print(f"Error: {exc}")
        raise typer.Exit(2)
    console.print(f"Added Origin row #{next_n} to {rework_path}")
```

Run — expect happy-path green.

### Task 2: Flag-validation and edge-case tests

**Files:**
- Modify: `tests/integration/test_plan_rework_add.py`

- [x] **Step 1: Test — canonical tracks emit NO warn**

```python
def test_rework_add_canonical_track_no_warn(tmp_path: Path) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    for tok in ("development", "operations", "decision"):
        result = runner.invoke(
            app,
            ["plan", "rework-add", str(path),
             "--item", "x", "--source", "y", "--track", tok],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert "not a canonical token" not in result.stderr
```

- [x] **Step 2: Test — non-canonical track warns, still succeeds**

```python
def test_rework_add_non_canonical_track_warns(tmp_path: Path) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework-add", str(path),
         "--item", "x", "--source", "y", "--track", "research"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert "not a canonical token" in result.stderr
```

- [x] **Step 3: Test — empty flag value exits 2 naming the flag**

```python
import pytest

@pytest.mark.parametrize("item,source,track", [
    ("", "y", "development"),
    ("   ", "y", "development"),
    ("x", "", "development"),
    ("x", "y", "   "),
])
def test_rework_add_empty_flag_exits_2(
    tmp_path: Path, item, source, track
) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app, ["plan", "rework-add", str(path),
              "--item", item, "--source", source, "--track", track],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "is required and must be non-empty" in result.stderr
```

- [x] **Step 4: Test — newline in any flag exits 2**

```python
def test_rework_add_newline_rejected(tmp_path: Path) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework-add", str(path),
         "--item", "line1\nline2", "--source", "y", "--track", "development"],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "must not contain newlines" in result.stderr
```

- [x] **Step 5: Test — pipe escape round-trips**

```python
def test_rework_add_pipe_escape_roundtrip(tmp_path: Path) -> None:
    path = _rework_file(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework-add", str(path),
         "--item", "wire | pipe", "--source", "y", "--track", "development"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    # File contains escaped pipe.
    assert r"wire \| pipe" in path.read_text()
    # Round-trip unescapes.
    assert parse_origin_table(path)[0].item == "wire | pipe"
```

- [x] **Step 6: Test — missing Origin section exits 2**

```python
def test_rework_add_missing_origin_exits_2(tmp_path: Path) -> None:
    path = tmp_path / "docs/superpowers/plans/2026-04-08-foo-rework-1.md"
    path.parent.mkdir(parents=True)
    path.write_text("# No Origin here\n\n**Status:** Not Started\n**Goal:** g\n")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework-add", str(path),
         "--item", "x", "--source", "y", "--track", "development"],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "no ## Origin section" in result.stderr
```

- [x] **Step 7: Test — malformed Origin header exits 2**

```python
def test_rework_add_malformed_origin_exits_2(tmp_path: Path) -> None:
    path = _rework_file(tmp_path, "rework_malformed_origin.md")
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["plan", "rework-add", str(path),
         "--item", "x", "--source", "y", "--track", "development"],
        catch_exceptions=False,
    )
    assert result.exit_code == 2
    assert "Origin table header malformed" in result.stderr
```

Run: `uv run pytest tests/integration/test_plan_rework_add.py -q` — all green.

---

## Phase 5: `vk plan rework-list` CLI [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/41 -->

**Depends on:** Phase 1, Phase 2

Reads parsed plans (needs Phase 1 for `track_label`) and Origin tables (needs Phase 2).

### Task 1: Core glob + record assembly

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `src/vk/plan/rework.py` (add `list_reworks` collector)

- [x] **Step 1: Write failing test for empty repo**

Create `tests/integration/test_plan_rework_list.py`:

```python
"""Integration tests for ``vk plan rework-list``."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

FIXTURES = Path(__file__).parent.parent / "fixtures/rework"


def test_rework_list_empty_repo(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    (tmp_path / "docs/superpowers/plans").mkdir(parents=True)
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    # Rich table prints headers but no data rows.
    assert "parent-slug" in result.stdout or result.stdout.strip() == ""
```

- [x] **Step 2: Implement `list_reworks` in `rework.py`**

Append to `src/vk/plan/rework.py`:

```python
from dataclasses import asdict


@dataclass(frozen=True)
class ReworkRecord:
    parent_slug: str
    rework_number: int
    status: str
    open_steps: int
    origin_items: int
    by_track: dict[str, int]
    path: str
    parent_path: str | None
    spec_path: str | None


def list_reworks(
    *,
    repo_root: Path,
    include_archived: bool = False,
) -> tuple[list[ReworkRecord], list[str]]:
    """Return (records, warnings). Warnings are per-file skip messages."""
    dirs = [repo_root / "docs/superpowers/plans"]
    if include_archived:
        dirs.append(repo_root / "docs/superpowers/archived-plans")

    records: list[ReworkRecord] = []
    warnings: list[str] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*-rework-*.md")):
            try:
                records.append(_record_for(p, repo_root))
            except Exception as exc:
                warnings.append(f"skipping {p}: {exc}")
    return records, warnings


def _record_for(path: Path, repo_root: Path) -> ReworkRecord:
    plan = parse_plan(path)
    # Derive parent_slug by stripping -rework-N from the filename slug.
    full_slug = derive_slug(path)
    m = _REWORK_NUM_RE.search(path.name)
    if not m:
        raise ValueError(f"rework file has no -rework-N suffix: {path.name}")
    n = int(m.group(1))
    parent_slug = re.sub(r"-rework-\d+$", "", full_slug)
    open_steps = sum(1 for t in plan.all_tasks for s in t.steps if s.state == " ")
    try:
        rows = parse_origin_table(path)
    except ValueError:
        rows = []
    by_track: dict[str, int] = {}
    for r in rows:
        by_track[r.track] = by_track.get(r.track, 0) + 1
    return ReworkRecord(
        parent_slug=parent_slug,
        rework_number=n,
        status=plan.status,
        open_steps=open_steps,
        origin_items=len(rows),
        by_track=by_track,
        path=str(path.relative_to(repo_root)),
        parent_path=None,
        spec_path=plan.spec,
    )
```

- [x] **Step 3: Register `vk plan rework-list` CLI**

In `plan_cmd.py`:

```python
@plan_app.command(name="rework-list")
def plan_rework_list(
    status: str | None = typer.Option(None, "--status", help="Filter by plan status."),
    track: str | None = typer.Option(None, "--track", help="Substring match on Origin Track."),
    plan: str | None = typer.Option(None, "--plan", help="Exact parent-slug match."),
    include_archived: bool = typer.Option(False, "--include-archived"),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON on stdout."),
) -> None:
    """List open (and optionally archived) rework plans in this repo."""
    import json as _json
    from vk.plan.rework import list_reworks
    from rich.table import Table

    repo_root = _resolve_repo_root()
    records, warnings = list_reworks(repo_root=repo_root, include_archived=include_archived)
    for w in warnings:
        err_console.print(f"warn: {w}")

    if status:
        records = [r for r in records if r.status.casefold() == status.casefold()]
    if track:
        needle = track.casefold()
        records = [
            r for r in records
            if any(needle in t.casefold() for t in r.by_track.keys())
        ]
    if plan:
        records = [r for r in records if r.parent_slug == plan]

    if json_output:
        console.print(_json.dumps([_record_to_json(r) for r in records]))
        return

    table = Table()
    for col in ("parent-slug", "rework-#", "status", "open-steps", "origin-items", "by-track"):
        table.add_column(col)
    for r in records:
        table.add_row(
            r.parent_slug,
            str(r.rework_number),
            r.status,
            str(r.open_steps),
            str(r.origin_items),
            _format_by_track(r.by_track),
        )
    console.print(table)


def _format_by_track(d: dict[str, int]) -> str:
    abbrev = {"development": "dev", "operations": "ops", "decision": "dec"}
    parts: list[str] = []
    for label, count in d.items():
        first = label.split()[0].lower() if label else ""
        parts.append(f"{count} {abbrev.get(first, first)}")
    return " / ".join(parts)


def _record_to_json(r: "ReworkRecord") -> dict[str, object]:
    return {
        "parent_slug": r.parent_slug,
        "rework_number": r.rework_number,
        "status": r.status,
        "open_steps": r.open_steps,
        "origin_items": r.origin_items,
        "by_track": r.by_track,
        "path": r.path,
        "parent_path": r.parent_path,
        "spec_path": r.spec_path,
    }
```

Add `from vk.plan.rework import ReworkRecord` for the type hint.

Run the empty-repo test — expect green.

### Task 2: Filters and `--json`

**Files:**
- Modify: `tests/integration/test_plan_rework_list.py`
- Create: `tests/fixtures/rework/rework_with_phases.md`

- [x] **Step 1: Create `rework_with_phases.md` fixture**

```markdown
# Foo — Rework 1

**Spec:** `docs/superpowers/specs/2026-04-07-kid-laptops-design.md`
**Parent plan:** `docs/superpowers/archived-plans/2026-04-08-foo.md` (merged + archived)
**Status:** In Progress

**Goal:** Address rework items on foo.

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|
| 1 | Thing one | PR #1 | development |
| 2 | Thing two | PR #1 | operations |
| 3 | Thing three | demo | decision → development |

---

## Phase 1: Do thing one [agentic]

**Depends on:** —
**Track:** development

### Task 1: Setup

- [ ] **Step 1:** Do it

## Phase 2: Smoke test [manual]

**Depends on:** Phase 1
**Track:** operations

### Task 1: Check

- [x] **Step 1:** Done
- [ ] **Step 2:** Still open

---

## Definition of Done

- [ ] TODO.
```

- [x] **Step 2: Test — two reworks list under default filters**

```python
def _seed_rework(tmp_path: Path, fixture: str, filename: str, archived: bool = False) -> Path:
    dir_ = tmp_path / ("docs/superpowers/archived-plans" if archived else "docs/superpowers/plans")
    dir_.mkdir(parents=True, exist_ok=True)
    dest = dir_ / filename
    shutil.copy(FIXTURES / fixture, dest)
    return dest


def test_rework_list_two_active_reworks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "foo" in result.stdout
    assert "bar" in result.stdout
```

- [x] **Step 3: Test — `--include-archived` picks up archived-plans**

```python
def test_rework_list_include_archived(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md", archived=True)
    runner = CliRunner()
    without = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    with_archived = runner.invoke(app, ["plan", "rework-list", "--include-archived"], catch_exceptions=False)
    assert "foo" not in without.stdout
    assert "foo" in with_archived.stdout
```

- [x] **Step 4: Test — `--status` filter case-insensitive exact match**

```python
def test_rework_list_status_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")  # In Progress
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")  # Not Started
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--status", "in progress"], catch_exceptions=False)
    assert "foo" in result.stdout
    assert "bar" not in result.stdout
```

- [x] **Step 5: Test — `--track decision` substring-matches `decision → development`**

```python
def test_rework_list_track_substring_matches_transition(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--track", "decision"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "foo" in result.stdout
```

- [x] **Step 6: Test — `--plan` exact parent-slug match**

```python
def test_rework_list_plan_filter(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_phases.md", "2026-04-08-foo-rework-1.md")
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-bar-rework-2.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--plan", "foo"], catch_exceptions=False)
    assert "foo" in result.stdout
    assert "bar" not in result.stdout
```

- [x] **Step 7: Test — `--json` emits valid, non-empty JSON**

```python
def test_rework_list_json_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list", "--json"], catch_exceptions=False)
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1
    assert data[0]["parent_slug"] == "foo"
    assert data[0]["rework_number"] == 1
    assert data[0]["origin_items"] == 3
    assert set(data[0]["by_track"].keys()) == {"development", "operations", "decision"}
```

- [x] **Step 8: Test — malformed file skipped with warn, others listed**

```python
def test_rework_list_skips_malformed_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("VK_REPO_ROOT", str(tmp_path))
    _seed_rework(tmp_path, "rework_with_rows.md", "2026-04-08-foo-rework-1.md")
    (tmp_path / "docs/superpowers/plans/2026-04-08-bar-rework-1.md").write_text(
        "not a plan at all"
    )
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "rework-list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "foo" in result.stdout
    assert "warn" in result.stderr or "skipping" in result.stderr
```

Run `uv run pytest tests/integration/test_plan_rework_list.py -q` — all green.

---

## Phase 6: `self-review` canonical-Track-token lint [agentic]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/42 -->

**Depends on:** Phase 1

### Task 1: Extend `plan_self_review`

**Files:**
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `tests/unit/test_cli.py` or add `tests/integration/test_plan_self_review_track.py`

- [x] **Step 1: Write failing tests for the new lint branch**

Create `tests/integration/test_plan_self_review_track.py`:

```python
"""Track-token lint branch of ``vk plan self-review``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from vk.cli import app

_PLAN_TEMPLATE = """# T

**Spec:** `s.md`
**Status:** Not Started

**Goal:** g.

---

## Phase 1: First [agentic]
**Depends on:** —
**Track:** {track}

### Task 1: Thing

- [ ] **Step 1:** Do it
"""


def _write_plan(tmp_path: Path, track: str) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(_PLAN_TEMPLATE.format(track=track))
    return p


def test_canonical_track_is_silent(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "development")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "non-canonical" not in result.stderr


def test_non_canonical_track_surfaces_as_issue(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "research")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 1
    assert "non-canonical **Track:** value 'research'" in result.stderr


def test_transition_syntax_passes_on_first_word(tmp_path: Path) -> None:
    p = _write_plan(tmp_path, "decision → development")
    runner = CliRunner()
    result = runner.invoke(app, ["plan", "self-review", str(p)], catch_exceptions=False)
    assert result.exit_code == 0
    assert "non-canonical" not in result.stderr
```

Run — expect 2 failures (research case doesn't surface; transition may trip).

- [x] **Step 2: Insert the lint check inside `plan_self_review`**

In `plan_cmd.py`, inside `plan_self_review`, after the phase-tag loop and before the `validate_dag` call:

```python
    _CANONICAL_TRACKS = {"development", "operations", "decision"}
    for phase in plan.phases:
        if phase.track_label is None:
            continue
        first = phase.track_label.strip().split()[0].lower()
        if first not in _CANONICAL_TRACKS:
            issues.append(
                f"Phase {phase.number} has non-canonical **Track:** value "
                f"'{phase.track_label}' (expected development / operations / decision)."
            )
```

Define `_CANONICAL_TRACKS` at module scope (next to the other constants) so it's reused by `plan_rework_add` too — refactor `plan_rework_add` to reference it.

Run the three tests — expect green. Run `uv run pytest -q --no-cov` — full green.

---

## Phase 7: Version bump, SKILL.md, release prep [manual]
<!-- Tracking: https://github.com/derio-net/superpowers-for-vk/issues/43 -->

**Depends on:** Phase 3, Phase 4, Phase 5, Phase 6

Operator-driven final sweep. No new source logic — just the lockstep bump per `CLAUDE.md`'s versioning rule and the user-visible skill-doc update.

### Task 1: Version bump across three source-of-truth files

**Files:**
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Modify: `uv.lock` (auto-generated via `uv sync`)

- [x] **Step 1: Bump `pyproject.toml`**

Set `[project].version = "1.2.0"`.

- [x] **Step 2: Bump `.claude-plugin/plugin.json`**

Set `.version = "1.2.0"`.

- [x] **Step 3: Bump `.claude-plugin/marketplace.json`**

Set `.plugins[0].version = "1.2.0"`.

- [x] **Step 4: Run `uv sync` to refresh `uv.lock`**

```bash
uv sync
```

Expect a single `vk==1.2.0` line changed in `uv.lock`. Commit the lockfile change in the same PR.

- [x] **Step 5: Confirm `vk --version`**

```bash
uv run vk --version
```

Expected stdout: a line containing `1.2.0`. If the CLI has no `--version` flag, verify via `python -c "from importlib.metadata import version; print(version('vk'))"`.

### Task 2: Update `skills/vk-plan/SKILL.md`

**Files:**
- Modify: `skills/vk-plan/SKILL.md`

- [x] **Step 1: Add rework-surface mention under "Procedure" or "Integration"**

Insert a bullet that names the three commands and when to invoke them. Draft:

```markdown
## Rework plans

After a parent plan ships, defer surfaced-but-unrealised items into a
separate rework plan — do not reopen the parent.

- `vk plan rework <parent-plan-path>` scaffolds the rework file.
- `vk plan rework-add <rework-path> --item ... --source ... --track ...`
  appends a row to the Origin table.
- `vk plan rework-list [--include-archived] [--status ...] [--track ...]`
  surfaces open reworks across the repo.

See the spec for the full convention: `docs/superpowers/specs/2026-04-22-vk-plan-rework-design.md`.
```

Placement: insert as a new `## Rework plans` section after the existing procedural body. Keep the frontmatter and existing sections intact.

### Task 3: Full-sweep CI gate + self-review

**Files:** (verification only)

- [x] **Step 1: Run ruff format + check**

```bash
uv run ruff format src/ tests/
uv run ruff check src/ tests/
```

Both clean.

- [x] **Step 2: Run mypy**

```bash
uv run mypy src/
```

Clean.

- [x] **Step 3: Run full pytest**

```bash
uv run pytest -q --no-cov
```

All green.

- [x] **Step 4: Self-review this plan file**

```bash
uv run vk plan self-review docs/superpowers/plans/2026-04-22-vk-plan-rework-command.md
```

Expect the only surviving issues to be structural-clean or already-addressed placeholders (the Goal bullet in the scaffold template uses "TODO" on purpose for operator handoff).

- [x] **Step 5: `--help` smoke test**

```bash
uv run vk plan rework --help
uv run vk plan rework-add --help
uv run vk plan rework-list --help
```

All three produce clean typer output with no stub text.

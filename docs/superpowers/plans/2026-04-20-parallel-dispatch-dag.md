# Parallel Dispatch DAG Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-20-parallel-dispatch-dag-design.md`
**Status:** Not Started

**Goal:** Replace the implicit "Phase N depends on Phase N-1" chain with an author-declared `**Depends on:**` DAG per plan. Unlock safe parallel phase execution while preserving the fail-loud guarantees that were introduced after the Frank hextra incident.

**Architecture:** Phase 1 lands the grammar: `Phase.depends_on` model field, parser + writer support, dispatch emission of per-dep `- Blocked by #N` lines, body-validator relaxation, and structural validators (cycle, forward-ref, self-ref, unknown-ref, grammar) applied only when `**Depends on:**` lines are present. Phase 2 lands the migration tooling and strict enforcement: `vk plan convert --add-deps`, the `missing-line` check for live plans, `vk execute check-deps` reading the declared DAG, the `vk dispatch migrate` refusal guard, skill docs, and the version bump to 1.1.0.

**Tech stack:** Python 3.11+, typer, pyyaml, rich, pytest, typer.testing.CliRunner. Extends existing modules under `src/vk/`; no new dependencies.

---

## Phase 1: Parser, dispatch emission, structural validation [agentic]

### Task 1: `Phase.depends_on` field + parser line extraction

**Files:**
- Modify: `src/vk/plan/models.py`
- Modify: `src/vk/plan/parser.py`
- Test: `tests/unit/test_plan_parser.py`

- [ ] **Step 1: Write failing tests for the parser's `**Depends on:**` extraction**

Append to `tests/unit/test_plan_parser.py`:

```python
class TestDependsOnParsing:
    """Parser extracts **Depends on:** lines into Phase.depends_on."""

    def _plan_with_phase(self, extra_line: str) -> str:
        return (
            "# T\n\n**Spec:** `specs/x.md`\n**Status:** Not Started\n\n"
            "**Goal:** Test.\n\n---\n\n"
            "## Phase 1: First [agentic]\n"
            f"{extra_line}"
            "\n### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_emdash_parses_as_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** —\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_none_alias_parses_as_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** None\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_single_phase_ref(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** Phase 3\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == (3,)

    def test_multiple_phase_refs(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** Phase 1, Phase 2\n"))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == (1, 2)

    def test_absent_line_yields_empty_tuple(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase(""))
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()

    def test_malformed_value_raises_with_phase_number(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._plan_with_phase("**Depends on:** foo, Phase bar\n"))
        with pytest.raises(ValueError, match="Phase 1"):
            parse_plan(p)

    def test_line_after_tracking_comment(self, tmp_path: Path) -> None:
        content = (
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: First [agentic]\n"
            "<!-- Tracking: https://github.com/o/r/issues/10 -->\n"
            "**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(content)
        plan = parse_plan(p)
        assert plan.phases[0].depends_on == ()
        assert plan.phases[0].tracking_url == "https://github.com/o/r/issues/10"
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_plan_parser.py::TestDependsOnParsing -v
```

Expected: all 7 tests FAIL because `depends_on` is not on `Phase` yet and the parser does not extract the line.

- [ ] **Step 3: Add `depends_on` to the `Phase` dataclass**

In `src/vk/plan/models.py`, add a `depends_on` field to `Phase`:

```python
@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["manual", "agentic"]
    depends_on: tuple[int, ...]
    tasks: tuple[Task, ...]
    tracking_url: str | None
```

Field order matters for `__init__`. Place `depends_on` after `tag` and before `tasks`. Update any constructor callers in the codebase (grep for `Phase(` to find them — likely only `parser.py` and test fixtures).

- [ ] **Step 4: Implement the parser extraction**

In `src/vk/plan/parser.py`, where phase blocks are parsed, extract the `**Depends on:**` line when present and compute `depends_on`:

```python
_DEPENDS_ON_RE = re.compile(
    r"^\*\*Depends on:\*\*\s+(.+?)\s*$",
    re.MULTILINE,
)
_PHASE_REF_RE = re.compile(r"^Phase\s+(\d+)$")

def _parse_depends_on(phase_body: str, phase_number: int) -> tuple[int, ...]:
    """Return the tuple of dependency phase numbers, or () if the line is absent."""
    match = _DEPENDS_ON_RE.search(phase_body)
    if match is None:
        return ()
    raw = match.group(1).strip()
    if raw in ("—", "None"):
        return ()
    parts = [p.strip() for p in raw.split(",")]
    deps: list[int] = []
    for part in parts:
        ref_match = _PHASE_REF_RE.match(part)
        if ref_match is None:
            raise ValueError(
                f"Phase {phase_number}: could not parse dependency list "
                f"'{raw}'. Expected 'Phase <int>' refs."
            )
        deps.append(int(ref_match.group(1)))
    return tuple(deps)
```

Search scope for `_DEPENDS_ON_RE` is the slice between the phase header (plus any `<!-- Tracking: -->` comment) and the first `### Task` header or the next `## Phase` header. Use the same boundary logic already in the parser for task extraction.

Call `_parse_depends_on(phase_body, phase_number)` during Phase construction and pass the result to the `depends_on=` keyword argument.

- [ ] **Step 5: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_plan_parser.py::TestDependsOnParsing -v
```

Expected: all 7 tests PASS. Also re-run the full parser suite to catch regressions:

```
uv run pytest tests/unit/test_plan_parser.py -v
```

Expected: all pre-existing parser tests continue to pass (any fixtures without `**Depends on:**` parse with `depends_on=()`).

- [ ] **Step 6: Quality gates**

```
uv run ruff check src/vk/plan/models.py src/vk/plan/parser.py tests/unit/test_plan_parser.py
uv run ruff format --check src/vk/plan/models.py src/vk/plan/parser.py tests/unit/test_plan_parser.py
uv run mypy src/vk/plan/models.py src/vk/plan/parser.py
```

Expected: PASS on all three.

- [ ] **Step 7: Commit**

```
git add src/vk/plan/models.py src/vk/plan/parser.py tests/unit/test_plan_parser.py
git commit -m "feat(plan): parse **Depends on:** lines into Phase.depends_on"
```

### Task 2: Writer round-trip for `**Depends on:**`

**Files:**
- Modify: `src/vk/plan/writer.py`
- Test: `tests/unit/test_plan_writer.py`

- [ ] **Step 1: Write a failing round-trip test**

Append to `tests/unit/test_plan_writer.py`:

```python
class TestDependsOnRoundTrip:
    """Writer emits **Depends on:** so that parse -> write -> parse is lossless."""

    def _build_plan_text(self) -> str:
        return (
            "# Fan In Plan\n\n"
            "**Spec:** `specs/x.md`\n"
            "**Status:** Not Started\n\n"
            "**Goal:** Test.\n\n---\n\n"
            "## Phase 1: Root A [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n\n"
            "## Phase 2: Root B [agentic]\n"
            "**Depends on:** —\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n\n"
            "## Phase 3: Fan in [agentic]\n"
            "**Depends on:** Phase 1, Phase 2\n\n"
            "### Task 1: Noop\n\n- [ ] **Step 1:** Nothing\n"
        )

    def test_round_trip_preserves_depends_on(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text(self._build_plan_text())
        plan = parse_plan(src)

        dst = tmp_path / "dst.md"
        write_plan(plan, dst)

        reparsed = parse_plan(dst)
        assert tuple(p.depends_on for p in reparsed.phases) == ((), (), (1, 2))

    def test_write_emits_emdash_for_roots(self, tmp_path: Path) -> None:
        src = tmp_path / "src.md"
        src.write_text(self._build_plan_text())
        plan = parse_plan(src)

        dst = tmp_path / "dst.md"
        write_plan(plan, dst)

        text = dst.read_text()
        assert "**Depends on:** —" in text
        assert "**Depends on:** Phase 1, Phase 2" in text
```

Ensure the test imports `parse_plan` and `write_plan` at the top.

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_plan_writer.py::TestDependsOnRoundTrip -v
```

Expected: FAIL — writer does not emit the line yet.

- [ ] **Step 3: Emit `**Depends on:**` in the writer**

In `src/vk/plan/writer.py`, after the phase header and any tracking comment are written, emit the `**Depends on:**` line:

```python
def _format_depends_on(phase: Phase) -> str:
    if not phase.depends_on:
        return "**Depends on:** —"
    refs = ", ".join(f"Phase {n}" for n in phase.depends_on)
    return f"**Depends on:** {refs}"
```

Invoke `_format_depends_on(phase)` in the phase-block writer and append it directly after the tracking comment (or directly after the header line if no tracking comment), followed by a blank line and then the task blocks. Preserve existing spacing around task blocks.

- [ ] **Step 4: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_plan_writer.py -v
```

Expected: PASS — both new tests plus all pre-existing writer tests.

- [ ] **Step 5: Quality gates**

```
uv run ruff check src/vk/plan/writer.py tests/unit/test_plan_writer.py
uv run ruff format --check src/vk/plan/writer.py tests/unit/test_plan_writer.py
uv run mypy src/vk/plan/writer.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add src/vk/plan/writer.py tests/unit/test_plan_writer.py
git commit -m "feat(plan): writer emits **Depends on:** for phased plans"
```

### Task 3: Dispatch emits one `- Blocked by #N` per declared dep + `phased-dag.md` fixture

**Files:**
- Create: `tests/fixtures/plans/phased-dag.md`
- Modify: `src/vk/commands/dispatch_cmd.py`
- Test: `tests/unit/test_dispatch_body.py`
- Test: `tests/integration/test_dispatch.py`

- [ ] **Step 1: Create the fan-in/fan-out fixture**

Create `tests/fixtures/plans/phased-dag.md`:

```
# Parallel DAG Fixture

**Spec:** `docs/superpowers/specs/2026-04-20-parallel-dispatch-dag-design.md`
**Status:** Not Started

**Goal:** Exercise fan-in, fan-out, and multi-root shapes for dispatch body tests.

---

## Phase 1: Scaffold [agentic]
**Depends on:** —

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 2: Parallel init [agentic]
**Depends on:** —

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 3: Consumer A [agentic]
**Depends on:** Phase 1

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 4: Consumer B [agentic]
**Depends on:** Phase 2

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 5: Fan in [agentic]
**Depends on:** Phase 3, Phase 4

### Task 1: Noop

- [ ] **Step 1:** Nothing
```

- [ ] **Step 2: Write failing unit tests for multi-blocker body emission**

Append to `tests/unit/test_dispatch_body.py`:

```python
class TestMultiBlockerBody:
    """_build_issue_body emits one '- Blocked by #N' per declared dep."""

    def test_empty_blocker_nums_emits_none(self) -> None:
        phase = Phase(
            number=1, title="Scaffold", tag="agentic",
            depends_on=(), tasks=(), tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase, plan_path=Path("plans/x.md"), target_repo="o/r",
            blocker_nums=(), total_phases=3, spec="s.md", goal="g",
        )
        assert "None — no blocking phases." in body
        assert "- Blocked by #" not in body

    def test_single_blocker_emits_one_line(self) -> None:
        phase = Phase(
            number=2, title="Second", tag="agentic",
            depends_on=(1,), tasks=(), tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase, plan_path=Path("plans/x.md"), target_repo="o/r",
            blocker_nums=(101,), total_phases=3, spec="s.md", goal="g",
        )
        assert body.count("- Blocked by #") == 1
        assert "- Blocked by #101" in body

    def test_multi_blocker_emits_lines_in_declared_order(self) -> None:
        phase = Phase(
            number=5, title="Fan in", tag="agentic",
            depends_on=(3, 4), tasks=(), tracking_url=None,
        )
        body = _build_issue_body(
            phase=phase, plan_path=Path("plans/x.md"), target_repo="o/r",
            blocker_nums=(203, 204), total_phases=5, spec="s.md", goal="g",
        )
        idx_a = body.index("- Blocked by #203")
        idx_b = body.index("- Blocked by #204")
        assert idx_a < idx_b
```

- [ ] **Step 3: Write a failing integration test for a fan-in dispatch**

Append to `tests/integration/test_dispatch.py`:

```python
class TestDispatchFanIn:
    """Multi-blocker bodies round-trip via dispatch --yes."""

    @patch("vk.commands.dispatch_cmd.gh")
    def test_fan_in_body_contains_both_blockers(
        self, mock_gh: MagicMock, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        import shutil
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-dag.md"
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-dag.md"
        shutil.copy(src, plan)

        urls = [
            "https://github.com/derio-net/test-repo/issues/101",
            "https://github.com/derio-net/test-repo/issues/102",
            "https://github.com/derio-net/test-repo/issues/103",
            "https://github.com/derio-net/test-repo/issues/104",
            "https://github.com/derio-net/test-repo/issues/105",
        ]
        mock_gh.create_issue.side_effect = urls
        mock_gh.extract_issue_number.side_effect = [101, 102, 103, 104, 105]
        mock_gh.edit_issue_body.return_value = None
        mock_gh.GhError = __import__("vk.gh", fromlist=["GhError"]).GhError

        result = runner.invoke(
            app, ["dispatch", "create", str(plan), "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0, result.stdout

        # Phase 5 was the third create call that produced a multi-dep body.
        phase5_body = [c.kwargs["body"] for c in mock_gh.create_issue.call_args_list][4]
        assert "- Blocked by #103" in phase5_body
        assert "- Blocked by #104" in phase5_body
        # Phase 1 (root) should emit the None literal.
        phase1_body = [c.kwargs["body"] for c in mock_gh.create_issue.call_args_list][0]
        assert "None — no blocking phases." in phase1_body
```

- [ ] **Step 4: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_dispatch_body.py::TestMultiBlockerBody tests/integration/test_dispatch.py::TestDispatchFanIn -v
```

Expected: FAIL — signature of `_build_issue_body` still takes `prev_num: int | None` and the create-loop still computes `prev_num = phase_to_issue.get(phase.number - 1)`.

- [ ] **Step 5: Refactor `_build_issue_body` to accept `blocker_nums`**

In `src/vk/commands/dispatch_cmd.py`, replace the `prev_num` parameter with `blocker_nums: tuple[int, ...]`:

```python
def _build_issue_body(
    phase: Phase,
    plan_path: Path,
    target_repo: str,
    blocker_nums: tuple[int, ...],
    total_phases: int,
    spec: str,
    goal: str,
) -> str:
    if not blocker_nums:
        deps_block = "None — no blocking phases."
    else:
        deps_block = "\n".join(f"- Blocked by #{n}" for n in blocker_nums)

    tracking_block = (
        f"📦 Repo:   {target_repo}\n"
        f"📋 Plan:   {plan_path}\n"
        f"📐 Spec:   {spec}\n"
        f"🎯 Phase:  {phase.number}/{total_phases} — {phase.title} [{phase.tag}]\n"
        f"🔗 Issue:  (assigned on create)\n"
        f"\n"
        f"**Goal (from plan):** {goal}\n"
    )

    return (
        f"{tracking_block}"
        f"\n---\n\n"
        f"## Instruction\n\n"
        f"Use superpowers-for-vk:vk-execute to implement Phase {phase.number} of this plan.\n\n"
        f"## Workspace\n\n"
        f"Repos: {target_repo}\n\n"
        f"## Dependencies\n\n"
        f"{deps_block}\n"
    )
```

- [ ] **Step 6: Update `dispatch_create` to compute `blocker_nums` from `depends_on`**

In `src/vk/commands/dispatch_cmd.py::dispatch_create`, replace the existing `prev_num = phase_to_issue.get(phase.number - 1)` line with:

```python
try:
    blocker_nums = tuple(phase_to_issue[dep] for dep in phase.depends_on)
except KeyError as exc:
    err_console.print(
        f"Error: Phase {phase.number} depends on Phase {exc.args[0]}, "
        f"but that phase has no dispatched Issue. "
        f"Run 'vk dispatch create <plan>' again — an earlier phase may have failed."
    )
    raise typer.Exit(3)
```

Update the `_build_issue_body(...)` call to pass `blocker_nums=blocker_nums` instead of `prev_num=prev_num`.

- [ ] **Step 7: Update `migrate` to use the same signature**

In `src/vk/commands/dispatch_cmd.py::migrate`, the block that computes `prev_num` from `tracked[phase.number - 1]` becomes:

```python
try:
    blocker_nums = tuple(
        gh.extract_issue_number(tracked[dep]) for dep in phase.depends_on
    )
except KeyError as exc:
    err_console.print(
        f"Error: Phase {phase.number} depends on Phase {exc.args[0]}, "
        f"but that phase has no tracking comment. Cannot migrate safely."
    )
    raise typer.Exit(2)
```

Update the `_build_issue_body(...)` call in `migrate` to pass `blocker_nums=blocker_nums`.

- [ ] **Step 8: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_dispatch_body.py tests/integration/test_dispatch.py -v
```

Expected: PASS — new tests plus all pre-existing dispatch tests (they construct `Phase` fixtures; check that each one now passes `depends_on=...`).

- [ ] **Step 9: Quality gates**

```
uv run ruff check src/vk/commands/dispatch_cmd.py tests/unit/test_dispatch_body.py tests/integration/test_dispatch.py
uv run ruff format --check src/vk/commands/dispatch_cmd.py tests/unit/test_dispatch_body.py tests/integration/test_dispatch.py
uv run mypy src/vk/commands/dispatch_cmd.py
```

Expected: PASS.

- [ ] **Step 10: Commit**

```
git add src/vk/commands/dispatch_cmd.py tests/unit/test_dispatch_body.py tests/integration/test_dispatch.py tests/fixtures/plans/phased-dag.md
git commit -m "feat(dispatch): emit one '- Blocked by #N' per declared dep"
```

### Task 4: Body validator relaxation

**Files:**
- Modify: `src/vk/commands/dispatch_body_validator.py`
- Test: `tests/unit/test_dispatch_body_validator.py`

- [ ] **Step 1: Write failing tests for the relaxed validator**

Append to `tests/unit/test_dispatch_body_validator.py`:

```python
class TestRelaxedValidator:
    """Validator accepts None literal or >=1 '- Blocked by #N' lines."""

    def _body_with_deps(self, deps_block: str) -> str:
        return (
            "📦 Repo: o/r\n\n---\n\n"
            "## Instruction\n\nDo stuff.\n\n"
            "## Workspace\n\nRepos: o/r\n\n"
            "## Dependencies\n\n"
            f"{deps_block}\n"
        )

    def test_accepts_none_literal_for_root_phase(self) -> None:
        validate_issue_body(self._body_with_deps("None — no blocking phases."), phase_number=1)

    def test_accepts_single_blocker_for_non_root(self) -> None:
        validate_issue_body(self._body_with_deps("- Blocked by #42"), phase_number=2)

    def test_accepts_multiple_blockers(self) -> None:
        validate_issue_body(
            self._body_with_deps("- Blocked by #42\n- Blocked by #43"), phase_number=3,
        )

    def test_rejects_missing_dependencies_section(self) -> None:
        body = "## Instruction\n\nDo.\n\n## Workspace\n\nRepos: o/r\n\n"
        with pytest.raises(BodyValidationError, match="Dependencies"):
            validate_issue_body(body, phase_number=2)

    def test_rejects_undashed_blocker_line(self) -> None:
        body = self._body_with_deps("Blocked by #42")
        with pytest.raises(BodyValidationError, match="dash-prefixed"):
            validate_issue_body(body, phase_number=2)

    def test_rejects_empty_dependencies_section_for_non_root(self) -> None:
        body = self._body_with_deps("")
        with pytest.raises(BodyValidationError):
            validate_issue_body(body, phase_number=2)
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_dispatch_body_validator.py::TestRelaxedValidator -v
```

Expected: FAIL on the `None` literal test (today's validator rejects it for phase > 0).

- [ ] **Step 3: Relax the validator**

Replace the contents of `src/vk/commands/dispatch_body_validator.py::validate_issue_body` with logic that accepts either form:

```python
_REQUIRED_SECTIONS = ("## Instruction", "## Workspace", "## Dependencies")
_NONE_LITERAL = "None — no blocking phases."


def validate_issue_body(body: str, phase_number: int) -> None:
    for section in _REQUIRED_SECTIONS:
        if section not in body:
            raise BodyValidationError(
                f"Generated body missing required section '{section}'. "
                f"The VK Issue Bridge will fail to parse this Issue. "
                f"Fix: investigate _build_issue_body in dispatch_cmd.py."
            )

    deps_idx = body.index("## Dependencies")
    deps_block = body[deps_idx:].split("\n\n", 2)[1] if "\n\n" in body[deps_idx:] else ""
    has_none = _NONE_LITERAL in deps_block
    dash_lines = [ln for ln in deps_block.splitlines() if ln.startswith("- Blocked by #")]
    undashed = [ln for ln in deps_block.splitlines()
                if ln.strip().startswith("Blocked by #") and not ln.startswith("- Blocked by #")]

    if undashed:
        raise BodyValidationError(
            f"Phase {phase_number}: '## Dependencies' contains a non-dash-prefixed "
            f"'Blocked by #N' line. The bridge's dep-gating regex requires the dash. "
            f"Fix: investigate _build_issue_body in dispatch_cmd.py."
        )

    if has_none:
        return

    if not dash_lines:
        raise BodyValidationError(
            f"Phase {phase_number}: '## Dependencies' is empty or malformed. "
            f"It must contain either 'None — no blocking phases.' "
            f"or one or more '- Blocked by #N' lines."
        )
```

- [ ] **Step 4: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_dispatch_body_validator.py -v
```

Expected: PASS — all 6 new tests plus all pre-existing validator tests.

- [ ] **Step 5: Quality gates**

```
uv run ruff check src/vk/commands/dispatch_body_validator.py tests/unit/test_dispatch_body_validator.py
uv run ruff format --check src/vk/commands/dispatch_body_validator.py tests/unit/test_dispatch_body_validator.py
uv run mypy src/vk/commands/dispatch_body_validator.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add src/vk/commands/dispatch_body_validator.py tests/unit/test_dispatch_body_validator.py
git commit -m "feat(dispatch): body validator accepts None literal or >=1 blocker lines"
```

### Task 5: Structural DAG validators in self-review and dispatch --dry-run

**Files:**
- Create: `src/vk/plan/validate.py`
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `src/vk/commands/dispatch_cmd.py`
- Test: `tests/unit/test_plan_validate.py`
- Test: `tests/unit/test_cli.py`

Scope: cycle, forward-ref, self-ref, unknown-ref, grammar-via-parser. **Missing-line is deferred to Phase 2** so pre-DAG plans don't break self-review in the Phase 1 window.

- [ ] **Step 1: Write failing tests for `validate_dag`**

Create `tests/unit/test_plan_validate.py`:

```python
from __future__ import annotations

import pytest

from vk.plan.models import Phase, Plan, PlanFormat
from vk.plan.validate import DagValidationError, validate_dag


def _phase(number: int, depends_on: tuple[int, ...]) -> Phase:
    return Phase(
        number=number, title=f"Phase {number}", tag="agentic",
        depends_on=depends_on, tasks=(), tracking_url=None,
    )


def _plan(phases: tuple[Phase, ...]) -> Plan:
    return Plan(
        title="T", spec="s.md", status="Not Started", goal="g",
        format=PlanFormat.PHASED, phases=phases, tasks=(),
    )


class TestValidateDag:
    def test_root_only_plan_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()),)))

    def test_linear_plan_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()), _phase(2, (1,)), _phase(3, (2,)))))

    def test_fan_in_passes(self) -> None:
        validate_dag(_plan((_phase(1, ()), _phase(2, ()), _phase(3, (1, 2)))))

    def test_self_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="Phase 2 depends on itself"):
            validate_dag(_plan((_phase(1, ()), _phase(2, (2,)))))

    def test_forward_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="forward reference"):
            validate_dag(_plan((_phase(1, (2,)), _phase(2, ()))))

    def test_unknown_reference_fails(self) -> None:
        with pytest.raises(DagValidationError, match="does not exist"):
            validate_dag(_plan((_phase(1, ()), _phase(2, (99,)))))

    def test_absent_depends_on_is_ignored_in_phase_1_window(self) -> None:
        """Pre-DAG plans (no **Depends on:** anywhere) pass structural validation."""
        validate_dag(_plan((_phase(1, ()), _phase(2, ()), _phase(3, ()))))
```

Also append to `tests/unit/test_cli.py`:

```python
class TestSelfReviewDagChecks:
    def test_self_review_rejects_cycle(self, tmp_path: Path) -> None:
        # Cycle can only arise from forward-ref under backward-only rule,
        # so we construct a forward reference and confirm the specific message.
        plan = tmp_path / "p.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** Phase 2\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0
        assert "forward reference" in (result.stdout + (result.stderr or ""))

    def test_self_review_rejects_unknown_ref(self, tmp_path: Path) -> None:
        plan = tmp_path / "p.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** Phase 99\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["plan", "self-review", str(plan)])
        assert result.exit_code != 0
        assert "does not exist" in (result.stdout + (result.stderr or ""))
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_plan_validate.py tests/unit/test_cli.py::TestSelfReviewDagChecks -v
```

Expected: FAIL — `validate_dag` does not exist and self-review doesn't call it.

- [ ] **Step 3: Implement `validate_dag`**

Create `src/vk/plan/validate.py`:

```python
"""Structural validation for phase dependency declarations."""

from __future__ import annotations

from vk.plan.models import Plan


class DagValidationError(ValueError):
    """Raised when a plan's declared DAG is structurally invalid."""


def validate_dag(plan: Plan) -> None:
    """Check cycle, forward-ref, self-ref, unknown-ref. Skip missing-line check.

    Backward-only deps (depends_on[i] < i) make cycles impossible unless a
    forward reference is present; checking forward-ref is the cycle check.
    """
    known = {p.number for p in plan.phases}
    for phase in plan.phases:
        for dep in phase.depends_on:
            if dep == phase.number:
                raise DagValidationError(
                    f"Phase {phase.number} depends on itself."
                )
            if dep not in known:
                raise DagValidationError(
                    f"Phase {phase.number} depends on Phase {dep}, "
                    f"which does not exist in this plan."
                )
            if dep >= phase.number:
                raise DagValidationError(
                    f"Phase {phase.number} depends on Phase {dep} — "
                    f"forward reference; only backward deps are permitted."
                )
```

- [ ] **Step 4: Wire `validate_dag` into `vk plan self-review`**

In `src/vk/commands/plan_cmd.py::self_review`, after the plan parses successfully, call `validate_dag(plan)` and map `DagValidationError` to a user-facing error with `typer.Exit(1)`.

```python
from vk.plan.validate import DagValidationError, validate_dag

# ...inside self_review, after parse_plan():
try:
    validate_dag(plan)
except DagValidationError as exc:
    err_console.print(f"Error: {exc}")
    raise typer.Exit(1)
```

- [ ] **Step 5: Wire `validate_dag` into `vk dispatch --dry-run`**

In `src/vk/commands/dispatch_cmd.py::dispatch_create`, after `_parse_and_validate(plan_path)` returns the `plan`, and before building any Issue body, call `validate_dag(plan)` with the same error mapping. Place it under the existing gate check so refusal reasons surface in dependency order: gate → parse → DAG validation.

- [ ] **Step 6: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_plan_validate.py tests/unit/test_cli.py -v
```

Expected: PASS — structural validator tests + self-review CLI tests + all pre-existing tests.

- [ ] **Step 7: Quality gates**

```
uv run ruff check src/vk/plan/validate.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py tests/unit/test_cli.py
uv run ruff format --check src/vk/plan/validate.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py tests/unit/test_cli.py
uv run mypy src/vk/plan/validate.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```
git add src/vk/plan/validate.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py tests/unit/test_cli.py
git commit -m "feat(plan): structural DAG validator in self-review and dispatch --dry-run"
```

### Phase 1 exit

Run full quality gates before opening the Phase 1 PR:

```
uv run pytest -q --no-cov
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
```

All must PASS. Open the PR with title `feat: parallel dispatch DAG — grammar, parser, validator` and body referencing Phase 1 of this plan.

---

## Phase 2: Migration tooling, strict enforcement, execute, docs, version bump [agentic]

### Task 1: `vk plan convert --add-deps` + `phased-no-deps.md` fixture

**Files:**
- Create: `tests/fixtures/plans/phased-no-deps.md`
- Modify: `src/vk/plan/convert.py`
- Modify: `src/vk/commands/plan_cmd.py`
- Test: `tests/unit/test_plan_convert.py`
- Test: `tests/integration/test_convert.py`

- [ ] **Step 1: Create the no-deps fixture**

Create `tests/fixtures/plans/phased-no-deps.md`:

```
# Legacy Linear Plan

**Spec:** `specs/x.md`
**Status:** Not Started

**Goal:** Simulates a pre-DAG plan that needs migration.

---

## Phase 1: Alpha [agentic]

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 2: Beta [agentic]

### Task 1: Noop

- [ ] **Step 1:** Nothing

## Phase 3: Gamma [agentic]

### Task 1: Noop

- [ ] **Step 1:** Nothing
```

- [ ] **Step 2: Write failing unit tests**

Append to `tests/unit/test_plan_convert.py`:

```python
class TestAddDeps:
    def test_add_deps_on_linear_plan(self, tmp_path: Path) -> None:
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        dst = tmp_path / "p.md"
        dst.write_text(src.read_text())
        add_deps(dst)
        text = dst.read_text()
        assert "## Phase 1: Alpha [agentic]\n**Depends on:** —" in text
        assert "## Phase 2: Beta [agentic]\n**Depends on:** Phase 1" in text
        assert "## Phase 3: Gamma [agentic]\n**Depends on:** Phase 2" in text

    def test_add_deps_is_idempotent(self, tmp_path: Path) -> None:
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        dst = tmp_path / "p.md"
        dst.write_text(src.read_text())
        add_deps(dst)
        first = dst.read_text()
        add_deps(dst)
        second = dst.read_text()
        assert first == second

    def test_add_deps_refuses_mixed_plan(self, tmp_path: Path) -> None:
        dst = tmp_path / "p.md"
        dst.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        with pytest.raises(MixedPlanError, match="declare both or neither"):
            add_deps(dst)
```

- [ ] **Step 3: Write a failing integration test**

Append to `tests/integration/test_convert.py`:

```python
class TestAddDepsCli:
    def test_add_deps_via_cli_modifies_file_and_commits(
        self, tmp_repo: Path
    ) -> None:
        import shutil
        src = Path(__file__).parent.parent / "fixtures" / "plans" / "phased-no-deps.md"
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-legacy.md"
        shutil.copy(src, plan)

        result = runner.invoke(
            app, ["plan", "convert", str(plan), "--add-deps", "--yes"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 0, result.stdout

        text = plan.read_text()
        assert "**Depends on:** —" in text
        assert "**Depends on:** Phase 1" in text
```

- [ ] **Step 4: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_plan_convert.py::TestAddDeps tests/integration/test_convert.py::TestAddDepsCli -v
```

Expected: FAIL — `add_deps` and `MixedPlanError` are not defined; `--add-deps` flag is not wired.

- [ ] **Step 5: Implement `add_deps` in `convert.py`**

Add to `src/vk/plan/convert.py`:

```python
class MixedPlanError(ValueError):
    """Raised when some phases have **Depends on:** and others do not."""


_DEPENDS_LINE_RE = re.compile(r"^\*\*Depends on:\*\*", re.MULTILINE)
_PHASE_HEADER_RE = re.compile(r"^## Phase (\d+):.*\[(manual|agentic)\]\s*$", re.MULTILINE)


def add_deps(plan_path: Path) -> None:
    """Migrate a phased plan by adding **Depends on:** lines.

    Phase 1 gets '—'; phase N (N>=2) gets 'Phase {N-1}'. Idempotent: phases
    that already have the line are left alone. If some phases have the line
    and others do not, raise MixedPlanError without writing.
    """
    text = plan_path.read_text()
    headers = list(_PHASE_HEADER_RE.finditer(text))
    if not headers:
        return  # nothing to do; not a phased plan

    # Determine which phases already have the line.
    slices: list[tuple[int, int]] = []
    for i, match in enumerate(headers):
        end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        slices.append((match.end(), end))
    has_line = [bool(_DEPENDS_LINE_RE.search(text[s:e])) for s, e in slices]

    if any(has_line) and not all(has_line):
        offenders_with = [str(int(h.group(1))) for h, flag in zip(headers, has_line, strict=True) if flag]
        offenders_without = [str(int(h.group(1))) for h, flag in zip(headers, has_line, strict=True) if not flag]
        raise MixedPlanError(
            f"Phases {', '.join(offenders_with)} have **Depends on:** but phases "
            f"{', '.join(offenders_without)} do not. Declare both or neither — "
            f"auto-inference is disabled."
        )
    if all(has_line):
        return  # idempotent no-op

    # Insert the line immediately after the header (skipping any tracking comment).
    new_parts: list[str] = []
    cursor = 0
    for i, match in enumerate(headers):
        phase_num = int(match.group(1))
        dep_line = "**Depends on:** —" if phase_num == 1 else f"**Depends on:** Phase {phase_num - 1}"
        header_end = match.end()
        # Look for a tracking comment immediately after the header.
        tail = text[header_end:slices[i][1]]
        tail_lines = tail.split("\n")
        insert_at = header_end
        if len(tail_lines) >= 2 and tail_lines[1].startswith("<!-- Tracking:"):
            insert_at = header_end + len("\n" + tail_lines[1])

        new_parts.append(text[cursor:insert_at])
        new_parts.append(f"\n{dep_line}")
        cursor = insert_at
    new_parts.append(text[cursor:])
    plan_path.write_text("".join(new_parts))
```

- [ ] **Step 6: Wire the `--add-deps` flag in `plan_cmd.py`**

In `src/vk/commands/plan_cmd.py`, extend the existing `convert` subcommand with the `--add-deps` option. Make it mutually exclusive with the existing `--single-phase` / `--one-per-task` / `--group-by-tag` flags (so `convert <plan> --add-deps --yes` works standalone). The `--add-deps` branch honours `resolve_action(dry_run, yes)`, calls `add_deps(plan_path)`, and on `--yes` also runs:

```python
subprocess.run(["git", "add", str(plan_path)], check=True, cwd=repo_root)
subprocess.run(
    ["git", "commit", "-m", "chore(plan): add **Depends on:** lines (migration)"],
    check=True, cwd=repo_root,
)
```

On `--dry-run`, print the diff (use `difflib.unified_diff` on original vs would-be-written text) and exit 0 without writing.

- [ ] **Step 7: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_plan_convert.py tests/integration/test_convert.py -v
```

Expected: PASS.

- [ ] **Step 8: Quality gates**

```
uv run ruff check src/vk/plan/convert.py src/vk/commands/plan_cmd.py tests/unit/test_plan_convert.py tests/integration/test_convert.py
uv run ruff format --check src/vk/plan/convert.py src/vk/commands/plan_cmd.py tests/unit/test_plan_convert.py tests/integration/test_convert.py
uv run mypy src/vk/plan/convert.py src/vk/commands/plan_cmd.py
```

Expected: PASS.

- [ ] **Step 9: Commit**

```
git add src/vk/plan/convert.py src/vk/commands/plan_cmd.py tests/unit/test_plan_convert.py tests/integration/test_convert.py tests/fixtures/plans/phased-no-deps.md
git commit -m "feat(plan): vk plan convert --add-deps migration mode"
```

### Task 2: Strict missing-line enforcement (live plans only)

**Files:**
- Modify: `src/vk/plan/validate.py`
- Modify: `src/vk/commands/plan_cmd.py`
- Modify: `src/vk/commands/dispatch_cmd.py`
- Test: `tests/unit/test_plan_validate.py`
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_plan_validate.py`:

```python
class TestMissingLineEnforcement:
    def test_missing_line_on_non_root_live_plan_fails(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        with pytest.raises(DagValidationError, match="has no \\*\\*Depends on:\\*\\* line"):
            validate_dag(plan, plan_path=plan_path)

    def test_missing_line_on_archived_plan_is_allowed(self, tmp_path: Path) -> None:
        plan_path = tmp_path / "archived-plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Complete\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        validate_dag(plan, plan_path=plan_path)

    def test_root_phase_missing_line_also_fails_in_live(self, tmp_path: Path) -> None:
        """Root phases MUST declare '**Depends on:** —' explicitly in live plans."""
        plan_path = tmp_path / "plans" / "p.md"
        plan_path.parent.mkdir(parents=True)
        plan_path.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** Not Started\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        plan = parse_plan(plan_path)
        with pytest.raises(DagValidationError, match="has no \\*\\*Depends on:\\*\\* line"):
            validate_dag(plan, plan_path=plan_path)
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/unit/test_plan_validate.py::TestMissingLineEnforcement -v
```

Expected: FAIL — `validate_dag` takes no `plan_path` argument yet.

- [ ] **Step 3: Detection — track whether the line was present during parsing**

The parser already returns `depends_on=()` for both `**Depends on:** —` and an absent line. To distinguish them, add a parser-level attribute `phase_has_depends_line: tuple[bool, ...]` to `Plan`. Update the model to include it, and the parser to populate it based on `_DEPENDS_ON_RE.search(phase_body) is not None`.

In `src/vk/plan/models.py`, add:

```python
@dataclass(frozen=True)
class Plan:
    # ... existing fields ...
    phase_has_depends_line: tuple[bool, ...] = ()
```

Default of `()` keeps pre-Phase-2 test fixtures working. Update all `Plan(...)` call sites (grep for `Plan(` in `src/` and `tests/`).

- [ ] **Step 4: Extend `validate_dag` to accept `plan_path` and enforce missing-line for live plans**

In `src/vk/plan/validate.py`:

```python
def validate_dag(plan: Plan, plan_path: Path | None = None) -> None:
    """Check cycle, forward-ref, self-ref, unknown-ref, and (for live plans)
    missing **Depends on:** lines.

    'Live plan' = a plan not under a directory named 'archived-plans'.
    If plan_path is None, the missing-line check is skipped.
    """
    # ...existing cycle/forward/self/unknown checks unchanged...

    if plan_path is None:
        return
    if "archived-plans" in plan_path.parts:
        return

    for phase, present in zip(plan.phases, plan.phase_has_depends_line, strict=True):
        if not present:
            raise DagValidationError(
                f"Phase {phase.number} has no **Depends on:** line. "
                f"Run 'vk plan convert {plan_path} --add-deps --yes' to migrate, "
                f"or declare it manually."
            )
```

- [ ] **Step 5: Update self-review and dispatch --dry-run to pass `plan_path`**

In `src/vk/commands/plan_cmd.py::self_review` and `src/vk/commands/dispatch_cmd.py::dispatch_create`, update the `validate_dag(plan)` call to `validate_dag(plan, plan_path=plan_path_resolved)`.

- [ ] **Step 6: Run the tests to confirm they pass**

```
uv run pytest tests/unit/test_plan_validate.py -v
```

Expected: PASS.

- [ ] **Step 7: Quality gates**

```
uv run ruff check src/vk/plan/validate.py src/vk/plan/models.py src/vk/plan/parser.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py
uv run ruff format --check src/vk/plan/validate.py src/vk/plan/models.py src/vk/plan/parser.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py
uv run mypy src/vk/plan/validate.py src/vk/plan/models.py src/vk/plan/parser.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```
git add src/vk/plan/validate.py src/vk/plan/models.py src/vk/plan/parser.py src/vk/commands/plan_cmd.py src/vk/commands/dispatch_cmd.py tests/unit/test_plan_validate.py
git commit -m "feat(plan): enforce **Depends on:** on live plans; exempt archived-plans"
```

### Task 3: `vk execute check-deps` reads the declared DAG

**Files:**
- Modify: `src/vk/commands/execute_cmd.py`
- Test: `tests/integration/test_plan_execute.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/integration/test_plan_execute.py`:

```python
class TestCheckDepsDag:
    def test_checkdeps_on_phase_depending_on_phase_3_ignores_phase_4(
        self, tmp_repo: Path
    ) -> None:
        """Phase 5 depends on Phase 3 only; check-deps passes even if Phase 4 unchecked."""
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-dag.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** In Progress\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [x] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [x] **Step 1:** s\n\n"
            "## Phase 3: C [agentic]\n**Depends on:** Phase 1\n\n"
            "### Task 1: T\n\n- [x] **Step 1:** s\n\n"
            "## Phase 4: D [agentic]\n**Depends on:** Phase 2\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 5: E [agentic]\n**Depends on:** Phase 3\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "5"])
        assert result.exit_code == 0, result.stdout
        assert "Dependencies satisfied" in result.stdout
        assert "Phase 3" in result.stdout

    def test_checkdeps_fails_when_declared_dep_incomplete(
        self, tmp_repo: Path
    ) -> None:
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-dag.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** In Progress\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n**Depends on:** —\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n**Depends on:** Phase 1\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(app, ["execute", "check-deps", str(plan), "2"])
        assert result.exit_code == 1
        assert "Phase 1" in (result.stdout + (result.stderr or ""))
```

- [ ] **Step 2: Run the tests to confirm they fail**

```
uv run pytest tests/integration/test_plan_execute.py::TestCheckDepsDag -v
```

Expected: FAIL — today's check-deps walks every phase `< target` and refuses due to Phase 4's unchecked step.

- [ ] **Step 3: Rewrite `check_deps`**

Replace the body of `check_deps` in `src/vk/commands/execute_cmd.py`:

```python
@execute_app.command(name="check-deps")
def check_deps(
    plan_path: Path = typer.Argument(..., help="Path to the plan file.", exists=True),
    target: int = typer.Argument(..., help="Phase number."),
) -> None:
    """Check if declared dependencies for a phase are satisfied."""
    plan_path = plan_path.resolve()
    _reject_flat(plan_path)
    plan = parse_plan(plan_path)

    phases_by_num = {p.number: p for p in plan.phases}
    target_phase = phases_by_num.get(target)
    if target_phase is None:
        err_console.print(f"Phase {target} not found in plan.")
        raise typer.Exit(2)

    for dep_num in target_phase.depends_on:
        dep_phase = phases_by_num.get(dep_num)
        if dep_phase is None:
            err_console.print(
                f"Phase {target} declares Phase {dep_num} as a dependency, "
                f"but Phase {dep_num} does not exist."
            )
            raise typer.Exit(1)
        unchecked = sum(1 for t in dep_phase.tasks for s in t.steps if s.state == " ")
        if unchecked > 0:
            err_console.print(
                f"Phase {target} depends on Phase {dep_num}, "
                f"which has {unchecked} unchecked step(s)."
            )
            raise typer.Exit(1)

    dep_list = (
        ", ".join(f"Phase {n}" for n in target_phase.depends_on)
        if target_phase.depends_on else "none (root phase)"
    )
    console.print(f"Dependencies satisfied for Phase {target} (checked: {dep_list}).")
```

- [ ] **Step 4: Run the tests to confirm they pass**

```
uv run pytest tests/integration/test_plan_execute.py -v
```

Expected: PASS.

- [ ] **Step 5: Quality gates**

```
uv run ruff check src/vk/commands/execute_cmd.py tests/integration/test_plan_execute.py
uv run ruff format --check src/vk/commands/execute_cmd.py tests/integration/test_plan_execute.py
uv run mypy src/vk/commands/execute_cmd.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add src/vk/commands/execute_cmd.py tests/integration/test_plan_execute.py
git commit -m "feat(execute): check-deps reads declared DAG instead of N-1 chain"
```

### Task 4: `vk dispatch migrate` refusal guard

**Files:**
- Modify: `src/vk/commands/dispatch_cmd.py`
- Test: `tests/integration/test_dispatch.py`

- [ ] **Step 1: Write a failing integration test**

Append to `tests/integration/test_dispatch.py`:

```python
class TestDispatchMigrateGuard:
    def test_migrate_refuses_pre_dag_plan(
        self, dispatch_config: Path, tmp_repo: Path
    ) -> None:
        plans_dir = tmp_repo / "docs" / "superpowers" / "plans"
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan = plans_dir / "2026-04-20-predag.md"
        plan.write_text(
            "# T\n\n**Spec:** `s.md`\n**Status:** In Progress\n\n**Goal:** g\n\n---\n\n"
            "## Phase 1: A [agentic]\n"
            "<!-- Tracking: https://github.com/derio-net/test-repo/issues/10 -->\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n\n"
            "## Phase 2: B [agentic]\n"
            "<!-- Tracking: https://github.com/derio-net/test-repo/issues/11 -->\n\n"
            "### Task 1: T\n\n- [ ] **Step 1:** s\n"
        )
        result = runner.invoke(
            app, ["dispatch", "migrate", str(plan), "--dry-run"],
            env={"GIT_DIR": str(tmp_repo / ".git")},
        )
        assert result.exit_code == 2
        combined = result.stdout + (result.stderr or "")
        assert "**Depends on:**" in combined
        assert "vk plan convert" in combined
        assert "--add-deps" in combined
```

- [ ] **Step 2: Run the test to confirm it fails**

```
uv run pytest tests/integration/test_dispatch.py::TestDispatchMigrateGuard -v
```

Expected: FAIL — migrate proceeds today regardless of whether `**Depends on:**` lines exist.

- [ ] **Step 3: Implement the guard in `migrate`**

In `src/vk/commands/dispatch_cmd.py::migrate`, after `parse_plan` returns and before the existing `for phase in plan.phases` rewrite loop:

```python
# Guard: refuse to migrate a plan that has dispatched Issues but no
# **Depends on:** declarations. The new dispatch body format requires
# per-phase deps to be declared in the plan file before we rewrite Issues.
if any(tracked) and not all(plan.phase_has_depends_line):
    err_console.print(
        "Error: Plan has dispatched Issues but no **Depends on:** declarations.\n"
        "Migrate the plan file first, then re-run migrate:\n"
        f"  vk plan convert {plan_path_resolved} --add-deps --yes\n"
        f"  vk dispatch migrate {plan_path_resolved} --yes"
    )
    raise typer.Exit(2)
```

(`tracked` is the existing `dict[int, str]` from `_get_already_tracked`; truthiness on it means at least one phase is dispatched.)

- [ ] **Step 4: Run the test to confirm it passes**

```
uv run pytest tests/integration/test_dispatch.py::TestDispatchMigrateGuard -v
```

Expected: PASS.

- [ ] **Step 5: Quality gates**

```
uv run ruff check src/vk/commands/dispatch_cmd.py tests/integration/test_dispatch.py
uv run ruff format --check src/vk/commands/dispatch_cmd.py tests/integration/test_dispatch.py
uv run mypy src/vk/commands/dispatch_cmd.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```
git add src/vk/commands/dispatch_cmd.py tests/integration/test_dispatch.py
git commit -m "feat(dispatch): migrate refuses pre-DAG plans; points at convert --add-deps"
```

### Task 5: Skill docs + version bump 1.1.0

**Files:**
- Modify: `skills/vk-plan/SKILL.md`
- Modify: `skills/vk-dispatch/SKILL.md`
- Modify: `skills/vk-execute/SKILL.md`
- Modify: `pyproject.toml`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`
- Test: `tests/unit/test_version.py` (already exists)

- [ ] **Step 1: Update `skills/vk-plan/SKILL.md`**

Add a new section under the existing "Rules" heading:

```markdown
## Dependency declarations

Every phase in a phased plan declares its blockers on a `**Depends on:**` line
directly under the phase header (after any `<!-- Tracking: -->` comment).

- Root phases: `**Depends on:** —` (em-dash).
- Non-root phases: `**Depends on:** Phase 1, Phase 2` (comma-separated Phase refs).
- Multiple roots are allowed (fan-out / diamond shapes).
- Deps are backward-only: Phase N may only reference Phase < N.

Example:

    ## Phase 3: Fan-in [agentic]
    **Depends on:** Phase 1, Phase 2

To migrate an existing linear plan: `vk plan convert <plan> --add-deps --yes`.
```

- [ ] **Step 2: Update `skills/vk-dispatch/SKILL.md`**

In the Error handling table, change the row for exit code 2 to include the new migrate refusal:

```markdown
| 2 | Plan parse error, flat plan, or legacy plan with no `**Depends on:**` lines | Run `vk plan convert <plan> --add-deps --yes` and retry |
```

- [ ] **Step 3: Update `skills/vk-execute/SKILL.md`**

In the Procedure section, update step 1's description under `check-deps`:

```markdown
1. Check dependencies (reads the phase's declared `**Depends on:**` list):
   ```bash
   vk execute check-deps <plan> <phase>
   ```
```

- [ ] **Step 4: Bump the version in three files**

Update `pyproject.toml`:

```toml
[project]
version = "1.1.0"
```

Update `.claude-plugin/plugin.json`:

```json
{
  "version": "1.1.0",
  ...
}
```

Update `.claude-plugin/marketplace.json`:

```json
{
  "plugins": [
    {
      "version": "1.1.0",
      ...
    }
  ]
}
```

- [ ] **Step 5: Update the version test**

In `tests/unit/test_version.py`, update the expected version to `"1.1.0"`.

- [ ] **Step 6: Resync the lockfile**

```
uv sync
```

Expected: writes updated `uv.lock` with `vk==1.1.0`.

- [ ] **Step 7: Verify the CLI reports the new version**

```
uv run vk --version
```

Expected: prints `vk, version 1.1.0` (or the project's equivalent `--version` output format).

- [ ] **Step 8: Run the full test suite and quality gates**

```
uv run pytest -q --no-cov
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
```

Expected: PASS across the board.

- [ ] **Step 9: Commit**

```
git add skills/ pyproject.toml .claude-plugin/plugin.json .claude-plugin/marketplace.json uv.lock tests/unit/test_version.py
git commit -m "chore: bump to 1.1.0 — DAG grammar, docs, execute+migrate hooks"
```

### Phase 2 exit

Re-run everything one more time and open the Phase 2 PR:

```
uv run pytest -q --no-cov
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run vk --version
```

All must PASS and version must read `1.1.0`. Open the PR with title `feat: parallel dispatch DAG — migration, strict enforcement, version 1.1.0` referencing Phase 2 of this plan.

After merge, run the operational migration against live plans in consumer repos:

```
vk plan convert <plan> --add-deps --yes
```

for every phased plan in `derio-net/*` that pre-dates 1.1.0. If any of those plans already have dispatched Issues, follow with `vk dispatch migrate <plan> --yes`.

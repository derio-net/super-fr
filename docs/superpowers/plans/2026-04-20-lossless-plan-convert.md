# Lossless Plan Convert Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-18-deprecate-flat-plans-design.md`
**Status:** Complete

**Goal:** Make `vk plan convert` preserve 100% of the source plan's content on a flat → phased migration, so the spec's "automatic + review" migration flow actually produces reviewable diffs instead of silently shredding author work.

**Background:** The deprecate-flat-plans spec documents a migration flow that depends on `vk plan convert` being lossless. On first real-world use against kid-laptops plans 7–9 (721 / 824 / 1160 lines respectively), the converter deleted ~85% of each plan's content: step bodies, code blocks, file-mention verbs, and every non-canonical header field. Four distinct bugs conspired; each is addressed in its own phase so the fix is reviewable as a sequence of small regex/model changes rather than one mega-diff. Phases 1–4 shipped together in commit `50d77d2` on branch `fix/plan-convert-content-loss`; this plan is the retroactive record, plus one more phase (5) for the remaining indentation regression.

**Tech Stack:** Python 3.11+, frozen dataclasses for the AST, `re.MULTILINE` regex, `textwrap.dedent` (phase 5), pytest, `uv run --group dev`.

**Architecture:** All four shipped phases change only three files under `src/vk/plan/` (`models.py`, `parser.py`, `writer.py`) plus their propagation in `convert.py`. The model gains three additive fields — `Task.file_mention_verbs`, `Step.label`, `Plan.preamble` — all with defaults to preserve source-compat for existing callers/tests. Phase 5 is parser-only: replace `body.strip()` with a dedent that preserves indentation semantics.

---

## Phase 1: Loose step-header regex tolerates trailing prose [agentic]

**Reason to exist:** The original `_RE_STEP` pattern required the checkbox line to END with `**`, which rejected the natural `**Step N: title** trailing prose.` shape authors use. Every such step was silently dropped — in kid-laptops plan 7, 8 of 9 steps per task disappeared.

### Task 1: Tolerate trailing prose after `**Step N: title**`

**Files:**
- Edit: `src/vk/plan/parser.py`
- Create: `tests/unit/test_plan_loose_format.py`
- Create: `tests/fixtures/plans/flat-loose-steps.md`

- [x] **Step 1: Add failing fixture and test case for loose-format steps.**

  Write `tests/fixtures/plans/flat-loose-steps.md` with a step like `- [ ] **Step 1: Create \`roles/demo/tasks/main.yml\`** documenting the role.` followed by an indented YAML fence. Write `TestLooseStepHeaders::test_all_steps_parsed` asserting `len(task.steps) == 2`. The test MUST fail on the pre-fix parser.

- [x] **Step 2: Loosen `_RE_STEP` to absorb trailing prose into the title.**

  Change the regex from requiring `\*\*\s*$` to allowing `\*\*[ \t]*(.*?)[ \t]*$`. Use `[ \t]*` (not `\s*`) so whitespace never crosses a newline — `\s` eats `\n`, which previously caused the regex to greedily slurp the next body line into group 4. Update `_parse_steps` to merge `group(3) + " " + group(4)` into the step title when `group(4)` is non-empty.

- [x] **Step 3: Verify `test_plan_loose_format.py::TestLooseStepHeaders` passes and all 58 pre-existing plan tests still pass.**

  ```bash
  cd /Users/derio/Docs/projects/DERIO_NET/superpowers-for-vk
  uv run --group dev python -m pytest tests/unit/test_plan_parser.py \
      tests/unit/test_plan_writer.py tests/unit/test_plan_convert.py \
      tests/unit/test_plan_loose_format.py --no-cov -q
  ```

---

## Phase 2: `**Files:**` verb preservation [agentic]

**Reason to exist:** `_RE_FILE_MENTION` captured only the path; the verb (Create / Edit / Test / Delete / Move / Rename / Modify) was discarded. On write, every mention came back as `- Create: \`x\``, which turned lines like `- Test: \`cd roles/foo && molecule test\`` into bogus fake-file `- Create:` entries.

### Task 1: Capture and re-emit the file-mention verb

**Files:**
- Edit: `src/vk/plan/models.py`
- Edit: `src/vk/plan/parser.py`
- Edit: `src/vk/plan/writer.py`
- Edit: `src/vk/plan/convert.py`
- Edit: `tests/unit/test_plan_loose_format.py`

- [x] **Step 1: Add failing round-trip test for verb preservation.**

  In `test_plan_loose_format.py::TestFileMentionVerbRoundTrip::test_verbs_preserved_after_round_trip`, assert both `- Edit: \`playbooks/site.yml\`` and `- Test: \`cd roles/demo && molecule test\`` appear in the re-written plan text.

- [x] **Step 2: Add `file_mention_verbs: tuple[str, ...] = ()` to `Task`.**

  The default-empty tuple keeps every existing `Task(..., files_mentioned=(...))` call-site compiling. An empty `file_mention_verbs` is the backward-compat signal for the writer to fall back to `Create`.

- [x] **Step 3: Promote `_RE_FILE_MENTION` group 1 to capture the verb; update `_parse_files` to return `list[tuple[str, str]]`.**

  The pattern becomes `^- (Create|Edit|Test|Delete|Move|Rename|Modify):\s*\`([^\`]+)\``. `_parse_tasks` splits the pairs into the two parallel tuples when constructing the `Task`.

- [x] **Step 4: Update `_write_tasks` in `writer.py` to zip verbs with paths.**

  `verbs = task.file_mention_verbs; verb = verbs[i] if i < len(verbs) else "Create"` — so programmatically-built tasks without `file_mention_verbs` still render as `Create:`.

- [x] **Step 5: Propagate `file_mention_verbs` through all three converters in `convert.py` (`to_flat`, `to_phased_one_per_task`, `_renumber_tasks`).**

  Without this, the new field is dropped during flat→phased conversion even though the parser filled it in.

- [x] **Step 6: Re-run the full plan test suite and the round-trip test.**

  ```bash
  uv run --group dev python -m pytest tests/unit/test_plan_*.py --no-cov -q
  ```

---

## Phase 3: `Plan.preamble` captures free-form header content [agentic]

**Reason to exist:** The `Plan` AST only had slots for `title`, `spec`, `status`, `goal`. Anything else in the header (`**Architecture:**`, `**Tech Stack:**`, `> **For agentic workers:** ...` blockquote) was parsed to nothing and silently vanished on write.

### Task 1: Add a `preamble` field and wire it through parse/write/convert

**Files:**
- Edit: `src/vk/plan/models.py`
- Edit: `src/vk/plan/parser.py`
- Edit: `src/vk/plan/writer.py`
- Edit: `src/vk/plan/convert.py`
- Edit: `tests/unit/test_plan_loose_format.py`

- [x] **Step 1: Add failing tests for Architecture + Tech Stack survival.**

  `TestPlanHeaderPreamble::test_architecture_survives_round_trip` and `test_tech_stack_survives_round_trip` each read the round-tripped text and assert `**Architecture:**` / `**Tech Stack:**` are present. Also extend the fixture to contain both plus a blockquote.

- [x] **Step 2: Add `preamble: str = ""` as the final field on `Plan`.**

  Default empty keeps all existing `Plan(...)` call-sites valid.

- [x] **Step 3: Implement `_extract_preamble(text)` in `parser.py`.**

  ```python
  _RE_HEADER_STRUCTURED_LINE = re.compile(
      r"^(# .+|\*\*Spec:\*\*.+|\*\*Status:\*\*.+|\*\*Goal:\*\*.+)$",
      re.MULTILINE,
  )
  def _extract_preamble(text: str) -> str:
      divider_idx = text.find("\n---")
      header_block = text[:divider_idx] if divider_idx != -1 else text
      remainder = _RE_HEADER_STRUCTURED_LINE.sub("", header_block)
      remainder = re.sub(r"\n{3,}", "\n\n", remainder)
      return remainder.strip("\n")
  ```

  Strategy: take the text up to the first `\n---`, regex-delete the known structured lines, collapse 3+ blank-line runs to 2 (stitching the gaps left by removed lines), strip outer blank lines. The result is every `**Architecture:**` / `**Tech Stack:**` / blockquote the author wrote, in original order.

- [x] **Step 4: Populate `preamble` in both `Plan` construction sites in `parse_plan`.**

  The same extraction applies to flat and phased plans — call `_extract_preamble(text)` before the format branch.

- [x] **Step 5: Emit the preamble in `_write_header` between `**Goal:**` and the `---` divider.**

  ```python
  if plan.preamble:
      lines.append("")
      lines.append(plan.preamble)
  ```

- [x] **Step 6: Propagate `preamble=plan.preamble` through all four `Plan(...)` constructions in `convert.py`.**

  Same reason as Phase 2 Step 5 — conversion is a new-object path that drops any field the converter doesn't explicitly carry over.

- [x] **Step 7: Confirm on a real kid-laptops plan.**

  ```bash
  cp /path/to/kid-laptops/docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env.md /tmp/plan7-work.md
  uv run --group dev vk plan convert /tmp/plan7-work.md --one-per-task --yes
  head -20 /tmp/plan7-work.md
  ```

  Expected: `**Architecture:**`, `**Tech Stack:**`, and the `> **For agentic workers:**` blockquote are all present between `**Goal:**` and `---`.

---

## Phase 4: Dotted step labels (`Step 0.1`, `Step 1.10`) [agentic]

**Reason to exist:** `_RE_STEP` matched only integer step numbers. Plans using dotted labels (kid-laptops plan 8 uses `Step 0.1` through `Step 0.4`, `Step 1.1` through `Step 1.10`, etc.) parsed as zero steps per task, and the writer emitted empty phase stubs.

### Task 1: Accept dotted step labels while keeping `number: int` for existing callers

**Files:**
- Edit: `src/vk/plan/models.py`
- Edit: `src/vk/plan/parser.py`
- Edit: `src/vk/plan/writer.py`
- Edit: `tests/unit/test_plan_loose_format.py`
- Edit: `tests/fixtures/plans/flat-loose-steps.md`

- [x] **Step 1: Extend fixture with a `Task 2` using `Step 0.1` / `Step 0.2` labels.**

  Append to `flat-loose-steps.md`. Add `TestDottedStepLabels::test_dotted_steps_parsed` asserting `len(task2.steps) == 2`, and `test_dotted_step_label_preserved` asserting `**Step 0.1: ...**` survives round-trip.

- [x] **Step 2: Add `label: str | None = None` to `Step`.**

  Keep `number: int` so every existing `Step(number=1, ...)` test call-site (30+ across `test_models.py`, `test_plan_writer.py`, etc.) keeps compiling. `label` is the raw token; `number` is the integer leading component for ordering/arithmetic.

- [x] **Step 3: Change `_RE_STEP`'s number group to `(\d+(?:\.\d+)*)` and update `_parse_steps` to derive `number` / `label`.**

  ```python
  raw_label = sm.group(2)
  number = int(raw_label.split(".", 1)[0])
  label = raw_label if "." in raw_label else None
  ```

  Dotted labels populate `label`; plain `1`, `2`, `3` keep `label=None` and round-trip as before.

- [x] **Step 4: Update `_write_steps` to prefer `label` when present.**

  ```python
  label = step.label if step.label is not None else str(step.number)
  lines.append(f"- [{step.state}] **Step {label}: {step.title}**")
  ```

- [x] **Step 5: Verify against kid-laptops plan 8.**

  ```bash
  cp /path/to/kid-laptops/.../2026-04-08-kid-laptops-8-remote-desktop.md /tmp/plan8-work.md
  uv run --group dev vk plan convert /tmp/plan8-work.md --one-per-task --yes
  grep -c "^- \[[x -]\] \*\*Step " /tmp/plan8-work.md  # expect 48, not 0
  ```

- [x] **Step 6: Commit phases 1–4 together and run the full suite.**

  ```bash
  git checkout -b fix/plan-convert-content-loss
  git add src/vk/plan/models.py src/vk/plan/parser.py src/vk/plan/writer.py \
          src/vk/plan/convert.py tests/unit/test_plan_loose_format.py \
          tests/fixtures/plans/flat-loose-steps.md
  git commit -m "fix(plan): preserve step bodies, file-mention verbs, preamble, and dotted labels on convert"
  uv run --group dev python -m pytest --no-header -q   # 319 passed, 9 skipped, 79% coverage
  ```

  Shipped as commit `50d77d2` on branch `fix/plan-convert-content-loss`.

---

## Phase 5: Preserve step-body indentation on parse [agentic]

**Reason to exist:** `_parse_steps` does `body = text[start:end].strip()`. `str.strip()` removes whitespace only from the outer ends of the whole string, so the first body line's 2-space indent (nested inside a `- [ ]` list) is dropped while subsequent lines keep theirs. Result: the opening ```` ``` ```` fence marker ends up at column 0 while the fence's content retains its original indent. The code block still renders, but with a disorienting 2-space prefix on every line of code. The fix: uniformly dedent the body to its minimum common indent using `textwrap.dedent`.

### Task 1: Replace `strip()` with `textwrap.dedent(...).rstrip()`

**Files:**
- Edit: `src/vk/plan/parser.py`
- Edit: `tests/unit/test_plan_loose_format.py`

- [x] **Step 1: Write the failing test first.**

  Add `TestStepBodyIndentation::test_dedent_preserves_fence_alignment` in `test_plan_loose_format.py`:

  ```python
  class TestStepBodyIndentation:
      def test_dedent_preserves_fence_alignment(self, loose_plan):
          step1 = loose_plan.tasks[0].steps[0]
          lines = step1.body.splitlines()
          # The first line of the body is the fence marker ``` — once dedent
          # is applied, every code-content line must start at column 0 too.
          fence_line = next(i for i, L in enumerate(lines) if L.startswith("```"))
          content_line = lines[fence_line + 1]
          assert not content_line.startswith(" "), (
              f"step body not dedented — fence content still indented: {content_line!r}"
          )
  ```

  Run it to confirm it fails on the current parser:

  ```bash
  cd /Users/derio/Docs/projects/DERIO_NET/superpowers-for-vk
  uv run --group dev python -m pytest tests/unit/test_plan_loose_format.py::TestStepBodyIndentation -q --no-cov
  ```

- [x] **Step 2: Import `textwrap` and swap `.strip()` for `dedent().rstrip()` in `_parse_steps`.**

  In `src/vk/plan/parser.py`:

  ```python
  import textwrap
  # ...
  body = textwrap.dedent(text[start:end]).rstrip()
  ```

  `textwrap.dedent` drops the common leading whitespace from every line — so a body whose lines all start with 2 spaces has those 2 spaces removed uniformly. `rstrip()` trims trailing blank lines/whitespace, keeping the leading blank line that `textwrap` preserves minimal. We deliberately do NOT call `lstrip()` on the result — that would re-introduce the phase-1 bug where the first line's indent differs from the rest.

- [x] **Step 3: Re-run the full plan test suite — confirm the new test goes green and no existing test regresses.**

  ```bash
  uv run --group dev python -m pytest --no-header -q
  ```

  Expected: `322 passed, 9 skipped` (one more than phase 4's 321), coverage ≥ 79%.

- [x] **Step 4: Verify end-to-end against kid-laptops plan 7.**

  ```bash
  cp /Users/derio/Docs/projects/HOMELAB/kid-laptops/docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env.md /tmp/plan7-work.md
  uv run --group dev vk plan convert /tmp/plan7-work.md --one-per-task --yes
  sed -n '25,40p' /tmp/plan7-work.md
  ```

  Expected: the `# roles/vscode` line and all markdown body inside ```` ```markdown ```` start at column 0, not column 2.

- [x] **Step 5: Commit on the same `fix/plan-convert-content-loss` branch.**

  ```bash
  git add src/vk/plan/parser.py tests/unit/test_plan_loose_format.py
  git commit -m "fix(plan): dedent step bodies on parse to preserve fence alignment"
  ```

- [x] **Step 6: Update this plan — mark phase 5 steps `[x]` and set `**Status:** Complete`.**

  After the commit, edit `docs/superpowers/plans/2026-04-20-lossless-plan-convert.md`: flip every Phase 5 checkbox to `[x]`, change the Status header to `Complete`, then run:

  ```bash
  uv run --group dev vk progress sync docs/superpowers/plans/2026-04-20-lossless-plan-convert.md
  ```

  Commit the plan update as a separate commit (`docs(plan): complete lossless-plan-convert`).

---

## Definition of Done

- All four pre-existing bugs (loose step headers, verb loss, preamble drop, dotted labels) have their own regression test in `tests/unit/test_plan_loose_format.py` and stay green on the full `pytest` suite.
- Step-body indentation is preserved via `textwrap.dedent` — a fence marker and its content end up at the same column after parse + write.
- `vk plan convert --one-per-task` on each of kid-laptops plans 7, 8, 9 produces a phased plan with line count at-or-above the source and identical step-checkbox count.
- `vk plan self-review` reports `Passed` on all three converted plans (excluding pre-existing placeholder-word findings that already live in plan 8's source content).
- The plan itself is saved to `docs/superpowers/plans/2026-04-20-lossless-plan-convert.md` and indexed in the relevant spec.

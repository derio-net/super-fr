# `vk plan rework` — rework plan command surface

**Status:** Draft
**Date:** 2026-04-22
**Repos affected:** `derio-net/superpowers-for-vk`. Cross-repo rename touches `derio-net/kid-laptops` (see §9).

## Goal

Operationalise the "rework plan" convention — captured in the `kid-laptops`
spec and proven in two live rework plans — as a set of `vk` CLI commands.
The commands scaffold rework files, append rows to an Origin table as deferred
items surface, and list open reworks across a repo. The CLI does not make
planning decisions; it mechanises the repetitive plumbing so the operator
(and more often, the agent acting on the operator's behalf) can defer
surfaced-but-not-realised work into a durable, vk-execute-compatible plan
without reopening the parent.

## Problem Statement

After a plan ships, code reviews and demos keep surfacing items that need to
land somewhere. Three prior storage strategies failed:

1. **GitHub Issues** drift from the plan files that are the source of truth.
2. **"Phase N follow-ups" appendices in the parent plan** orphan cross-cutting
   items, lose PR-dismissed items when the PR closes, and vanish from plan
   scanners once the parent is archived.
3. **Reopening the closed parent plan** rewrites the delivery record — ticked
   checkboxes become an inconsistent history — and confuses `vk plan format`
   / `vk execute check-deps` when a Complete plan grows new unticked items.

The pattern that works is a **separate, lean rework plan named after the
parent**, with an Origin table at the top, operator-grouped actionable
phases below, and a Definition of Done that echoes the origin rows. The
convention is documented in the kid-laptops spec; two rework files in the
wild (`kid-laptops-5-parental-controls-rework-1`,
`kid-laptops-7-vscode-dev-env-rework-1`) exercise it at two scales.

This spec codifies three CLI commands that turn that convention into
mechanical CLI work, keeping the planning intelligence in the operator / agent
and the plumbing in `vk`.

## Non-goals

- **No GitHub Issues integration.** Plan files remain the source of truth.
- **No PR-comment scraping.** No `--from-pr <N>` or similar. Items enter the
  Origin table only through explicit operator/agent action.
- **No back-pointer writer** against the parent plan. The rework file links
  *to* the parent; manual edits on the parent are the operator's call.
- **No cross-cutting subcommand.** Cross-plan reworks (e.g.
  `retroactive-sprint-1-5-fixes`) are a regular `vk plan` file that references
  multiple parents in its header. No special command surface.
- **No pre-deploy-checklist integration.** Rework plans and
  `PRE_DEPLOY_CHECKLIST.md` are independent artefacts.
- **No `vk plan rework-close` DoD-walker.** Completion and archival follow the
  same lifecycle as any plan.
- **No `--force-number` flag.** If a rework number collision needs manual
  repair, the operator (or agent-assisted) hand-edits. YAGNI in v1.
- **No changes to `vk plan list-incomplete`.** That command does not exist
  and is not introduced here.
- **No parser support for multiple tags per phase** (`[agentic] [development]`).
  Phase header stays `[agentic]|[manual]`; work-category lives in a new
  `**Track:**` body-field.

## Cross-cutting principle: fail loud, non-interactive

Inherited from the parallel-dispatch-DAG spec. Every failure names the
offending condition and names the command or edit that fixes it. No
interactive prompts under any circumstance — agent callers cannot answer
them without blocking the whole conversation. Where the CLI has insufficient
information to proceed, it exits `2` with an actionable message. Warnings
go to stderr; stdout stays clean for programmatic consumption.

## Design decisions

| # | Decision | Alternatives considered |
|---|---|---|
| D1 | v1 ships the full trio: `vk plan rework`, `vk plan rework-add`, `vk plan rework-list` in one spec→plan→implementation cycle. | Ship scaffold-only, defer add/list. |
| D2 | `rework-add` appends an Origin row only. No phase side-effects. Phase creation is done by the operator or the `vk-plan` skill in a follow-up step. | Auto-create one phase per row; require `--phase` flag. |
| D3 | Scaffolded file is bare-bones: header + empty Origin table (header row only) + DoD stub. No placeholder phases. | Pre-seed `## Phase 1: [Name]` like `vk plan new` does. |
| D4 | The informational work-category field is named **`Track`**. Rendered as `**Track:**` under each phase header and as the right-most column of the Origin table. Free-form string; canonical tokens are `development` / `operations` / `decision`; transitions like `decision → development` and compounds like `development (future-triggered)` are accepted. | `Type` (overloaded with programming types), `Mode` (collides with the agentic/manual mode-tag and `ConfirmAction` PROMPT mode), `Kind` (generic), `Category` (longer). |
| D5 | Canonical-token validation is a **soft warn** emitted only by `self-review`, never by the parser itself. | Enum-enforce at CLI flag level; warn on every parse. |
| D6 | `--source` accepts free-form text with an **empty guard** (whitespace-only is exit 2). Pipes are escaped; newlines rejected. | Structured `--source-pr N` shortcut; no guard at all. |
| D7 | Scaffold rejects parents outside `docs/superpowers/plans/` and `docs/superpowers/archived-plans/` (exit 2). Accepts parents still in `plans/` but **warns** to stderr that the `Parent plan:` header may need updating after archival. | Strict: reject until parent is archived. Silent: accept any path. |
| D8 | Back-pointer writer against the parent is deferred past v1. The rework file carries the `Parent plan:` link; the reverse link is a manual edit. | `vk plan rework-close` that walks DoD → parent appendix. |
| D9 | Template lives as a Python literal in `src/vk/plan/rework.py`, mirroring `plan_new` at `src/vk/commands/plan_cmd.py:91-117`. | Packaged template file rendered via `importlib.resources`; per-repo override from `plan-config.yaml`. |
| D10 | Next-rework-number scan covers both `plans/` and `archived-plans/`. Gaps are tolerated (`max(N) + 1`); duplicate `N` across the two directories is an exit-2 ambiguity error. Concurrent open reworks on one parent are allowed. | Reject concurrent open reworks; fill gaps; offer `--force-number`. |
| D11 | Minor version bump `1.1.0 → 1.2.0`. New user-visible subcommands. | Patch (too small for three new subcommands); major (no breaking change to existing commands). |
| D12 | Primary caller is the **agent** acting during a session, not a human at a prompt. CLI design target is machine ergonomics: deterministic exit codes, no TTY prompts, easy to call N times in one turn. Human callers remain supported incidentally. | Design for human-first; add a human-friendly interactive wizard. |

## What stays unchanged

- Existing `vk plan` subcommands: `new`, `format`, `convert`, `self-review`,
  `spec-index`. No flag or behaviour changes.
- `vk dispatch`, `vk execute`, `vk progress`. A rework plan is a normal
  phased plan from their perspective and flows through unchanged.
- `validate_dag` and the explicit `**Depends on:**` grammar from the
  parallel-dispatch-DAG spec. `**Track:**` is informational and has no DAG
  consequence.
- Phase header tag syntax `[agentic]|[manual]`. The work-category is a
  body-field, not a second bracketed tag.
- Plan filename convention (`YYYY-MM-DD-<slug>.md`) and the `derive_slug`
  helper at `src/vk/plan/filename.py`.
- Archive lifecycle. Rework plans move from `plans/` to `archived-plans/`
  when Status flips to Complete, identically to any plan.

---

## 1. Architecture and module layout

```
src/vk/plan/
├── rework.py          (new)   scaffold, rework-add, rework-list core logic
│                              + Python-literal template (D9)
│                              + parse_origin_table() helper
├── filename.py        (keep)  derive_slug() reused as-is
├── parser.py          (edit)  add _TRACK_RE; parse **Track:** body-line
├── models.py          (edit)  Phase gains track_label: str | None = None
└── writer.py          (edit)  emit **Track:** line when set

src/vk/commands/
└── plan_cmd.py        (edit)  three thin typer wrappers that delegate to
                               rework.py — match the existing plan_cmd.py
                               pattern (no business logic in the command
                               module beyond arg resolution + exit codes)
```

**Module placement rationale.** The three commands share a template constant
and a set of filesystem helpers (parent-location resolution, next-number
scan, rework-file matching, Origin-table I/O). They do not share enough
internal state to justify a multi-file package. One ~250-line `rework.py`
is right-sized; split only if it passes ~400 LoC.

**Command naming rationale.** `vk plan rework`, `vk plan rework-add`,
`vk plan rework-list` — flat verb-noun at each level. Matches existing vk
CLI shape (`vk plan new`, `vk plan format`, `vk plan convert`,
`vk plan self-review`, `vk plan spec-index`). No new nesting introduced.

---

## 2. Command surface

### 2.1 `vk plan rework <parent-plan-path>`

**Signature.**

```
vk plan rework PARENT_PATH
```

Positional `PARENT_PATH` is required. No flags in v1.

**Behaviour.**

1. Resolve `parent_path`. If missing, exit 2.
2. Validate location: must be in `docs/superpowers/plans/` or
   `docs/superpowers/archived-plans/`. Otherwise exit 2.
3. Parse parent via `parse_plan`. Extract `.spec` and `.title`.
4. Compute slug via `derive_slug(parent_path)` and extract the parent's
   `YYYY-MM-DD` prefix from its filename. Re-use the prefix verbatim — the
   convention requires sort-adjacency between parent and rework.
5. If parent is in `plans/` (not yet archived), emit a stderr warning that
   the `Parent plan:` header will point at `plans/` and will need updating
   after archival (D7). Proceed.
6. Compute next rework number `N` (see §4).
7. Compute prior-rework chain: highest-numbered rework in
   `archived-plans/` is the `Prior rework:` value. If no archived prior,
   omit the field entirely.
8. Render scaffold from the Python-literal template (§3).
9. Write to `docs/superpowers/plans/<date>-<slug>-rework-<N>.md`.
10. Print `Created: <path>` to stdout.

**Exits.** `0` on success. `2` on missing / mis-located parent, ambiguous
rework number (D10), or any parse error on the parent.

### 2.2 `vk plan rework-add <rework-plan-path>`

**Signature.**

```
vk plan rework-add REWORK_PATH --item TEXT --source TEXT --track TEXT
```

All three flags required. No interactive fallbacks.

**Behaviour.**

1. Resolve `rework_path`. If missing, exit 2.
2. Validate each of `--item` / `--source` / `--track` is non-empty after
   `.strip()`. Otherwise exit 2 naming which flag.
3. Reject newline characters in any flag value (exit 2). A markdown table row
   cannot span lines.
4. If `--track` (lower-cased, first token) is not in
   `{development, operations, decision}`, emit stderr warning. Proceed.
5. Read the file. Locate the `## Origin` section and its table.
   - Missing section → exit 2 with "Was this scaffolded via `vk plan rework`?"
   - Malformed header row → exit 2 with the expected header string.
6. Parse existing rows; determine next `#` = `max(row.number) + 1`, or 1 if
   empty.
7. Escape `|` in `--item` and `--source` by replacing with `\|`. Strip
   trailing whitespace on all values.
8. Append `| N | <item> | <source> | <track> |` at the end of the Origin
   table block.
9. Write file.
10. Print `Added Origin row #N to <path>` to stdout.

**Exits.** `0` on success. `2` on structural problems.

### 2.3 `vk plan rework-list`

**Signature.**

```
vk plan rework-list [--status VALUE] [--track VALUE] [--plan SLUG]
                    [--include-archived] [--json]
```

All flags optional.

**Behaviour.**

1. Glob `docs/superpowers/plans/**/*-rework-*.md`. If `--include-archived`,
   also glob `docs/superpowers/archived-plans/`.
2. For each match:
   - Parse via `parse_plan`. If parse fails, stderr-warn the path + the
     error, skip the file.
   - Extract parent slug by stripping `-rework-<N>` from the filename slug.
   - Extract `N` from the filename.
   - Read `plan.status`.
   - Count open steps: `sum(1 for t in plan.all_tasks for s in t.steps if s.state == " ")`.
   - Parse Origin table via the `rework.py` helper. Count rows and
     tally by Track value.
3. Apply filters:
   - `--status`: case-insensitive exact match on `plan.status`.
   - `--track`: case-insensitive **substring** match against any Origin
     row's Track column (so `--track decision` matches `decision → development`).
   - `--plan`: exact match on parent slug.
4. Emit output:
   - Default: Rich table with columns `parent-slug`, `rework-#`, `status`,
     `open-steps`, `origin-items`, `by-track`. The `by-track` column emits
     each non-zero Track count separated by ` / `, with canonical tokens
     abbreviated (`dev` / `ops` / `dec`) and non-canonical tokens shown as
     their first lowercase word. Example: `2 dev / 1 ops`.
   - `--json`: JSON array on stdout; each object has the table fields plus
     `path`, `parent_path`, `spec_path`.

**Exits.** `0` in all cases. Zero results is not an error. Unparseable
rework files are skipped with a stderr warning.

---

## 3. Scaffold template

Literal markdown written by `vk plan rework`. Python f-string with the
fields identified below as interpolations.

```markdown
# {title}

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `{spec}`
**Parent plan:** `{parent_path}` {parent_annotation}
{prior_rework_line}
**Status:** Not Started

**Goal:** [Address rework items on {parent_slug} without reopening the parent.]

---

## Origin

| # | Item | Source | Track |
|---|------|--------|-------|

---

## Definition of Done

- [ ] TODO: echo each resolved origin item here when the rework completes.
```

**Interpolation rules.**

- `title`: `f"{parent.title} — Rework {N}"`. If the parent has no H1 title,
  fall back to `f"Rework {N} for {parent_slug}"` and stderr-warn.
- `spec`: `parent.spec` verbatim. If parent has no `**Spec:**` field, the
  whole `**Spec:** ...` line is **omitted** — not written with an empty value.
- `parent_path`: absolute-from-repo path, quoted in backticks to match the
  sample reworks.
- `parent_annotation`: `(merged + archived)` when parent is in
  `archived-plans/`, `(not yet archived)` when in `plans/`. Parenthesised,
  no backticks.
- `prior_rework_line`: if an archived prior rework exists,
  `**Prior rework:** \`<path>\`` on its own line. Otherwise the line is
  omitted entirely (not rendered with `—`).
- `parent_slug`: human-readable form of the slug for the Goal placeholder
  (no transformation beyond what `derive_slug` already returns; the operator
  edits the Goal anyway).

**What the template deliberately omits.** No `**Tech Stack:**` line (the
operator / agent adds it during realization if needed). No phase headers.
No blockquote prose beyond the required "For agentic workers" banner.

---

## 4. Next-rework-number computation

Given a parent plan at `<dir>/<date>-<slug>.md`:

1. Scan `docs/superpowers/plans/` for filenames matching
   `<date>-<slug>-rework-*.md`. Collect the integer portion.
2. Scan `docs/superpowers/archived-plans/` identically.
3. Let `P = set of Ns in plans/`, `A = set of Ns in archived-plans/`.
4. If `P ∩ A` is non-empty, exit 2 with the ambiguity message naming the
   colliding `N` (D10 fail-loud on dual-dir collision).
5. `N = max(P ∪ A) + 1`. If `P ∪ A` is empty, `N = 1`.
6. Gaps in `P ∪ A` are tolerated (D10).

Concurrent open reworks (`P` containing more than one entry) are allowed
without warning. The operator may be splitting work intentionally.

---

## 5. Parser, model, and writer changes

### 5.1 Parser (`src/vk/plan/parser.py`)

Add a new regex adjacent to `_DEPENDS_ON_RE`:

```python
_TRACK_RE = re.compile(
    r"^\*\*Track:\*\*\s+(.+?)\s*$",
    re.MULTILINE,
)
```

In `_parse_phases`, extract the body slice between a phase header and the
first task under it. Apply `_DEPENDS_ON_RE` and `_TRACK_RE` to that slice.
If multiple `**Track:**` lines appear, the first wins; do not raise.

### 5.2 Model (`src/vk/plan/models.py`)

Extend `Phase`:

```python
@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["manual", "agentic"]
    depends_on: tuple[int, ...]
    tasks: tuple[Task, ...]
    tracking_url: str | None
    track_label: str | None = None   # NEW
```

Default `None` preserves positional-constructor compatibility with existing
test fixtures — matches the `phase_has_depends_line` pattern at
`models.py:91`.

### 5.3 Writer (`src/vk/plan/writer.py`)

When emitting a phase, if `track_label is not None`, write
`**Track:** <value>` on the line immediately after `**Depends on:**`. If
`track_label is None`, emit no line.

### 5.4 Validator (`src/vk/plan/validate.py`)

Unchanged. `**Track:**` has no DAG, dispatch, or execute consequence.

### 5.5 Canonical-token lint in `self-review`

`plan_cmd.plan_self_review` gains one check: walk the plan's phases; for
each phase with `track_label` set whose lower-cased first word is not in
`{development, operations, decision}`, emit an issue:

```
Phase N has non-canonical **Track:** value '<v>' (expected development /
operations / decision).
```

The existing issue-collector surfaces it; exit code remains `1` as with
every other `self-review` warning.

---

## 6. Origin-table helpers (in `rework.py`)

### 6.1 `parse_origin_table(path: Path) -> list[OriginRow]`

Where `OriginRow` is a frozen dataclass:

```python
@dataclass(frozen=True)
class OriginRow:
    number: int
    item: str
    source: str
    track: str
```

Reads the file, locates the `## Origin` heading, walks forward to the
table, skips header and separator rows, parses data rows. Unescapes `\|`
back to `|`. Raises a typed exception on malformed header — caller
translates to exit 2.

### 6.2 `append_origin_row(path: Path, row: OriginRow) -> None`

Reads file, locates the Origin table (via the same locator used by
`parse_origin_table`), inserts the row immediately after the last data
row (or immediately after the separator if table is empty), writes back.
Preserves all other file content byte-for-byte.

### 6.3 Containment

Origin-table parsing is rework-specific and lives **only** in `rework.py`.
It is not bled into `Plan` AST (`parse_plan` does not know about Origin
tables). This keeps the generic plan model free of convention-specific
structure.

---

## 7. Error handling and exit codes

| Command | Scenario | Exit | Stream | Message (template) |
|---|---|---|---|---|
| `rework` | Parent path missing | 2 | stderr | `Error: parent plan not found: <path>` |
| `rework` | Parent not in `plans/` or `archived-plans/` | 2 | stderr | `Error: parent plan must live in docs/superpowers/plans/ or docs/superpowers/archived-plans/. Got: <path>` |
| `rework` | Parent in `plans/` (not archived) | 0 | stderr (warn) | `warn: parent is not yet archived; Parent plan header points at plans/. Update when parent is moved.` |
| `rework` | `N` ambiguous across dirs | 2 | stderr | `Error: ambiguous rework state: rework-<N> exists in both plans/ and archived-plans/. Resolve manually before scaffolding.` |
| `rework` | Parent has no H1 title | 0 | stderr (warn) | `warn: parent has no H1 title; using slug-derived fallback.` |
| `rework` | Output path already exists (defensive) | 2 | stderr | `Error: output path already exists: <path>` |
| `rework-add` | Rework path missing | 2 | stderr | `Error: rework plan not found: <path>` |
| `rework-add` | Missing / empty / whitespace-only flag value | 2 | stderr | `Error: --<flag> is required and must be non-empty.` |
| `rework-add` | Newline in flag value | 2 | stderr | `Error: --<flag> must not contain newlines.` |
| `rework-add` | Non-canonical `--track` | 0 | stderr (warn) | `warn: --track value '<v>' is not a canonical token (development / operations / decision). Accepted as free-form.` |
| `rework-add` | No `## Origin` section | 2 | stderr | `Error: plan has no ## Origin section. Was this scaffolded via 'vk plan rework'?` |
| `rework-add` | Malformed Origin table header | 2 | stderr | `Error: Origin table header malformed. Expected: \| # \| Item \| Source \| Track \|` |
| `rework-list` | No matches | 0 | stdout | Empty table (or `[]` with `--json`) |
| `rework-list` | File fails to parse | 0 | stderr (warn) + skip | `warn: skipping <path>: <error>` |

**Exit-code philosophy.** `0` = command did what it was asked (possibly
with warnings). `2` = structural refusal. `1` is reserved for
`self-review`-style "found issues" results — no v1 rework command uses it.

---

## 8. Testing plan

### 8.1 Unit tests

| File | Coverage |
|---|---|
| `tests/unit/test_rework.py` (new) | `next_rework_number` across all Q11 cases; `render_scaffold` variants; `parse_origin_table` happy path + malformed header; `append_origin_row` including pipe-escape round-trip and newline rejection |
| `tests/unit/test_plan_parser.py` (extend) | `**Track:**` parsing: single value, transition syntax, absent, multiple-lines-first-wins |
| `tests/unit/test_plan_writer.py` (extend) | Round-trip: `track_label` set / unset; emission order relative to `**Depends on:**` |
| `tests/unit/test_models.py` (extend) | `Phase.track_label` default keeps positional-constructor fixtures green |
| `tests/unit/test_plan_validate.py` (verify) | Plans with `**Track:**` values pass `validate_dag` unchanged |

### 8.2 Integration tests

Use Typer's `CliRunner` (same pattern as `tests/integration/test_plan_execute.py`).

| File | Coverage |
|---|---|
| `tests/integration/test_plan_rework.py` (new) | Scaffold: archived parent happy path; parent in plans/ (stderr-warn assertion); missing parent exit 2; mis-located parent exit 2; rework-1 archived → rework-2 with `Prior rework:`; rework-1 archived + rework-2 active → rework-3 created (Q11-b-ii); rework-N collision across dirs → exit 2 (Q11-d-i) |
| `tests/integration/test_plan_rework_add.py` (new) | Happy path appends row + stdout confirms; canonical `--track` no warn; non-canonical stderr-warn; empty flag exit 2; pipe-escape visible in file; newline rejected; missing Origin section exit 2 |
| `tests/integration/test_plan_rework_list.py` (new) | Empty tree; two reworks in plans/; `--include-archived`; `--status` / `--track` / `--plan` filters; `--track decision` matches `decision → development`; `--json` output is valid JSON; one malformed file does not break listing |

### 8.3 Fixtures

`tests/fixtures/rework/` (new), committed as `.md` files:

- `parent_archived.md` — minimal archived parent with spec, title, one phase.
- `parent_no_spec.md` — parent with no `**Spec:**`.
- `rework_empty.md` — freshly scaffolded rework, empty Origin table.
- `rework_with_rows.md` — Origin table with three rows covering all three
  canonical Track values.
- `rework_with_phases.md` — realized rework with phases that carry
  `**Track:**` body lines (for parser / list tests).
- `rework_malformed_origin.md` — Origin section present, table header wrong.

### 8.4 What is *not* tested

- Back-pointer writing (D8, not implemented).
- `--from-pr` scraping (non-goal).
- `--force-number` flag (D10).
- Python-version matrix (existing CI covers this).

---

## 9. Dependencies and cross-repo effects

### 9.1 This repo

- Version bump `1.1.x → 1.2.0` in `pyproject.toml`,
  `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` (D11).
  Minor per `CLAUDE.md`'s versioning rule ("new mandatory behavior / new
  subcommand").
- `skills/vk-plan/SKILL.md` updated to reference the rework command surface
  and explain when to invoke it.

### 9.2 `derio-net/kid-laptops`

The convention spec and the two sample reworks use `Type` as the
work-category field name (Origin table column and, in the samples as
originally written, phase body lines). These three files need a `Type →
Track` rename before or alongside the `vk` release, so the sample reworks
remain consistent with the codified convention:

- `docs/superpowers/specs/2026-04-07-kid-laptops-design.md` — "Rework plan
  convention" section.
- `docs/superpowers/plans/2026-04-08-kid-laptops-5-parental-controls-rework-1.md`
  — Origin table column header; any `**Type:**` body lines if present
  after operator edits.
- `docs/superpowers/plans/2026-04-08-kid-laptops-7-vscode-dev-env-rework-1.md`
  — same.

The sample reworks also currently use `[operations]` and
`[decision → development]` in phase headers, which neither the existing
parser nor this spec's `[agentic]|[manual]` contract accepts. Those phase
headers should be normalised to `[agentic]|[manual]` with the category
moved to a `**Track:**` body line as part of the same cross-repo PR.

### 9.3 Release sequencing

`vk` ships independently; the kid-laptops rename is a parallel PR in its own
repo. Neither repo blocks the other — kid-laptops reworks already function
as plain phased plans (without `**Track:**`) once their phase tags are
normalised.

---

## 10. Success criteria

1. `vk plan rework --help`, `vk plan rework-add --help`,
   `vk plan rework-list --help` all produce clean typer output. No stub
   commands.
2. Every existing test in the main-branch corpus stays green.
3. New parser tests for `Phase.track_label` and new rework CLI tests pass.
4. Running `vk plan self-review` on a freshly scaffolded rework file
   produces only the expected "Goal placeholder" warning. No structural
   errors.
5. Round-trip fidelity: scaffold a rework, parse it, re-emit via
   `write_plan`, diff → empty.
6. Every command runs cleanly in a non-TTY environment (verified in
   integration tests).
7. Three version-source files move in lockstep to `1.2.0`; `uv run vk
   --version` reports the new number.
8. kid-laptops `Type → Track` rename PR is open. Merge order is independent
   — this `vk` release does not depend on the kid-laptops PR merging
   first, and kid-laptops plans already function without `**Track:**`
   once their phase tags are normalised to `[agentic]|[manual]`.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| `vk plan rework` Command Surface Implementation Plan |  | `docs/superpowers/archived-plans/2026-04-22-vk-plan-rework-command/` | — |

# VK CLI Toolchain Design Spec

## Summary

Convert the vk-* skills from prose-with-embedded-bash into a real Python toolchain: one `vk` CLI with subcommands, installed via `uv tool install`, covered by pytest, with SKILL.md files reduced to thin decision-layer wrappers. In doing so, fix two foundational issues: dispatch defaults to fail-closed (opt-in only), and local-mode repos get a flat plan format instead of vestigial phases.

## Problem Statement

The current vk-* skills are ~1000 lines of prose-with-embedded-bash interpreted by the agent at runtime. Every bash snippet, every Edit, every grep is its own tool call plus permission prompt. A simple `vk-dispatch` run takes ~15 tool calls and ~15 operator confirmations. The prose is untestable: there is no unit test for "does vk-dispatch correctly emit tracking comments in idempotent order?"

Additionally, the dispatch default is fail-open: a repo without a `plan-config.yaml` silently connects to `derio-net/Derio Ops`. And local-mode repos are forced into the phased plan format, which was invented for GitHub Issue dispatch and adds overhead in non-dispatched contexts.

## Success Criteria

1. A full `vk dispatch` run becomes **one bash call with one confirmation** (dry-run, then `--yes`).
2. Behavior is specified by tests, not prose. Any change starts with a failing test.
3. A repo without a `dispatch:` block in its `plan-config.yaml` cannot accidentally dispatch.
4. A repo without a `dispatch:` block gets **flat** plans (Task > Step). A repo with a `dispatch:` block gets **phased** plans (Phase > Task > Step). One decision drives everything.
5. SKILL.md files are under 80 lines each, focused on *when to use* and *how to interpret CLI output*.

## Scope

**In scope:**

- Python package `vk` in `superpowers-for-vk/src/vk/`, installable via `uv tool install .`
- CLI subcommands: plan helpers, dispatch, progress (5 capabilities), execute helpers, audit
- Shared core: config reader, plan parser (both formats), git helpers, gh subprocess wrapper
- Pytest suite with unit + CLI integration tests, ruff lint, mypy strict, coverage gate (85%)
- New thin SKILL.md files for all four vk-* skills
- Migration of existing `plan-config.yaml` files in dependent repos
- Replacement of `scripts/validate-skills.sh` with pytest-based validation

**Non-goals:**

- Rewriting upstream superpowers skills (brainstorming, executing-plans, etc.)
- GUI, TUI, or web UI
- Replacing the `gh` CLI (we subprocess-wrap it)
- Supporting backends other than GitHub Issues
- Interactive conversational flows inside the CLI (those stay in SKILL.md prose)
- Backwards compatibility with old SKILL.md prose (hard cutover; old versions survive in git history)

## Design Decisions

| # | Decision | Alternatives considered |
|---|----------|------------------------|
| D1 | **Fail-closed dispatch default.** Missing file, missing `dispatch:` key, or `dispatch: false` all mean disabled. | Fail-open (current), three-state (missing file vs missing key) |
| D2 | **Opt-in model.** Dispatch enabled only when an explicit `dispatch:` map is present in plan-config.yaml. | Dispatch enabled by default with opt-out |
| D3 | **Format tied to dispatch presence (Option Y).** No explicit flag; `dispatch:` block present = phased, absent = flat. | Explicit `plan.structure` flag, always-phased |
| D4 | **Omit dispatch option from vk-plan handoff when disabled.** Show only subagent-driven and inline execution. One-liner note explains why. | Keep visible but greyed out, offer to scaffold config |
| D5 | **Error messages include fix hint (Option B).** Paste-ready `dispatch:` block template in the refusal message. | Terse one-liner |
| D6 | **Inline approach (Option A).** Each skill/module has its own copy of the gate check. No shared helper script or cross-reference. | Centralize in vk-dispatch, shared schema doc |
| D7 | **Scope S2: full graceful degradation.** All four skills handle fail-closed mode: vk-progress degrades per-capability, vk-execute accepts (plan, phase) directly. | Minimal (vk-plan + vk-dispatch only), full + naming cleanup |
| D8 | **One `vk` CLI with subcommands.** Single entry point. | Separate `vk-plan`, `vk-dispatch` executables |
| D9 | **Python package in this repo (`superpowers-for-vk`).** | Separate `vk-cli` repo |
| D10 | **`uv` as the toolchain.** `uv sync`, `uv run`, `uv tool install`. | pip + venv + build + pipx |
| D11 | **`gh` subprocess wrapping.** Leverage existing auth. | PyGithub (requires token management) |
| D12 | **typer + pyyaml + rich.** No markdown AST lib (hand-rolled parser). | click/argparse, ruamel.yaml, mistune |
| D13 | **Python 3.11 minimum.** tomllib, Self typing, exception groups. | 3.10, 3.12+ |
| D14 | **Hard cutover for SKILL.md files.** No parallel maintenance period. | Staged migration with both versions running |
| D15 | **Filename slug: `lstrip("-")` on rest-after-date.** Handles single-dash and double-dash patterns uniformly. | Pattern-matching on separator count |
| D16 | **Anti-pattern rules kept inline in SKILL.md (Option P5a).** Pruned to 3-5 lines per rule, no separate guide doc. | Separate `plan-writing-guide.md` |
| D17 | **`vk plan convert` included in scope.** Four modes: phased-to-flat, flat-to-phased via --single-phase, --one-per-task, or --group-by-tag. | Deferred to follow-up, manual conversion only |

## What Stays Unchanged

- The brainstorming conversational flow (stays in `superpowers:brainstorming` skill prose)
- The TDD execution loop (stays in `superpowers:executing-plans` / `superpowers:subagent-driven-development`)
- The `superpowers:finishing-a-development-branch` handoff
- The user-level `vk-plan-override.md` redirect (brainstorming invokes vk-plan, not writing-plans)
- The plan-config.yaml field schema (plan, header, dispatch sections) -- only the default interpretation changes

---

## Package Layout

```
superpowers-for-vk/
├── pyproject.toml
├── uv.lock
├── src/
│   └── vk/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── plan/
│       │   ├── __init__.py
│       │   ├── parser.py
│       │   ├── writer.py
│       │   ├── models.py
│       │   ├── format.py
│       │   ├── filename.py
│       │   └── convert.py
│       ├── git.py
│       ├── gh.py
│       ├── spec_index.py
│       └── commands/
│           ├── __init__.py
│           ├── plan_cmd.py
│           ├── dispatch_cmd.py
│           ├── progress_cmd.py
│           ├── execute_cmd.py
│           ├── init_cmd.py
│           ├── install_cmd.py
│           └── common.py
├── tests/
│   ├── conftest.py
│   ├── unit/
│   │   ├── test_config.py
│   │   ├── test_plan_parser.py
│   │   ├── test_plan_writer.py
│   │   ├── test_plan_convert.py
│   │   ├── test_filename.py
│   │   ├── test_format.py
│   │   ├── test_spec_index.py
│   │   ├── test_models.py
│   │   ├── test_gh.py
│   │   └── test_skill_validation.py
│   ├── integration/
│   │   ├── conftest.py
│   │   ├── test_dispatch.py
│   │   ├── test_progress.py
│   │   ├── test_convert.py
│   │   └── test_execute.py
│   └── fixtures/
│       ├── plans/
│       │   ├── phased-small.md
│       │   ├── phased-large.md
│       │   ├── phased-dispatched.md
│       │   ├── flat-small.md
│       │   ├── flat-mixed-tags.md
│       │   └── not-a-plan.md
│       ├── configs/
│       │   ├── dispatch-enabled.yaml
│       │   ├── dispatch-false.yaml
│       │   ├── no-dispatch-key.yaml
│       │   ├── empty.yaml
│       │   └── dispatch-minimal.yaml
│       └── specs/
│           ├── spec-with-index.md
│           └── spec-without-index.md
├── skills/
│   ├── vk-plan/SKILL.md
│   ├── vk-dispatch/SKILL.md
│   ├── vk-progress/SKILL.md
│   └── vk-execute/SKILL.md
└── docs/
    └── superpowers/
        ├── plan-config.yaml
        ├── specs/
        └── plans/
```

### Dependencies

```toml
[project]
name = "vk"
version = "0.3.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "pyyaml>=6",
    "rich>=13",
]

[project.scripts]
vk = "vk.cli:app"

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-cov>=5",
    "ruff>=0.6",
    "mypy>=1.11",
]
```

### Installation

```bash
# Developer setup
uv sync && uv run pytest && uv run vk --help

# User install
uv tool install git+https://github.com/derio-net/superpowers-for-vk

# Skills install (symlinks skills/ into ~/.claude/skills/)
vk install-skills
```

---

## Canonical Dispatch Gate

Dispatch is **enabled** for a repo if and only if:

1. `docs/superpowers/plan-config.yaml` exists at the repo root, **AND**
2. The file contains a top-level `dispatch:` key whose value is a map (not the literal `false`, `null`, or any non-map scalar)

All other states mean dispatch is **disabled**.

### Truth table

| Input | `dispatch_enabled` |
|-------|-------------------|
| File missing | `False` |
| File exists, no `dispatch` key | `False` |
| `dispatch: false` | `False` |
| `dispatch: null` | `False` |
| `dispatch: true` (scalar, not map) | `False` + warning |
| `dispatch: {}` (empty map) | `True` (opt-in; owner defaults to `derio-net`, project to `Derio Ops`, repo resolved from git remote) |
| `dispatch: {owner: foo, ...}` | `True` |

### Error message template (shown on gate refusal)

```
Dispatch unavailable -- no `dispatch:` block in `docs/superpowers/plan-config.yaml` for this repo.

To enable, add this to the file:

  dispatch:
    target: github-issues
    owner: <your-github-owner>
    project_board: "<Project Name>"
    default_repo: <owner>/<repo>
    labels:
      agentic: vk-ready
      manual: manual
```

### Implementation

```python
@dataclass(frozen=True)
class DispatchConfig:
    owner: str
    project_board: str
    default_repo: str
    target: str = "github-issues"
    labels: dict[str, str] = field(
        default_factory=lambda: {"agentic": "vk-ready", "manual": "manual"}
    )

@dataclass(frozen=True)
class Profile:
    plan: PlanConfig
    header: HeaderConfig
    dispatch: DispatchConfig | None  # None = fail-closed

    @property
    def dispatch_enabled(self) -> bool:
        return self.dispatch is not None

    @property
    def format(self) -> PlanFormat:
        return PlanFormat.PHASED if self.dispatch_enabled else PlanFormat.FLAT
```

---

## Dual Format: Flat vs Phased

### Format selection (Decision D3)

Dispatch presence drives format. No explicit flag.

| `dispatch:` block | Plan format | Description |
|-------------------|-------------|-------------|
| Present (map) | **Phased**: Phase > Task > Step | Each phase = one PR = one GitHub Issue |
| Absent | **Flat**: Task > Step | Tasks are top-level; `[manual]`/`[agentic]` tags on tasks |

### Format detection from existing files

Detection is **structural**, not config-driven. The plan file itself declares its format by its headers:

- At least one `## Phase N:` header = PHASED
- No phase headers but has `### Task N:` headers = FLAT
- Neither = not a vk plan (error)

This means existing phased plans remain parseable even if the repo switches to local-only. New plans follow the profile's format.

### Flat format example

```markdown
# Feature Implementation Plan

**Spec:** `docs/superpowers/specs/2026-04-12-feature-design.md`
**Status:** Not Started
**Goal:** Implement the feature.

---

### Task 1: Set up database schema [agentic]

**Files:**
- Create: `migrations/001_create_table.sql`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write the failing test**
...

### Task 2: Configure DNS records [manual]

- [ ] **Step 1: Log in to Cloudflare dashboard**
  URL: https://dash.cloudflare.com/...
...

### Task 3: Implement API endpoint [agentic]
...
```

### Manual/agentic tag placement

| Format | Tag on | Example |
|--------|--------|---------|
| Phased | Phase header | `## Phase 2: Core modules [agentic]` |
| Flat | Task header | `### Task 3: Configure DNS [manual]` |

### Format enforcement

| Command | Check |
|---------|-------|
| `vk plan new` | Writes using `profile.format` |
| `vk dispatch` | Refuses flat plans: *"Cannot dispatch a flat plan."* |
| `vk execute scope` | Accepts both; flat scopes by task, phased by phase |
| `vk progress sync` | Both supported; flat syncs at task granularity |
| `vk plan self-review` | Format-specific checks (phase tags vs task tags) |

### No auto-migration

Switching a repo from dispatched to local does not auto-convert existing phased plans. Old plans remain parseable. Only new plans follow the new format. Users can explicitly convert with `vk plan convert`.

---

## Plan Parser AST

Five frozen dataclasses:

```python
CheckboxState = Literal[" ", "x", "-"]  # unchecked, done, skipped

@dataclass(frozen=True)
class Step:
    number: int
    title: str
    body: str
    state: CheckboxState

@dataclass(frozen=True)
class Task:
    number: int
    title: str
    tag: Literal["manual", "agentic"] | None
    steps: tuple[Step, ...]
    files_mentioned: tuple[str, ...]

@dataclass(frozen=True)
class Phase:
    number: int
    title: str
    tag: Literal["manual", "agentic"]
    tasks: tuple[Task, ...]
    tracking_url: str | None

@dataclass(frozen=True)
class Plan:
    title: str
    spec: str | None
    status: str
    goal: str
    format: PlanFormat
    phases: tuple[Phase, ...]   # populated in phased format
    tasks: tuple[Task, ...]     # populated in flat format

    @property
    def all_tasks(self) -> tuple[Task, ...]:
        if self.format is PlanFormat.FLAT:
            return self.tasks
        return tuple(t for p in self.phases for t in p.tasks)
```

The parser is regex-driven (~150 lines). Body content between headers is preserved as raw markdown strings, enabling lossless round-trip (`parse -> write -> parse` produces identical AST).

---

## Filename Slug Derivation

Handles both single-dash (`YYYY-MM-DD-{name}.md`) and double-dash (`YYYY-MM-DD--{layer}--{details}.md`) patterns:

```python
def derive_slug(plan_path: Path) -> str:
    stem = plan_path.stem
    m = re.match(r"^\d{4}-\d{2}-\d{2}", stem)
    if not m:
        raise ValueError(f"Plan filename must start with YYYY-MM-DD: {plan_path.name}")
    rest = stem[m.end():]
    slug = rest.lstrip("-")
    if not slug:
        raise ValueError(f"Empty slug after stripping date prefix: {plan_path.name}")
    return slug
```

`lstrip("-")` handles any leading-dash run uniformly. See superpowers-for-vk#5 for discovery context.

---

## Plan Conversion (`vk plan convert`)

Four conversion modes, all non-interactive:

### Phased to flat

- Flatten all phases into a single task list
- Task numbering reset globally (1, 2, 3, ...)
- Each task inherits its parent phase's `[manual]`/`[agentic]` tag
- **Refuses** if plan has `<!-- Tracking: -->` comments without `--force`
  (prevents orphaning GitHub Issue links)

### Flat to phased (three modes, mutually exclusive, one required)

| Flag | Behavior |
|------|----------|
| `--single-phase` | Wrap everything in one `## Phase 1` with the dominant tag |
| `--one-per-task` | Each task becomes its own phase |
| `--group-by-tag` | Consecutive tasks with the same tag merge into one phase |

All modes: file rewritten in place, committed with standard message, `--dry-run`/`--yes` contract applies.

Round-trip invariant: `phased -> flat -> phased(single-phase)` preserves all task content and ordering.

---

## CLI Surface

### Top-level

```
vk [--version] [--help] <command>

Commands:
  plan            Write, save, and maintain plan files
  dispatch        Dispatch a phased plan to GitHub Issues
  progress        Track work lifecycle
  execute         Helpers for phase/task execution
  init            Scaffold plan-config.yaml in a new repo
  install-skills  Symlink SKILL.md files into ~/.claude/skills/
```

Every command and subcommand gets auto-generated `--help` via typer.

### `--dry-run` / `--yes` contract

| Flags | Behavior |
|-------|----------|
| (none) | Show dry-run output, prompt `Proceed? [y/N]` |
| `--dry-run` | Show dry-run output, exit 0, no mutations |
| `--yes` | Execute immediately, no prompt |
| `--dry-run --yes` | Error: mutually exclusive |

Agent workflow: `vk dispatch <plan> --dry-run` (show to operator) then `vk dispatch <plan> --yes` (on approval). Two bash calls, one in-conversation confirmation.

### `vk plan` subcommands

```
vk plan new <name> [--spec PATH] [--save]
vk plan self-review <plan-path>
vk plan spec-index <plan-path> [--dry-run | --yes]
vk plan convert <plan-path> --to FORMAT [--force | --single-phase | --one-per-task | --group-by-tag] [--dry-run | --yes]
vk plan format [REPO_ROOT]
```

### `vk dispatch`

```
vk dispatch <plan-path> [--repo OWNER/REPO] [--project "Name"] [--dry-run | --yes]

Exit codes:
  0  success (or all phases already dispatched)
  1  gate disabled / config error
  2  plan parse error (flat format, missing phases)
  3  gh error (auth, rate limit, access)
  4  partial success (some phases failed)
```

### `vk progress` subcommands

```
vk progress sync <plan-path> [--dry-run | --yes]
vk progress board [--format table|json] [--stale-days N]
vk progress create <title> --type TYPE [--repo OWNER/REPO] [--lifecycle STATE]
vk progress transition <target> <new-state> [--yes]
vk progress audit [--format report|json]
```

Each subcommand auto-detects mode via dispatch gate. `progress create` refuses in local mode.

### `vk execute` subcommands

```
vk execute check-deps <plan-path> <phase-or-task-number>
vk execute scope <plan-path> <phase-or-task-number>
vk execute check-step <plan-path> <step-id> [--state x|-] [--note TEXT]
vk execute pr-body <plan-path> <phase-or-task-number> [--issue NUMBER]
```

Step IDs: `P<phase>.T<task>.S<step>` (phased) or `T<task>.S<step>` (flat).

`check-step` guarantees: never unchecks a checked box, validates step exists, stages but does not commit, idempotent on re-run.

### `vk init`

```
vk init [--dispatch OWNER/REPO] [--project "Name"]
```

Without `--dispatch`: writes a fail-closed local-only config. With `--dispatch`: writes a full dispatch block. Creates `docs/superpowers/{specs,plans,archived-plans}/` if missing. Refuses to overwrite existing config without `--force`.

### `vk install-skills`

```
vk install-skills [--copy]
```

Default: symlinks `skills/vk-*/` into `~/.claude/skills/vk-*`. `--copy` for cross-filesystem installs.

---

## Graceful Degradation (Dispatch Disabled)

### vk-plan execution handoff

Dispatch enabled: three options (Dispatch to VK, Subagent-driven, Inline execution).
Dispatch disabled: two options (Subagent-driven, Inline execution) plus note: *"Dispatch unavailable -- add a `dispatch:` block to `plan-config.yaml` to enable."*

### vk-progress per-capability

| Capability | Dispatch enabled | Dispatch disabled |
|------------|-----------------|-------------------|
| Sync | Issue states -> checkboxes -> spec index | Checkbox state -> Status header -> spec index |
| Board | Query project board, group by lifecycle | Scan local plan files, group by Status header |
| Create | Create GitHub Issue + board entry | Unavailable (print gate refusal) |
| Transition | Move Issue lifecycle state on board | Edit plan `**Status:**` header + spec index sync |
| Audit | Issues + Grafana + local drift checks | Local-only drift checks (status vs checkboxes, spec index sync, stale plans) |

### vk-execute

| Mode | Input | Dep check | PR body |
|------|-------|-----------|---------|
| Dispatched | Issue URL/number | Query `Blocked by #N` Issues | `Closes #<issue>` |
| Local | `(plan_path, phase_or_task)` | Earlier phases/tasks have all checkboxes checked | `Implements Phase N of <plan-path>` |

---

## SKILL.md Shape After Pythonization

All four SKILL.md files move into `superpowers-for-vk/skills/` (version-controlled in this repo) and get deployed via `vk install-skills`.

| File | Lines now | Lines after | What moves to code |
|------|-----------|-------------|-------------------|
| vk-plan | 353 | ~80 | Bash snippets, incident context, full task examples, self-review loops |
| vk-dispatch | 266 | ~55 | All 6 dispatch steps, idempotency logic, gate regex, field-edit patterns |
| vk-progress | 284 | ~65 | All 5 capabilities' bash, state-map tables, gh queries |
| vk-execute | 104 | ~75 | Minor; adds CLI check-deps/scope/check-step/pr-body calls |

**Conversational parts stay in prose:** vk-plan's brainstorm-to-plan flow, vk-execute's TDD delegation to `superpowers:executing-plans`. These are dialogue contracts with the model, not mechanical procedures.

**Mechanical parts become CLI calls:** gate checks, plan parsing, file mutations, git commits, gh interactions. Each is a single `vk <subcommand>` invocation from the agent's perspective.

Anti-pattern rules (no placeholders, fence-leak prevention, TDD-first) are kept inline in vk-plan/SKILL.md, pruned to 3-5 lines per rule without incident rationale. `vk plan self-review` enforces the most common ones automatically.

---

## Testing Strategy

### Three layers

| Layer | Purpose | Speed | Volume |
|-------|---------|-------|--------|
| Unit | Pure functions, no subprocess/filesystem | <5s | ~70% |
| CLI integration | CliRunner, temp git repos, fixture files | ~20s | ~25% |
| gh contract | Mocked subprocess, verify gh invocation shape | <2s | ~5% |

### Coverage

85% line coverage gate via `pytest-cov`. Not 100% because rich formatting and rare error branches (gh auth failures, rate limits) are low-value to unit test.

### Quality gates

```bash
uv run ruff check src/ tests/          # lint
uv run ruff format --check src/ tests/  # format
uv run mypy src/                        # strict type checking
uv run pytest                           # tests + coverage
```

All must pass. `mypy --strict` from day one.

### CI

GitHub Actions, three parallel jobs: lint, typecheck, test. No `gh` in CI (contract tests use mocked subprocess). Total wall time: ~40 seconds.

### Fixtures

Committed to `tests/fixtures/`. Plans (phased, flat, dispatched, mixed-tags, not-a-plan), configs (enabled, false, no-key, empty, minimal), specs (with-index, without-index). Parametrized tests auto-discover new fixtures.

### Skill validation

`scripts/validate-skills.sh` replaced by `tests/unit/test_skill_validation.py`:
- YAML frontmatter parses, `name` and `description` fields present
- First non-empty line is `---`
- File under 120 lines (guardrail against prose re-bloat)

---

## Sub-Project Decomposition

Seven sub-projects, each producing its own implementation plan.

### Dependency graph

```
P0 (scaffold)
 └─ P1 (core modules)
     └─ P2 (vk dispatch)
         ├─ P3 (vk progress)
         └─ P4 (vk plan + execute helpers)
             └─ P5 (SKILL.md rewrites + init + install-skills)
                 └─ P6 (migration sweep) [manual]
```

P3 and P4 can run in parallel after P2. All others are sequential.

### P0: Python project scaffolding [agentic]

Walking skeleton: `vk --version` and `vk --help` work, one passing test, CI green.

Delivers: `pyproject.toml`, `src/vk/{__init__,__main__,cli}.py`, `tests/conftest.py`, CI workflow, `uv.lock`.

Exit criteria: `uv run vk --version` prints version, `uv run pytest` passes, CI green.

Estimated: ~8 files, ~3 tasks.

### P1: Core modules [agentic]

Shared brain: config reader, plan parser (both formats), writer, filename, format detection, converter, spec index, git/gh helpers. Full unit test coverage. No CLI commands yet.

Delivers: all `src/vk/` modules except `commands/`, all unit tests, all fixtures.

Exit criteria: `uv run pytest tests/unit/` passes with >=85% coverage.

Estimated: ~15 files, ~8 tasks. **Largest sub-project.**

Depends on: P0.

### P2: `vk dispatch` command [agentic]

First real CLI subcommand. The "10 tool uses, 15 confirmations" to "1 call" win.

Delivers: `dispatch_cmd.py`, `common.py` (shared CLI helpers), CLI integration tests, gh contract tests.

Exit criteria: dry-run prints correct preview; apply with mocked gh creates correct issues; all gate refusals tested.

Estimated: ~5 files, ~6 tasks.

Depends on: P1.

### P3: `vk progress` commands [agentic]

All five capabilities as CLI subcommands, dual-mode (dispatch/local).

Delivers: `progress_cmd.py`, CLI integration tests for all 5 capabilities in both modes.

Exit criteria: each subcommand works in both modes (or correctly refuses for `create`).

Estimated: ~3 files, ~7 tasks.

Depends on: P2.

### P4: `vk plan` + `vk execute` helper commands [agentic]

Mechanical helpers that SKILL.md calls for plan writing and phase execution.

Delivers: `plan_cmd.py` (new, self-review, spec-index, convert, format), `execute_cmd.py` (check-deps, scope, check-step, pr-body), CLI integration tests.

Exit criteria: each subcommand has >=3 integration tests. Round-trip conversion passes. `check-step` never unchecks a checked box.

Estimated: ~4 files, ~8 tasks.

Depends on: P2.

### P5: SKILL.md rewrites + `vk init` + `vk install-skills` [agentic]

Replace all four prose SKILL.md files with thin wrappers. Add utility commands.

Delivers: four new SKILL.md files (total ~275 lines), `init_cmd.py`, `install_cmd.py`, skill validation tests. Deletes `scripts/validate-skills.sh`.

Exit criteria: all SKILL.md files pass validation tests. `vk install-skills` creates working symlinks. `vk init` produces a valid config.

Estimated: ~8 files, ~6 tasks.

Depends on: P4.

### P6: Migration + validation sweep [manual]

Operator runbook. Audit HOMELAB repos, run `vk init` where missing, verify existing plans parse, smoke-test dispatch-enabled repos.

Steps:
1. Audit `~/Docs/projects/HOMELAB/*/docs/superpowers/plan-config.yaml`
2. `vk init` for unconfigured repos
3. Verify dispatch blocks have all required fields
4. Test `vk plan convert --dry-run` on existing phased plans in local-only repos
5. Remove old `~/.claude/skills/vk-*` files (replaced by symlinks)
6. Smoke-test `vk --version` and `vk dispatch --dry-run` in dispatch-enabled repos
7. Verify CI green in superpowers-for-vk

Depends on: P5.

### Version strategy

| Sub-project | Version |
|-------------|---------|
| P0 | 0.3.0 (initial package) |
| P1 | 0.3.0 (library, no release) |
| P2 | 0.4.0 (first usable CLI) |
| P3 | 0.5.0 |
| P4 | 0.6.0 |
| P5 | 1.0.0 (feature-complete, skill cutover) |
| P6 | no bump (operator runbook) |

## Implementation Plans

| Plan | Repo | File | Status | Depends on |
|------|------|------|--------|------------|
| P0 Scaffolding | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p0-scaffold.md` | Complete | — |
| P1 Core modules | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p1-core-modules.md` | Complete | P0 |
| P2 Dispatch | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p2-dispatch.md` | Not Started | P1 |
| P3 Progress | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p3-progress.md` | Not Started | P2 |
| P4 Plan + Execute | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p4-plan-execute.md` | Not Started | P2 |
| P5 Skill rewrites | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p5-skill-rewrites.md` | Not Started | P4 |
| P6 Migration | `derio-net/superpowers-for-vk` | `docs/superpowers/plans/2026-04-12-vk-cli-p6-migration.md` | Not Started | P5 |

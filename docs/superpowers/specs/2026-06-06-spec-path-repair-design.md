# Spec-path repair + lifecycle-independent refs — Design

## Problem

On 2026-06-06 the operator found spec-table plan paths that no longer
match reality. Root cause confirmed and reproduced:

```
active-form cell  (docs/superpowers/plans/X)          → resolves ✓
legacy-form cell  (docs/superpowers/archived-plans/X) → None ✗
```

Two functions anchor on a literal `plans` path segment, which the
single segment `archived-plans` never matches:

1. `spec.py::_resolve_local_plan_dir` — the archive fallback chain
   (`plans/ → implemented/plans/ → archived-plans/`) is gated on
   `"plans" in parts`; legacy-form cells skip it entirely and resolve
   to `None`.
2. `migrate.py::_archive_path_variants` — same gate returns
   `(None, None)`, so the cross-repo gh lookup can't rescue those rows
   either.

Any spec row written under the pre-2.5.0 archive convention (hand
`git mv` to `archived-plans/`, path recorded in the table) became
invisible the moment `vk migrate dirs` relocated the directory. Five+
specs in this repo alone carry such rows. Consequences: `vk spec
status` reports them Unreachable/Missing, and `_spec_fully_implemented`
blocks with "row unresolved locally (cross-repo?)" — the owning specs
never qualify for auto-archive, in every repo migrated by the 2.5.0
rollout.

The same bug class lives on two more surfaces ("possibly elsewhere",
confirmed):

- `_meta.yaml::parent_plan` — a real stale instance exists
  (`2026-05-09-vk-v2-library-rework-1` → `archived-plans/…`);
  `plan_ops.rework_create` resolves it with no fallback.
- `_meta.yaml::spec` — goes stale when the spec archives to
  `implemented/specs/`: `render.py::spec_url` builds the GitHub blob
  link in every issue body from it (404 after archival) and
  `rework_create` does `repo_root / meta.spec` with no fallback.

## Doctrine reversal (explicit)

2.5.0 shipped "spec tables are never rewritten on archive — tolerate
stale paths via resolver fallback." The fallback anticipated cells
recorded in *active* form going stale, but not cells recorded in
*legacy-archive* form — the one form `migrate dirs` was guaranteed to
strand. The replacement doctrine is **normalize once, idempotently**:
refs become lifecycle-independent so they *cannot* go stale, and the
repair pass converges historical forms with loud warnings for anything
unresolvable. (The super-fr split spec already records this reversal in
its migration step 6.)

## Decisions (operator Q&A, 2026-06-06)

| Decision | Choice |
|---|---|
| Canonical ref form | Bare slug — `2026-06-04--obs--security-trace-analyst` (= plan dir name); spec refs: bare filename `2026-06-06-spec-path-repair-design.md` |
| Repair scope | All three surfaces: spec File cells, `_meta.yaml parent_plan:`, `_meta.yaml spec:` (incl. read-side fallbacks in `spec_url` / `rework_create`) |
| Repair triggers | `vk archive` + `vk migrate dirs` repair in passing, PLUS standalone idempotent `vk repair` (dry-run default, `--yes` to write) |
| Fleet cleanup | Post-merge subagent sweep, one PR per repo — recorded as follow-up, not a plan phase |

## Design

### 1. Shared ref resolver — read side accepts every form, forever

New module `src/vk/refs.py` (pure, no gh):

```python
def plan_slug(ref: str) -> str
    """Normalize any historical ref form to the bare slug: strips
    backticks, trailing slash, and any directory prefix (the slug is
    always the last path segment)."""

def resolve_plan_ref(ref: str, repo_root: Path) -> Path | None
    """plan_slug(ref), then try docs/superpowers/{plans,
    implemented/plans, archived-plans}/<slug> in that order."""

def resolve_spec_ref(ref: str, repo_root: Path) -> Path | None
    """Same shape for specs: docs/superpowers/{specs,
    implemented/specs, archived-specs}/<name>.md."""
```

Call-site changes (replace, don't duplicate — the #263 pattern of one
shared predicate):

- `spec.py::_resolve_local_plan_dir` → delegates to `resolve_plan_ref`
  (its `"plans" in parts` fallback block is deleted; the blind spot
  dies structurally).
- `migrate.py::_archive_path_variants` → derives the gh-lookup
  candidates from `plan_slug` (all three roots), fixing the cross-repo
  arm of the same bug.
- `render.py::spec_url` and `plan_ops.rework_create` → resolve
  `meta.spec` / `parent_plan` via `resolve_spec_ref` /
  `resolve_plan_ref` before building URLs / parsing.

Cells with annotations (`` `docs/…/X/` (shipped via PR #146) ``) keep
working: resolution extracts the backticked token / first
whitespace-delimited token; the annotation tail is preserved verbatim
by repair.

### 2. Writers emit the canonical form

- `plan_ops._append_spec_row` (used by `vk plan create` / `rework`)
  writes the File cell as the bare slug.
- `rework_create` writes `parent_plan:` as the bare slug and `spec:`
  as the bare spec filename.
- Everything keeps parsing: the resolver accepts old and new forms
  alike, so mixed-form tables are never an error.

### 3. `vk repair` — standalone, idempotent, loud

New verb (thin typer wrapper, `commands/repair_cmd.py`, apply_cmd
conventions: dry-run default / `--yes` / text+json / shared exit
codes). Walks the whole superpowers tree:

1. Every spec under `specs/` and `implemented/specs/`: rewrite each
   Implementation Plans File cell to the bare slug **iff the ref
   resolves**; preserve the annotation tail and all other columns.
2. Every plan `_meta.yaml` under `plans/` and `implemented/plans/`:
   rewrite `parent_plan:` / `spec:` to canonical form iff resolvable.
3. Unresolvable refs: **loud warning, never silent** — name the file,
   the row/field, and every path tried; leave the ref untouched.
   Warnings go to stderr and the json payload.

Properties: idempotent (second run is a no-op — asserted by test);
read-only without `--yes`. The dry-run is the audit surface, but the
verb is not marketed as allowlist-safe (it can mutate with `--yes`) —
`vk status` remains the read-only allowlist citizen. Exit codes: 0
success or clean dry-run (warnings don't fail it — a report, not a
gate), 5 parse error. Cross-repo rows are skipped with a notice
(repair runs per-repo; the fleet sweep handles the rest).

### 4. Repair in passing

- `vk archive`: after its `git mv`s succeed, run the step-3 repair
  routine over the repo (idempotent, cheap) so the move and the ref
  normalization land in the same commit the operator makes.
- `vk migrate dirs`: same, after its moves.
- Both report what they rewrote, same format as `vk repair`.

### 5. What does NOT change

- `plan_locally_complete`, `archive_gate`, diff/apply semantics, the
  bridge: untouched. This is a resolution + data-hygiene layer.
- The 2.5.0 legacy-layout hard-stop: unchanged (`archived-plans/`
  *directories* still hard-stop; this feature handles stale *refs* to
  long-gone locations).
- Spec tables' column shape and the `## Implementation Plans` contract.

## Error handling

- Repair accumulates per-file failures rather than short-circuiting
  (apply's doctrine); a write failure on one spec doesn't abort the
  walk; exit 4 if any write failed.
- Dirty-worktree refusal at the affected paths, mirroring `vk archive`
  (repair rewrites tracked files; the operator commits).
- Resolution never guesses: ambiguity (same slug present under two
  roots) resolves in the documented order (active wins) and emits a
  warning naming both.

## Testing

Mirrors existing patterns (fixture trees, `CliRunner`, FakeGhClient
where gh is touched):

1. **refs.py truth table:** bare slug / active / implemented / legacy /
   backticked+annotated / trailing slash / `—` placeholder / spec refs,
   × {present in plans, implemented, archived-plans, absent, duplicated
   across roots}.
2. **Regression (the bug):** a legacy-form cell over an
   `implemented/plans/` dir resolves; `_spec_fully_implemented` now
   archives the owning spec; the old `None` behavior is asserted dead.
3. **Writers:** `plan create` / `rework` emit bare-slug cells and
   canonical `_meta` refs.
4. **Repair:** rewrites all three surfaces; preserves annotations and
   unrelated columns byte-for-byte; second run no-op; unresolvable ref
   → warning with every tried path, file untouched; dry-run writes
   nothing (FakeGh-style call-log assertion); dirty-tree refusal.
5. **In-passing:** archive + migrate dirs leave a repo with zero
   stale-form refs.
6. **Read-side fallbacks:** `spec_url` over an archived spec yields the
   implemented/ blob URL; `rework_create` from an archived parent
   works.

## Versioning

Minor bump (new verb + new mandatory writer behavior + doctrine
reversal), per CLAUDE.md.

## Follow-up (post-merge, not in this plan)

Fleet sweep: after the release lands and `vk` upgrades, dispatch
parallel subagents (one per repo, own worktree: frank, paperclip,
agent-images, vibe-kanban, willikins…) running `vk repair --yes` →
one small PR per repo. The super-fr split's step-6 sweep then has no
path prefixes left to rewrite.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-06-06-spec-path-repair | `derio-net/superpowers-for-vk` | `2026-06-06-spec-path-repair` | — |

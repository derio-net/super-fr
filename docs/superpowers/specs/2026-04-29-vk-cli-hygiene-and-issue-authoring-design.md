# vk CLI Hygiene + Agent-Authored Issues

**Status:** Draft
**Date:** 2026-04-29
**Repos affected:** `derio-net/superpowers-for-vk`

## Goal

Fix four compounding issues in the vk writing / dispatch / progress surface area,
all surfaced while running the label-lifecycle-fix spec. Consolidated from #55, #74,
#77, and a new feature thread.

**A. `vk plan self-review` is silent on multi-repo plans (Thread 1a, was #55).**
A plan whose phases declare different `**Target repo:**` values looks authoritative
to its author, but `vk dispatch create` ignores per-phase repo annotations — its
`--repo` flag is plan-wide. Authors following older multi-repo plan precedents
write un-dispatchable plans that pass all validators until dispatch time.

**B. `vk plan spec-index` appends duplicate rows instead of replacing (Thread 1b,
was #55).** The upsert function matches rows by plan title, not by file path. When a
plan's title changes (or when the same file is re-indexed after a rename), a second
row is appended pointing at the same path. The operation appears idempotent but
produces corrupted output, and downstream `vk progress sync` then has two rows to
keep in lockstep.

**C. `vk progress sync` corrupts the spec's Implementation Plans table (Thread 2,
was #74).** Four distinct failure modes, all rooted in the same spec-index
reconciliation logic:
1. Matches the row to update by plan title — misses when title differs from the
   row label, appends a duplicate instead.
2. Rebuilds the updated row from a fixed-schema template, silently resetting `Repo`
   and `Depends on` cells to blank / `—` (operator-set values are lost).
3. Replaces the entire `## Implementation Plans` section — strips any free-form prose
   that follows the table in that section.
4. `_build_table` unconditionally wraps the `File` column in backticks, turning a
   `—` placeholder into `` `—` `` on every row rebuild, including unchanged rows.

Hit twice on the label-lifecycle-fix spec and once on the frank-side
restart-resilience spec; each time required a manual `git checkout HEAD -- <spec>`
to recover.

**D. New: `vk issue create/convert` to author bridge-compatible Issues (Thread 4).**
The bridge contract (`## Instruction` / `## Workspace` / `## Dependencies`) is today
hand-assembled. An agent completing a brainstorm, debug session, or design review
should be able to file the follow-on Issue without manual body-editing. Similarly,
ad-hoc bug reports labeled `vk-ready` currently log a `PARSE ERROR` on every bridge
tick because they lack the contract sections. A `convert` verb would retroactively
make them bridge-routable.

## Non-goals

- **`vk admin labels-sync`** (Thread 3, was #77) — the command does not exist yet.
  The design constraint is captured in §4 below and must be respected when
  `admin_cmd.py` is written. No separate plan is created for this thread.
- Changing the 5-column canonical schema for the Implementation Plans table.
- Adding batch / multi-plan support to `vk issue create`.
- Changing how `vk dispatch create` handles `--repo` (plan-wide flag is intentional;
  the fix is to warn at authoring time, not to add per-phase repo dispatch).

## Shared root cause (Threads 1b + 2)

Both bugs converge on the same function: `spec_index.upsert_entry()`.

```
upsert_entry()
  ├── matches existing rows by e.plan == entry.plan (title equality)   ← Bug 1b / 2-symptom-1
  ├── replaces the entire ## Implementation Plans section content       ← Bug 2-symptom-3
  └── _build_table() wraps File column in backticks unconditionally     ← Bug 2-symptom-4

_reconcile_spec_index() in progress_cmd.py
  ├── also matches by plan title                                        ← Bug 2-symptom-1 (duplicate)
  └── creates IndexEntry(repo="", depends_on="—") dropping saved cells ← Bug 2-symptom-2
```

Fixing `upsert_entry()` fixes Threads 1b and 2-symptoms-1/3/4. Fixing
`_reconcile_spec_index()` fixes 2-symptom-2. Thread 1a is independent.

## Design

### §1 — `vk plan self-review`: multi-target repo warning (Thread 1a)

**Phase model change.** Add `target_repo: str | None = None` to the `Phase`
dataclass in `src/vk/plan/models.py`. Default `None` preserves backwards
compatibility with plans that omit the annotation.

**Parser change.** In `src/vk/plan/parser.py`, when parsing each phase header
block, extract the `**Target repo:**` line if present:

```python
_RE_TARGET_REPO = re.compile(r"^\*\*Target repo:\*\*\s*(.+)$", re.MULTILINE)
```

Store the captured value (stripped) as `Phase.target_repo`.

**Self-review check.** In `plan_self_review()` (`src/vk/commands/plan_cmd.py`),
after the existing Track-label lint, add:

```python
repos = {p.target_repo for p in plan.phases if p.target_repo}
if len(repos) > 1:
    repo_root = resolve_repo_root(cwd=plan_path.parent)
    config_path = repo_root / "docs" / "superpowers" / "plan-config.yaml"
    profile = load_profile(config_path)
    if profile.dispatch_enabled:
        issues.append(
            "Multi-repo plan: phases declare different **Target repo:** values "
            f"({', '.join(sorted(repos))}). vk dispatch --repo is plan-wide; "
            "per-phase repo overrides are not supported. "
            "Write one plan per target repo."
        )
```

This warns only when dispatch is actually configured for the repo, avoiding false
positives in repos without a dispatch block. The check runs before DAG validation
so a multi-repo warning surfaces alongside other structural issues.

### §2 — `spec_index.py`: path-based matching + prose preservation (Threads 1b + 2)

Three targeted fixes to `src/vk/spec_index.py`.

**Fix 2a — `upsert_entry()`: match by file path, not plan title.**

```python
# Before
for i, e in enumerate(existing):
    if e.plan == entry.plan:
        existing[i] = entry
        found = True
        break

# After
for i, e in enumerate(existing):
    if e.file == entry.file:
        existing[i] = entry
        found = True
        break
```

When a match is found by path, the entire row is replaced with the caller-supplied
`entry` (title, status, repo, depends_on). The caller is responsible for populating
`repo` and `depends_on` correctly (see §3). Emit a note — `"Updated row"` vs
`"Appended row"` — so the operator can see which branch ran.

**Fix 2b — `upsert_entry()`: only replace the table block, not the whole section.**

Current code replaces from `## Implementation Plans\n` to the next `##` section:

```python
new_text = text[:section_start] + f"\n{table}\n" + text[section_end:]
```

This strips any prose that follows the table within the section.

Fix: find the contiguous block of `|`-prefixed lines within the section and replace
only those lines. Everything before the first `|` line (within the section) and after
the last `|` line is left unchanged.

```python
section_text = text[section_start:section_end]
lines = section_text.splitlines(keepends=True)

table_first = next((i for i, l in enumerate(lines) if l.strip().startswith("|")), None)
table_last = max((i for i, l in enumerate(lines) if l.strip().startswith("|")), default=None)

if table_first is None:
    # No existing table — append at end of section
    pre = text[:section_end].rstrip("\n")
    new_text = pre + f"\n\n{table}\n" + text[section_end:]
else:
    kept_before = "".join(lines[:table_first])
    kept_after = "".join(lines[table_last + 1 :])
    new_section = kept_before + table + "\n" + kept_after
    new_text = text[:section_start] + new_section + text[section_end:]
```

**Fix 2c — `_build_table()`: guard backticks on non-path File values.**

```python
# Before
lines.append(f"| {e.plan} | {e.repo} | `{e.file}` | {e.status} | {e.depends_on} |")

# After
file_cell = f"`{e.file}`" if e.file and e.file not in ("—", "-", "") else (e.file or "—")
lines.append(f"| {e.plan} | {e.repo} | {file_cell} | {e.status} | {e.depends_on} |")
```

Rows where the File cell is a display placeholder (e.g. Phase 4 "operator action"
rows with `—`) are no longer re-quoted on every table rebuild.

### §3 — `progress_cmd.py`: path-based lookup + column preservation (Thread 2)

Two fixes to `src/vk/commands/progress_cmd.py`.

**Fix 3a — `_reconcile_spec_index()`: match by file path, preserve saved cells.**

```python
# Before
matching = [e for e in entries if e.plan == plan_title]
...
entry = IndexEntry(
    plan=plan_title,
    repo="",
    file=rel_file,
    status=status,
    depends_on="—",
)

# After
existing_entry = next((e for e in entries if e.file == rel_file), None)
if (existing_entry
        and existing_entry.status == status
        and existing_entry.plan == plan_title):
    return False  # already current; unchanged

entry = IndexEntry(
    plan=plan_title,
    repo=existing_entry.repo if existing_entry else "",
    file=rel_file,
    status=status,
    depends_on=existing_entry.depends_on if existing_entry else "—",
)
```

Only `status` (and `file` when archiving renames the path) is mutated. `repo` and
`depends_on` are copied from the existing row so operator-set values survive.

**Fix 3b — `transition` command: same pattern.**

The `transition` command at `progress_cmd.py:315–360` creates an `IndexEntry` with
the same hardcoded blanks. Apply the identical read-existing-entry-first pattern.

**Archive rename path.** When `_archive_plan` moves the file, the second call to
`_reconcile_spec_index` supplies the new `archived_path`. The lookup should match by
the *old* path (the pre-move `rel_file`), then update the `file` cell to the new
path. Pass both old and new paths:

```python
def _reconcile_spec_index(
    plan_path: Path,
    plan_title: str,
    status: str,
    repo_root: Path,
    *,
    dry_run: bool = False,
    prev_plan_path: Path | None = None,
) -> bool:
    ...
    lookup_path = str((prev_plan_path or plan_path).relative_to(repo_root))
    existing_entry = next((e for e in entries if e.file == lookup_path), None)
    ...
```

When archiving, `sync()` calls:
```python
_reconcile_spec_index(archived_path, plan.title, "Complete", repo_root,
                      prev_plan_path=plan_path)
```

### §4 — `vk admin labels-sync` apply mode UX (Thread 3 — design constraint)

`admin_cmd.py` does not exist yet. When it is implemented, the following constraint
applies and must not be violated:

**In apply mode (`--yes`), do not call `_render_dryrun_table`.** Print only the
per-repo summary line: what labels were created, renamed, or deleted. The dry-run
table is for previewing; apply mode is for auditing what was done. Operators who want
the preview run dry-run first (`vk admin labels-sync --dry-run`), then apply.

```python
def labels_sync(repos, dry_run, yes, ...):
    for repo in repos:
        actions = _compute_label_actions(repo, ...)
        if dry_run:
            _render_dryrun_table(repo, actions)   # preview only
        else:
            _apply_label_actions(repo, actions)
        _print_summary_line(repo, actions)        # always printed
```

The `_render_dryrun_table` function, once written, must never be called from the
apply branch.

### §5 — `vk issue create` and `vk issue convert` (Thread 4)

**CLI registration.** New module `src/vk/commands/issue_cmd.py` exports
`issue_app = typer.Typer(...)`. Register in `src/vk/cli.py`:

```python
from vk.commands.issue_cmd import issue_app
app.add_typer(issue_app, name="issue")
```

**`vk issue create`.**

```
vk issue create TOPIC
  [--skill TEXT]      # default: superpowers:brainstorming
  [--repo TEXT]       # default: current git remote (owner/repo)
  [--blockers TEXT]   # default: "None — no blocking phases."
  [--title TEXT]      # default: first 72 chars of TOPIC
  [--label TEXT]      # default: vk-ready (pass "" to skip label)
  [--dry-run]         # print body, don't create
```

`TOPIC` is the free-form problem description. If `-` is passed, read from stdin.

The command:
1. Resolves `repo` from `--repo` or `git remote get-url origin` (stripped to
   `owner/repo`).
2. Resolves `skill` from `--skill`.
3. Builds a bridge-compatible body using `_build_issue_body()`:

```python
def _build_issue_body(topic: str, skill: str, repos: str, blockers: str) -> str:
    return (
        f"{topic}\n\n"
        f"---\n\n"
        f"## Instruction\n\n"
        f"Use {skill} to explore the above and produce deliverables.\n\n"
        f"## Workspace\n\n"
        f"Repos: {repos}\n\n"
        f"## Dependencies\n\n"
        f"{blockers}\n"
    )
```

4. Validates the body via `validate_issue_body(body, phase_number=0)` (pass 0 for
   ad-hoc issues — the validator only checks structure).
5. With `--dry-run`: prints title and body to stdout, exits 0.
6. Without `--dry-run`: runs `gh issue create --title TITLE --body BODY [--label LABEL]`
   and prints the resulting URL.

**`vk issue convert`.**

```
vk issue convert NUMBER
  [--repo TEXT]       # default: current git remote
  [--skill TEXT]      # default: superpowers:brainstorming
  [--blockers TEXT]   # default: "None — no blocking phases."
  [--dry-run]
```

`NUMBER` is a GitHub Issue number (integer).

The command:
1. Fetches the existing body via `gh issue view NUMBER --repo REPO --json body`.
2. Checks if the body already contains all three contract sections. If so, prints
   `"Issue #N already has contract sections. Nothing to do."` and exits 0
   (idempotent).
3. Otherwise, appends the contract block after the original prose:

```python
new_body = existing_body.rstrip("\n") + "\n\n---\n\n" + contract_block
```

   where `contract_block` is the `## Instruction` … `## Dependencies` section
   (without the original topic, since it's already in the existing body).
4. Validates `new_body` via `validate_issue_body(new_body, phase_number=0)` to confirm
   the result is bridge-compatible.
5. With `--dry-run`: prints the new body.
6. Without `--dry-run`: runs `gh issue edit NUMBER --repo REPO --body NEW_BODY`.

**Error exits.** Exit 2 for read/auth failures (gh not authenticated, issue not
found). Exit 3 for mutation failures (gh API error on create/edit). Exit 1 for
usage errors (invalid number, conflicting flags).

## Testing

**Thread 1a** (`plan_self_review`):
- Unit: plan with phases having identical `target_repo` values → no warning.
- Unit: plan with phases having mixed `target_repo` values + dispatch enabled → warning emitted.
- Unit: plan with mixed `target_repo` values + dispatch disabled → no warning (avoids false positives).
- Unit: plan with no `target_repo` annotations → no warning.

**Threads 1b + 2** (`spec_index`, `_reconcile_spec_index`):
- Unit: `upsert_entry` with new file path → row appended.
- Unit: `upsert_entry` with same file path but different title → row updated in place (no duplicate).
- Unit: `upsert_entry` on a spec section with trailing prose → prose preserved after the table.
- Unit: `_build_table` with `file="—"` → cell rendered as `—` without backticks.
- Unit: `_reconcile_spec_index` with existing row → `repo` and `depends_on` preserved; only `status` changes.
- Integration: write a spec with an Implementation Plans table + trailing prose, run `vk progress sync`, assert prose is intact and row was updated in place.

**Thread 4** (`vk issue`):
- Unit: `_build_issue_body` output passes `validate_issue_body`.
- Unit: `vk issue create --dry-run` with topic from stdin → prints correct body, no gh call.
- Unit: `vk issue convert --dry-run` on issue that already has contract sections → noop message.
- Unit: `vk issue convert --dry-run` on plain bug report → appended body contains all three sections.
- Integration (optional): mock `gh` subprocess, assert correct arguments on create/edit.

**Not tested here:** `vk admin labels-sync` UX (§4) — tested when `admin_cmd.py` is written.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| vk spec-index hygiene (Threads 1a + 1b + 2) |  | `docs/superpowers/archived-plans/2026-04-29-vk-spec-index-hygiene/` | — |
| vk issue command (Thread 4) |  | `docs/superpowers/archived-plans/2026-04-29-vk-issue-command/` | — |

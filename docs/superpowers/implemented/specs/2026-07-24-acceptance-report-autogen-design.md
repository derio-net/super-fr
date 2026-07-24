# Acceptance report auto-generation — design

**Status:** design · **Date:** 2026-07-24 · **Slug:** acceptance-report-autogen

## Goal

> Always create/update the corresponding HTML report file each time
> `docs/acceptance/matrix.yaml` is updated.

Today `docs/acceptance/report.html` is **gitignored** (`.gitignore:34`) and
only ever exists as an ephemeral CI artifact or a throwaway local render. The
`matrix.yaml` → `report.html` correspondence is therefore never enforced: the
committed source (`matrix.yaml`) has no committed rendering, and any local
`report.html` silently rots the moment a row changes. This feature makes the
HTML report a **tracked artifact that is always in sync with the matrix**, by
(a) committing it, (b) regenerating it on the CLI mutation path, and (c) gating
drift in CI — the same "tripwire, not prose" posture super-fr already uses for
the OpenCode skill mirrors and the version lockstep.

## Non-goals

- Not changing the report's *visual* design or the matrix schema.
- Not adding a git pre-commit hook (AGENTS.md: "No local pre-commit hook — CI
  is the single source of truth").
- Not having CI commit the report back (bot-commit churn; local-first instead).
- Not touching the existing CI **artifact** upload (the github-linked,
  ephemeral render in `acceptance-report.yml` stays — it serves Actions
  navigation and is orthogonal to the committed local report).

## Current shape (read before trusting prose)

- `packages/fr/src/fr/acceptance/report.py` — `render(matrix, links, stamp)`
  builds the HTML; `LinkBuilder` resolves `<repo>:<path>` refs. `_actual_path`
  does **filesystem I/O** (`(base/path).exists()`, follows archived-spec twins)
  — a determinism hazard for a committed, diff-checked file.
- `packages/fr/src/fr/commands/acceptance_cmd.py`
  - `report_cmd` — renders to `docs/acceptance/report.html`; `stamp` embeds
    `git log -1 --format=%cs %h` (**per-commit volatile** — fatal for a
    committed + checked file).
  - `add_cmd` — the one CLI that mutates `matrix.yaml` (textual append +
    post-write `load_matrix` invariant + rollback). Status flips
    (`not-implemented`→`ci`, etc.) are **hand-edits** with no CLI.
- `packages/fr/src/fr/acceptance/scaffold.py` — `init` writes
  `GITIGNORE_LINE = "docs/acceptance/report.html"` into `.gitignore` and does
  **not** generate a report. `RULE_TEMPLATE` / `.claude/rules/acceptance-matrix.md`
  describe the report as "(gitignored)".
- `.gitignore:34` — `docs/acceptance/report.html`.

## Design

### D1 — `report.html` becomes tracked

Remove `docs/acceptance/report.html` from `.gitignore`. `fr acceptance init`
stops appending that ignore line and instead **generates an initial
`report.html`** (deterministic, local links) so a freshly-scaffolded repo has
the committed correspondence from row zero. Existing consumer repos that already
carry the ignore line are handled by the sync guidance in the rule text; the
installer/version bump strands nothing (the render code ships in `fr`).

### D2 — deterministic render (a pure function of `matrix.yaml`)

A committed, diff-checked report must be reproducible from `matrix.yaml` alone —
independent of git HEAD and of which sibling/archived files happen to exist in
the checkout. Introduce a **deterministic rendering** used by the committed
path:

- **Stamp:** drop the `git log -1` date/hash. Deterministic stamp =
  `f"{N} rows · links: {mode}"` (N = row count) — informative, matrix-derived,
  stable.
- **Links:** `LinkBuilder` gains `probe: bool = True`. When `probe=False`,
  `_actual_path` skips the `.exists()` / archive-twin filesystem lookups and
  emits the raw ref path. This removes the last source of tree-dependent
  output, so the render depends only on `matrix.yaml` + `link_mode`.

Surface: `fr acceptance report --deterministic` (implies the stamp + `probe=False`).
The committed report is rendered with `--link-mode local --deterministic`
(local relative links are viewable when the HTML is opened from a checkout;
GitHub does not render committed HTML anyway). The existing default
(`report_cmd` with git stamp + probing) is unchanged for ad-hoc local renders.

### D3 — regenerate on the CLI mutation path

After `add_cmd` successfully appends a row and re-validates the matrix, it
**regenerates `docs/acceptance/report.html`** with the deterministic/local
parameters. The row is already valid and committed-to-disk before the render;
a render failure does **not** roll back the row (it would discard valid work) —
it prints a warning to run `fr acceptance report`, and the D4 tripwire is the
backstop. This delivers "create/update each time `matrix.yaml` is updated" for
the programmatic path.

### D4 — enforce sync for every update path (hand-edits included)

`add_cmd` cannot cover hand-edited status flips. So sync is *enforced*, not just
best-effort:

- `fr acceptance report --check` — render the matrix deterministically and
  compare to the on-disk `report.html`; exit non-zero on drift with a
  "run `fr acceptance report` and commit" hint. (Read-only; writes nothing.)
- `tests/unit/test_tripwire_acceptance_report_sync.py` — asserts the committed
  `docs/acceptance/report.html` equals a fresh deterministic render of the
  committed `docs/acceptance/matrix.yaml`. Mirrors
  `test_tripwire_opencode_skills_sync.py`: the test imports the same drift
  helper the CLI `--check` uses, so the gate and the CLI can never disagree.
  Runs in the existing CI `test` job — no workflow change, lowest risk.

### D5 — docs / scaffold text

Update every "report.html (gitignored)" claim to reflect the committed,
tripwire-kept-in-sync reality: `.claude/rules/acceptance-matrix.md`,
`scaffold.py`'s `RULE_TEMPLATE`, and the generated
`.opencode/instructions/acceptance-matrix.md` mirror (via
`scripts/sync-opencode.py`). Bump the plugin version (**minor** — new CLI flags
+ mandatory committed-report behavior).

## Decisions (made autonomously — this is a non-interactive VK card; ratify at merge)

- **DEC-1 Commit vs. local-only:** commit `report.html` (D1). Rationale: "always
  create/update the corresponding html file" reads as a maintained, versioned
  artifact; local-only regen leaves other clones and CI with no committed
  correspondence and nothing to enforce.
- **DEC-2 Link mode of the committed report:** `local` (D2). GitHub renders
  committed `.html` as source, not a page; local relative links resolve when the
  file is opened from a checkout. The CI artifact keeps `github` links.
- **DEC-3 Enforcement:** a unit tripwire in the existing `test` job (D4), not a
  new CI workflow step, matching the repo's established tripwire pattern.
- **DEC-4 add-regen failure policy:** never roll back a valid row on a render
  error; warn + rely on the tripwire (D3).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-24-acceptance-report-autogen | `derio-net/super-fr` | `2026-07-24-acceptance-report-autogen` | — |

## Test Plan

Business-level acceptance (rows added to `docs/acceptance/matrix.yaml`; the
mechanics are unit-pinned, the end-to-end walk is the post-merge item):

1. **`report.html` is tracked and initially in sync.** `git ls-files` includes
   `docs/acceptance/report.html`; `fr acceptance report --check` exits 0 on the
   committed pair. (unit: tripwire test)
2. **CLI mutation keeps the report in sync.** `fr acceptance add ...` on a temp
   repo updates both `matrix.yaml` and `report.html`; a follow-up
   `fr acceptance report --check` exits 0. (unit)
3. **Hand-edit drift is caught.** Mutating `matrix.yaml` without regenerating
   makes `fr acceptance report --check` (and the tripwire) exit non-zero with
   the fix hint. (unit)
4. **Deterministic render is stable.** Rendering the same matrix twice, and
   across differing tree state (archived twin present/absent), yields identical
   bytes. (unit)
5. **Scaffold.** `fr acceptance init` on an empty repo generates a committed-
   ready `report.html` and does not add the gitignore line. (unit)
6. **[post-merge] End-to-end operator walk:** on a real clone, `fr acceptance
   add` a throwaway row, confirm `report.html` changed in the same working
   tree, `git diff` shows both files, revert. Confirms the committed artifact
   moves with the matrix in a live checkout.

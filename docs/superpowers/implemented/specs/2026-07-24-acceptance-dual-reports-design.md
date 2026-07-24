# Acceptance dual reports (local + github) — design

**Status:** design · **Date:** 2026-07-24 · **Slug:** acceptance-dual-reports

## Goal

Two operator asks, building directly on #403 (report kept in sync with the matrix):

1. **Two committed HTML reports, not one** — one with **local** links (viewable
   from a checkout) and one with **github** links (clickable on github.com).
2. **Every fr-acceptance repo creates/updates *both* files the moment it touches
   `docs/acceptance/matrix.yaml`** — not just super-fr, and without a per-repo
   workflow migration.

## Current shape (post-#403)

- `packages/fr/src/fr/acceptance/report.py` — `render_deterministic(matrix, root,
  out_dir, sibling_root, link_mode="local")` is a pure function of the matrix
  (matrix-derived stamp, `probe=False`, resolved paths); for `github` it pins
  `ref="main"`. `render_report(...)` is the ad-hoc git-stamped variant.
- `packages/fr/src/fr/commands/acceptance_cmd.py`
  - `report_cmd` — `--deterministic` writes one file (local by default);
    `--check` verifies one file; `--out`/`--link-mode`/`--ref` for ad-hoc.
  - `add_cmd` — regenerates the single `docs/acceptance/report.html`.
  - `check_cmd` → `fr.acceptance.check.check()` — the universal gate (refs,
    staleness, statuses). Runs in every scaffolded CI workflow.
- `scaffold.py` `init` — generates `docs/acceptance/report.html`; un-gitignored.
- Enforcement today: super-fr's `tests/unit/test_tripwire_acceptance_report_sync.py`
  (super-fr only) + `add`-regen (best-effort, all repos).

## Design

### D1 — the committed report SET

Two canonical committed files under `docs/acceptance/`, both deterministic:

- `report.html` — **local** links (unchanged path; back-compat).
- `report.github.html` — **github** links pinned to `main`, clickable on github.com.

`report.py` gains the single source of truth:

```python
REPORT_SET = {  # rel-path under repo root -> link_mode
    "docs/acceptance/report.html": "local",
    "docs/acceptance/report.github.html": "github",
}

def render_committed_set(matrix, root) -> dict[str, str]:
    """{rel_path: html} for both committed reports, each deterministic."""
```

`add`, `init`, `report --deterministic`, `report --check`, the tripwire, and the
`check` gate all go through `REPORT_SET` / `render_committed_set`, so the file
list lives in exactly one place.

### D2 — CLI: set by default, single file on `--out`

- `fr acceptance report --deterministic` (no `--out`) → writes **both** files.
- `fr acceptance report --check` (no `--out`) → verifies **both**; exit 3 naming
  the drifted/missing file.
- `fr acceptance report --deterministic --out X [--link-mode Y]` → single file
  (explicit override; back-compat).
- Ad-hoc `fr acceptance report [--link-mode …] [--out …] [--ref …]` (no
  `--deterministic`/`--check`) → single git-stamped file, unchanged.

`add_cmd` regenerates the whole set (warn-don't-roll-back on render error, as #403).
`init` generates the whole set (degrade-don't-crash, as #403).

### D3 — enforcement folds into `fr acceptance check` (the "all repos" mechanism)

`check()` gains a report-sync assertion **gated on existence**: if *any* file in
`REPORT_SET` exists in the repo, then **every** file must exist AND match a fresh
`render_committed_set` — else `check` reports an error and exits non-zero. If
*no* report file exists (a report-less hand-rolled matrix or a bare test
fixture), the assertion is skipped — zero blast radius on repos/tests that never
opted into committed reports.

Because every scaffolded CI workflow already runs `fr acceptance check`, this
delivers ask #2 for **all** fr-acceptance repos **with no workflow change**: the
instant a repo touches `matrix.yaml` without regenerating both reports, its
existing gate goes red. `fr acceptance report --check` remains as the standalone
that `check` reuses (one comparison implementation, gate and CLI can't disagree).

`check` stays read-only (renders in memory, compares) — allowlist-safe as before.

### D4 — super-fr tripwire, docs, gitignore, gitattributes

- `test_tripwire_acceptance_report_sync.py` asserts **both** committed files
  match `render_committed_set` (fast local signal; redundant with the folded
  `check` but cheap).
- `.gitattributes` pins `report.github.html` to `text eol=lf` (byte-compared,
  same rationale as `report.html`).
- `report.github.html` is not gitignored (no rule needs changing — it's new).
- Rule text (`.claude/rules/acceptance-matrix.md`), `scaffold.py`'s
  `RULE_TEMPLATE`, and the `.opencode` mirror updated to describe both reports +
  the check-gate enforcement. Version bump **minor** (3.16.0 → 3.17.0).

### D5 — CI workflow templates: unchanged for enforcement

No enforcement step is added — `fr acceptance check` already runs and now covers
reports. The existing "Build report (github @ sha) + upload artifact" step is
left intact (it runs *after* the check step, so it never clobbers the validated
committed files in-workspace); the ephemeral sha-pinned artifact and the new
committed `report.github.html` (github @ main) coexist. Backend-aware link modes
(gitea/gitlab) remain the pre-existing out-of-scope gap.

## Decisions (autonomous — non-interactive VK card; ratify at merge)

- **DEC-1 filenames:** `report.html` (local, unchanged) + `report.github.html`
  (github). Keeps the existing path stable; the `.github.` infix reads clearly.
- **DEC-2 enforce via `check`, not a new workflow step.** Folding into the
  universal gate is the only way ask #2 reaches **existing** consumer repos
  without each editing its workflow. Gated on report existence to bound blast
  radius. Consumer impact: on the next `fr` upgrade, a repo that has
  `report.html` but not yet `report.github.html` will see `check` go red until it
  runs `fr acceptance report --deterministic` and commits — this is the intended
  "all repos now carry both."
- **DEC-3 github report pins `ref=main`** (deterministic; matches #403's github
  determinism and the report's existing sibling-pins-main shortcut).
- **DEC-4 keep the ephemeral CI artifact** (zero-risk; the committed github
  report supersedes it in usefulness but removing it is unrelated churn).

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-07-24-acceptance-dual-reports | `derio-net/super-fr` | `2026-07-24-acceptance-dual-reports` | — |

## Test Plan

1. **Both reports are generated together.** `fr acceptance report --deterministic`
   writes `report.html` (local links) and `report.github.html` (github blob
   links @ main); both are deterministic across runs. (unit)
2. **`add` regenerates both.** `fr acceptance add` on a temp repo updates
   `matrix.yaml` + both reports; `fr acceptance report --check` then exits 0. (unit)
3. **`--check` catches drift/missing in either file.** Mutating the matrix, or
   deleting `report.github.html`, makes `report --check` exit non-zero naming the
   file. (unit)
4. **`fr acceptance check` enforces the set when present, skips when absent.** A
   repo with both reports in sync passes; one with `report.html` present but
   `report.github.html` missing (or stale) fails; a repo with no report files is
   unaffected. (unit)
5. **`init` scaffolds both, un-gitignored.** (unit)
6. **[post-merge] Consumer walk:** in a sibling fr-acceptance repo, upgrade `fr`,
   run `fr acceptance add` a throwaway row, confirm both html files change in the
   same tree and `fr acceptance check` is green; revert.

# Acceptance Matrix — first-class acceptance tests across the fr pipeline

> Status: **approved 2026-07-04** (operator Q&A in-session; decisions §2) — awaiting plan.
> Origin: generalizes a reference implementation from a downstream fr-enabled
> repo, shipped the same day. Reference semantics and review-caught traps are
> restated here in full, so this spec is self-contained.

## 1. Summary

Every fr project accumulates **business-level acceptance tests** — "the
operator can actually do X" — that today live scattered across spec Test
Plans, close-out walks, and heads. The ones automated in CI stay true; the
rest rot silently. The reference implementation proved the fix: a per-repo
**registry** (`docs/acceptance/matrix.yaml`) mapping each acceptance to its
verification levels and an automation status, a **generator** (HTML report,
link modes), a **CI gate** (failing rows fail; skipped/not-implemented warn),
and a **backfill rule**. What it lacked — operator-confirmed as a MUST — is a
**nag mechanism**: warnings on a cron run's Actions page reach nobody.

This spec makes acceptance rows first-class fr citizens:

- **`fr acceptance`** CLI group (check / report / status / add / init / backfill),
- pipeline integration: **fr-brainstorming emits draft rows → plans link them
  → fr-execute flips statuses → fr-goal close-out surfaces the debt**,
- a three-channel **nag**: session-start injection, `fr status`/fr-progress
  section, and a scheduled **digest issue**,
- an agent-driven **backfill** path for existing repos.

## 2. Decision record (operator, 2026-07-04)

1. **Nag = all three channels.** (a) Session-start injection: fr-enabled repos
   surface open `skipped`/`not-implemented` rows into every agent session, so
   any resident agent nags conversationally; (b) `fr status` + fr-progress gain
   an acceptance section, and fr-goal's close-out MUST list rows it leaves
   un-promoted in the PR body and final report; (c) the weekly CI run upserts a
   single "Acceptance debt" issue per repo. CI annotations remain but are
   acknowledged insufficient alone.
2. **Central matrix + plan linkage.** One `docs/acceptance/matrix.yaml` per
   repo. fr-brainstorming emits draft rows (status `not-implemented`) alongside
   the spec; plan phases carry `acceptance: [row-ids]`; execution flips
   statuses; `fr plan self-review` fails a plan whose spec has zero linked rows.
3. **New `fr acceptance` group** (not folded into existing verbs).
4. **Backfill is agent-driven via a skill** wrapping `fr acceptance backfill`.
5. **Rows are presented and defended at the end of brainstorming** (operator,
   2026-07-04): the brainstorm closes with the draft rows as a first-class
   deliverable — each with a one-line defense (which business claim it pins,
   why that verification level is the target). Silent row creation is not
   acceptance-of-scope; the presentation is.
6. **Mid-flight additions are encouraged, then defended at PR time** (operator,
   2026-07-04): during planning or implementation the agent is explicitly
   flexible — and encouraged — to ADD rows when a legitimate business need
   surfaces (an edge the spec missed, a failure mode discovered in review, a
   constraint that became load-bearing). Additions are **presented and
   defended in the PR body when the PR is created — never ironed over** into
   the diff as if they had always been there.

## 3. The registry (schema — ported unchanged from the reference impl)

```yaml
rows:
  - id: kebab-stable-id
    capability: "Grouping — tables render in first-seen order"
    acceptance: "The business-level statement"
    origin: ["<repo>:<path>[#anchor]", ...]   # spec §, design doc, study row
    levels:                                    # test refs per level, [] = not verified there
      unit: ["<repo>:<path>[#Lline]"]
      api: []
      int: []
      ui: []
    status: ci | scheduled | skipped | not-implemented | failing
    notes: "evidence detail, drift context, backfill owed"
```

Status semantics: `ci` = per-PR automated (cannot drift silently) ·
`scheduled` = cron/path-trigger automated · `skipped` = verification exists
but not in CI (proven live once, manual walk) → **warning, backfill owed** ·
`not-implemented` = no test or surface yet → warning · `failing` = known red
→ **the gate fails**. Statuses move explicitly, never silently
(`not-implemented` → `skipped` → `ci|scheduled`).

Refs are `<repo>:<path>` — the repo's own name for self-refs, sibling repo
names for cross-repo evidence. Multi-repo projects are normal; sister refs are
verifiable only where a checkout exists (local runs), and that asymmetry is
stated, not hidden.

## 4. `fr acceptance` CLI group

| Verb | Behavior |
|---|---|
| `check` | The gate. Validates: status enum; unique ids; unknown `levels` keys rejected (a typo must not silently drop refs); every ref whose repo is checked out resolves to a real file; **staleness guard** — every spec under the specs dirs (live + implemented) containing a Test Plan section is cited by ≥1 row origin; **plan linkage** — every live plan's `acceptance:` ids exist. Exit contract: `failing` rows → **2**; resolution/staleness/schema errors → **1**; warnings only → **0** with CI-annotation-formatted lines. |
| `report` | Renders the HTML report. `--link-mode github` (CI): own-repo refs at `--ref`, sibling repos pinned to their default branch; `--link-mode local`: paths relative to the emitted HTML via `--sibling-root` (default `..` — repos as siblings). Level chips and origins are links; summary tiles are computed from rows so they cannot disagree with the tables; sharp-line panels generated by status. |
| `status` | Terminal nag: counts by status + the open `skipped`/`not-implemented` rows with their `notes` (the backfill-owed detail), oldest first. Allowlist-safe/read-only (like `fr status`). |
| `add` | Append a row from flags (`--id --capability --acceptance --origin --level unit=<ref> --status --notes`); schema-validated; used by skills so agents never hand-edit YAML shapes wrong. |
| `init` | Scaffold into a repo: `docs/acceptance/matrix.yaml` skeleton, the CI workflow (check → report artifact → digest-issue upsert on schedule), the backfill-rule text into the repo's agent-instruction file, gitignore entry for the generated report. Idempotent. |
| `backfill` | Emits the agent work-protocol (see §7) as markdown — the paired skill drives it. Deterministic part: lists specs with Test Plans not yet cited, plans without linked rows, test-tree inventory hints. |

### Porting notes — traps the reference implementation's reviews caught (all MUST hold, each pinned by a test)

1. **Archive-twin resolution**: specs move `specs/` ↔ `implemented/specs/` at
   `fr archive` without renaming. Links follow the file in both link modes;
   `check` downgrades a moved ref from error to an update-when-convenient
   warning; a cited spec **stays cited** for the staleness guard across the
   move. (Found the hard way: the close-out that archives a spec would
   otherwise break the gate in the same PR.)
2. **`--sibling-root` default is `..`** (repos as siblings). The draft's
   `../..` was off by one, which both broke local links AND silently skipped
   the only sister-repo ref verification that exists.
3. **`#Lline` / `#anchor` fragments** are part of the ref grammar: kept for
   github URLs, stripped for existence checks and local links.
4. Repo-presence detection requires **`.git` to exist** — a plain directory at
   the sibling path (e.g. a worktree cache parent) is not a checkout.
5. **Unknown `levels` keys hard-fail**; `bool` is not a number; generated HTML
   escapes every YAML-sourced string (quote-safe).
6. Tooling must be **cwd-independent** (anchor on the package/repo, not the
   process cwd) and BSD/GNU-portable (a `sed 0,/re/` GNU-ism silently
   invalidated two negative fixtures once).
7. CI workflow: **PR-time path filters must include every own-repo path the
   matrix references** (scripts, workflows, docs), or a rename merges and the
   break surfaces only at the weekly cron. Sister-repo changes are honestly
   out of PR-time reach — the cron + local checks cover them; say so in the
   workflow header.

## 5. Pipeline integration (skills)

- **fr-brainstorming**: the brainstorm's design output includes **draft
  acceptance rows** — each key "operator can do X" claim becomes a row
  (`status: not-implemented`, origin = the new spec) via `fr acceptance add`.
  **The brainstorm ENDS by presenting the rows to the operator with a
  one-line defense each** (decision 5): the claim it pins, the target level,
  why it is business-level rather than an implementation detail. Under
  fr-goal's batched contract the presentation rides the spec-review step
  (rows appear in the spec and the run's report); standalone, it is the
  brainstorm's closing exchange. The spec hand-off checklist includes "rows
  added AND presented".
- **fr-plan**: phase YAML gains optional `acceptance: [row-ids]` (plan-level
  linkage, backward-only like `depends_on`). `fr plan self-review` errors when
  the plan's spec has a Test Plan but zero linked rows, and when a linked id
  does not exist. **Planning may ADD rows** (decision 6): when decomposition
  exposes a business acceptance the brainstorm missed, the agent adds it
  (`fr acceptance add`, origin = spec + plan) rather than burying it in a
  step description — flagged as an addition, defended later at PR time.
- **fr-execute**: completing a phase that carries `acceptance:` ids prompts
  the status flip (`not-implemented` → `skipped`/`ci`), with the test refs
  that justify it — an unflipped row is called out in the phase completion
  note. **Implementation may ADD rows too** (decision 6): a discovered edge,
  a review finding that reveals a missing business guarantee, a constraint
  that turned load-bearing — the agent is encouraged to add, never to
  silently widen or narrow scope.
- **fr-goal / PR delivery**: the close-out step runs `fr acceptance status`
  and MUST carry any remaining `skipped`/`not-implemented` rows into the PR
  body ("acceptance debt") and the final operator report. **The PR body also
  carries an "Acceptance rows added since brainstorm" section** (decision 6):
  every mid-flight row with its one-line defense — presented for the
  operator's judgment at review, never ironed over. Mechanical support:
  `fr acceptance check --added-since <ref>` diffs row ids against a base ref
  so the PR section can be generated, and an addition missing from the PR
  body is a self-review finding.
- **fr-progress**: the status board includes the acceptance section.

## 6. The nag channels (decision 1, mechanics)

1. **Session-start injection**: `fr acceptance status --brief` output is
   injected into agent sessions in fr-enabled repos (hook registered via the
   plugin, same pattern as existing super-fr hooks; content capped — counts +
   top-3 oldest warnings). Harness-agnostic fallback: `init` writes a standing
   line into the repo's agent-instruction file telling any agent to run the
   command at session start.
2. **`fr status` / fr-progress**: section as above.
3. **Digest issue**: the scheduled CI run upserts (never duplicates) one
   "Acceptance debt" issue in the repo: table of open warning rows, updated in
   place, auto-closed when zero. Implementation may reuse the `check` output
   with a `--digest` formatter; idempotence keyed on an issue marker comment.

## 7. Backfill (agent-driven, via skill)

`fr acceptance backfill` emits the protocol; a new skill (`fr-acceptance` or a
section in fr-progress) drives an agent to:

1. inventory specs (live + implemented) with Test Plan sections; design/study
   docs with acceptance-like tables; the test tree(s);
2. DRAFT rows — one per business acceptance, not per test — with real refs and
   **honest statuses** (per-PR-automated evidence ⇒ `ci`; everything proven
   only by hand ⇒ `skipped`; absent ⇒ `not-implemented`);
3. run `fr acceptance check`, fix, and open a review PR (the operator audits
   statuses — the agent must not inflate coverage).

The skill's calibration text mirrors the reference experience: the drift
channel is precisely the hand-tracked claims; when in doubt between `ci` and
`skipped`, choose `skipped`.

## 8. Out of scope (recorded)

- Cross-repo *live* verification in CI (no sister checkouts on runners) — the
  asymmetry is documented, not solved.
- Auto-deriving `failing` from live CI state of other repos' workflows (a
  future `check --live` could query check-runs; v1 statuses are declared).
- Report theming/branding beyond the reference CSS.

## 9. Acceptance (for THIS feature — eat the dog food)

On merge of the implementing plan, super-fr's own repo runs `fr acceptance
init` + backfill: the matrix exists here, the gate runs in this repo's CI, and
this spec's rows are its first entries. Version bump per release policy
(skill-doc + CLI changes ⇒ minor), CHANGELOG entry, `fr skills` overview
updated.

## Test Plan (post-merge, operator-visible)

1. In a scratch fr-enabled repo: `fr acceptance init` → matrix + workflow +
   rule land; `check` green on the skeleton.
2. `fr acceptance add` a row with a bogus level key / bad status → schema
   errors; with `status: failing` → `check` exits 2 and the workflow fails.
3. Archive a cited spec → `check` warns (does not error); report links follow
   the file.
4. Brainstorm → plan → execute a toy feature: rows born at brainstorm and
   **presented with per-row defenses at the brainstorm's close**; linked in
   the plan; flipped at execution; `fr plan self-review` catches a plan with
   no linked rows.
5. Mid-flight addition: add a row during the toy implementation →
   `fr acceptance check --added-since <base>` lists it, and the delivered PR
   body carries the "rows added since brainstorm" section with its defense;
   an addition omitted from the PR body surfaces as a self-review finding.
6. Session start in the scratch repo surfaces the open warnings; the weekly
   digest issue upserts and closes when the debt hits zero.

## Implementation Plans

| Plan | Target repo | Slug | Status |
|---|---|---|---|
| 2026-07-04-acceptance-matrix | `derio-net/super-fr` | `2026-07-04-acceptance-matrix` | — |

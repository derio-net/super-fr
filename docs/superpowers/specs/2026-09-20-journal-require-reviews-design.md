# Review is an obligation with an artifact — `fr journal check --require-reviews`

- **Issue:** derio-net/super-fr#430
- **Date:** 2026-09-20
- **Status:** design

## Background

fr-goal's per-phase code review (`SKILL.md` §6, `review-phase` in the shipped
`fr-goal` manifest) is the only obligation in the pipeline with no enforcing
artifact. Every sibling obligation produces state a command can read:

| Obligation | Enforcement |
|---|---|
| Plan well-formed | `fr plan self-review` — non-zero on failure |
| Acceptance linkage | `fr acceptance check` |
| Findings resolved | `fr journal check` — fails on any effectively-open finding |
| Steps performed | tick state in `NN.yaml`, visible in `fr status` |
| **Per-phase code review** | **prose in `skills/fr-goal/SKILL.md`** |

Nothing records that a review happened; nothing notices when one does not.
`fr status` is byte-identical either way. **There is no state in which "review
skipped" is distinguishable from "review passed clean"** — and an obligation
whose satisfaction and violation look the same is not a control.

The failure is observed, not hypothetical: a real fr-goal run
(derio-net/frank#733) completed three phases and invoked
`superpowers:requesting-code-review` zero times, substituting the
orchestrator's own inline verification. That work caught real defects, but it
is the orchestrator reviewing its own orchestration, which is structurally
unable to catch what an outside review exists for. The omission surfaced only
because the operator asked directly, three phases in.

### What the issue asked for, and what has changed since

#430 made three proposals. **Proposal 3 has already shipped** — review is per
phase, not per milestone: the manifest's `implement` step is a grouped
`for_each: phase` whose members are `implement-phase` + `review-phase`, so the
ambiguous word "milestone" no longer appears and the judgement call it invited
is gone. The issue's §7/§8 section numbers are stale for the same reason;
today's skill numbers them §6 (review-phase) and §7 (deliver).

Proposals 1 and 2 remain, and this spec implements them.

### One correction to proposal 1

The issue says "`requesting-code-review` should emit a `review`-kind journal
entry". That skill is `superpowers:requesting-code-review`, shipped by the
third-party superpowers plugin
(`~/.claude/plugins/cache/claude-plugins-official/superpowers/5.1.0/`).
super-fr cannot edit it. The obligation therefore has no editable home in the
skill that performs the review, and must live in the super-fr skills that
*invoke* it.

## Goals

1. A completed phase leaves a machine-readable trace that it was reviewed.
2. A command fails when that trace is absent, at the point where the run claims
   it is ready to deliver.
3. That command is invoked by the run cursor, not by an instruction — because
   an instruction to run the enforcement is the same unenforced obligation one
   level up.

## Non-goals

- Verifying that a review was any *good*. The gate checks that an outside
  review was performed and recorded, not its quality. A review entry whose
  body says "looked, found nothing" satisfies it, exactly as `fr journal check`
  is satisfied by a finding marked `refuted`.
- Changing `superpowers:requesting-code-review`. Not ours.
- Changing any artifact's schema. `review` is already a member of
  `JournalKind` and `phase` is already an optional field on `JournalEntry`
  (`fr/journal/model.py`), so no stamp bump and no migration are owed under
  `.claude/rules/artifact-versioning.md`.

## Decisions (operator-answered, 2026-09-20)

**D1 — the emit lives in super-fr's own skill prose**, not in a new wrapper
skill and not in a new CLI verb. `fr journal add --scope plan --slug <s>
--kind review --phase N` already writes exactly the entry required; a
`super-fr:fr-review` wrapper would be a whole new shipped surface (install.sh
wiring, OpenCode mirror, harness-parity row, tool-neutrality scan) carrying
one sentence of instruction. Prose is sufficient *because* D2/D3 make skipping
it fail loudly — which is the entire difference between this and the status
quo.

**D2 — `--require-reviews` is an opt-in flag**, as the issue asks.
`fr journal check --scope plan` behaves exactly as it does today unless the
flag is passed. The repo's own history is the argument: 35 `review` entries
exist across its journals and only 8 carry a `phase=` token, so a default-on
gate would fail live and archived plans over a convention that was never
stated. Back-compat is preserved; the flag's own weakness — that someone must
remember to pass it — is closed by D3 rather than by breaking consumers.

**D3 — the cursor runs the gate, not the prose.** A new `kind: cli` step in
the shipped `fr-goal` manifest, placed before `deliver`, whose exit code is
the verdict. This is #430's own thesis applied to the fix: an obligation
enforced by an instruction is an obligation that can be absorbed into the
working context.

**D4 — `[manual]` phases are exempt.** fr-goal back-loads manual work and
ships it unimplemented for the operator to push to the PR themselves; the
operator is its reviewer. Requiring the orchestrator to produce a review
artifact for code it did not write, and may not have seen, is a gate that
fails for the wrong reason. The exemption is *named in the failure message*,
so it is visible rather than a silent carve-out.

## Design

### A. The artifact — one `review` entry per completed phase

No schema change. The entry is written with the existing verb:

```bash
fr journal add --scope plan --slug <plan-slug> --kind review --phase N \
  --title "phase N review" \
  --body "<what was reviewed; findings raised, by id; or 'no findings'>"
```

What makes an entry *count* is one machine-checkable fact: `kind=review` and
`phase=N` in its delimiter header. The body carries the findings prose, which
the gate deliberately does not parse — findings already have their own
artifact (`kind=finding`) and their own gate (the open-findings check), and a
second, weaker parse of the same information in a review body would be a
tripwire that asserts the code calls the function it calls.

Prose is added to the two super-fr skills that invoke review:

- `plugins/super-fr/skills/fr-goal/SKILL.md` §6 — emit the entry after each
  `review-phase`, naming the phase and the findings raised.
- `plugins/super-fr/skills/fr-debugging/SKILL.md` — same obligation where it
  invokes review.

Both are canonical sources with generated OpenCode mirrors, so
`scripts/sync-opencode.py` runs and the regenerated mirrors are committed
(AGENTS.md, "Skills/rules: canonical source vs. generated mirrors").

### B. The gate — `fr journal check --require-reviews`

Three additions to `fr journal check` (`fr/commands/journal_cmd.py`):

1. `--require-reviews` (bool, default false) — turns the new gate on.
2. `--plan-dir` (optional path) — the plan folder whose phases are checked,
   defaulting to `docs/superpowers/plans/<slug>`. Mirrors `fr journal
   handoff`'s existing option of the same name and default.
3. `--slug` becomes **optional when `--plan-dir` is given**, deriving as
   `Path(plan_dir).name`. This exists for one concrete reason: the manifest
   step in §C can interpolate `{{ artifacts.plan }}` but cannot compute its
   basename, so without this the gate is not expressible as a `cli` step at
   all. With neither `--slug` nor `--plan-dir`, exit 2.

Semantics:

- `--require-reviews` requires `--scope plan` — only plan journals have
  phases. Any other scope is exit 2, the same refusal shape `handoff` uses.
- Parse the plan. A phase is **owed a review** when `state.completion.at` is
  set and `phase.tag != "manual"`.
- A phase's review is **present** when the journal holds at least one entry
  with `kind == "review"` and `phase == <number>`.
- Owed-but-absent phases → exit 1, listing them, and naming the manual
  exemption so a reader is not left wondering why phase 4 is not in the list.
- The plan being unparseable or missing is **exit 2, fail-closed**. A gate
  that cannot read the plan does not know whether it passed; `handoff` already
  takes this position for the same reason.

Composition with the existing open-findings gate: both run, both report, exit
1 if either fails. The open-findings message keeps its exact current wording
(`N open finding(s): <ids>`) because things grep it.

### C. The call site — a `journal-check` step in the shipped manifest

`plugins/super-fr/workflows/fr-goal.yaml` gains one top-level step between
`implement` and `deliver`:

```yaml
  - id: journal-check
    kind: cli
    needs: [plan]
    run: fr journal check --scope plan --plan-dir {{ artifacts.plan }} --require-reviews
```

`kind: cli` steps execute directly under `fr run advance` and their exit code
is the verdict, so a run whose phases completed without recorded reviews
cannot reach `deliver`. fr-goal §7's prose is updated to say the cursor runs
this, rather than instructing the agent to run it.

**Known cost, stated rather than discovered:** adding a top-level step changes
the shape, and `_check_step_drift` (`fr/commands/run_cmd.py:258`) refuses to
advance any run whose recorded step set differs from the manifest's. Every
in-flight `fr-goal` run — including the one delivering this very change —
will report drift at its next `advance`. This is the drift check working, not
failing: the manifest's own header comment already states that runs started
against an older shape hit drift by design. The recovery is
`fr run adopt <plan-dir> --run-id <fresh-id>`, which rebuilds a cursor from
what is on disk, completed phases included.

### D. Release

Minor bump. A new CLI flag and a new mandatory workflow step are a
user-visible workflow addition, not a fix
(AGENTS.md, "Release / version bumping").

## Test Plan

Post-merge, operator-driven:

1. On a live plan in this repo, mark a non-manual phase complete with no
   `review` entry naming it; confirm
   `fr journal check --scope plan --plan-dir <dir> --require-reviews` exits 1
   and names that phase.
2. Emit the entry with `fr journal add --kind review --phase N`; confirm the
   same command exits 0.
3. Confirm a `[manual]` phase with `completion.at` set does **not** appear in
   the failure list, and that the message says why.
4. On a real fr-goal run, confirm `fr run advance` executes the
   `journal-check` step and blocks `deliver` on its non-zero exit.
5. Confirm a run started against the pre-change shape reports drift naming
   `added: journal-check`, and that `fr run adopt --run-id` recovers it.

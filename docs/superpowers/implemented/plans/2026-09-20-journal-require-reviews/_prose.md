# Review is an obligation with an artifact

Spec: `docs/superpowers/specs/2026-09-20-journal-require-reviews-design.md`
Issue: derio-net/super-fr#430

## What this plan builds

Three things, in dependency order, and a fourth that keeps the published
documentation honest:

1. **An artifact.** A reviewed phase writes a plan-journal entry with
   `kind=review` and `phase=N`. No schema change — `review` is already a
   `JournalKind` and `phase` is already an optional field, so this is a
   convention being made load-bearing rather than a new shape.
2. **A gate.** `fr journal check --require-reviews` fails when a phase the
   plan claims is done has no review entry naming it.
3. **A call site that is not prose.** A `kind: cli` step in the shipped
   `fr-goal` manifest, placed before `deliver`, whose exit code is the
   verdict.
4. **The prose and the published explainer**, brought up to what the tool now
   does.

## Why it is shaped this way

#430's observation is that per-phase code review is the only fr-goal
obligation with no enforcing artifact: nothing records that a review happened
and nothing notices when one does not, so "review skipped" and "review passed
clean" are the same state. Every sibling obligation already produces something
a command can read — `fr plan self-review`, `fr acceptance check`,
`fr journal check`, tick state in `NN.yaml`.

The trap this plan is built to avoid is the same failure one level up. If the
enforcement is itself an instruction — "§7 should pass `--require-reviews`" —
then the fix inherits the defect it was written to remove. Hence phase 3: the
run cursor executes the gate, and an orchestrator that would have skipped the
review cannot skip the thing that checks for it.

## The one decision worth re-reading before you start

**Which completion predicate the gate keys on.** The issue says
"`completion.at` set". `fr/render.py` carries two predicates, and the
plausible-looking one is wrong:

- `_phase_complete` requires, for an agentic phase, `completion.at` **and an
  observed merged PR**. fr-goal opens exactly one PR per plan, at `deliver`,
  after this gate runs. A gate keyed on it would pass every plan forever
  while appearing to work — the precise defect class #430 is about.
- `plan_locally_complete` answers the question this gate actually asks:
  *does the plan itself claim this phase is done?* — `completion.at` set **or**
  every step ticked, with no GitHub observation involved. `fr spec status`,
  `fr archive` and the dispatch guard in `diff.py` already share it.

The gate uses `plan_locally_complete`, which is deliberately wider than the
issue asked for: a phase with every step ticked and no `completion.at` still
claims to be done, and must not be an escape hatch. `P2.T2.S1(c)` is the test
that distinguishes the three candidates, and it is the reason phase 2 exists
as its own phase rather than folding into phase 1.

The predicate is tag-agnostic by design, so the `[manual]` exemption (spec D4)
is applied at the call site rather than by changing a predicate three other
surfaces depend on.

## Two costs this plan accepts rather than discovers

**The gate is opt-in.** `fr journal check --scope plan` behaves exactly as it
does today without the flag. Of this repo's 13 plan-scope `review` entries only
8 carry a `phase=` token, so a default-on gate would fail live and archived
plans over a convention that was never stated. `P1.T1.S1(f)` pins that
back-compat assertion explicitly, because it is what a later refactor is most
likely to break without noticing.

**Adding a top-level step drifts every in-flight run**, including the run
delivering this plan. `_check_step_drift` (`run_cmd.py:258`) refuses to advance
a cursor whose recorded step set differs from the manifest's. That is the drift
check working. `P3.T2.S1` verifies the drift actually happens rather than
assuming it, and the recovery is `fr run adopt <plan-dir> --run-id <fresh>`.

## Phase map

| Phase | What lands | Tier |
|---|---|---|
| 1 | Skeleton: the three new CLI options and every way they refuse | standard |
| 2 | The gate: owed phases, present reviews, exit codes, the manual exemption | standard |
| 3 | The `journal-check` step in the shipped manifest, and proof of the drift | standard |
| 4 | Skill prose (fr-goal §6/§7, fr-debugging) and the OpenCode mirrors | mechanical |
| 5 | The published fr-goal explainer, regenerated the verified way | standard |
| 6 | Release: acceptance rows flipped with evidence, minor bump, full CI gate | mechanical |

Phase 1 is the walking skeleton: it smokes the whole delivery path — a real
test module, the real CliRunner harness, and the real binary against this
repo's own plan — while the flag's only behaviour is its refusals. It
deliberately does **not** stub a silently-passing gate, so a half-finished
phase 1 cannot be mistaken for a working one.

Phase 5 exists because `.claude/rules/explainers-currency.md` makes it owed:
`docs/explainers/01-fr-goal.md` narrates this pipeline step by step, and a
shipped-skill pipeline change plus a minor bump are both triggers. Its first
step re-renders the *unmodified* page and requires a byte-identical result
before any prose is written — the check that has already caught two separate
renderer-environment traps.

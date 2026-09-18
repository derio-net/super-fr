# Harness parity matrix

Implements `docs/superpowers/specs/2026-09-18-harness-parity-matrix-design.md`
(issue [#436](https://github.com/derio-net/super-fr/issues/436)).

## What this plan is actually fixing

Not "we lack a document about harnesses." The measured failure is that a full
`/fr-goal` run on OpenCode produced a spec, a plan, a run cursor, seven journal
decisions and a reviewed implementation **without ever asking the operator
anything** — and looked healthy the whole way. fr-goal's single operator
touchpoint was specified as an `AskUserQuestion` call, which is a Claude Code
tool; on OpenCode there was no tool to call, so the model cleared the gate and
carried on.

That is this repo's recurring failure mode — *a change that reports success
while doing nothing* — reappearing at the harness boundary. The plan therefore
buys three distinct things, in this order:

1. **Visibility that cannot rot** (phases 1–2). A declared matrix is worth
   nothing if it is transcribed by hand; #436's own table is already wrong
   about Hermes. So every hook row is checked against the actual registration
   file, in both directions, and a hook script with no row fails CI.
2. **The leak closed at its source** (phase 3). Not by translating tool names
   at sync time, which would fork one prose into three, but by making the
   canonical prose neutral and pinning it with a tripwire.
3. **A gate that says when it is not a gate** (phases 4–5). Provenance plus a
   loud notice. Deliberately not proof — see below.

## The honest limit, stated up front

Nothing here can prove a human answered a question. An agent can pass
`--answered-by operator` as easily as it can clear a gate today. What changes
is that the **default is `agent`**, so the stronger claim has to be typed
deliberately, and the claim then travels into the PR body where a human reads
it. The operator chose this over a hard refusal, because refusing without
evidence of a TTY would break every legitimate non-interactive dispatch —
vibe-kanban, CI, pods — which is the same class of context the artifact
migration gate deliberately serves with one explicit step.

We are buying auditability, not enforcement, and the spec says so in its
non-goals rather than letting a reader assume otherwise.

## Phase shape and why

| # | phase | tier | depends on |
|---|---|---|---|
| 1 | Walking skeleton: vocabulary, `parity.yaml`, `fr harness parity` render | standard | — |
| 2 | The derived check: observe, compare, tripwire | hard | 1 |
| 3 | Tool-name neutrality: vocabulary, tripwire, neutral gate prose | standard | 1 |
| 4 | Gate provenance: `answered_by`, stamp bump, migration | hard | 1 |
| 5 | Degrade loudly: detection, the notice, PR body, phase-sequence | standard | 1, 4 |
| 6 | Ship: install wiring, acceptance flips, docs, version bump, full gate | standard | 2, 3, 5 |

Phases 2, 3 and 4 all hang off phase 1 and off nothing else — they are three
independent consumers of the same vocabulary, and keeping them independent is
what lets phase 1 be a genuine skeleton rather than a prologue.

**Phase 1 is the walking skeleton** and its smoke is specific: run
`fr harness parity` **from outside the repo**, against the installed package.
`parity.yaml` lives inside `src/fr/` so hatchling ships it with no manifest
work — the same trick `fr/workflows/fr-goal.yaml` already uses — but "it ships"
is exactly the kind of claim that is true until it isn't. A repo-relative
`Path(__file__).parents[…]` would pass every in-checkout test and fail on the
first pod. So the skeleton exercises the packaged path, not the checkout path.

**Phase 2 is tiered `hard`** because the three observers are three different
kinds of evidence — JSON registration, YAML snippet parsed through
`fr.hermes.snippet_entries`, and a marker comment in TypeScript — and the
temptation to make the third one clever (parse the TS, infer the behaviour) is
the wrong call that would cost a parser to maintain forever. The marker *is*
the declaration; `bun test` covers whether the port works.

**Phase 3's tripwire is written to fail first.** It is asserted against the six
live `AskUserQuestion` occurrences before the prose is fixed, and those six are
recorded in the journal. A tripwire whose first sighting is green has proved
only that it runs.

**Phase 4 carries obligations from another rule, not from this spec.**
`RunState` is frozen and `extra="forbid"`, so adding `answered_by` is a shape
change under `.claude/rules/artifact-versioning.md`: stamp bump, registered
migration, `schema_version` on the model, and `fr migrate artifacts --yes` run
in this PR — because the moment `current_version` moves, this repo's own CI
goes red until the artifacts are migrated. That is dogfooding, and the rule
says so from experience.

**Phase 5 closes instance 1** — the original #436 report, an agent skipping
`fr-plan` — with no new hook. `fr run` already enforces order, because
`implement` declares `needs: [spec, plan]`. The fix is to make
`fr-brainstorming`, invoked standalone, start or adopt a run, so the cursor
that already works is always present. Under fr-goal a run exists and it is a
no-op, and the prose has to say that so the two paths cannot both fire.

## No manual phase

Every phase is fully agent-completable: no secrets, no UI operations, no deploy
actions, no cluster-dependent config. The spec's Test Plan is post-merge and
operator-driven by nature — its central claims are about *other harnesses*
(a live `/fr-goal` on OpenCode, one on Hermes, a standalone brainstorm on
OpenCode), which this repo's CI cannot exercise. Those ride the PR body
verbatim per fr-goal §7; they are not a back-loaded `[manual]` phase, because
nothing about them is work to be pushed to this branch.

## Acceptance rows

Five rows were born with the spec, all `not-implemented`, one per business
claim. Phases 1–5 each advance exactly one; phase 6 flips all five to `ci` with
their proving test files. `harness-parity-derived-check` is the row that
matters most — *a matrix exists* and *a matrix cannot go stale* are different
claims, and only the second one is worth having.

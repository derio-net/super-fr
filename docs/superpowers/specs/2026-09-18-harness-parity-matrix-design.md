# Harness parity — a declared matrix, derived from the wiring, with loud degradation

- **Issue:** [#436](https://github.com/derio-net/super-fr/issues/436)
- **Date:** 2026-09-18
- **Status:** designed

## 1. Problem

super-fr presents itself as harness-neutral — one engine, thin harness wiring. The wiring is
thin in very different ways per harness, and **nothing detects the difference**. A gate that is
mechanically enforced on Claude Code is prose on OpenCode and absent on Hermes, with no warning
to the operator and no test that fails.

Two confirmed classes of drift, both from #436:

**A. Hook coverage.** Ten hook scripts ship under `plugins/super-fr/hooks/`. Claude Code
registers all ten (`hooks.json`); Hermes registers four (`.hermes/config.snippet.yaml`);
OpenCode ports one, partially (`packages/fr-opencode-plugin`, edit-class tools only, no bash).
Nothing asserts that this is *intended* rather than an oversight.

**B. Claude-only tool names shipped to every harness.** `fr-goal` §1 and `fr-init` §2 both
specify their operator touchpoint as an **`AskUserQuestion`** call — a Claude Code tool. Both
sync scripts copy skills byte-for-byte, so the name rides unchanged into `.opencode/skills/`
and `.hermes/skills/`: six occurrences, not the four the issue estimated.

**The measured consequence (2026-09-18).** A full `/fr-goal` run on OpenCode + Terra against
issue #429 (PR #479) produced a spec, a plan, a run cursor, seven journal decisions and a
reviewed two-phase implementation — and **never asked the operator anything**. The run cursor
shows the gated `brainstorm` step self-resolving to `state: done`. The prompt was ruled out.
On OpenCode there is simply no tool to call, so the model proceeded.

### 1.1 The issue's own table is already stale — which is the argument

#436 lists `fr-acceptance-nag` as absent on Hermes. It is not:
`.hermes/config.snippet.yaml` registers it on `pre_llm_call`. A hand-maintained table of
per-harness wiring drifts from the wiring for exactly the reason the wiring drifts from the
claim — nobody re-derives it. **The matrix must be checked against the real registration
files, not transcribed from them.**

## 2. Goal

One declared, checked-in matrix of *surface × harness → state*, validated against the actual
registration files, reachable from any harness with no plugin installed, and consulted at
runtime so a degraded surface announces itself instead of behaving as though it fired.

### Non-goals

- **Porting the missing hooks.** Closing OpenCode's bash gap or Hermes' sentinel gap is
  separate work per surface. This spec makes each gap *declared, visible and test-pinned*;
  it does not fill them. A matrix that only admits `enforced` would be a wish-list.
- **Making an agent unable to lie.** No mechanism here can prove a human answered a question.
  §3.D deliberately buys visibility, not proof — see the risk in §4.
- **Supporting Codex or Copilot CLI.** They enter the matrix as `unsupported` rows so the
  schema is shaped to hold them, nothing more.
- **Per-harness skill prose.** The mirrors stay byte-identical to canonical (§3.C).

## 3. Design

### A. `fr.harness` — the module, the vocabulary, the data

A new package `packages/fr/src/fr/harness/`:

```
__init__.py    HARNESSES, STATES, re-exports
model.py       Surface / ParityRow / Matrix schema, parse_matrix()
parity.yaml    the declared matrix (ships in the wheel)
observe.py     read the real registration files -> observed state
check.py       declared vs observed -> findings
```

`parity.yaml` sits *inside* `src/fr/`, so hatchling's `packages = ["src/fr"]` ships it with
no manifest work — the same trick `fr/workflows/fr-goal.yaml` already uses.

**`HARNESSES`** is a closed, ordered set: `claude-code`, `opencode`, `hermes`, `codex`,
`copilot-cli`. Closed for the same reason `fr.capabilities.CAPABILITIES` is closed — a typo
becomes a validation error rather than a silently-missing column. `codex` and `copilot-cli`
are present from day one, every row `unsupported`, so adding support is a state change on
existing rows rather than a schema migration.

**`STATES`** is a closed set of five:

| state | meaning |
|---|---|
| `enforced` | a hook, tool or CLI gate mechanically blocks or fires |
| `partial` | enforced for some of the surface's scope only; `scope_note` is **required** |
| `advisory` | the behaviour is asked for in prose; nothing enforces it |
| `absent` | not present at all, and not claimed to be |
| `unsupported` | the harness is not supported; the question does not arise yet |

`partial` is the fifth state #436 did not name, and it earns its place: OpenCode's
`fr-isolation-required` port guards `edit`/`write`/`patch`/`multiedit` but **not** `bash`.
Calling that `enforced` is the exact lie this spec exists to prevent; calling it `absent`
would be a second lie in the other direction and would invite someone to "fix" a port that
already works for most of its scope.

**A row** is one surface × five harness states:

```yaml
surfaces:
  - id: fr-isolation-required
    kind: hook                       # hook | interaction
    script: fr-isolation-required.sh # hook rows only; must exist on disk
    summary: Edits to tracked source must happen inside an fr-isolation workspace.
    harnesses:
      claude-code: {state: enforced}
      opencode:
        state: partial
        scope_note: edit/write/patch/multiedit only — bash is ungated (#436)
      hermes: {state: enforced}
      codex: {state: unsupported}
      copilot-cli: {state: unsupported}
```

### B. The check is derived, not transcribed

`fr.harness.observe` reads the registration files and computes what each harness *actually*
wires, per hook script:

- **claude-code** — `plugins/super-fr/hooks/hooks.json`: a script named by any event's
  `command` is observed `enforced`, else `absent`.
- **hermes** — `.hermes/config.snippet.yaml`: same rule over `hooks.<event>[].command`,
  which is relative to `plugins/super-fr/hooks/`. Reuses `fr.hermes.snippet_entries` rather
  than re-parsing, so the two cannot disagree about what the snippet says.
- **opencode** — `packages/fr-opencode-plugin/src/index.ts`. This one is not a registration
  file but source, so observation is deliberately shallow: a script is observed non-`absent`
  iff the plugin names it in a `// super-fr-parity: <script>` marker comment. The marker is
  the declaration; grepping TypeScript for behaviour would be a parser we would then have to
  maintain. Any hook with no marker observes `absent`.

`check.py` compares observed against declared and reports a finding when they disagree,
**in both directions**:

- declared `enforced` / observed `absent` → an overclaim; the dangerous direction.
- declared `absent` / observed `enforced` → the surface was wired and the matrix not updated;
  this is the case that already exists today (`fr-acceptance-nag` on Hermes).

`partial` and `advisory` are not mechanically derivable — a hook either is registered or is
not. So for those, `check` asserts only the weaker fact the files *can* answer:
`partial` requires the script to be observed present on that harness, `advisory` requires it
to be observed absent (prose cannot be a registration), and both require a `scope_note`.

**Every shipped hook script must have a row, and every hook row must name a shipped script.**
That pairing is what makes "a test fails when a hook adds a surface without declaring its
per-harness state" true by construction rather than by diligence.

### C. Tool-name neutrality — enforced at the source, not translated at sync

#436 suggests translating tool names at sync time. **Rejected.** Both sync scripts write
`dest.write_text(src.read_text())` and six existing tripwires assert byte-identity between
canonical and mirror. Translation would fork the prose three ways, break all six, and leave
three texts to keep in agreement.

Instead the *canonical* prose goes harness-neutral, the mirrors stay byte-identical, and a
tripwire pins it: **no skill may name a harness-specific tool outside an explicitly scoped
per-harness clause.**

`fr.harness.TOOL_VOCABULARY` maps each harness to the tool names that are its own
(`AskUserQuestion`, `Skill`, `NotebookEdit`, `WorktreeCreate` … for claude-code;
`delegate_task` for hermes; `tool.execute.before` for opencode). The tripwire scans every
canonical `SKILL.md` and every mirror, and fails on any occurrence not inside a scoped clause.

A **scoped clause** is an existing, already-load-bearing shape: fr-goal §5 carries
`**Harness — dispatch:** Claude Code uses the fr-phase-executor Agent … Hermes
delegate_task(goal, context) …`. That paragraph names two harnesses' tools *and says which is
which*, so a reader on either harness is correctly served. The tripwire recognises a clause
by a `**Harness — <topic>:**` lead-in and permits any vocabulary inside it, requiring only
that every supported harness be named. Bare prose naming one harness's tool as *the* way to
do something is the failure.

fr-goal §1 and fr-init §2 are then rewritten to name the operator touchpoint neutrally —
"put every question to the operator through your harness's question surface, in one batch,
and STOP" — with the concrete tool relegated to a scoped clause.

### D. The gate: provenance and loud degradation

Neutral prose alone would not have stopped the measured failure: the OpenCode agent did not
lack instructions, it lacked a tool, and then cleared the gate anyway. Three changes:

**D.1 `fr run advance` degrades loudly.** When a `gate: operator` step blocks, `advance`
already prints the gate line. It now also detects the harness (`FR_HARNESS`, else inferred
from the environment: `CLAUDE_PLUGIN_ROOT`/`CLAUDECODE` → claude-code, `OPENCODE*` →
opencode, `HERMES*` → hermes) and consults the `operator-gate` row. When that row is not
`enforced` for the detected harness, it prints the degradation notice:

```
gate: your harness (opencode) has NO operator-question tool — this gate is advisory here.
      Put the questions to the operator in your reply and STOP. Clearing this gate without
      asking is recorded as `answered_by: agent` and reported in the delivered PR.
```

Loud is the point. The failure mode this repo keeps producing is *a change that reports
success while doing nothing*; an advisory gate that looks identical to an enforced one is
that failure mode wearing a gate's clothes.

**D.2 `fr run resolve` records provenance.** A new `--answered-by operator|agent` option,
**defaulting to `agent`**. The default is the conservative one on purpose: an unmodified
caller records the weaker claim, so nothing is silently upgraded to "a human answered".
`StepRecord` gains `answered_by: Literal["operator","agent"] | None = None`, set only when a
gate is cleared — the same shape as the existing `gate: cleared` field, which is likewise an
authorization rather than a lifecycle position.

Because `RunState` is `extra="forbid"`, this is a **shape change** under
`.claude/rules/artifact-versioning.md`: it ships a `run` stamp bump, a registered migration,
and — since this moves the `run` kind's `current_version` past 1 — the optional defaulted
`schema_version: int = 1` on `RunState` that the rule requires in the same PR.

**D.3 `fr run check` and the PR body surface it.** `fr run check` reports every gate cleared
with `answered_by: agent` as a finding. fr-goal's `deliver` step includes that list in the PR
body under an "Operator gates" heading, so a run that never asked arrives at review saying so
in its own words.

### E. Interaction surfaces, and what closes instance 1

Beyond the ten hook rows, the matrix carries `kind: interaction` rows. Four at ship:

| surface | claude-code | opencode | hermes | codex / copilot |
|---|---|---|---|---|
| `operator-gate` | `enforced` | `advisory` | `advisory` | `unsupported` |
| `phase-sequence` | `enforced` | `enforced` | `enforced` | `unsupported` |
| `subagent-dispatch` | `enforced` | `absent` | `enforced` | `unsupported` |
| `status-line` | `enforced` | `absent` | `absent` | `unsupported` |

`phase-sequence` is **instance 1** of #436 — an agent finishing `fr-brainstorming` and going
straight to production code, skipping `fr-plan`. The matrix picks the mechanism the issue
itself proposed: `fr run` is harness-neutral and already enforces order, because
`implement` declares `needs: [spec, plan]` and the cursor will not advance past a step whose
inputs no artifact satisfies. It is `enforced` on all three supported harnesses **when the
work is driven through a run** — which is precisely why `fr-brainstorming`, invoked
standalone, now starts or adopts one. A brainstorm that creates a cursor cannot be followed
by an implementation that never acquired a plan; a brainstorm that creates nothing can.

This is the honest reading of "closed by whichever mechanism the matrix picks": not a new
hook, but making the neutral mechanism that already works the one that is always present.

### F. `fr harness parity` — the operator surface

```
fr harness parity                 # render the matrix (table; --format json)
fr harness parity --check         # declared vs observed; exit 1 on drift
fr harness parity --harness opencode   # one column, with every scope_note
```

Render reads only the shipped `parity.yaml`, so it works on a pod with no plugin installed.
`--check` needs the registration files and therefore a super-fr checkout; run outside one it
says so and exits 0 rather than inventing a verdict — the `fr acceptance check` precedent.

`fr harness parity` is **not** mirrored to OpenCode or Hermes, for the same reason shipped
workflow manifests are not: it is a CLI surface every harness drives identically, so there is
nothing harness-specific to generate.

## 4. Risks and mitigations

| Risk | Mitigation |
|---|---|
| **The matrix becomes another stale table.** The exact failure it exists to fix. | §3.B derives every hook row from the registration files; a row and its script must pair up. The states that cannot be derived (`partial`, `advisory`) still get the weaker derived assertion plus a mandatory `scope_note`. |
| **Provenance is theatre — an agent can pass `--answered-by operator`.** | Accepted and stated (§2 non-goals). The value is that the *default* is `agent`, so the lie must be typed deliberately, and §3.D.3 surfaces it in the PR where a human reads it. Hard refusal was rejected: it breaks vibe-kanban, CI and pod dispatch, the same contexts the artifact-migration gate deliberately serves with one explicit step. |
| **OpenCode observation via marker comments can rot** — the comment stays after the code is deleted. | The marker is only trusted to say "this hook is ported"; the per-harness `bun test` job covers whether the port works. A marker with no matching `EDIT_TOOLS`-class registration is a review concern, not a silent pass: `check` requires the marker's script to exist on disk. |
| **Harness detection guesses wrong**, printing a degradation notice on a harness that has the tool. | Detection is `FR_HARNESS` first, inference second, and an *unrecognised* environment prints the notice rather than suppressing it — fail loud, matching the isolation gate's fail-closed posture. A wrong notice costs one confusing paragraph; a missing one costs a silent skipped gate. |
| **`schema_version` on `RunState` strands in-flight runs.** | The migration is registered and the artifact-versioning rule's gate runs it; `fr run adopt` already reconstructs a cursor from disk for work that predates the field. |

## 5. Test Plan (post-merge, operator-driven)

The matrix's central claims are about *other harnesses*, which CI on this repo cannot
exercise. These are owed after merge:

1. **OpenCode, the measured failure.** Run `/fr-goal` against a small issue on OpenCode.
   Confirm `fr run advance` prints the degradation notice at `brainstorm`, that the agent
   stops and asks in its reply, and that if it clears the gate anyway the PR body carries the
   `answered_by: agent` line. This is the direct regression test for #436 instance 2.
2. **Hermes.** Same run via `delegate_task`. Confirm the notice appears and the four
   registered hooks still fire (`fr hermes install` unchanged by this PR).
3. **Instance 1.** On OpenCode, invoke `fr-brainstorming` standalone, approve the design,
   then instruct "implement it test-driven" in the same turn. Confirm the run cursor exists
   and that reaching implementation without a plan is refused.
4. **Drift detection, live.** Add a hook registration to `.hermes/config.snippet.yaml`
   without touching `parity.yaml`; confirm `fr harness parity --check` fails naming it.
   Revert.
5. **`fr harness parity` off a checkout.** Run it on a pod from the installed wheel; confirm
   render works and `--check` declines cleanly.

## Implementation Plans

- `docs/superpowers/plans/2026-09-18-harness-parity-matrix/`

## References

- Issue [#436](https://github.com/derio-net/super-fr/issues/436) — both instances
- `docs/superpowers/implemented/specs/2026-08-14-workflow-shapes-and-workitem-dispatch-design.md` — `fr run`, gates, capability closure
- `docs/superpowers/implemented/specs/2026-07-23-hermes-agent-compat-design.md` — the Hermes port
- `.claude/rules/artifact-versioning.md` — the obligation §3.D.2 incurs
- `packages/fr-opencode-plugin/README.md` — the OpenCode port's scope

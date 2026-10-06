# Model bindings survive provider churn — design

**Date:** 2026-10-06
**Slug:** `2026-10-06-model-binding-churn`
**Status:** design (fr-goal, batch `model-bindings`)
**Repo:** `derio-net/super-fr` (single-repo change)
**Issues:** super-fr#591 — one PR

## 1. Goal

A tier binding that names a model the provider no longer serves must be caught
before it fails a dispatch, and replaced by a rule rather than by luck:

1. **Probe live.** fr asks the provider whether a bound model still answers. It
   does this when a binding is set, when a run starts, and before a phase is
   dispatched. The catalogue's `status` field is never read as availability.
2. **Fall back by family, then by tier.** A dead model is replaced by its
   same-family successor when one is live. Otherwise fr picks a live model by tier
   position and cost. When neither rule finds one, fr refuses loudly.
3. **Ask when someone can answer, decide when nobody can.** On a terminal and at
   fr-goal's question gate, fr proposes and the operator chooses. Mid-run, before a
   dispatch, fr decides by the same rules, records the choice in the run journal and
   says so loudly.
4. **Offer upgrades, never apply them.** A newer model in a family that is still
   live is an offer. It is listed and asked about, and never applied unasked.

### Non-goals

- **Live probing on Claude Code and Hermes.** The operator chose OpenCode only.
  Claude Code cannot be probed from package source: `claude -p` is forbidden there
  (`tests/unit/test_tripwire_claude_p.py`, rule `no-claude-p-batch`). Its Agent tool
  also takes family aliases, so churn there mostly reaches the orchestrator's own
  `--model`. Hermes has no probe surface on the operator's hosts. Both report
  `unprobed`, and nothing substitutes their bindings.
- **Triage batch launch** (`fr triage batch dispatch`). It resolves an orchestrator
  model for the herdr runner, but herdr supports only Claude Code today
  (`packages/fr-herdr/src/fr_herdr/runner.py:97`), which is unprobed.
- **A substitution ledger outside runs.** The operator chose the run journal as the
  only record. Outside a run, a substitution leaves only its loud stderr line.
- **Rewriting a repo-layer binding** (`docs/superpowers/models.yaml`). That file is
  a tracked contract, so fr refuses rather than editing it (R9).

## 2. Background (verified against the code and a live provider)

- **Bindings are unchecked strings.** `fr.models.set_binding`
  (`packages/fr/src/fr/models.py:105`) writes whatever `fr models set`
  (`packages/fr/src/fr/commands/models_cmd.py:94`) passes it. The command then
  materialises OpenCode agent files through `fr.opencode_agents.materialize_agents`
  (`packages/fr/src/fr/opencode_agents.py:145`). Resolution is repo over user, in
  `fr.models.resolved_config` (`models.py:70`).
- **Runs read bindings without checking them.** `_unbound_tiers`
  (`packages/fr/src/fr/commands/run_cmd.py:3347`) puts the unbound phase tiers into
  every agent-step brief (gh#538). The brief is built by `_build_brief` (`run_cmd.py:3305`; key at `:3343`) for flat, grouped and gated steps alike, and `tests/unit/test_run_cli.py:1095` pins its exact key set. `_orchestrator_model_notice` (`run_cmd.py:3473`) warns
  when the session model differs from the `orchestrator` binding, at `start`
  (`run_cmd.py:4450`) and at every `advance` (`run_cmd.py:5047`). A grouped
  member's dispatch is opened in `_advance_group` (`run_cmd.py:4071`). The unit is
  marked running at `:4174`, `_open_dispatch` is called at `:4194` with
  `tier=_dispatch_tier(repo_root, state, _effective_tier(member, step), phase_n)`,
  and the brief is printed by `_print_member_dispatch` (`run_cmd.py:4012`). A flat
  `kind: agent` step is dispatched on a second path (`run_cmd.py:5201-5223`,
  `_open_dispatch(..., tier=step.tier)`). The shipped `spec-review` step uses that
  path with `tier: hard` (`plugins/super-fr/workflows/fr-goal.yaml:85-86`), and on
  OpenCode its reviewer is materialised per tier just as the phase executor is.
- **Interactivity is already defined once.** `fr.artifacts.trigger.is_interactive`
  (`packages/fr/src/fr/artifacts/trigger.py:280`) requires a TTY on stdin and
  stdout, no CI marker, and no truthy `FR_NON_INTERACTIVE` (`trigger.py:295`). An
  agent's shell never passes it.
- **Advance commits through `_RunWrites`** (`run_cmd.py:163`). `note()` adds a path
  to the command's single commit. Plan-journal entries are appended by
  `fr.journal.model.append_journal_entry` (`packages/fr/src/fr/journal/model.py:576`).
- **A live probe on OpenCode** was measured on 2026-10-06 against a GitHub Copilot
  provider:
  - `opencode run --pure --format json -m <provider/model> "<prompt>"` answers a
    live model with a `text` event, in 2–5 s. The cost is about $0.03 for a small
    model, almost all of it a cache write of OpenCode's system prompt.
  - It exits **0 even when the model fails**. The JSON stream then carries
    `{"type":"error","error":{"name":"UnknownError",...}}`, whether the model is
    retired or never existed.
  - The real cause appears only on stderr with `--print-logs --log-level ERROR`:
    `ProviderModelNotFoundError: Model not found: github-copilot/gpt-6-sol. Did you
    mean: gpt-6.1-sol?`.
  - The issue's earlier capture shows the other retirement shape: the model is still
    in the catalogue, marked `"status": "active"`, but the provider answers
    `Error: The requested model is not supported.`
- **The catalogue gives lineage, not availability.** `opencode models <provider>
  --verbose` prints, for each model, a `provider/id` line followed by a JSON object.
  That object carries `family`, `release_date`, `cost.input`, `cost.output` and
  `capabilities.toolcall`. A model can leave the catalogue (`gpt-6-sol` has, today).
  It can also stay in it after the provider stops serving it (`gpt-5.6-luna`, in
  #591).
- **This machine has a dead binding right now.** The operator's OpenCode
  `orchestrator` binding is `github-copilot/gpt-6-sol`, which fails as shown above.
  `gpt-6.1-sol` (family `gpt-sol`) is live.

## Requirements

R1. `fr models set --harness opencode` probes the model live before persisting it.
An inconclusive probe warns and persists. `--no-probe` skips the probe and says
that it did. For any other harness, `set` persists without probing and prints `not
probed (live probing covers opencode only)`.

When the provider will not serve the model, the outcome depends on whether anyone
can answer:

- **On a terminal** (`is_interactive()`), `set` asks. It shows the provider's error
  and offers R4's proposal (default yes). A yes persists the proposal instead; a no
  persists nothing and exits 2.
- **Off a terminal**, it refuses (exit 2), printing the provider's error and the
  proposal, if any.

R2. A probe's verdict is one of `live`, `dead` or `unknown`. `dead` requires positive
provider evidence that the model is not served (model-not-found or not-supported).
Every other failure is `unknown`, including a timeout, a missing CLI, an auth error
or a server error. The catalogue's `status` field is never consulted.

R3. Probe verdicts are cached per (harness, model) under `$HOME/.cache/fr/models/`
for 6 hours. `fr models set` and `fr models check` always probe fresh. Whenever fr
reads a bound model's catalogue entry, it keeps the entry as that model's last-known
snapshot. The snapshot is what lets fr reason about a model after it leaves the
catalogue.

R4. A replacement for a dead binding is chosen by fixed rules, tried in order. The
first rule that yields a live model wins:

1. **Family rule.** Same provider, same `family` (taken from the catalogue entry, or
   else the snapshot), a newer `release_date`, tool-calling and live. The newest such
   model wins.
2. **Tier rule.** Phase tiers only, never `orchestrator`. The candidate is
   tool-calling, live and from the same provider. It is distinct from the
   `orchestrator` binding and from every other bound tier. After substitution, the
   bound tiers' known prices must still satisfy `mechanical` ≤ `standard` ≤ `hard`.
   Among candidates, the price nearest the dead model's wins, then the newest. When
   the dead model's price is unknown, the newest wins.
3. **Provider hint.** When the dead model has no catalogue entry and no snapshot, so
   that neither rule above has inputs, fr uses the model named in the probe's
   `Did you mean: <id>?` (same provider), if that model is live.

Every `Choice` carries its rule and `price_ratio` (the new price over the dead one,
or `None` when either price is unknown). fr probes at most 5 candidates per choice.
If no rule yields a model, there is no replacement.

**Autonomous picks** (R8) are bounded further. Only the family and tier rules
qualify, and `price_ratio` must be known and ≤ 2. A proposal shown to an operator
(R1, R5, R7) carries no such bound; it shows its ratio, and `unknown` when the ratio
is unknown.

R5. `fr models check [--harness <h>]` reports one line per binding (each phase tier
plus `orchestrator`) for every bound harness. Each line gives the verdict (`live`,
`dead`, `unknown` or `unprobed`), and for a dead binding the proposed replacement,
the rule that chose it and the price ratio. For a live binding it lists any upgrade
offer (R12).

On a terminal (`is_interactive()`: a TTY on both streams, no CI marker, no truthy
`FR_NON_INTERACTIVE`), it asks per dead binding (default yes) and per offer (default
no) whether to apply. An accepted change is persisted and materialised exactly as
`fr models set` would do it. Off a terminal it only reports, and exits 1 when any
binding is dead.

R6. `fr run start` checks the detected harness's bindings: the `orchestrator` binding
and every phase tier. It prints one loud line per dead binding and per offer, and
never blocks.

Every agent-step brief carries two new keys, `dead_bindings` and `binding_offers`.
They are lists only in the brief of a step with `gate: operator` on a probed harness:

- `dead_bindings`: `{tier, model, verdict, proposal: {model, rule, price_ratio} |
  null, reason}`;
- `binding_offers`: `{tier, model, offer}`.

Otherwise both keys are `null`.

R7. fr-goal's question round asks one question per `dead_bindings` entry, with its
proposal as the recommended option, and one per `binding_offers` entry, with "keep
the current model" recommended. Each answer is recorded as a brainstorm `decision`.
For an accepted change, the decision's body names the old model, the new model, the
reason (`retired` or `upgrade`), `decider: operator` and the rule, and the change is
applied with `fr models set`.

R8. Before `fr run advance` dispatches any `kind: agent` unit on OpenCode, it checks
the binding for the tier the dispatch record will carry. That is the tier passed to
`_open_dispatch`, on both the grouped path (`_dispatch_tier(… _effective_tier …)`)
and the flat path (`step.tier`). A unit with no tier, or one whose tier resolves to
`None`, is not checked. A cached verdict counts.

- **Dead, with an autonomous pick under R4:** fr rewrites the user `models.yaml` and
  materialises the agent files. It appends a `decision` entry to the run journal
  (R11) carrying the same five fields as R7, with `decider: autonomous`. It commits
  the entry with the cursor move, prints a loud `SUBSTITUTED` line, and then prints
  the brief.
- **Dead, with no autonomous pick:** exit 2, no brief, and the unit is not opened.
  The message names the candidates fr tried, any operator-only proposal, and the
  `fr models set` line to fix it.
- **Unknown:** fr warns and dispatches.

R9. When the dead binding comes from the repo layer (`docs/superpowers/models.yaml`),
fr never rewrites it. `advance` refuses (exit 2) and names the file.

R10. Claude Code and Hermes bindings are reported as `unprobed`, and nothing
substitutes them.

R11. Every substitution, whether the operator or fr decided it, prints one loud
stderr line naming old → new, the reason, the decider and the rule.

Inside a run, the **run journal** records it. That is the run's spec journal while
the run has no plan artifact, and its plan journal once it has one. R7 and R8 say
how. Outside a run, the stderr line is the only record.

A substitution is recorded if and only if it is applied: R8's write order (§C)
guarantees that no failure leaves one without the other.

R12. An upgrade offer is a live binding's same-family model that is newer, live and
tool-calling. It is never applied without an operator's yes, from R5's prompt or
R7's question.

## Design

### A. The `fr.bindings` package (R2–R4, R10, R12)

This is a new package, `packages/fr/src/fr/bindings/`. It is a sibling of
`fr/models.py`, which stays the config layer, unchanged except for one new lookup
(below).

**`catalogue.py`**

- `CatalogueEntry` is frozen: `id`, `provider`, `family`, `release_date`, `price`,
  `toolcall`.
- The parser reads the `opencode models <provider> --verbose` text: a
  `provider/id` header line, then a JSON object. A malformed block is skipped and
  counted, and the parse never raises.
- `price` is `cost.input + cost.output`, or `None` when absent.
- Snapshots live in `$HOME/.cache/fr/models/snapshots.json`.

**`probe.py`**

- `Verdict` is `Literal["live", "dead", "unknown", "unprobed"]`. `ProbeResult` is
  `(verdict, detail, hint, at)`, where `hint` is the provider's `Did you mean: <id>`,
  if any.
- The `Prober` Protocol is `probe(model) -> ProbeResult` plus
  `catalogue(provider) -> list[CatalogueEntry]`.
- `OpenCodeProber` runs `opencode run --pure --print-logs --log-level ERROR
  --format json -m <model> "Reply with exactly: OK"` with a 60 s timeout. Its cwd is
  a fresh temporary directory, so `fr usage` never attributes the probe session to a
  run.
- Classification: any `text` event means `live`. Stderr matching
  `ProviderModelNotFoundError` or `model is not supported` (case-insensitive) means
  `dead`, with that line as the detail. Anything else is `unknown`.
- `prober_for(harness)` returns `None` for every harness except `opencode`.
- The cache lives in `$HOME/.cache/fr/models/probes.json`, with a 6 h TTL and a
  `fresh=True` bypass. The clock is passed in.
- All subprocess calls go through one seam (`run_opencode`), so tests inject a fake.

**`choose.py`** is pure: no clock, no subprocess, no file I/O.

- `choose_replacement(tier, dead, bindings, entries, snapshot, hint, probe) ->
  Choice | NoChoice` implements R4's rules in order. `probe` is a callable, so
  candidates are probed lazily and at most 5 times.
- `Choice` is `(model, rule: "family" | "tier" | "hint", price_ratio)`. `NoChoice`
  is `(reason, tried)`.
- `is_autonomous(choice) -> bool` is R4's bound: rule `family` or `tier`, and a
  known `price_ratio` ≤ 2. Callers decide what to do with a choice through this
  one predicate.
- `offers(bindings, entries, probe)` implements R12.
- Ordering is checked only between tiers whose prices are known. A neighbour with
  an unknown price constrains nothing.

**`health.py`**

- `check_bindings(harness, repo_cfg, user_cfg, prober, *, tiers=None, fresh) ->
  list[BindingHealth]` is the one function that R1, R5, R6 and R8 call. It probes
  each requested binding, chooses for each dead one and collects offers.
- Each `BindingHealth` records which layer the binding came from (`repo` or
  `user`), for R9.
- `fr.models` gains `binding_layer(harness, tier, *, repo_cfg, user_cfg)`, a lookup
  beside `resolved_config` that follows the same falsy-is-unbound rule.

**Tests that pin R2.** `tests/unit/test_bindings_probe.py` holds a fixture in which
the catalogue entry says `"status": "active"` while the probe stderr says not
supported. The verdict must be `dead`, and no code path reads `status`.

### B. `fr models` (R1, R5, R11)

`models_cmd.py` changes:

- `set` gains `--no-probe`. For `opencode` it probes fresh before `set_binding` and
  behaves as R1 says on and off a terminal.
- A new `check` command implements R5.
- Every accepted change, in `set` or in `check`, goes through one helper
  (`_apply_binding`): `set_binding`, then `materialize_agents`, then
  `_report_changes`, then R11's line.
- The module docstring lists `check`.

### C. Run integration (R6–R9, R11)

In `run_cmd.py`:

- **`start_cmd`.** After the orchestrator notice, it calls `check_bindings` for the
  detected harness (cache allowed) and prints one yellow line per dead binding and
  per offer.
- **`_build_brief`.** It adds `dead_bindings` and `binding_offers`: computed from
  `check_bindings` (cache allowed) when `step.gate == "operator"` and the harness is
  probed, and `null` otherwise. The key-set pin in `test_run_cli.py:1095` grows by
  these two keys. Brief keys are not artifact fields, so no stamp moves.
- **One pre-dispatch guard, `_guard_dispatch_binding(repo_root, state, step_id,
  key, tier)`.** It is called on both dispatch paths, before anything is marked
  running or saved, with the exact tier `_open_dispatch` will receive:
  - in `_advance_group`, before `items[pending] = "running"` (`:4174`);
  - on the flat path, before its `_open_dispatch` (`:5201`).

  It returns quietly when the harness is not OpenCode, when the tier is `None`, or
  when the verdict is `live`. On `unknown` it prints a yellow warning and returns.
  On `dead`:
  - **Repo layer, or no autonomous choice (R9, R8):** it raises `typer.Exit(2)`
    with the reason, the tried list, any operator-only proposal and the
    `fr models set` line. Nothing has been opened or saved.
  - **Autonomous choice:** it applies the substitution in an order that keeps
    "recorded iff applied" (R11):
    1. It resolves the run-journal path (plan journal when the run has a plan
       artifact, else spec journal). It calls `_RunWrites.remember(path)`, appends
       `JournalEntry(kind="decision", id="model-substitution-<tier>-<n>")` with the
       five fields and the price ratio, and calls `note()` so the cursor commit
       carries it.
    2. It keeps the user `models.yaml` bytes, calls `set_binding` and
       `materialize_agents`, and prints `SUBSTITUTED …` in bold yellow.
    3. If step 2 raises, it restores the `models.yaml` bytes and re-materialises
       from them. It restores the journal file to its remembered bytes, prints
       `SUBSTITUTION NOT APPLIED old → new: <error>` and exits 2.

    If the cursor commit itself fails after step 2, the journal entry is still on
    disk beside the applied binding, uncommitted. The existing "NOT committed"
    reporting of `_RunWrites` names it, so the pair stays consistent on disk.
- **The operator path in a run.** The operator's answer at the brainstorm gate is a
  `decision` in the brainstorm record (R7), and the `fr models set` the orchestrator
  runs afterwards prints R11's line. No new run artifact is needed.

### D. Skill, docs, parity (R7, R10)

- **`plugins/super-fr/skills/fr-goal/SKILL.md` §1.** Beside the model-per-tier
  sentence, add one: "a question per entry of the brief's `dead_bindings`
  (recommended: its `proposal`) and per `binding_offers` entry (recommended: keep);
  each answer is a `decision` whose body names old, new, reason, `decider: operator`
  and rule, and an accepted change is applied with `fr models set`".
- **Mirrors.** Regenerate them with `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- **`harness/parity.yaml`.** Add a `kind: interaction` row, `model-binding-probe`:
  - `opencode: partial`, with a scope note that the classifier and the mid-session
    agent-file pickup are proven only against a stub until
    `model-binding-live-opencode` runs;
  - `claude-code` and `hermes`: `absent`, each with a scope note;
  - `codex` and `copilot-cli`: `unsupported`.
- **`AGENTS.md`.** Add a one-paragraph `fr.bindings` entry under `fr`.
- **`docs/explainers/01-fr-goal.md`.** Update it only if it describes the
  model-per-tier question. If it does, regenerate the `.html` per
  `.claude/rules/explainers-currency.md`.
- **Change fragment.** Add `.changes/feat-batch-model-bindings.yaml`,
  `bump: minor`.

## Risks

- **Provider message drift.** The `dead` classifier matches two phrases. If a
  provider changes its wording, a dead model reads as `unknown`, which warns rather
  than silently dispatching. The error is safe, but it is not caught. Captured
  fixtures pin both shapes today (RFC 2606 names for anything third-party).
- **Mid-session agent-file pickup is unproven.** R8 rewrites
  `fr-phase-executor-<tier>.md` while the orchestrating OpenCode session is running.
  It assumes the next task dispatch reads the new `model:`. No measurement backs
  this yet. If OpenCode caches agent definitions per session, the substitution is
  recorded and announced while the old model still runs. The live row
  `model-binding-live-opencode` is the proof: it checks the served model in
  `opencode.db` after a mid-session rewrite. The parity row stays `partial` until
  then.
- **Probe cost.** A run start probes up to four bindings and up to four offers: a
  few cents up to about $0.50, cached for 6 h. That cost is stated rather than
  hidden.
- **OpenCode's CLI shape.** OpenCode's CLI is not versioned for fr. The parser
  tolerates malformed blocks, and a missing `opencode` gives `unknown`, never a
  crash.

## Test Plan

Post-merge rows only. The pre-merge walk is set out in `## Verification`.

1. `model-binding-live-opencode` (`live`). On a real OpenCode install, bind
   `standard` to a model the provider no longer serves:
   - **Interactive:** `fr models check` on a terminal proposes the same-family
     successor, and accepting it materialises the agent file.
   - **At the gate:** an `/fr-goal` brainstorm brief lists the dead binding, and
     the question round asks it.
   - **Unattended:** with the binding dead again and the run at `implement`,
     `fr run advance` substitutes autonomously, the plan journal carries the
     decision, and the phase executor dispatched in that same, already-running
     session runs on the new model (verified in `opencode.db`). This step is what
     proves the mid-session agent-file pickup.

## Verification

This PR is verified by its own `candidate` walk at `deliver`. Each scenario puts a
stub `opencode` on `PATH`, scripted per model, so the walk is deterministic and
spends nothing:

1. `tests/scenarios/model-binding-set-probe.sh` (row `model-binding-set-probe`) runs
  off a terminal. Stub states: live; retired but still in the catalogue as
  `"status": "active"` (refused); a server error (warns and persists);
  `--no-probe`.
2. `tests/scenarios/model-binding-replacement.sh` (row `model-binding-replacement`)
  drives `fr models check` off a terminal. It covers the family successor, the tier
  rule keeping order and distinctness, a candidate above 2× shown as operator-only,
  the provider hint for a model with no entry and no snapshot, and no replacement.
3. `tests/scenarios/model-binding-check.sh` (row `model-binding-check-report`) covers
  all four verdicts, an offer listed and not applied, and exit 1 on a dead binding.

The `status: active` pin also lives in `tests/unit/test_bindings_probe.py` (§A).

strategy: candidate
- model-binding-set-probe: candidate
- model-binding-replacement: candidate
- model-binding-check-report: candidate
- model-binding-probe-cache: none — TTL, fresh bypass and snapshot fallback need a controllable clock and cache dir; unit tests over `fr.bindings.probe`/`catalogue` with an injected clock cover it in CI
- model-binding-live-opencode: live — only a real provider retiring a real model proves the probe's classifier and the mid-session agent-file pickup in opencode.db end to end
- model-binding-run-integration: none — needs a run cursor at `implement` and the brainstorm gate; unit tests over `start_cmd`, `_build_brief` and `_guard_dispatch_binding` on both dispatch paths with a fake prober cover it in CI

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-model-binding-churn | `derio-net/super-fr` | `2026-10-06-model-binding-churn` | — |

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
  (`packages/fr/src/fr/commands/models_cmd.py:96`) passes it. The command then
  materialises OpenCode agent files through `fr.opencode_agents.materialize_agents`
  (`packages/fr/src/fr/opencode_agents.py:145`). Resolution is repo over user, in
  `fr.models.resolved_config` (`models.py:67`).
- **Runs read bindings without checking them.** `_unbound_tiers`
  (`packages/fr/src/fr/commands/run_cmd.py:3347`) puts the unbound phase tiers into
  every flat brief (gh#538). `_orchestrator_model_notice` (`run_cmd.py:3473`) warns
  when the session model differs from the `orchestrator` binding, at `start`
  (`run_cmd.py:4450`) and at every `advance` (`run_cmd.py:5047`). A grouped
  member's dispatch is opened in `_advance_group` (`run_cmd.py:4071`, the
  `_open_dispatch` call near `run_cmd.py:4196`) and printed by
  `_print_member_dispatch` (`run_cmd.py:4012`).
- **Interactivity is already defined once.** `fr.artifacts.trigger.is_interactive`
  (`packages/fr/src/fr/artifacts/trigger.py:280`) requires a TTY on stdin and stdout
  and no CI marker. An agent's shell never passes it.
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

R1. `fr models set --harness opencode` probes the model live before persisting it. A
model the provider will not serve is refused (exit 2) with the provider's error and
the proposed replacement, if any. An inconclusive probe warns and persists.
`--no-probe` skips the probe and says that it did. For any other harness, `set`
persists without probing and prints `not probed (live probing covers opencode
only)`.

R2. A probe's verdict is one of `live`, `dead` or `unknown`. `dead` requires positive
provider evidence that the model is not served (model-not-found or not-supported).
Every other failure is `unknown`, including a timeout, a missing CLI, an auth error
or a server error. The catalogue's `status` field is never consulted.

R3. Probe verdicts are cached per (harness, model) under `$HOME/.cache/fr/models/`
for 6 hours. `fr models set` and `fr models check` always probe fresh. Whenever fr
reads a bound model's catalogue entry, it keeps the entry as that model's last-known
snapshot. The snapshot is what lets fr reason about a model after it leaves the
catalogue.

R4. A replacement for a dead binding is chosen by fixed rules:

- **Family rule.** Same provider, same `family`, a newer `release_date`, tool-calling
  and live. The newest such model wins.
- **Tier rule.** Used only when the family rule finds nothing. The candidate is
  tool-calling, live and from the same provider. It is distinct from the
  `orchestrator` binding and from every other bound tier. After substitution, the
  prices of the bound tiers must still satisfy `mechanical` ≤ `standard` ≤ `hard`.
  Among candidates, the price nearest the dead model's wins, then the newest.

An autonomous pick costs at most 2× the dead model's price (catalogue input plus
output). fr probes at most 5 candidates per substitution. If the dead model has no
catalogue entry and no snapshot, fr makes no autonomous pick, and asking is the only
path. If neither rule finds a model, there is no replacement.

R5. `fr models check [--harness <h>]` reports one line per binding (each phase tier
plus `orchestrator`) for every bound harness. Each line gives the verdict (`live`,
`dead`, `unknown` or `unprobed`), and for a dead binding the proposed replacement and
the rule that chose it. For a live binding it lists any upgrade offer (R12). On a
terminal it asks, per dead binding and per offer, whether to apply. An accepted
proposal is persisted and materialised exactly as `fr models set` would do it. Off a
terminal it only reports, and exits 1 when any binding is dead.

R6. `fr run start` checks the detected harness's bindings: the `orchestrator` binding
and every phase tier. It prints one loud line per dead binding and per offer. The
brief of every step with `gate: operator` carries `dead_bindings` and
`binding_offers`. Each is a list of `{tier, model, verdict, proposal: {model, rule} |
null, reason}` or `{tier, model, offer}`, or `null` when the harness is unprobed or
undetected.

R7. fr-goal's question round asks one question per `dead_bindings` entry, with its
proposal as the recommended option, and one per `binding_offers` entry, with "keep
the current model" recommended. Each answer is recorded as a brainstorm `decision`.
An accepted change is applied with `fr models set`.

R8. Before `fr run advance` prints a phase's dispatch brief on OpenCode, it checks
that phase's tier binding. A cached verdict counts.

- **Dead, with a pick under R4:** fr rewrites the user `models.yaml` and materialises
  the agent files. It then appends a plan-journal `decision` entry naming the old
  model, the new model, the reason (`retired`), the decider (`autonomous`) and the
  rule. The entry is committed in the same commit as the cursor move. fr prints a
  loud `SUBSTITUTED` line and then prints the brief.
- **Dead, with no pick:** exit 2, no brief, and the unit is not opened. The message
  names the candidates fr tried and the `fr models set` line to fix it.
- **Unknown:** fr warns and dispatches.

R9. When the dead binding comes from the repo layer (`docs/superpowers/models.yaml`),
fr never rewrites it. `advance` refuses (exit 2) and names the file.

R10. Claude Code and Hermes bindings are reported as `unprobed`, and nothing
substitutes them.

R11. Every substitution, whether the operator or fr decided it, prints one loud
stderr line naming old → new, the reason, the decider and the rule. Inside a run,
the run journal records it, as R7 and R8 describe. Outside a run, that line is the
only record.

R12. An upgrade offer is a live binding's same-family model that is newer, live and
tool-calling. It is never applied without an operator's yes, from R5's prompt or
R7's question.

## Design

### A. The `fr.bindings` package (R2–R4, R10, R12)

This is a new package, `packages/fr/src/fr/bindings/`. It is a sibling of
`fr/models.py`, which stays the config layer, unchanged:

- `catalogue.py`: `CatalogueEntry` (frozen: `id`, `provider`, `family`,
  `release_date`, `price`, `toolcall`). The parser reads the `opencode models
  <provider> --verbose` text: a `provider/id` header line, then a JSON object. A
  malformed block is skipped and counted, and the parse never raises. Snapshots are
  stored in `$HOME/.cache/fr/models/snapshots.json`. `price` is
  `cost.input + cost.output`, or `None` when absent.
- `probe.py`:
  - `Verdict` is `Literal["live", "dead", "unknown", "unprobed"]` and `ProbeResult`
    is `(verdict, detail, at)`.
  - The `Prober` Protocol is `probe(model) -> ProbeResult` plus
    `catalogue(provider) -> list[CatalogueEntry]`.
  - `OpenCodeProber` runs `opencode run --pure --print-logs --log-level ERROR
    --format json -m <model> "Reply with exactly: OK"` with a 60 s timeout. Its cwd
    is a fresh temporary directory, so the probe session is never attributed to a
    run by `fr usage`.
  - Classification: any `text` event means `live`. Stderr matching
    `ProviderModelNotFoundError` or `model is not supported` (case-insensitive)
    means `dead`, with that line as the detail. Anything else is `unknown`.
  - `prober_for(harness)` returns `None` for every harness except `opencode`.
  - The cache lives in `$HOME/.cache/fr/models/probes.json`, with a 6 h TTL and a
    `fresh=True` bypass.
  - All subprocess calls go through one seam (`run_opencode`), so tests inject a
    fake.
- `choose.py` is pure. It takes no clock, no subprocess and no file I/O:
  - `choose_replacement(tier, dead, bindings, entries, probe) -> Choice | NoChoice`
    implements R4. `probe` is a callable, so the tier rule can probe candidates
    lazily. `Choice` carries `(model, rule: "family" | "tier", price_ratio)`.
    `NoChoice` carries `(reason, tried)`.
  - `offers(bindings, entries, probe)` implements R12.
  - Ordering is checked only between tiers whose prices are known. A neighbour with
    an unknown price constrains nothing, and the `Choice` notes that.
- `health.py`:
  - `check_bindings(harness, cfg, prober, *, fresh) -> list[BindingHealth]` is the
    one function that R1, R5, R6 and R8 call. It probes each binding, chooses for
    each dead one and collects offers.
  - It also records which layer each binding came from (`repo` or `user`), which R9
    needs. `fr.models` gains `binding_layer(harness, tier, repo_cfg, user_cfg)`, a
    lookup beside `resolved_config`.

### B. `fr models` (R1, R5, R11)

`models_cmd.py` changes:

- `set` gains `--no-probe`. For `opencode`, `set` probes fresh before
  `set_binding`. A dead result exits 2, printing the detail and
  `check_bindings`' proposal. An unknown result prints a yellow warning, then
  persists.
- A new `check` command is added. On a terminal (`is_interactive()`) it confirms
  each dead proposal (default yes) and each offer (default no). An accepted change
  goes through the same `set_binding` + `materialize_agents` +
  `_report_changes` path as `set`, and prints R11's line with `decider=operator`.
- The module docstring lists `check`.

### C. Run integration (R6–R9, R11)

In `run_cmd.py`:

- **`start_cmd`.** After the orchestrator notice, the command calls
  `check_bindings` for the detected harness (cache allowed). It prints one yellow
  line per dead binding and per offer. It never blocks `start`.
- **Brief keys.** `_flat_brief` (the function returning the brief dict that carries
  `unbound_tiers`) adds `dead_bindings` and `binding_offers` for steps whose
  `gate == "operator"`. They are computed from `check_bindings` (cache allowed).
  These are brief keys, not artifact fields, so no stamp moves.
- **`_advance_group`.** Before the unit is marked `running`, and so before
  `_open_dispatch`, the command resolves the phase's tier (`_phase_tier`). On
  OpenCode it calls `check_bindings` for that tier only, then:
  - **Dead with a `Choice` from the user layer:** `set_binding` on the user file,
    then `materialize_agents`. It builds a `JournalEntry(kind="decision",
    id="model-substitution-<tier>-p<N>[-<k>]")` whose body names old, new,
    `reason: retired`, `decider: autonomous`, the rule and the price ratio. It
    appends that entry to the plan journal and `note()`s the path so `_RunWrites`
    commits it with the cursor. Finally it prints `SUBSTITUTED …` in bold yellow on
    stderr.
  - **Dead with `NoChoice`, or from the repo layer:** `typer.Exit(2)` with the
    reason, the tried list and the `fr models set` line. Nothing is opened or
    saved.
  - **Unknown:** a yellow warning, then the normal path.
- **The operator path in a run.** The operator's answer at the brainstorm gate is
  already a `decision` in the brainstorm record (R7). The `fr models set` the
  orchestrator runs afterwards prints R11's line. No new run artifact is needed.

### D. Skill, docs, parity (R7, R10)

- **`plugins/super-fr/skills/fr-goal/SKILL.md` §1.** Beside the model-per-tier
  sentence, add: "a question per entry of the brief's `dead_bindings` (recommended:
  its `proposal`) and per `binding_offers` entry (recommended: keep), each answer a
  `decision`, an accepted change applied with `fr models set`".
- **Mirrors.** Regenerate the mirrors with `scripts/sync-opencode.py` and
  `scripts/sync-hermes.py`.
- **`harness/parity.yaml`.** Add a `model-binding-probe` row: `opencode: enforced`;
  `claude-code` and `hermes` are `absent`, each with a scope note; `codex` and
  `copilot-cli` are `unsupported`. Its `kind` matches the existing non-hook rows.
  `fr harness parity --check` must stay green.
- **`AGENTS.md`.** Add a one-paragraph `fr.bindings` entry under `fr`.
- **`docs/explainers/01-fr-goal.md`.** Update it only if it describes the
  model-per-tier question. If it does, regenerate the `.html` per
  `.claude/rules/explainers-currency.md`.
- **Change fragment.** Add `.changes/feat-batch-model-bindings.yaml` with
  `bump: minor`.

## Risks

- **Provider message drift.** The `dead` classifier matches two phrases. If a
  provider changes its wording, a dead model reads as `unknown`, which warns rather
  than silently dispatching. The error is safe, but it is not caught. Captured
  fixtures pin both shapes today (RFC 2606 names for anything third-party).
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
     decision, and the dispatched phase executor runs on the new model (verified in
     `opencode.db`).

## Verification

This PR is verified by its own `candidate` walk at `deliver`. Each scenario puts a
stub `opencode` on `PATH`, scripted per model (live, retired-in-catalogue,
gone-from-catalogue, server error), so the walk is deterministic and spends nothing.

strategy: candidate
- model-binding-live-opencode: live — only a real provider retiring a real model proves the probe's classifier and opencode.db attribution end to end
- model-binding-run-integration: none — needs a run cursor at `implement` and the brainstorm gate; unit tests over `start_cmd`, the brief keys and `_advance_group` with a fake prober cover it in CI

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-10-06-model-binding-churn | `derio-net/super-fr` | `2026-10-06-model-binding-churn` | — |

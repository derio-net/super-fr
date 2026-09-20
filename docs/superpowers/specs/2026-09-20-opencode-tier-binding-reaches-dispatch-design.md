# A tier binding the operator answers must reach the agent OpenCode dispatches

- **Issue:** [#498](https://github.com/derio-net/super-fr/issues/498) — follow-up to
  [#494](https://github.com/derio-net/super-fr/issues/494) / PR
  [#495](https://github.com/derio-net/super-fr/pull/495)
- **Date:** 2026-09-20
- **Status:** designed

## 1. Problem

`fr-goal` §1 asks a model-per-tier question when `fr models resolve` is unbound. On
OpenCode the answer **cannot take effect in the run that asked for it**. The operator is
asked, answers, and tiering silently does not happen: no error, no warning, and a session
row that looks exactly like a working tiered dispatch.

The chain, all of it shipped by PR #495:

1. `plugins/super-fr/skills/fr-goal/SKILL.md` asks the question, and §5 dispatches
   `subagent_type: fr-phase-executor-<tier>`.
2. `scripts/install.sh` resolves each tier's model **at install time** and bakes it into
   `~/.config/opencode/agent/fr-phase-executor-<tier>.md`.
3. `fr.models.set_binding` persists `~/.config/fr/models.yaml` — **and nothing else**.
4. Nothing re-runs the installer or the sync.

So the dispatch resolves the right agent *name* against a file whose `model:` was frozen
at install. Claude Code is unaffected: it resolves at dispatch and passes the model to the
dispatch call, so a mid-run binding applies immediately. This is OpenCode-only because
OpenCode's task tool carries no model — the agent name is the only carrier, and a name's
model is a file on disk.

### 1.1 There are two failure modes, and the issue names only one

Reproduced in a sandbox before designing anything (journal discovery `x1`; the operator's
real config was not mutated):

```
installed agent, from a prior install:   model: <A>
fr models set --harness opencode --tier hard --model <B>
fr models resolve  →                     <B>
the agent OpenCode dispatches  →         model: <A>
files written by that set:               fr/models.yaml   ← and nothing else
```

- **Unbound → bound** (#498's case): no `model:` key, silent fallback to the session model.
- **Bound → rebound** (the sharper one): the agent pins the model the operator explicitly
  moved away from. A **wrong value stated confidently**, which is worse than an absent one —
  the absent case at least has a chance of being read as "no tier line".

This is load-bearing. #498's candidate fix 4 — *dispatch untiered when unresolved* — cannot
reach the stale case at all, because there the model **is** resolved, just wrong. Only
closing the loop at the binding addresses both.

### 1.2 Why this is worth more than its size

It is the failure mode this repo keeps rediscovering: **a step that reports success while
doing nothing.** Kin to #486's `file_exists` returning `False` on a malformed request, and
to the parity row that read `absent` for a capability that worked. Here the operator is
*actively asked* to make a decision and the decision is discarded.

It also compromises PR #495's own Test Plan. Asserting `agent = fr-phase-executor-<tier>`
proves the rewritten §5/§6 prose drove the dispatch; it does not prove tiering resolved.
Those two separate only if the session row's `model` is asserted as well — see §3.C.

## 2. Goal

A tier binding takes effect at the moment it is made, on every harness, and the case where
it cannot be resolved is visible in the artifact anyone actually checks.

### Non-goals

- **Per-call model on OpenCode.** It does not exist; the task tool's input is
  `{prompt, description, subagent_type, command}` (verified against 1.18.31, #494 spec
  §3.A). That absence is *why* the tier rides in the agent name.
- **Re-rendering agents from canonical at bind time.** The materialiser rewrites the
  already-installed file in place (§3.A). Re-rendering would need a checkout or marketplace
  clone, which `fr models set` cannot assume.
- **Revisiting the tier-variant design.** It is correct for OpenCode's dispatch API. The
  install-time-only resolution is the defect, not the variants.
- **Hermes or Claude Code.** Neither is affected.

## 3. Design

### A. One materialiser, two triggers

A single in-place rewrite, living beside the models config rather than inside it — a new
`fr/opencode_agents.py`. `fr.models` stays what it is, a config loader; writing OpenCode
agent files is not its job, and coupling it to one harness's on-disk layout would make the
next harness's binding path a second special case.

```
materialize_agents(config_home, *, models_cfg) -> list[Change]
```

- **Targets are discovered, not named** (spec-review `r1`). The materialiser globs
  `<config_home>/opencode/agent/*.md` and rewrites any file whose stem ends in `-<tier>` for
  a tier in `fr.types.PHASE_TIERS`. It must NOT hardcode `fr-phase-executor`: it cannot read
  `plugins/super-fr/agents/` (no checkout is guaranteed at bind time), so a literal stem
  would be a second source of truth for the agent set that nothing reconciles — and it would
  silently skip a second canonical agent the moment one exists. install.sh's regex
  (`^(.+)-(mechanical|standard|hard)\.md$`) already works this way; this is that rule,
  moved.
- **XDG-aware** via the same resolution `fr.models.default_models_path` uses
  (`$XDG_CONFIG_HOME` then `$HOME/.config`), which is what makes this testable in a sandbox
  at all.
- **Rewrites in place**, on the layout contract PR #495's generator guarantees: drop any
  top-level `model:` line, and insert the resolved one directly after `mode: subagent`.
  Unresolved → no key written (never an empty one, which OpenCode would try to resolve).
  This is install.sh's awk, moved into Python and now the only copy.
- **A missing agent file is a no-op, reported, not an error.** An operator who never opted
  into OpenCode delivery has nothing to update, and `fr models set` must not fail for them.
- **Returns what it changed**, so both callers can say so rather than claiming silently.

Two triggers:

| caller | how |
|---|---|
| `fr models set` | `models_cmd.set_cmd` calls `materialize_agents` directly after `set_binding` persists, and prints each change |
| `scripts/install.sh` | calls the new verb `fr models apply --harness opencode`; **the awk rewrite is deleted** |

**The new verb is a real cost, stated.** `install.sh` is bash and cannot call a Python
function, so "one implementation, two triggers" needs one shell-callable entry point. The
decision's own question text claimed "new CLI surface: none" — that was wrong, and the
correction is recorded in journal decision `d1` rather than designed around. It is
consistent with install.sh already invoking `fr hermes install`.

**Ordering note.** PR #495 moved OpenCode delivery after install.sh's `fr` CLI step because
it needed `fr models resolve`. That requirement is unchanged — it now needs `fr models
apply` — so the ordering assertion added in that PR still holds and still matters.

### B. An unresolvable tier dispatches the untiered agent, observably

Decision `d2`, #498's fix 4. Today an unresolved tier still dispatches
`fr-phase-executor-<tier>`, which inherits the session model — producing a session row
indistinguishable from a working tiered dispatch. Instead: when `fr models resolve
--harness opencode --tier <t>` comes back empty, dispatch the **base**
`fr-phase-executor` and journal why.

No new machinery: `fr models resolve` already prints nothing and exits 0 when unbound, which
is the whole contract this needs. The change is one clause in `fr-goal` §5's
`**Harness — dispatch:**` clause, pinned by a prose test in the shape
`tests/unit/test_fr_goal_dispatch_prose.py` already established.

This is a **complement** to §3.A, not an alternative: it covers the case the loop cannot
close (no binding exists at all), while §3.A covers both cases where one does.

### C. The acceptance row I shipped overclaiming

Decision `d3`.

- **`opencode-subagent-dispatch`** (shipped `skipped` in PR #495) gains *"and the session
  row's model matches the phase tier's binding"*. Its current text reads as evidence for
  tiering that its evidence never gathered — the live row proved a parented child session
  under the right agent *name*, which is a different claim.
- **`opencode-tier-binding-reaches-dispatch`** is new: a binding set *after* install reaches
  the agent OpenCode dispatches.

The overclaim is corrected in the same PR that makes it true.

## 4. Risks

- **Writing outside the repo from a config command.** `fr models set` gains a side effect on
  `~/.config/opencode/`. Mitigated by scope: only `fr-phase-executor-*` files, only the
  `model:` line, only files that already exist, and every change reported. An operator who
  does not use OpenCode sees one "nothing to update" line.
- **Two writers of one file** — install.sh and `fr models set`. Both now go through the same
  function, which is the point; the risk is a third writer appearing later. The generator's
  do-not-hand-edit banner and the layout contract are what keep that honest.
- **The prose fix in §3.B is prose.** A model can ignore it. The prose test proves the
  instruction is present, not that it was followed — stated plainly here because this repo's
  convention is that a syntactic gate is not a behavioural one.

## 5. Test Plan

**In this PR:**

1. Unit: `materialize_agents` — inserts after the `mode: subagent` anchor; replaces a stale
   `model:`; omits the key when unresolved; leaves the untiered base agent alone; no-ops
   reportably on a missing file; touches no file other than the four.
2. Unit: the **stale-binding regression** specifically — an agent carrying `model: <A>`,
   a binding set to `<B>`, then the agent reads `<B>`. This is §1.1, and it is the test
   whose absence let the defect ship.
3. Integration: `install.sh` still delivers correct models with the awk path deleted. The
   three **integration** tests from PR #495 must pass **unchanged** — they assert behaviour
   (a resolved binding lands after the anchor; one resolve per tier; an unbound tier gets no
   key), so they are exactly the safety net for swapping the implementation underneath.
   Two **unit** tests will need updating, and the spec should not pretend otherwise
   (spec-review `r2`): `test_install_runs_agents_delivery_after_fr_cli_install` anchors on
   the comment `"# Derive the tier from the filename suffix"`, which lives in the deleted awk
   block, and `test_install_calls_fr_models_resolve_for_agents` asserts the literal
   `"fr models resolve --harness opencode"`, which becomes `fr models apply`. Both are
   text-assertions over `install.sh`; both must keep asserting the same *property* (delivery
   is ordered after the `fr` CLI step; delivery goes through `fr` rather than reimplementing
   resolution) against the new call.
4. Integration: `fr models set` under a sandboxed `HOME`/`XDG_CONFIG_HOME` updates the
   installed agent, and reports what it changed.
5. Prose: `fr-goal` §5 instructs the untiered fallback; `scan_prose` still clean.
6. `fr harness parity --check` clean; `fr acceptance check` clean with both rows.

**Post-merge, operator-driven:**

7. From unbound, in a real `/fr-goal` run on OpenCode: answer the tier question, then show a
   `session` row where `agent = fr-phase-executor-<tier>` **and** `model` is the answered
   model. This is #498's acceptance, and the half no unit test can buy.

## 6. Evidence hygiene

Per `.claude/rules/third-party-privacy.md`: the sandbox reproduction in §1.1 and the journal
use `<A>`/`<B>` and `provider/a-different-model` rather than real model ids where the id is
not the point, and no absolute home paths. Real model ids appear only where they are the
technical fact being reported.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-20-opencode-tier-binding-reaches-dispatch | `derio-net/super-fr` | `2026-09-20-opencode-tier-binding-reaches-dispatch` | — |

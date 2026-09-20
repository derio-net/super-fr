# Journal: 2026-09-20-opencode-tier-binding-reaches-dispatch

<!-- fr:journal kind=decision scope=spec id=d1 created=2026-09-20T08:49:38 -->
### d1 · decision · Close the loop at the binding: one materialiser, two triggers

Operator decision (batched Q&A, 2026-09-20), gh#498 Q1. A tier binding must reach the agent OpenCode actually dispatches at the moment the operator decides it, not at the next install. One shared in-place materialiser, called by BOTH `fr models set` and install.sh, replacing install.sh`s awk rewrite so there is one implementation rather than two that can disagree. Rejected: just-in-time materialisation at dispatch (a new verb writing files mid-run — and the option already declined in #494`s d2 in favour of install-time), and prose-only documentation of the re-install requirement.

CORRECTION the orchestrator owes on its own question text: the option was labelled "new CLI surface: none". That is wrong. install.sh is bash and cannot call a Python function, so deleting its awk rewrite requires something shell-callable — one small verb (`fr models apply --harness opencode`), with `fr models set` calling the same internal function directly. One implementation, two triggers, one new verb. Consistent with install.sh already invoking `fr hermes install`. The substance of the decision is unaffected.

<!-- fr:journal kind=decision scope=spec id=d2 created=2026-09-20T08:49:38 -->
### d2 · decision · An unresolvable tier dispatches the UNTIERED agent, observably

Operator decision, gh#498 Q2 (the issue`s own fix 4). When a tier`s model cannot be resolved, dispatch the base `fr-phase-executor` rather than the tier agent, and journal why. Today the tier agent is dispatched with no `model:` and silently inherits the session model, which produces a session row indistinguishable from a working tiered dispatch — `agent = fr-phase-executor-hard` with the session default underneath. Dispatching the untiered name instead makes the absence visible in the one artifact anyone checks. Rejected: keeping today`s behaviour with documentation, and refusing the dispatch outright (turns a degradation into a blocker when inline is the safer fallback). Mechanism is prose in fr-goal §5 plus the existing `fr models resolve` contract (prints nothing, exits 0 when unbound) — no new machinery; pinned by a prose test in the shape test_fr_goal_dispatch_prose.py established.

<!-- fr:journal kind=decision scope=spec id=d3 created=2026-09-20T08:49:38 -->
### d3 · decision · Tighten the row I shipped overclaiming, and add one for the binding path

Operator decision, gh#498 Q3. `opencode-subagent-dispatch` (shipped `skipped` in PR #495) asserts a genuine parented child session with `agent = fr-phase-executor*`. As #498 points out, that proves the rewritten §5/§6 prose drove the dispatch; it does NOT prove tiering resolved, and the two separate only if the session row`s `model` is asserted too. So the row was overclaiming in the sense that it reads as evidence for tiering it never gathered. Its acceptance text gains "and the session row`s model matches the phase tier`s binding", and a new row `opencode-tier-binding-reaches-dispatch` covers the specific regression: a binding set AFTER install reaches the agent OpenCode dispatches. The overclaim is corrected in the same PR that makes it true. Rejected: adding a new row only (leaves the old row reading as tiering evidence), and no matrix change (the acceptance-matrix rule requires rows citing a spec`s Test Plan).

<!-- fr:journal kind=discovery scope=spec id=x1 created=2026-09-20T08:49:38 -->
### x1 · discovery · The stale-binding case is worse than #498 describes, and fix 4 alone cannot reach it

Reproduced in a sandbox before designing anything (no mutation of the operator`s real config): copied an installed `fr-phase-executor-hard.md` carrying `model: <A>` from a prior install, then ran `fr models set --harness opencode --tier hard --model <B>` under a sandboxed XDG_CONFIG_HOME.

- `fr models resolve` returns <B>.
- The installed agent still reads `model: <A>`.
- `find` shows that `set` wrote exactly one file: `fr/models.yaml`. Nothing else.

So there are TWO failure modes, not one. #498 describes unbound-then-bound: no `model:` key, silent fallback to the session model. The sharper one is bound-then-REBOUND: the agent pins the model the operator explicitly moved away from — a wrong value stated confidently, which is worse than an absent one, because the absent case at least has a chance of being noticed as "no tier line".

This is load-bearing for the design: #498`s fix 4 ("dispatch untiered when unresolved") cannot reach the stale case at all, because there the model IS resolved — just wrong. Only closing the loop at the binding (d1) addresses both, which is why d2 is a complement to d1 and not an alternative.

<!-- fr:journal kind=finding scope=spec id=r-s1 created=2026-09-20T08:51:32 state=open -->
### r-s1 · finding [open] · d3 is partly unimplementable: no CLI verb can edit a row's acceptance text

Spec-authoring finding. Decision d3 asks to tighten `opencode-subagent-dispatch``s acceptance TEXT. There is no supported path: `fr acceptance add` refuses an existing id by design, `fr acceptance set-status` takes only --status/--notes/--level, and `.claude/rules/acceptance-matrix.md` forbids agents hand-editing the YAML ("agents never hand-edit YAML shapes"). There is no delete verb either, so add-after-remove is not available.

Taken instead, and stated rather than worked around: the correction is recorded in the row`s `notes` via `set-status` (supported, and it appears in all three committed reports), and the tiering claim moves to its own new row `opencode-tier-binding-reaches-dispatch`. The headline text of the old row therefore still reads as before; its note now says explicitly what it does and does not prove.

This is adjacent to #431 ("fr can create journal findings and acceptance rows but cannot transition their state"), which was about STATE and is largely closed by `set-status`/`journal resolve`. This is the same gap one field over: a row`s own claim is immutable once written, so a claim that turns out to be too broad can only be annotated, never corrected. Follow-up issue owed for `fr acceptance edit --acceptance/--capability`. Left OPEN deliberately: the spec-level correction is done, but the tooling gap is real and unfixed, and marking it fixed would be the mislabelling #491 is about.

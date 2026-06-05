# ✅ SHIPPED 2026-05-17 via PR #146

This plan is complete (all steps ticked `x`, phase `completion.at` set on the date above). orthogonal operator-side guard; not subsumed by the rebuild

Original content preserved below.

---

# Dispatch-reachability gate for `vk apply --yes`

Closes the race that allowed PR #135 to ship a cross-repo fix
without the underlying plan ever existing on `origin/main`. The
operator-side gate refuses `vk apply --yes` unless every plan file
and the spec referenced in `_meta.yaml` is present at `origin/HEAD`.
No flag / env-var escape hatch — the contract becomes mandatory.

See the design spec at
`docs/superpowers/specs/2026-05-17-dispatch-reachability-gate-design.md`
for the full rationale: why `origin/HEAD` (not `origin/main`), why
no escape hatch, why the spec is also gated, the workflow-impact
analysis (2-PR-per-dispatch becomes mandatory rather than
convention), and the concrete sequence for resuming the in-flight
cross-repo bug fix (#132 / #134) once this gate ships.

A skeleton spec for the kali-bridge venv architecture redesign was
briefly opened then archived 2026-05-17 — the audit found the right
fix is the broader v2 bridge rebuild
([#147](https://github.com/derio-net/superpowers-for-vk/issues/147)),
not a patch on the fat bridge's venv. This gate-fix plan is
orthogonal and not prerequisite to that rebuild.

## Shape

One phase, four tasks. TDD throughout — failing tests before each
implementation, "all green" gate at the end of each task so the
implementing agent can pause cleanly.

- **T1** introduces a one-liner `file_on_ref` helper in
  `src/vk/git.py`. Four tmp_path-based tests cover present /
  uncommitted / nonexistent / unknown-ref cases.
- **T2** introduces the `_check_plan_reachable_on_origin_head`
  gate function in `src/vk/commands/apply_cmd.py`. Tests use a
  realistic setup (tmp_path + bare origin + clone + push) to
  verify the function reports the right missing-paths list across
  the matrix: all-pushed / plan-not-pushed / spec-not-pushed /
  meta.spec-is-None.
- **T3** wires the gate into `_apply_one(...)` at the top of the
  `--yes` branch, with three integration tests that monkeypatch
  the gate to confirm: rejection path produces exit 2 + structured
  error + no gh mutations; pass-through preserves the existing
  apply flow; dry-run skips the gate entirely. Skill and CLAUDE.md
  docs updated in the same task.
- **T4** bumps the version triple (2.1.5 → 2.1.6), refreshes the
  lock file, runs the full pre-push verification, and a CLI
  sanity check confirming dry-run remains unaffected.

## Why this is one phase, not several

~30 LOC of source change (one git helper + one gate function + a
~20-line wiring block in `_apply_one`) plus ~150 LOC of tests.
Tightly coupled: T2 can't be tested independently of T1's helper
existing; T3 can't be tested independently of T2's function
existing; T4's version bump only makes sense once T3's behavior
is observable. The "one phase = one PR" convention from the
preceding writeback plan (2026-05-13) and the cross-repo plan
(2026-05-16) applies cleanly.

## Out of scope

- **No bridge-side guards** of any kind. The kali venv drift class
  is addressed by the sibling shared-PV redesign spec; runtime
  version checks would be redundant once that redesign ships.
- **No changes to the renderer / observer / diff / apply pipeline.**
  The gate is added before `apply()` is called; the pipeline
  itself is untouched.
- **No retroactive resolution of #134.** Re-adding `vk-ready` to
  #134 after this gate merges is a one-line operator action,
  documented in the spec's "Workflow impact" section, not a code
  change in this plan.
- **No changes to dispatch via `vk-execute` or other downstream
  flows.** The gate only affects `vk apply --yes` (and `vk apply
  --all --yes`, which iterates `_apply_one`).
- **No `vk plan create` transactionality fix.** Filed separately
  as #133 — surfaced in the same plan-authoring session but
  orthogonal.

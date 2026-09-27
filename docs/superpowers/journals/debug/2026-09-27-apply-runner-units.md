# Journal: 2026-09-27-apply-runner-units

<!-- fr:journal kind=repro scope=debug id=3e596ff70ca9 created=2026-09-27T08:26:34 -->
### 3e596ff70ca9 · repro · fr apply --to herdr queues phase Issues herdr never takes

apply_cmd.py checks only `to in runner_names()`, then labels phase Issues runner:herdr. HerdrRunner.can_dispatch returns True only for unit == 'run', so every tick refuses each phase item — reported as `<id>: unknown repo '<repo>'` (reason=unknown_repo) — and the Issues wait forever. Repro by reading: apply_cmd.py ~492-500, fr_herdr/runner.py:130, fr_dispatch/__init__.py:494-497.

<!-- fr:journal kind=root-cause scope=debug id=6d30756ffe9e created=2026-09-27T08:26:37 -->
### 6d30756ffe9e · root-cause · The Runner protocol declares no units, so apply cannot ask; tick's refusal message hardcodes 'unknown repo'

A runner's unit limit lives only inside can_dispatch(item), which needs a built runner and a built item. apply cannot build a runner (vk/cncd have no from_env — they are constructed only in their bridge), so its only possible check is name registration. Separately, tick maps every can_dispatch False to 'unknown repo', even when the unit is the refusal. Fix: a declared `units` class attribute on Runner (like `capabilities`), read off the entry-point class in apply before any forge call; tick names the unit when it is the reason.

<!-- fr:journal kind=finding scope=debug id=apply-runner-units-fix created=2026-09-27T08:53:40 state=fixed -->
### apply-runner-units-fix · finding [fixed] · Runner.units declared; apply refuses a non-phase runner before the forge; tick names the unit

Source: Runner.units (protocols.py), registry.runner_units, apply_cmd refusal after the name check and before _make_gh_client; vk/cncd {phase}, herdr {run}, each can_dispatch gated on self.units; tick unit_mismatch vs generic refusal message. Pinned first by tests/unit/test_apply_runner_units.py (committed red in d27f7f12: 5 failed — apply reached the forge client, no runner declared units, tick said 'unknown repo'); green after. Full suite: 6519 passed, 2 failed under heavy host load (test_run_idle_guard, test_record_review_fixes), both pass when rerun alone — unrelated to this change.

<!-- fr:journal kind=review scope=debug id=8d55554d378a created=2026-09-27T08:59:17 -->
### 8d55554d378a · review · Independent adversarial review: no findings

A separate read-only reviewer read every touched file plus neighbours (triage_batch_cmd, bridge_cli, render, shapes/resolve, testing, import-direction test). Verified: refusal fires before _make_gh_client and merge_evidence; render() projects runner labels on plan.phases only, so phase is the only unit apply --to queues; triage batch dispatch uses load_runner + can_dispatch (herdr only); soft-point import stays find_spec-guarded. Sub-threshold note, no action: fr_vk METRICS_REASON_ALIASES has no unit_mismatch entry, so it passes through unaliased (unreachable for vk today). Reviewer had no shell, so it read files at HEAD rather than the git diff.

# Journal: 2026-09-27-apply-runner-units

<!-- fr:journal kind=repro scope=debug id=3e596ff70ca9 created=2026-09-27T08:26:34 -->
### 3e596ff70ca9 · repro · fr apply --to herdr queues phase Issues herdr never takes

apply_cmd.py checks only `to in runner_names()`, then labels phase Issues runner:herdr. HerdrRunner.can_dispatch returns True only for unit == 'run', so every tick refuses each phase item — reported as `<id>: unknown repo '<repo>'` (reason=unknown_repo) — and the Issues wait forever. Repro by reading: apply_cmd.py ~492-500, fr_herdr/runner.py:130, fr_dispatch/__init__.py:494-497.

<!-- fr:journal kind=root-cause scope=debug id=6d30756ffe9e created=2026-09-27T08:26:37 -->
### 6d30756ffe9e · root-cause · The Runner protocol declares no units, so apply cannot ask; tick's refusal message hardcodes 'unknown repo'

A runner's unit limit lives only inside can_dispatch(item), which needs a built runner and a built item. apply cannot build a runner (vk/cncd have no from_env — they are constructed only in their bridge), so its only possible check is name registration. Separately, tick maps every can_dispatch False to 'unknown repo', even when the unit is the refusal. Fix: a declared `units` class attribute on Runner (like `capabilities`), read off the entry-point class in apply before any forge call; tick names the unit when it is the reason.

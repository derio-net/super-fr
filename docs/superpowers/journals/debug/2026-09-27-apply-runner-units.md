# Journal: 2026-09-27-apply-runner-units

<!-- fr:journal kind=repro scope=debug id=3e596ff70ca9 created=2026-09-27T08:26:34 -->
### 3e596ff70ca9 · repro · fr apply --to herdr queues phase Issues herdr never takes

apply_cmd.py checks only `to in runner_names()`, then labels phase Issues runner:herdr. HerdrRunner.can_dispatch returns True only for unit == 'run', so every tick refuses each phase item — reported as `<id>: unknown repo '<repo>'` (reason=unknown_repo) — and the Issues wait forever. Repro by reading: apply_cmd.py ~492-500, fr_herdr/runner.py:130, fr_dispatch/__init__.py:494-497.

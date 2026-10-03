# Journal: 2026-10-02-batch-ci-health

<!-- fr:journal kind=repro scope=debug id=72e8c9479738 created=2026-10-02T19:47:44+00:00 -->
### 72e8c9479738 · repro · Full suite -n auto + coverage on macOS (12 cores): 7716 passed, 97 skipped, 864s; none of #629/#630/#640 fired

uv run pytest -n auto --durations=40 --cov-fail-under=0 from the worktree, opencode on PATH. test_opencode_runs_the_delivered_gate took 22.8s under load (limit 120s); the inherited-COLUMNS child test was under 12s (1.8s alone; limit 120s); TestInstallRules passed. All three are load-dependent flakes that this run did not reproduce. #643 is a deterministic gap, confirmed by reading: _sibling_offenders bans only fr_dispatch/fr_vk.

<!-- fr:journal kind=hypothesis scope=debug id=1d15d4659019 created=2026-10-02T19:47:45+00:00 -->
### 1d15d4659019 · hypothesis · The batch has three independent root causes, not one

(a) #629 and #640: a subprocess has a fixed 120s timeout, and under full -n auto load on a macOS host it can run past it. Shared cause, shared fix (scale the timeout). (b) #630: install.sh's marketplace rsync excludes only .git, __pycache__ and .venv, so it walks the repo root while xdist workers create and delete .coverage.* files (rsync exit 23). A real install also copies .coverage and .venv-container. Confirmed by reading install.sh:477. (c) #643: the import-direction tripwire hardcodes its banned set, so fr_cncd is missing. Nothing in common with (a) or (b).

<!-- fr:journal kind=root-cause scope=debug id=1ce114ed4371 created=2026-10-03T19:55:58+00:00 -->
### 1ce114ed4371 · root-cause · Three causes: fixed 120s child timeouts (#629/#640), unfiltered marketplace rsync (#630), hand-written sibling ban (#643)

Operator confirmed fixing all three in one PR after the stop-and-ask. #629/#640: the budget doesn't scale with xdist contention (inferred from the issues' evidence; not reproduced in a local 864s -n auto + coverage run). #630: the rsync at install.sh:477 excluded only .git/__pycache__/.venv. #643: _sibling_offenders hardcoded {fr_dispatch, fr_vk}.

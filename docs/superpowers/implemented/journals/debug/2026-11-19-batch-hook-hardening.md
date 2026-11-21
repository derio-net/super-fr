<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-hook-hardening

<!-- fr:journal kind=repro scope=debug id=17d08f0dbe2f created=2026-11-19T19:24:59+00:00 -->
### 17d08f0dbe2f · repro · Batch hook-hardening: five live gaps confirmed on origin/main e2e22e50c

- #1509: fr-isolation-required.sh:26,37 parses the payload with bare jq under set -eu; no jq means the script aborts before printing a deny (fail-open). Its sibling library already has an absolute-path resolver (fr_json_resolve) it does not use.
- #1484: lib/fr-isolation-decision.sh fr_json_field runs "$FR_JSON_BIN" -c without -P/-I, and _fr_try_parser resolves bare names with command -v (honours relative PATH entries) unlike fr_git_resolve/fr_fr_resolve, which walk absolute PATH entries only (#1429).
- #1481: plugin spawns bare 'bash' (src/tui/segment.ts:47) and 'gh' (src/push.ts:35) via execFile; five hooks gate on command -v jq and then run bare jq.
- #1508: scripts/install.sh uv tool install --force packages/fr with no lock/constraints; npm install -g @devcontainers/cli unversioned.
- #1510: packages/fr-opencode-plugin/bun.lock holds glob 13.0.5 and minimatch 10.2.5 as exact pins of @opencode/util 2.1.0 (plus glob 10.x/minimatch 9.x via rimraf).

<!-- fr:journal kind=hypothesis scope=debug id=11ead4405329 created=2026-11-19T19:25:01+00:00 -->
### 11ead4405329 · hypothesis · Two root causes, not one

A (#1509, #1484, #1481): helper binaries and interpreters are reached by bare name / command -v and run without isolation flags, instead of through the absolute-PATH-entry resolvers already used for git and fr (fr_git_resolve, fr_fr_resolve, plugin resolveGit/resolveFr). Fix: one resolver for jq/python3/bash/gh, used everywhere, python with -I.
B (#1508, #1510): delivered dependencies are resolved at install time instead of from a tested lock: uv tool install without the workspace uv.lock as constraints, unversioned npm -g, and bun.lock carrying advisory versions pinned by an upstream package (needs overrides). Different mechanism, different files, different tests. Per batch rule, stop and ask before fixing.

<!-- fr:journal kind=root-cause scope=debug id=46e27da33460 created=2026-11-19T20:17:11+00:00 -->
### 46e27da33460 · root-cause · A: hooks and plugin reach jq/python3/bash/gh by bare name, python without -I

The resolvers for git (fr_git_resolve, plugin resolveGit) and fr (fr_fr_resolve, resolveFr) walk absolute PATH entries only; the JSON parser resolver used command -v (relative entries count) and ran python3 -c (cwd on sys.path); the Claude edit gate and ten other hooks run bare jq; the plugin execFiles bare bash and gh. Operator chose to fix A and B in one PR.

<!-- fr:journal kind=root-cause scope=debug id=07300a16a16e created=2026-11-19T20:17:13+00:00 -->
### 07300a16a16e · root-cause · B: installs resolve dependencies afresh instead of from the tested lock

install.sh's uv tool install takes no constraints from uv.lock; npm -g @devcontainers/cli is unversioned; bun.lock carries glob 13.0.5/10.5.0 and minimatch 10.2.5/9.0.9 pinned by @opencode/util 2.1.0 and rimraf 5, inside GHSA-3g3m-2fjr-6pw4 (glob >=9.0.0 <=14.0.1, fix 14.0.2) and GHSA-g3hv-75wg-m249 (minimatch >=7.0.0 <11.0.1, fix 11.0.1), ranges re-read from the advisory database. Dev graph only: delivery copies src/, the plugin imports types only.

<!-- fr:journal kind=finding scope=debug id=eccd12d862b2 created=2026-11-19T20:41:43+00:00 state=fixed -->
### eccd12d862b2 · finding [fixed] · A fixed: tools resolved from absolute PATH entries, python -I, edit gate denies without jq

lib: fr_which/_fr_first_candidate replace command -v; fr_jq/fr_gh/fr_jq_resolve/fr_gh_resolve; python3 -I -c; a python3 that cannot run is skipped. fr-isolation-required.sh: parses via fr_json_field, every read guarded, denies on no parser / failing parser / unreadable payload (deny_fixed needs no parser). Ten hooks + Hermes push guard call fr_jq/fr_gh. Plugin: src/tools.ts resolveTool; segment.ts and push.ts spawn the resolved bash/gh. Tests first: tests/unit/test_hooks_planted_tools.py, packages/fr-opencode-plugin/test/tools.test.ts (commit ee6da13e8).

<!-- fr:journal kind=finding scope=debug id=007b308a9c60 created=2026-11-19T20:41:46+00:00 state=fixed -->
### 007b308a9c60 · finding [fixed] · B fixed: install constrained to uv.lock, devcontainer CLI pinned, plugin lock out of both advisory ranges

install.sh exports uv.lock (--frozen --all-packages --no-dev --no-emit-workspace) to ~/.local/share/fr/install-constraints.txt and passes --constraints to both uv tool installs when uv supports it; warns otherwise. Real unstubbed install verified: typer 0.24.1, pydantic 2.13.4 as locked. npm installs @devcontainers/cli@0.87.0 (FR_DEVCONTAINER_CLI_VERSION overrides). package.json overrides glob 14.0.3, minimatch 11.0.4: newest patched releases older than two weeks; bun test 337 pass, tsc clean. Tests: tests/integration/test_install_locked_deps.py, tests/unit/test_opencode_plugin_lock_advisories.py.

<!-- fr:journal kind=review scope=debug id=e888afdd2e7b created=2026-11-19T20:41:48+00:00 -->
### e888afdd2e7b · review · Independent adversarial review: one important finding, fixed; two minor, one fixed

1 (important, fixed): a python3 that resolves but cannot run (pyenv shim, CLT stub) made the unguarded fr_json_field calls abort the edit gate under set -eu with no deny. Fixed: reads guarded, deny_fixed fallback, resolver probes python and falls through to jq; tests test_a_python3_that_cannot_run_and_no_jq_still_denies (fails before), ..._falls_through_to_jq. 2 (minor, fixed): jq branch handed __HOOK_PARSE_ERROR__ as a file path; now denies. 3 (minor, not fixed, out of scope): plugins/super-fr/scripts/fr-statusline-claude.sh runs a bare jq (status line, not a hook) and fr-run-idle-guard.sh a command -v pkill; noted in the PR. Residual: the glob override forces rimraf@5 onto glob 14 in the dev graph; rimraf is never run by the plugin or its tests.

<!-- fr:journal kind=finding scope=debug id=babb2387bc80 created=2026-11-19T21:35:05+00:00 state=refuted -->
### babb2387bc80 · finding [refuted] · CI shard 4 placement-move-and-drift failure: flake, not this change

test_placement_move_and_drift failed once in CI (fr placement move refused: an acceptance fragment uncommitted in feat__live). The scenario runs no hook, jq, python3 or install.sh; it passed 3/3 in the workspace on the same tree, and a rerun of the failed job passed. main is green at 612b3976c.

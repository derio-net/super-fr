<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-batch-hook-hardening

<!-- fr:journal kind=repro scope=debug id=17d08f0dbe2f created=2026-11-19T19:24:59+00:00 -->
### 17d08f0dbe2f · repro · Batch hook-hardening: five live gaps confirmed on origin/main e2e22e50c

- #1509: fr-isolation-required.sh:26,37 parses the payload with bare jq under set -eu; no jq means the script aborts before printing a deny (fail-open). Its sibling library already has an absolute-path resolver (fr_json_resolve) it does not use.
- #1484: lib/fr-isolation-decision.sh fr_json_field runs "$FR_JSON_BIN" -c without -P/-I, and _fr_try_parser resolves bare names with command -v (honours relative PATH entries) unlike fr_git_resolve/fr_fr_resolve, which walk absolute PATH entries only (#1429).
- #1481: plugin spawns bare 'bash' (src/tui/segment.ts:47) and 'gh' (src/push.ts:35) via execFile; five hooks gate on command -v jq and then run bare jq.
- #1508: scripts/install.sh uv tool install --force packages/fr with no lock/constraints; npm install -g @devcontainers/cli unversioned.
- #1510: packages/fr-opencode-plugin/bun.lock holds glob 13.0.5 and minimatch 10.2.5 as exact pins of @opencode/util 2.1.0 (plus glob 10.x/minimatch 9.x via rimraf).

#!/usr/bin/env bash
# Row model-binding-check-report: `fr models check` reports every binding with
# one of four verdicts (live, dead, unknown, unprobed), lists an upgrade offer
# without applying it, and exits 1 off a terminal when a binding is dead.
# A stub `opencode` (_stub_opencode.sh); no provider is reached.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_stub_opencode.sh"

stub_reset
stub_model prov orch o 2026-01-01 2
stub_model prov orch-2 o 2026-06-01 2
stub_model prov std s 2026-01-01 2
stub_model prov std-2 s 2026-03-01 2
stub_model prov hard h 2026-01-01 4
stub_state prov/std unsupported
stub_state prov/hard error
bind_models claude-code standard=claude-sonnet-5
bind_models opencode orchestrator=prov/orch standard=prov/std hard=prov/hard
before="$(cat "$XDG_CONFIG_HOME/fr/models.yaml")"

run_fr out models check
require_exit 1 "$out"
expect_grep 'opencode/orchestrator: prov/orch — live' "$out" "live"
expect_grep 'opencode/standard: prov/std — dead' "$out" "dead"
expect_grep 'opencode/hard: prov/hard — unknown' "$out" "unknown"
expect_grep 'claude-code/standard: claude-sonnet-5 — unprobed' "$out" "unprobed"
expect_grep 'opencode/orchestrator:.*offer: prov/orch-2' "$out" "an upgrade offer is listed"
[ "$(cat "$XDG_CONFIG_HOME/fr/models.yaml")" = "$before" ] || fail "an off-terminal check must write nothing"

# Without a dead binding the same report exits 0.
stub_reset
stub_model prov orch o 2026-01-01 2
bind_models opencode orchestrator=prov/orch
run_fr out models check
require_exit 0 "$out"
expect_grep 'opencode/orchestrator: prov/orch — live' "$out" "all live exits 0"

echo "ok: model-binding-check"

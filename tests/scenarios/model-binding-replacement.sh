#!/usr/bin/env bash
# Row model-binding-replacement: `fr models check`, off a terminal, proposes a
# replacement for a dead binding by fixed rules — family successor, then tier
# position and price, then the provider's own hint — and says so plainly when
# nothing qualifies. A stub `opencode` (_stub_opencode.sh); no provider is reached.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_stub_opencode.sh"

check() { run_fr out models check --harness opencode; require_exit 1 "$out"; }

# family rule: the newest live same-family successor wins; a retired one is skipped.
stub_reset
stub_model prov std s 2026-01-01 2
stub_model prov std-2 s 2026-03-01 2
stub_model prov std-3 s 2026-05-01 2
stub_state prov/std notfound
stub_state prov/std-3 unsupported
bind_models opencode standard=prov/std
check
expect_grep 'opencode/standard: prov/std — dead.*prov/std-2 \(rule family, price ×1\.0\)' "$out" "family successor, retired one skipped"

# tier rule: no family successor. Candidates must keep mechanical <= standard <= hard
# and stay distinct from every bound model; the nearest price wins.
stub_reset
stub_model prov mech m 2026-01-01 1
stub_model prov std s 2026-01-01 2
stub_model prov hard h 2026-01-01 4
stub_model prov orch o 2026-01-01 3
stub_model prov too-cheap a 2026-02-01 0
stub_model prov too-dear b 2026-02-01 9
stub_model prov fits c 2026-02-01 3
stub_state prov/std notfound
bind_models opencode mechanical=prov/mech standard=prov/std hard=prov/hard orchestrator=prov/orch
check
expect_grep 'opencode/standard: prov/std — dead.*prov/fits \(rule tier, price ×1\.5\)' "$out" "tier rule keeps order and distinctness"
refuse_grep 'too-cheap|too-dear|prov/orch \(rule' "$out" "an out-of-order or already-bound model is never proposed"

# above 2x: shown, but marked operator-only (fr would never apply it unasked).
stub_reset
stub_model prov std s 2026-01-01 2
stub_model prov std-2 s 2026-03-01 5
stub_state prov/std notfound
bind_models opencode standard=prov/std
check
expect_grep 'prov/std-2 \(rule family, price ×2\.5, operator-only\)' "$out" "a >2x candidate is operator-only"

# provider hint: no catalogue entry and no snapshot for the dead model.
stub_reset
stub_model prov sol-2 sol 2026-09-01 2
stub_state prov/sol-1 notfound:sol-2
bind_models opencode orchestrator=prov/sol-1
check
expect_grep 'opencode/orchestrator: prov/sol-1 — dead.*prov/sol-2 \(rule hint, price ×\?, operator-only\)' "$out" "the provider's hint"

# no replacement at all.
stub_reset
stub_model prov alone s 2026-01-01 2
stub_state prov/alone notfound
bind_models opencode standard=prov/alone
check
expect_grep 'opencode/standard: prov/alone — dead.*no replacement' "$out" "no replacement is said plainly"

echo "ok: model-binding-replacement"

#!/usr/bin/env bash
# Row model-binding-set-probe: `fr models set --harness opencode` probes the
# model live before persisting it, off a terminal (CI=true, via _common.sh).
# A stub `opencode` is scripted per model (_stub_opencode.sh); nothing here
# reaches a provider.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
. "$here/_stub_opencode.sh"

set_model() { run_fr out models set --harness opencode --tier standard --model "$1" "${@:2}"; }
yaml() { cat "$XDG_CONFIG_HOME/fr/models.yaml" 2>/dev/null; }

# live: persisted, quietly.
stub_reset
stub_model prov live-model fam 2026-01-01 1
set_model prov/live-model
require_exit 0 "$out"
expect_grep 'standard: prov/live-model' "$(yaml)" "a live model is persisted"
refuse_grep 'SUBSTITUTED' "$out" "a plain set is not a substitution"

# retired but still in the catalogue as "status": "active": the provider says
# not supported, so it is refused and nothing is written.
stub_reset
stub_model prov retired fam 2026-01-01 1 active
stub_state prov/retired unsupported
set_model prov/retired
require_exit 2 "$out"
expect_grep 'not supported' "$out" "the provider's own error is shown"
[ ! -e "$XDG_CONFIG_HOME/fr/models.yaml" ] || fail "a refused set must not write models.yaml"

# a server error is not evidence: warn and persist.
stub_reset
stub_model prov flaky fam 2026-01-01 1
stub_state prov/flaky error
set_model prov/flaky
require_exit 0 "$out"
expect_grep 'inconclusive' "$out" "an unknown probe warns"
expect_grep 'standard: prov/flaky' "$(yaml)" "an unknown probe still persists"

# --no-probe: persists a dead model, says so, and never asks the provider.
stub_reset
stub_state prov/retired unsupported
set_model prov/retired --no-probe
require_exit 0 "$out"
expect_grep 'probe skipped' "$out" "--no-probe says it skipped"
expect_grep 'standard: prov/retired' "$(yaml)" "--no-probe persists"
[ ! -s "$STUB/calls.log" ] || fail "--no-probe must not run opencode: $(cat "$STUB/calls.log")"

echo "ok: model-binding-set-probe"

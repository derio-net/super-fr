#!/usr/bin/env bash
# Rows fr-ops-status, fr-ops-apply-idempotent, fr-ops-profile-guard,
# fr-ops-evidence-attest, fr-ops-probe-trust, fr-ops-model-carriers: a fixture plan
# with one op per state, `apply --phase` twice (the second writes nothing), the
# out-of-profile refusal, a cycle refused before anything runs, an identity failure
# that names the identity, attest, and the trust gate.
#
# Credential free: checks are `test -f` on files OUTSIDE the repo ($MARKS; a probe that
# names a file inside the repo is hashed into the trust, so creating it would untrust).
# The ops profile is a fixture fr-profiles.yaml with `ops: true`, plus FR_PROFILE and
# KUBERNETES_SERVICE_HOST as container evidence. `fr ops trust` needs a terminal and is
# refused here by design, so the grant is written by fr's own trust-writing function
# (fr.ops.trust.grant_trust) into a pre-seeded FR_OPS_TRUST_DIR.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
export MARKS="$work/marks" FR_OPS_TRUST_DIR="$work/trust"
mkdir -p "$MARKS" "$FR_OPS_TRUST_DIR"
export FR_PROFILE=ops KUBERNETES_SERVICE_HOST=10.0.0.1
py="$(candidate_python)"

git init -q -b main . || fail "git init"
mkdir -p .devcontainer .fr docs/superpowers/plans/p docs/superpowers/plans/cyc docs/superpowers/plans/idp docs/superpowers/plans/idapply docs/superpowers/plans/mut docs/superpowers/plans/nochk
cat > .devcontainer/fr-profiles.yaml <<'YAML'
profiles:
  ops: {purpose: operate, secrets: [], ops: true}
default: ops
YAML
cat > .fr/ops.yaml <<'YAML'
env_passthrough: [MARKS]
identities:
  bot:
    env:
      BOT_TOKEN: {from: 'exit 1'}
YAML
cat > docs/superpowers/plans/p/ops.yaml <<'YAML'
schema_version: 1
ops:
  - {id: done-op, summary: already there, phase: pre-merge, check: 'true'}
  - id: open-op
    summary: not yet created
    phase: pre-merge
    needs: [done-op]
    check: 'test -f "$MARKS/open"'
    apply: 'touch "$MARKS/open"'
  - {id: na-op, summary: not applicable here, phase: pre-merge, check: 'false', na_if: 'true'}
  - {id: hand-op, summary: done in a UI, phase: post-merge}
YAML
cat > docs/superpowers/plans/cyc/ops.yaml <<'YAML'
schema_version: 1
ops:
  - {id: a, summary: a, phase: pre-merge, needs: [b], check: 'false', apply: 'touch "$MARKS/cyc-ran"'}
  - {id: b, summary: b, phase: pre-merge, needs: [a], check: 'false', apply: 'touch "$MARKS/cyc-ran"'}
YAML
cat > docs/superpowers/plans/idp/ops.yaml <<'YAML'
schema_version: 1
ops:
  - {id: as-bot, summary: needs the bot, phase: pre-merge, identities: [bot], check: 'true'}
YAML
cat > docs/superpowers/plans/idapply/ops.yaml <<'YAML'
schema_version: 1
ops:
  - {id: as-bot-apply, summary: applies as the bot, phase: pre-merge, identities: [bot], check: 'false', apply: 'touch "$MARKS/idapply-ran"'}
YAML
cat > docs/superpowers/plans/mut/ops.yaml <<'YAML'
schema_version: 1
ops:
  - id: danger
    summary: changes something
    phase: pre-merge
    mutating: true
    side_effects: [rewrites the thing]
    undo: 'rm -f "$MARKS/mut"'
    check: 'test -f "$MARKS/mut"'
    apply: 'touch "$MARKS/mut"'
YAML
cat > docs/superpowers/plans/nochk/ops.yaml <<'YAML'
schema_version: 1
ops:
  - {id: unchecked, summary: applied but not verifiable, phase: pre-merge, apply: 'touch "$MARKS/nochk"'}
YAML
git add -A && git commit -qm seed || fail "seed commit"

trust_plan() {
  "$py" - "$1" <<'PY' || fail "could not write the trust grant"
import sys
from pathlib import Path
from fr.ops.load import load_ops, load_ops_config
from fr.ops.trust import fingerprint, grant_trust, head_tree, tree_digest
root, slug = Path.cwd(), sys.argv[1]
tree = head_tree(root)
ops = load_ops(root / "docs/superpowers/plans" / slug, root).ops
fp = fingerprint(ops, load_ops_config(root), root, code_tree=tree_digest(tree))
grant_trust(root, slug, fp, tree=tree)
PY
}
P=docs/superpowers/plans/p

# --- trust gate (R19): nothing runs until the grant ---------------------------------
run_fr out ops status --plan "$P"
require_exit 2 "$out"
expect_grep 'not trusted' "$out" "an ungranted op set is refused"
expect_grep 'fr ops trust' "$out" "the refusal names fr ops trust"
run_fr out ops trust --plan "$P"
require_exit 2 "$out"
expect_grep 'terminal' "$out" "trust is refused without a terminal"
trust_plan p; trust_plan cyc; trust_plan idp; trust_plan idapply; trust_plan mut; trust_plan nochk

# --- status states and exit codes ----------------------------------------------------
run_fr out ops status --plan "$P"
require_exit 1 "$out"
expect_grep 'DONE \(checked\).*done-op' "$out" "a passing check is DONE (checked)"
expect_grep 'OPEN.*open-op' "$out" "a failing check is OPEN"
expect_grep 'N/A.*na-op' "$out" "na_if makes an op N/A"
expect_grep 'UNVERIFIABLE.*hand-op' "$out" "an op with no check is UNVERIFIABLE"

# --- the profile guard (R6): status warns, apply refuses -------------------------------
out="$(env -u FR_PROFILE fr ops apply --plan "$P" --phase pre-merge --yes 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'fr isolation up --profile ops --branch chore/ops-p' "$out" "the refusal names the ops workspace route"
expect_grep 'fr isolation exec --branch chore/ops-p' "$out" "and the exec command"
[ ! -e "$MARKS/open" ] || fail "a refused apply ran the op"
out="$(env -u FR_PROFILE fr ops status --plan "$P" 2>&1)"; RC=$?
expect_grep 'not inside an ops profile' "$out" "status only warns outside an ops profile"

# --- apply --phase, twice (R4) ----------------------------------------------------------
run_fr out ops apply --plan "$P" --phase pre-merge
require_exit 2 "$out"
expect_grep '--yes' "$out" "no terminal and no --yes is refused"
run_fr out ops apply --plan "$P" --phase pre-merge --yes
require_exit 0 "$out"
[ -e "$MARKS/open" ] || fail "apply did not run open-op"
expect_grep 'done-op.*already done; recorded it' "$out" "a done op is skipped and its closure recorded once (R7)"
expect_grep 'open-op: applied' "$out" "the open op was applied"
snapshot="$(find docs/superpowers/journals -type f -exec cat {} + | cksum)"
run_fr out ops apply --plan "$P" --phase pre-merge --yes
require_exit 0 "$out"
refuse_grep 'applied' "$out" "the second run applies nothing"
expect_grep 'open-op.*already done, nothing written' "$out" "and says so"
[ "$(find docs/superpowers/journals -type f -exec cat {} + | cksum)" = "$snapshot" ] || fail "the second run wrote to the journal"
run_fr out ops status --plan "$P" --phase pre-merge
require_exit 0 "$out"

# --- a cycle is refused before anything runs -----------------------------------------------
run_fr out ops apply --plan docs/superpowers/plans/cyc --phase pre-merge --yes
require_exit 2 "$out"
expect_grep 'cycle' "$out" "a needs cycle is refused"
[ ! -e "$MARKS/cyc-ran" ] || fail "a cycle ran something"

# --- an identity failure names the identity ----------------------------------------------------
run_fr out ops status --plan docs/superpowers/plans/idp
require_exit 1 "$out"
expect_grep 'CANNOT-VERIFY' "$out" "an unreadable identity is CANNOT-VERIFY"
expect_grep 'bot' "$out" "and names the identity"

# --- an identity that cannot be read at apply time names the identity, nothing runs ----------
run_fr out ops apply --plan docs/superpowers/plans/idapply --phase pre-merge --yes
require_exit 1 "$out"
expect_grep 'bot' "$out" "the apply-time identity failure names the identity"
[ ! -e "$MARKS/idapply-ran" ] || fail "an op ran without its identity"

# --- a mutating op needs --yes AND --yes-mutating ----------------------------------------------------
run_fr out ops apply --plan docs/superpowers/plans/mut --phase pre-merge --yes
require_exit 2 "$out"
expect_grep -- '--yes-mutating' "$out" "a mutating op without --yes-mutating is refused"
[ ! -e "$MARKS/mut" ] || fail "a refused mutating op ran"
run_fr out ops apply --plan docs/superpowers/plans/mut --phase pre-merge --yes-mutating
require_exit 2 "$out"
[ ! -e "$MARKS/mut" ] || fail "--yes-mutating alone confirmed a mutating op"
run_fr out ops apply --plan docs/superpowers/plans/mut --phase pre-merge --yes --yes-mutating
require_exit 0 "$out"
[ -e "$MARKS/mut" ] || fail "both flags did not run the mutating op"

# --- an apply with no check is flagged, never re-applied silently -----------------------------------
run_fr out ops apply --plan docs/superpowers/plans/nochk --phase pre-merge --yes
require_exit 0 "$out"
expect_grep 'attest' "$out" "an unchecked apply is flagged for attestation"
[ -e "$MARKS/nochk" ] || fail "the unchecked op did not run"
rm -f "$MARKS/nochk"
run_fr out ops apply --plan docs/superpowers/plans/nochk --phase pre-merge --yes
require_exit 0 "$out"
expect_grep 'already applied' "$out" "a re-run says it was already applied"
[ ! -e "$MARKS/nochk" ] || fail "an unchecked op was re-applied silently"
run_fr out ops status --plan docs/superpowers/plans/nochk
require_exit 1 "$out"
expect_grep 'UNVERIFIABLE' "$out" "status still cannot verify it"

# --- an unknown op is refused (exit 2), naming it -------------------------------------------------------
run_fr out ops apply --plan "$P" no-such-op --yes
require_exit 2 "$out"
expect_grep 'no-such-op' "$out" "an unknown op id is refused by name"

# --- attest (R8) ------------------------------------------------------------------------------------
run_fr out ops attest hand-op --note "saw it" --plan "$P"
require_exit 2 "$out"
expect_grep 'terminal' "$out" "attest needs a terminal"

echo "ok: fr-ops-status-apply"

#!/usr/bin/env bash
# Row opencode-2-store-read / opencode-2-v1-refusal: the installed `fr` reads
# OpenCode 2's store (`session_v2` / `session_message`) and refuses a 1.x session
# by name (spec 2026-10-20-opencode-2-support R13, R14). The store is the
# committed fixture tests/fixtures/opencode/two-sessions.db (built, shape captured
# live, identity redacted), copied so nothing writes the committed file.
#   fr usage collect/report, a 2.x session  -> its dollars, model and tool calls
#   fr usage report, a 1.x-only session     -> unavailable, naming 1.x and the upgrade
#   fr run advance on an operator gate      -> 2.x: observed (no notice);
#                                              1.x: the R14 refusal, never FR_OPENCODE_DB
#   fr run status                           -> the cursor reads, gate still pending
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"
branch=feat/opencode-store

world="$(mktemp -d)"
trap 'rm -rf "$world"' EXIT
export HOME="$world/home" FR_HARNESS=opencode FR_OPENCODE_DB="$world/opencode.db"
mkdir -p "$HOME"
unset FR_OPENCODE_SESSION_ID OPENCODE_SESSION_ID CLAUDE_CODE_SESSION_ID
cp "$here/../fixtures/opencode/two-sessions.db" "$FR_OPENCODE_DB" || fail "copy the store"

# --- usage: one adapter, both answers -----------------------------------------
run_fr out usage collect --harness opencode --session ses_v2demo --session ses_v1only
require_exit 0 "$out"
expect_grep 'collected 2 session\(s\), 1 unavailable' "$out" "the 1.x session is unavailable"

run_fr out usage report --harness opencode --session ses_v2demo --session ses_v1only
require_exit 0 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]│' ' ')"
expect_grep 'example-model \$0\.01' "$flat" "the 2.x session's dollars are the store's own"
expect_grep 'OpenCode 1\.x' "$flat" "the 1.x session is named as 1.x"
expect_grep 'upgrade opencode; super-fr supports 2\.0 only' "$flat" "and the fix is named"
refuse_grep 'FR_OPENCODE_DB' "$flat" "a 1.x session is not a wrong-database hint"

# --- run: the operator gate on a 2.x session, then a 1.x one -------------------
echo seed > seed.md && git add -A && git commit -qm seed || fail "seed commit"
git worktree add -q -b "$branch" "$world/ws" || fail "worktree"
cd "$world/ws" || fail "cd ws"
mkdir -p docs/superpowers/workflows
cat > docs/superpowers/workflows/gated.yaml <<'YAML'
workflow: gated
schema: 1
unit: run
steps:
  - id: brainstorm
    kind: cli
    gate: operator
    run: "true"
YAML
printf '{"toplevel": "%s", "branch": "%s", "mode": "worktree", "created_at": "2026-10-20T00:00:00+00:00"}\n' \
  "$PWD" "$branch" > .fr-isolation
git add -A docs && git commit -qm shape || fail "shape commit"

run_fr out run start gated --branch "$branch" --run-id r1
require_exit 0 "$out"

OPENCODE_SESSION_ID=ses_v2demo run_fr out run advance r1
require_exit 0 "$out"
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
refuse_grep 'cannot verify|1\.x|not in the OpenCode database' "$flat" "a 2.x session is observed"

OPENCODE_SESSION_ID=ses_v1only run_fr out run advance r1
flat="$(printf '%s' "$out" | tr -s '[:space:]' ' ')"
expect_grep 'OpenCode 1\.x' "$flat" "the gate names a 1.x session as 1.x"
expect_grep 'upgrade opencode; super-fr supports 2\.0 only' "$flat" "and names the upgrade"
refuse_grep 'FR_OPENCODE_DB' "$flat" "never as a wrong-database hint"

run_fr out run status r1
require_exit 0 "$out"
expect_grep 'brainstorm' "$out" "the cursor reads"

echo "ok: opencode-store-v2"

#!/usr/bin/env bash
# Row herdr-restart-idle: `fr-herdr restart-idle` (the installed console script) lists
# every claude pane with one verdict line, ends with a summary, sends no key on a dry
# run, and refuses with exit 2 outside a herdr session. herdr is a fake that replays
# what herdr 0.9.1 printed live (fixtures/herdr-restart/); nothing here reaches a real
# herdr.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

command -v fr-herdr >/dev/null || fail "no fr-herdr on PATH (the install must expose it)"

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
export HERDR_FAKE_LOG="$work/herdr.log"
: > "$HERDR_FAKE_LOG"
export PATH="$here/fixtures/herdr-restart:$PATH"

# Transcripts: the suggestion pane and the background-work pane have one for their
# session; the third idle pane has none.
slug="-home-user-Docs-projects-super-fr"
mkdir -p "$work/claude/projects/$slug"
echo '{}' > "$work/claude/projects/$slug/b2f6a75f-6ece-48d3-998f-e04afe1254f3.jsonl"
echo '{}' > "$work/claude/projects/$slug/8521da52-601a-4129-ad09-69800bf4b1b4.jsonl"
export CLAUDE_CONFIG_DIR="$work/claude"

# Inside herdr: a dry run, the default.
out="$(HERDR_ENV=1 HERDR_PANE_ID=w0:p0 fr-herdr restart-idle 2>&1)"; RC=$?
require_exit 0 "$out"
expect_grep '^ok +w2:p5Z' "$out" "the idle pane with a faint suggestion would restart"
expect_grep '^skip background-work +w2:p2W' "$out" "background shells skip the pane"
expect_grep '^skip no-transcript +w6:p1' "$out" "a pane with no transcript is skipped"
expect_grep '^skip status working +w36:p1' "$out" "a working pane is skipped"
expect_grep '^skip status working +w36:p1 +derio-net/super-fr/run/batch-archive-followups$' "$out" "each pane line ends with its tab label (captured tab list)"
expect_grep '^1 would restart, 8 skipped, 0 failed$' "$out" "the summary includes unrelated OpenCode skip"
expect_grep 'dry run' "$out" "a dry run says so"
if grep -Eq 'send-text|send-keys|agent start|agent prompt' "$HERDR_FAKE_LOG"; then
  cat "$HERDR_FAKE_LOG" >&2; fail "a dry run sent something to herdr"
fi

# --exclude is repeatable; the excluded pane is skipped with that reason.
out="$(HERDR_ENV=1 HERDR_PANE_ID=w0:p0 fr-herdr restart-idle --exclude w2:p5Z --exclude w2:p2W 2>&1)"; RC=$?
require_exit 0 "$out"
expect_grep '^skip excluded +w2:p5Z' "$out" "an excluded pane is skipped"
expect_grep '^0 would restart, 9 skipped, 0 failed$' "$out" "nothing left to restart"

# Outside herdr: a refusal, and herdr is not asked.
: > "$HERDR_FAKE_LOG"
out="$(env -u HERDR_ENV fr-herdr restart-idle --yes 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'not inside a herdr session' "$out" "the refusal names the rule"
[ ! -s "$HERDR_FAKE_LOG" ] || fail "herdr was called outside a herdr session"
echo "ok: herdr-restart-idle"

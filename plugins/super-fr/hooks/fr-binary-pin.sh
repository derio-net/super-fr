#!/bin/bash
# SessionStart hook: pin the fr this harness's hooks run, for its shell (super-fr#746).
#
# The shell tool runs each command as `zsh -c`, which re-reads ~/.zshenv; a
# PATH rebuild there can put a different fr first than the one the hooks (no
# shell, the harness's own PATH) resolve. So PATH order cannot choose fr.
# Instead this exports `FR_HARNESS_FR=<fr --identity>` into $CLAUDE_ENV_FILE,
# which Claude Code sources before every Bash command; .zshenv leaves non-PATH
# variables alone, so the shell sees it, and fr refuses at CLI entry when a
# PATH-reached fr disagrees (fr/binary_identity.py).
#
# Fail-open: no env file, no fr, or an fr too old to know --identity exits 0
# and pins nothing — session start must never break, and an unpinned shell is
# exactly today's behaviour.

set -u

[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
# shellcheck source=lib/fr-isolation-decision.sh
. "$(cd "$(dirname "$0")" && pwd)/lib/fr-isolation-decision.sh"
fr_fr_resolve || exit 0

identity=$("$FR_FR_BIN" --identity 2>/dev/null) || exit 0
identity=${identity%%$'\n'*}
[ -n "$identity" ] || exit 0

# Single-quote the value; an embedded ' becomes '\''.
quoted=${identity//\'/\'\\\'\'}
line=$(printf "export FR_HARNESS_FR='%s'" "$quoted")

# One pin per session (super-fr#1259). ASSUMPTION, from the layout observed in Claude
# Code: $CLAUDE_ENV_FILE is one of several `sessionstart-hook-*.sh` files in one
# directory, and the harness sources ALL of them before each Bash command, in order. A
# resumed session keeps the earlier hooks' files, so an old pin there would be sourced
# and the new one lose or conflict. So append the new pin to every sibling that already
# holds a pin (a plain file, never a symlink, never one that has none), then to ours.
# Append only, never rewrite or create; a failure on any one file is ignored. Our own
# file is skipped here and appended once below. The `-L` test and the `>>` are not
# atomic (bash has no O_NOFOLLOW): a process running as this same user could swap a
# sibling for a symlink in between and receive one export line. It could already edit
# these files directly, so that grants nothing new (review p3-r2).
envdir=$(dirname "$CLAUDE_ENV_FILE")
for sibling in "$envdir"/sessionstart-hook-*.sh; do
  [ "$sibling" = "$CLAUDE_ENV_FILE" ] && continue
  [ -f "$sibling" ] && [ ! -L "$sibling" ] || continue
  grep -q '^export FR_HARNESS_FR=' "$sibling" 2>/dev/null || continue
  printf '%s\n' "$line" >>"$sibling" 2>/dev/null || true
done
printf '%s\n' "$line" >>"$CLAUDE_ENV_FILE" 2>/dev/null || exit 0
exit 0

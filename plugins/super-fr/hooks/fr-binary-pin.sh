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
command -v fr >/dev/null 2>&1 || exit 0

identity=$(fr --identity 2>/dev/null) || exit 0
identity=${identity%%$'\n'*}
[ -n "$identity" ] || exit 0

# Single-quote the value; an embedded ' becomes '\''.
quoted=${identity//\'/\'\\\'\'}
printf "export FR_HARNESS_FR='%s'\n" "$quoted" >>"$CLAUDE_ENV_FILE" 2>/dev/null || exit 0
exit 0

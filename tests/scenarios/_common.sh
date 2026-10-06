# Shared by tests/scenarios/<row>.sh (sourced, never run on its own).
#
# A scenario drives the INSTALLED `fr` (first on PATH) from its working
# directory, which `fr verification walk` and tests/integration/test_scenarios.py
# both make a fresh `git init` fixture. It asserts with grep on the CLI's output
# and exits non-zero on the first failed assertion. It never reaches a forge.
set -u
unset FR_HARNESS_FR   # the candidate is judged on its own, not on the operator's pin
export COLUMNS=200 NO_COLOR=1 FR_SKIP_MIGRATION=1 CI=true GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=scenario GIT_AUTHOR_EMAIL=scenario@example.invalid
export GIT_COMMITTER_NAME=scenario GIT_COMMITTER_EMAIL=scenario@example.invalid

fail() { echo "SCENARIO FAIL: $*" >&2; exit 1; }

# expect_grep <pattern> <text> <what>: <text> must match <pattern> (ERE).
expect_grep() {
  printf '%s\n' "$2" | grep -Eq -- "$1" || { printf '%s\n' "$2" >&2; fail "$3 (no match for: $1)"; }
}

# refuse_grep <pattern> <text> <what>: <text> must NOT match <pattern>.
refuse_grep() {
  if printf '%s\n' "$2" | grep -Eq -- "$1"; then printf '%s\n' "$2" >&2; fail "$3 (unexpected: $1)"; fi
}

# run_fr <var> <args...>: capture combined output into <var>, exit code in RC.
run_fr() {
  local __var="$1"; shift
  local __out
  __out="$(fr "$@" 2>&1)"; RC=$?
  printf -v "$__var" '%s' "$__out"
}

require_exit() { [ "$RC" -eq "$1" ] || fail "expected exit $1, got $RC: $2"; }

command -v fr >/dev/null || fail "no fr on PATH"

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

# scenario_require_fresh_repo: refuse unless the working directory is the toplevel of a
# freshly `git init`ed repo, with no commit and no remote: the fixture
# tests/integration/test_scenarios.py and `fr verification walk` hand a scenario (review
# p6-r5). A scenario that adds an origin, commits or pushes calls it FIRST, so one run
# from a real checkout refuses before it touches anything: one committed onto `main` and
# tried to push to the real remote. Run a scenario through
# `uv run pytest tests/integration/test_scenarios.py -k <name>`.
scenario_require_fresh_repo() {
  local top
  top="$(git rev-parse --show-toplevel 2>/dev/null)" ||
    fail "not a fresh fixture: $(pwd) is not a git repo (run scenarios through tests/integration/test_scenarios.py)"
  [ "$(cd "$top" && pwd -P)" = "$(pwd -P)" ] ||
    fail "not a fresh fixture: $(pwd) is not the toplevel of its repo ($top)"
  if git rev-parse --verify -q HEAD >/dev/null 2>&1; then
    fail "not a fresh fixture: $(pwd) has commits; this scenario commits and pushes, so it runs only in a freshly \`git init\`ed repo (tests/integration/test_scenarios.py)"
  fi
  [ -z "$(git remote 2>/dev/null)" ] ||
    fail "not a fresh fixture: $(pwd) has a remote ($(git remote | tr '\n' ' ')); this scenario adds its own origin and pushes to it"
}

# Long-prefix uv entrypoints may have a /bin/sh trampoline, not a Python shebang.
# Resolve the installed tool's symlink, then use its own sibling interpreter.
candidate_python() {
  local exe target i
  exe="$(command -v fr)"
  for i in 1 2 3 4 5 6 7 8; do
    [ -L "$exe" ] || break
    target="$(readlink "$exe")"
    case "$target" in /*) exe="$target" ;; *) exe="$(dirname "$exe")/$target" ;; esac
  done
  [ ! -L "$exe" ] || fail "candidate fr symlink loop"
  [ -x "$(dirname "$exe")/python" ] || fail "no candidate tool interpreter beside fr"
  printf '%s\n' "$(dirname "$exe")/python"
}

# matrix_fragment [<feature>]: stdin is a document in the RETIRED matrix shape
# (`schema_version`/`org`/`repo`, then `rows:` LAST); writes its rows, byte for
# byte, as the acceptance fragment docs/acceptance/features/<feature>.yaml
# (default `legacy`), carrying `repo: <org>/<repo>` (spec 2026-11-04 R16).
matrix_fragment() {
  local feature="${1:-legacy}"
  mkdir -p docs/acceptance/features
  awk -v feature="$feature" '
    /^schema_version:/ && !rows { next }
    /^org:/ && !rows { org = $2; next }
    /^repo:/ && !rows { repo = $2; next }
    /^rows:/ && !rows {
      print "schema_version: 2"; print "feature: " feature; print "repo: " org "/" repo
      print; rows = 1; next
    }
    rows { print }
  ' > "docs/acceptance/features/$feature.yaml"
}

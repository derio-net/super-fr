# Shared by the review-lenses-* scenarios that need a run (sourced after _common.sh,
# never run alone).
#
# lens_world <world-dir> [<base lenses.yaml text>]: turn the cwd (a fresh `git init`)
# into a base clone on `main` with a bare origin, holding the spec
# docs/superpowers/specs/2026-11-12-walk-design.md and, when given, `.fr/lenses.yaml`;
# push it, then cd into a linked worktree on `feat/walk` (an fr-isolation workspace)
# with the two-step workflow `lens-walk` (design emits the spec and writes the spec
# journal; build writes it too). Leaves the run `r1` started in that worktree.
git_ci() { git -c user.name=scenario -c user.email=scenario@example.org "$@"; }
LENS_SPEC=docs/superpowers/specs/2026-11-12-walk-design.md
LENS_SLUG=2026-11-12-walk
LENS_JOURNAL=docs/superpowers/journals/specs/$LENS_SLUG.md

lens_world() {
  lens_base "$@"
  run_fr out run start lens-walk --branch feat/walk --run-id r1
  require_exit 0 "$out"
  RECORD_VERSION="$("$(candidate_python)" -c 'from fr.record.model import RECORD_SCHEMA_VERSION as v; print(v)')" \
    || fail "cannot read the candidate's record version"
}

# lens_base <world-dir> [<base lenses.yaml text>]: lens_world without starting a run.
lens_base() {
  local world="$1" base_config="${2:-}"
  git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
  git init -q --bare -b main "$world/origin.git" || fail "bare origin"
  git remote add origin "$world/origin.git"
  mkdir -p docs/superpowers/specs docs/superpowers/workflows
  printf '# Walk\n\n## Requirements\n\nR1. Walk.\n' > "$LENS_SPEC"
  cat > docs/superpowers/workflows/lens-walk.yaml <<'YAML'
workflow: lens-walk
schema: 1
unit: run
steps:
  - id: design
    kind: agent
    emits: [spec, journal:spec]
  - id: build
    kind: agent
    needs: [spec]
    emits: [journal:spec]
YAML
  if [ -n "$base_config" ]; then
    mkdir -p .fr && printf '%s' "$base_config" > .fr/lenses.yaml
  fi
  git add -A && git_ci commit -qm base || fail "base commit"
  git push -q origin main || fail "push"
  git fetch -q origin
  git remote set-head origin main >/dev/null || fail "set-head"
  git worktree add -q -b feat/walk "$world/ws" || fail "worktree"
  cd "$world/ws" || fail "cd ws"
  printf '{"toplevel": "%s", "branch": "feat/walk", "mode": "worktree", "created_at": "2026-11-12T00:00:00+00:00"}\n' \
    "$PWD" > .fr-isolation
}

# lens_review_world <world-dir> [<base lenses.yaml text>]: lens_review_repo, then run
# `r1` on `lens-rev` with `plan` resolved and the cursor on `lens-review`, not yet
# advanced.
LENS_PLAN=2026-11-12-walk
LENS_PLAN_REL=docs/superpowers/plans/$LENS_PLAN
lens_review_world() {
  lens_review_repo "$@"
  run_fr out run start lens-rev --branch feat/walk --run-id r1
  require_exit 0 "$out"
  run_fr out run advance r1
  require_exit 0 "$out"
  run_fr out run resolve r1 --step plan --state done --emitted "plan=$LENS_PLAN_REL"
  require_exit 0 "$out"
}

# lens_review_repo <world-dir> [<base lenses.yaml text>]: lens_base, then on the branch
# the workflow `lens-rev` (plan, then the shipped `lens-review` step's evidence, then
# deliver), the plan $LENS_PLAN_REL, and a feature that changes src/app.py and
# src/auth/token.py. Starts no run.
lens_review_repo() {
  lens_base "$@"
  local repo; repo="$(cd "$here/../.." && pwd)"
  cat > docs/superpowers/workflows/lens-rev.yaml <<'YAML'
workflow: lens-rev
schema: 1
unit: run
steps:
  - id: plan
    kind: agent
    emits: [plan]
  - id: lens-review
    kind: agent
    tier: standard
    needs: [plan]
    emits: [journal:plan]
    evidence: [lenses, review, reviewer, findings]
  - id: deliver
    kind: agent
    needs: [plan]
YAML
  mkdir -p "$(dirname "$LENS_PLAN_REL")" && cp -R "$repo/tests/unit/fixtures/v2_plan_minimal" "$LENS_PLAN_REL" \
    || fail "copy the plan"
  sed -i.bak "s/2026-05-09-fixture-minimal/$LENS_PLAN/" "$LENS_PLAN_REL/_meta.yaml" \
    && rm -f "$LENS_PLAN_REL/_meta.yaml.bak"
  mkdir -p src/auth && printf 'a = 1\n' > src/app.py && printf 't = 1\n' > src/auth/token.py
  git add -A docs src && git_ci commit -qm feature || fail "feature commit"
}

# lens_opened: when the lens-review unit opened (its last attempt's dispatch).
lens_opened() {
  "$(candidate_python)" -c '
import sys
from pathlib import Path
from fr.run import units
from fr.run.model import load_run_state
a = units.last_attempt(load_run_state(Path("."), "r1"), "step/lens-review")
print(a.dispatched)' || fail "cannot read when lens-review opened"
}

# lens_session <child>=<return file>...: an OpenCode store whose `general` children
# returned those texts, inside the lens review's window; exported as the session.
lens_session() {
  local dir; dir="$(mktemp -d "$world/store.XXXX")"
  FR_OPENCODE_DB="$("$(candidate_python)" "$here/fixtures/lens-review-session.py" \
    "$dir" "$(lens_opened)" "$@")" || fail "cannot build the session store"
  export FR_HARNESS=opencode FR_OPENCODE_DB FR_OPENCODE_SESSION_ID=ses_run
  unset CLAUDE_CODE_SESSION_ID OPENCODE_SESSION_ID
}

# lens_return <file> <lens> <files> [<finding line>]: what a lens reviewer returns.
lens_return() {
  printf 'Reviewed.\n\n```review-lens\nlens: %s\nexamined: %s\n```\n\n```review-findings\n%s\n```\n' \
    "$2" "$3" "${4:-none}" > "$1"
}

# lens_step <step> <journal yaml lines> [<extra top-level yaml>]: advance to <step>,
# write its record and resolve it; the exit code is in RC, the output in $out.
lens_step() {
  local step="$1" journal="$2" extra="${3:-}"
  run_fr out run advance r1
  require_exit 0 "$out"
  local record="docs/superpowers/runs/r1.records/$step.yaml"
  mkdir -p "$(dirname "$record")"
  printf 'schema_version: %s\nrun: r1\nstep: %s\noutcome: done\njournal:\n%s\n%s' \
    "$RECORD_VERSION" "$step" "$journal" "$extra" > "$record"
  git add -A docs && git_ci commit -qm "record $step" || fail "record commit"
  run_fr out run resolve r1 --step "$step" --record "$record" --no-advance
}

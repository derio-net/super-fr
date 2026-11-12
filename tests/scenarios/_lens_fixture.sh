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
  run_fr out run start lens-walk --branch feat/walk --run-id r1
  require_exit 0 "$out"
  RECORD_VERSION="$("$(candidate_python)" -c 'from fr.record.model import RECORD_SCHEMA_VERSION as v; print(v)')" \
    || fail "cannot read the candidate's record version"
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

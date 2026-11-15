# Shared by owed-reuse-uncapped.sh and archive-refusal-writes-nothing.sh (sourced).
# Builds the closeout-owed world: a `git init` fixture with a bare local origin served
# through `insteadOf` from a github.com url, a matrix naming the repo, and one merged
# plan `$plan` for the spec `$spec`. Needs `$world` (a scratch directory) and `_common.sh`.
plan=2026-10-11-widget
spec=docs/superpowers/specs/2026-10-11-widget-design.md
key='spec:2026-10-11-widget#step2'

owed_world() {
  git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
  git init -q --bare -b main "$world/origin.git" || fail "bare origin"
  git remote add origin https://github.com/example-org/widgets.git
  git config url."$world/origin.git".insteadOf https://github.com/example-org/widgets.git
  mkdir -p docs/acceptance "docs/superpowers/plans/$plan" docs/superpowers/specs
  matrix_fragment <<'YAML'
schema_version: 5
org: example-org
repo: widgets
rows: []
YAML
  cat > "$spec" <<MD
# Widget

## Test Plan

1. Run the widget suite in CI.
2. Walk the widget live after merge.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| $plan | example-org/widgets | \`docs/superpowers/plans/$plan\` | — |
MD
  cat > "docs/superpowers/plans/$plan/_meta.yaml" <<YAML
schema_version: 2
plan: $plan
spec: $spec
target_repo: example-org/widgets
created: '2026-10-11'
YAML
  printf '# Widget plan\n' > "docs/superpowers/plans/$plan/_prose.md"
  cat > "docs/superpowers/plans/$plan/01.yaml" <<'YAML'
schema_version: 2
phase:
  number: 1
  title: Build it
  tag: agentic
  depends_on: []
  tracking_issue: null
  files:
    - src/**
tasks:
  - number: 1
    title: Build
    steps:
      - id: P1.T1.S1
        text: Build the widget
state:
  steps:
    P1.T1.S1:
      state: x
      ticked_at: null
      note: null
  completion:
    at: null
    note: null
    observed_prs: []
YAML
}

# owed_world_commit: commit the world and publish it, so the plan counts as merged.
owed_world_commit() {
  git add -A && git commit -qm seed || fail "seed commit"
  git push -q origin main || fail "push"
}

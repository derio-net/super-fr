# Shared by the docs-check-* scenarios (sourced after _common.sh, never run alone).
#
# docs_world <world-dir>: turn the cwd (already a `git init` fixture) into a repo
# on `main` with a bare local origin, `.fr/docs.yaml` naming `docs/*.md`, one page
# `docs/a.md` covering `src/*.py`, and one covered file; then branch to `feature`.
git_ci() { git -c user.name=scenario -c user.email=scenario@example.org "$@"; }

PAGE_BODY='---
title: A
covers:
  - src/*.py
reviewed: 2026-11-11 first
---
# A
'

docs_world() {
  local world="$1"
  git symbolic-ref HEAD refs/heads/main || fail "HEAD to main"
  git init -q --bare -b main "$world/origin.git" || fail "bare origin"
  git remote add origin "$world/origin.git"
  mkdir -p .fr docs src
  printf 'pages:\n  - docs/*.md\n' > .fr/docs.yaml
  printf '%s' "$PAGE_BODY" > docs/a.md
  printf 'x = 1\n' > src/x.py
  git add -A && git_ci commit -qm base || fail "base commit"
  git push -q origin main || fail "push"
  git fetch -q origin
  git remote set-head origin main >/dev/null || fail "set-head"
  git checkout -q -b feature || fail "feature branch"
}

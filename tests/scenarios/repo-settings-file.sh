#!/usr/bin/env bash
# Row repo-settings-file: `fr settings init` writes a fully commented defaults file;
# `show` reads it from the DEFAULT branch of origin (source repo), an unknown key
# on main is refused by `check` and `show` naming it, an unservable placement
# (stealth) is refused as not yet available, and quiet in this file points at the
# `fr` branch. The fixture is a fresh `git init` with a local bare origin.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

origin="$(mktemp -d)/origin.git"
git init -q --bare -b main "$origin" || fail "bare origin"
git symbolic-ref HEAD refs/heads/main || fail "branch main"
git remote add origin "$origin"
echo seed > README.md
git add -A && git commit -qm seed || fail "seed commit"
git push -q -u origin main || fail "seed push"
git remote set-head origin main >/dev/null

run_fr out settings init
require_exit 0 "$out"
[ -f .fr/settings.yaml ] || fail "init wrote no .fr/settings.yaml"
live="$(grep -Ev '^[[:space:]]*#|^[[:space:]]*$' .fr/settings.yaml || true)"
[ -z "$live" ] || fail "init left a live key: $live"
expect_grep 'Allowed: ' "$(cat .fr/settings.yaml)" "init states each key's allowed values"

run_fr out settings init
require_exit 2 "$out"

git add -A && git commit -qm "settings" && git push -q origin main || fail "land settings"
printf 'git:\n  push: ask\n' > .fr/settings.yaml
git commit -qam "ask before pushing" && git push -q origin main || fail "land push: ask"
run_fr out settings show
require_exit 0 "$out"
expect_grep 'git\.push +ask +repo' "$out" "show reports a landed key with source repo"
expect_grep 'git\.pr +auto +default' "$out" "show reports an unset key as default"

printf 'forge:\n  bogus: on\n' > .fr/settings.yaml
git commit -qam "unknown key" && git push -q origin main || fail "land unknown key"
run_fr out settings check
require_exit 2 "$out"
expect_grep 'forge\.bogus' "$out" "check names the unknown key"
run_fr out settings show
require_exit 2 "$out"
expect_grep 'forge\.bogus' "$out" "show names the unknown key"

printf 'placement: stealth\n' > .fr/settings.yaml
git commit -qam "stealth" && git push -q origin main || fail "land stealth"
run_fr out settings check
require_exit 2 "$out"
expect_grep 'not yet available' "$(printf '%s' "$out" | tr '\n' ' ')" "stealth is refused as not yet available"

# Quiet is switched on by the `fr` branch, never by this file (plan 3, phase 3).
printf 'placement: quiet\n' > .fr/settings.yaml
git commit -qam "quiet" && git push -q origin main || fail "land quiet"
run_fr out settings check
require_exit 2 "$out"
expect_grep 'fr settings init --quiet' "$(printf '%s' "$out" | tr '\n' ' ')" "quiet in .fr/settings.yaml points at the fr branch"
echo "ok: repo-settings-file"

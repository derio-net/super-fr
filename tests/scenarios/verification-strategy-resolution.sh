#!/usr/bin/env bash
# Row verification-strategy-resolution: a strategy resolves repo-first then
# shipped, a repo-authored one is usable, and a malformed manifest is refused
# by `fr verification check`.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

run_fr out verification list;                 require_exit 0 "$out"
expect_grep '^candidate +[a-z]' "$out" "candidate resolves from a shipped source"
refuse_grep ' repo$' "$out" "a fresh repo has no repo-authored strategy"

mkdir -p docs/superpowers/verifications
cat > docs/superpowers/verifications/staging.yaml <<'YAML'
verification: staging
schema: 1
description: Install a staging build; the operator drives the scenario.
when: pre-merge
driver: operator
install: null
scenario: null
source: none
YAML
run_fr out verification list;                 require_exit 0 "$out"
expect_grep '^staging +repo' "$out" "a repo-authored strategy is listed as repo"
run_fr out verification check staging;        require_exit 0 "$out"
expect_grep 'staging: ok' "$out" "the repo-authored strategy validates"

# A repo file wins wholesale over a shipped one of the same name.
sed 's/^verification: staging/verification: live/' docs/superpowers/verifications/staging.yaml \
  > docs/superpowers/verifications/live.yaml
run_fr out verification list;                 require_exit 0 "$out"
expect_grep '^live +repo' "$out" "a repo manifest shadows the shipped one"

# A manifest that names another strategy than its file is refused.
printf 'verification: other\nschema: 1\nwhen: pre-merge\ndriver: agent\n' \
  > docs/superpowers/verifications/mismatch.yaml
run_fr out verification check mismatch;       require_exit 2 "$out"
expect_grep 'mismatch' "$out" "the mismatch refusal names the strategy"

# A malformed manifest is refused, by name, and --all fails on it.
printf 'verification: broken\nschema: 1\nwhen: sometime\ndriver: agent\n' \
  > docs/superpowers/verifications/broken.yaml
run_fr out verification check broken;         require_exit 2 "$out"
expect_grep 'broken' "$out" "the refusal names the malformed strategy"
run_fr out verification check --all;          require_exit 2 "$out"
expect_grep 'broken' "$out" "--all reports the malformed strategy"
expect_grep 'candidate: ok' "$out" "--all still checks the shipped strategies"
echo "ok: verification-strategy-resolution"

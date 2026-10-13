#!/usr/bin/env bash
# Bring a repo's `protect main` ruleset to a declared state, in two stages
# (spec 2026-10-11-merge-train-safety §F, R17). Runbook: docs/merge-protection.md.
#
#   --stage bypass    set the FR_AUTOMATION_APP_ID variable and add the
#                     derio-fr-automation app as an always-bypass actor
#   --stage require   add the required `ci-ok` check with "require branches to
#                     be up to date"; refuses until the bypass is in place and
#                     the newest release commit was pushed by the app
#
# Each stage merges into the existing ruleset (deletion, non_fast_forward and
# any other rule are kept) and is a no-op when already applied. Reads nothing
# secret. --dry-run prints the request body and writes nothing. --force skips
# the release check of `require`, never its bypass check.
set -euo pipefail

RULESET_NAME="protect main"
APP_SLUG="derio-fr-automation"
VAR_NAME="FR_AUTOMATION_APP_ID"

repo="" stage="" dry=0 force=0
usage() { echo "usage: $0 [--repo OWNER/REPO] --stage bypass|require [--dry-run] [--force]" >&2; exit 2; }
while [ $# -gt 0 ]; do
  case "$1" in
    --repo | --stage)
      [ $# -ge 2 ] || usage
      if [ "$1" = "--repo" ]; then repo="$2"; else stage="$2"; fi
      shift 2 ;;
    --dry-run) dry=1; shift ;;
    --force) force=1; shift ;;
    *) usage ;;
  esac
done
case "$stage" in bypass | require) ;; *) usage ;; esac
if [ -z "$repo" ]; then
  repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi
org="${repo%%/*}"

rulesets="$(gh api "repos/$repo/rulesets")"
rs_id="$(jq -r --arg n "$RULESET_NAME" \
  '[.[] | select(.name == $n and (.source_type // "Repository") == "Repository")][0].id // empty' <<<"$rulesets")"
if [ -z "$rs_id" ]; then
  echo "no ruleset named '$RULESET_NAME' in $repo" >&2
  exit 1
fi
current="$(gh api "repos/$repo/rulesets/$rs_id")"

installs="$(gh api "orgs/$org/installations")"
app_id="$(jq -r --arg s "$APP_SLUG" '[.installations[] | select(.app_slug == $s)][0].app_id // empty' <<<"$installs")"
if [ -z "$app_id" ]; then
  echo "the $APP_SLUG app is not installed on $org" >&2
  exit 1
fi

has_bypass="$(jq --argjson id "$app_id" \
  '[(.bypass_actors // [])[] | select(.actor_type == "Integration" and .actor_id == $id)] | length > 0' <<<"$current")"

if [ "$stage" = "bypass" ]; then
  body="$(jq --argjson id "$app_id" '
    {name, target, enforcement, conditions, rules, bypass_actors}
    | .bypass_actors = ((.bypass_actors // [])
        | if any(.[]; .actor_type == "Integration" and .actor_id == $id) then .
          else . + [{actor_id: $id, actor_type: "Integration", bypass_mode: "always"}] end)
  ' <<<"$current")"
else
  if [ "$has_bypass" != "true" ]; then
    echo "refusing: the $APP_SLUG bypass actor is not on '$RULESET_NAME'; run --stage bypass first" >&2
    exit 1
  fi
  if [ "$force" -ne 1 ]; then
    tags="$(gh api --paginate "repos/$repo/tags?per_page=100" | jq -s 'add // []')"
    tag="$(jq -r '.[].name | select(test("^v[0-9]"))' <<<"$tags" | sort -V | tail -1)"
    sha="$(jq -r --arg t "$tag" '.[] | select(.name == $t) | .commit.sha' <<<"$tags")"
    if [ -z "$tag" ] || [ -z "$sha" ]; then
      echo "refusing: no v* tag found to prove a release was pushed by the app (--force skips this)" >&2
      exit 1
    fi
    runs="$(gh api "repos/$repo/actions/runs?head_sha=$sha&event=push")"
    pushed="$(jq --arg l "${APP_SLUG}[bot]" \
      '[.workflow_runs[] | select(.triggering_actor.login == $l)] | length > 0' <<<"$runs")"
    if [ "$pushed" != "true" ]; then
      echo "refusing: $tag ($sha) has no push-event run triggered by ${APP_SLUG}[bot];" >&2
      echo "a GITHUB_TOKEN push triggers none, so the release was not pushed by the app (--force skips this)" >&2
      exit 1
    fi
  fi
  body="$(jq '
    {name, target, enforcement, conditions, rules, bypass_actors}
    | (.rules // []) as $rules
    | ([$rules[] | .type] | index("required_status_checks")) as $at
    | .rules = (if $at == null then
          $rules + [{type: "required_status_checks", parameters: {
            strict_required_status_checks_policy: true,
            do_not_enforce_on_create: false,
            required_status_checks: [{context: "ci-ok"}]}}]
        else
          $rules | to_entries | map(
            if .key == $at then
              .value.parameters.strict_required_status_checks_policy = true
              | .value.parameters.required_status_checks =
                  ((.value.parameters.required_status_checks // [])
                   | if any(.[]; .context == "ci-ok") then . else . + [{context: "ci-ok"}] end)
              | .value
            else .value end)
        end)
  ' <<<"$current")"
fi

before="$(jq -S '{name, target, enforcement, conditions, rules, bypass_actors}' <<<"$current")"
after="$(jq -S . <<<"$body")"

if [ "$dry" -eq 1 ]; then
  echo "$body"
  exit 0
fi

if [ "$before" = "$after" ]; then
  echo "ruleset '$RULESET_NAME' already has the $stage stage: nothing to change"
else
  gh api -X PUT "repos/$repo/rulesets/$rs_id" --input - <<<"$body" >/dev/null
  echo "ruleset '$RULESET_NAME' updated for stage $stage:"
  echo "$body"
fi

if [ "$stage" = "bypass" ]; then
  have="$(gh variable list --repo "$repo" --json name,value -q ".[] | select(.name == \"$VAR_NAME\") | .value" || true)"
  if [ "$have" = "$app_id" ]; then
    echo "variable $VAR_NAME already $app_id"
  else
    gh variable set "$VAR_NAME" --body "$app_id" --repo "$repo"
    echo "variable $VAR_NAME set to $app_id"
  fi
fi

#!/usr/bin/env bash
# Set a repo up to release as the derio-fr-automation GitHub App, safely
# (spec 2026-11-21-release-app-hardening, R3-R14). Runbook: docs/merge-protection.md.
#
# Run it from your own shell with your own `gh`. Steps run in a fixed order:
#   1 app        the app is installed on selected repositories with exact permissions
#   2 env        the `release` environment: a main-only branch policy, no admin bypass
#   3 key        prove the .pem belongs to the app, store it as the environment secret
#   4 variable   FR_AUTOMATION_APP_ID, only once the key and main's release.yml are ready
#   5 history    "protect main": deletion + non_fast_forward, no bypass actor
#   6 tags       "protect release tags": v* deletion + update, no bypass actor
#   7 require    "require ci-ok" + the app as its only bypass, after an app-pushed release
#
# Every step reads the live state first and is a no-op ("ok: ...") when it is right.
# Every write is shown and confirmed (default no). Declining a step write stops the
# script; declining an offer (optional cleanup) continues. --dry-run writes nothing.
# --force skips only the release check of `require`. --rotate-key replaces the key.
#
# The key, the JWT and the installation token are never printed, logged or put in
# argv: the key reaches only openssl (by path) and `gh secret set` (stdin); the JWT
# and the token reach only an Authorization header that curl reads from a file
# descriptor. Never run this with `set -x`.
set -euo pipefail
umask 077

APP_SLUG="derio-fr-automation"
VAR_NAME="FR_AUTOMATION_APP_ID"
SECRET_NAME="FR_AUTOMATION_APP_KEY"
ENV_NAME="release"
RS_HISTORY="protect main"
RS_TAGS="protect release tags"
RS_REQUIRE="require ci-ok"
API="https://api.github.com"

repo="" dry=0 force=0 rotate=0
usage() {
  echo "usage: $0 [--repo OWNER/REPO] [--dry-run] [--force] [--rotate-key]" >&2
  exit 2
}
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      [ $# -ge 2 ] || usage
      repo="$2"
      shift 2 ;;
    --dry-run) dry=1; shift ;;
    --force) force=1; shift ;;
    --rotate-key) rotate=1; shift ;;
    *) usage ;;
  esac
done
if [ -z "$repo" ]; then
  repo="$(gh repo view --json nameWithOwner -q .nameWithOwner)"
fi
case "$repo" in */*) ;; *) usage ;; esac
owner="${repo%%/*}"

TMPD="$(mktemp -d)"
TOKEN=""
JWT=""
HTTP=""
READ_OUT=""

ok() { echo "ok: $*"; }
note() { echo "$*"; }

# ---- credentials: never in argv, never printed --------------------------------

api() { # api METHOD URL BEARER -> HTTP (status only); the body is in $TMPD/body
  local m="$1" u="$2" cred="$3"
  HTTP="$(curl -sS -o "$TMPD/body" -w '%{http_code}' -X "$m" \
    -H @<(printf 'Authorization: Bearer %s\n' "$cred") \
    -H 'Accept: application/vnd.github+json' "$u")" || HTTP="000"
}

revoke_token() {
  [ -n "$TOKEN" ] || return 0
  api DELETE "$API/installation/token" "$TOKEN"
  TOKEN=""
  rm -f "$TMPD/body"
}

cleanup() {
  local rc=$?
  set +e
  revoke_token
  JWT=""
  rm -rf "$TMPD"
  return $rc
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

b64url() { openssl base64 -A | tr '+/' '-_' | tr -d '='; }

make_jwt() { # make_jwt KEYPATH
  local now h p s
  now="$(date +%s)"
  h="$(printf '{"alg":"RS256","typ":"JWT"}' | b64url)"
  p="$(printf '{"iat":%s,"exp":%s,"iss":%s}' $((now - 60)) $((now + 540)) "$APP_ID" | b64url)"
  s="$(printf '%s.%s' "$h" "$p" | openssl dgst -sha256 -sign "$1" | b64url)"
  printf '%s.%s.%s' "$h" "$p" "$s"
}

# ---- reading and writing --------------------------------------------------------

# read_json <gh api args...>: READ_OUT holds the body. Returns 0 when present, 4
# when GitHub answers 404 (absent). Any other failure stops the script: an error is
# never read as "absent".
read_json() {
  local err="$TMPD/err"
  if READ_OUT="$(gh api "$@" 2>"$err" </dev/null)"; then
    return 0
  fi
  if grep -q 'HTTP 404' "$err"; then
    READ_OUT=""
    return 4
  fi
  echo "error: gh api $* failed: $(head -c 300 "$err")" >&2
  exit 1
}

gh_json() { gh api -X "$1" "$2" --input - <<<"$3" >/dev/null; } # METHOD PATH BODY
gh_delete() { gh api -X DELETE "$1" >/dev/null; }

# act <description> <command...>: a step write. Shown, confirmed (default no); a
# declined write stops the script so no later step runs on a half-made state.
act() {
  local desc="$1" ans=""
  shift
  if [ "$dry" -eq 1 ]; then
    echo "would: $desc"
    return 0
  fi
  echo "write: $desc"
  printf 'apply? [y/N] '
  read -r ans || ans=""
  case "$ans" in
    y | Y | yes | YES) ;;
    *)
      echo
      echo "declined: stopping, no later step ran" >&2
      exit 1 ;;
  esac
  "$@"
}

# offer <description> <command...>: optional cleanup. Declining continues.
offer() {
  local desc="$1" ans=""
  shift
  if [ "$dry" -eq 1 ]; then
    echo "would offer: $desc"
    return 0
  fi
  echo "offer: $desc"
  printf 'delete? [y/N] '
  read -r ans || ans=""
  case "$ans" in
    y | Y | yes | YES) "$@" ;;
    *) echo; echo "kept" ;;
  esac
}

# ---- state shared between steps --------------------------------------------------

APP_ID="" INST_ID=""
ENV_EXISTS=0 ENV_SECRET=0 VAR_VAL="" VAR_WAIT=0
MAIN_ID="" MAIN_JSON="" MAIN_BYPASS=0 MAIN_DEFERRED=0 ASSUME_MAIN_CLEAN=0

env_secret_present() {
  gh secret list --env "$ENV_NAME" --repo "$repo" --json name </dev/null \
    | jq -e --arg n "$SECRET_NAME" 'any(.[]; .name == $n)' >/dev/null && echo 1 || echo 0
}
repo_secret_present() {
  gh secret list --repo "$repo" --json name </dev/null \
    | jq -e --arg n "$SECRET_NAME" 'any(.[]; .name == $n)' >/dev/null && echo 1 || echo 0
}
var_value() {
  gh variable list --repo "$repo" --json name,value </dev/null \
    | jq -r --arg n "$VAR_NAME" '[.[] | select(.name == $n)][0].value // empty'
}

# ---- preflight: the half-done state (R11) -----------------------------------------

preflight() {
  echo "== preflight =="
  if read_json "repos/$repo/environments/$ENV_NAME"; then
    ENV_EXISTS=1
    ENV_JSON="$READ_OUT"
    ENV_SECRET="$(env_secret_present)"
  else
    ENV_EXISTS=0
    ENV_JSON=""
    ENV_SECRET=0
  fi
  VAR_VAL="$(var_value)"
  if [ -n "$VAR_VAL" ] && [ "$ENV_SECRET" -eq 0 ]; then
    note "half-done: $VAR_NAME is set but no '$ENV_NAME' environment secret $SECRET_NAME exists."
    note "Releases fail until the secret exists and main's release.yml declares 'environment: $ENV_NAME'."
    offer "unset $VAR_NAME (releases return to GITHUB_TOKEN mode until a later run sets it again)" \
      gh variable delete "$VAR_NAME" --repo "$repo"
    if [ "$dry" -eq 0 ]; then VAR_VAL="$(var_value)"; fi
  else
    ok "no half-done state"
  fi
}

# ---- 1 app (R6) -------------------------------------------------------------------

step_app() {
  echo "== 1 app =="
  local installs inst sel perms want
  installs="$(gh api "orgs/$owner/installations" </dev/null)"
  inst="$(jq -c --arg s "$APP_SLUG" '[.installations[] | select(.app_slug == $s)][0] // empty' <<<"$installs")"
  if [ -z "$inst" ]; then
    echo "refusing: the $APP_SLUG app is not installed on $owner." >&2
    echo "Install it in the web UI (docs/merge-protection.md), on selected repositories only." >&2
    exit 1
  fi
  INST_ID="$(jq -r .id <<<"$inst")"
  APP_ID="$(jq -r .app_id <<<"$inst")"
  sel="$(jq -r .repository_selection <<<"$inst")"
  perms="$(jq -cS .permissions <<<"$inst")"
  want='{"contents":"write","issues":"write","metadata":"read"}'
  if [ "$sel" != "selected" ]; then
    echo "refusing: $APP_SLUG is installed on '$sel' repositories; it must be 'selected'." >&2
    echo "Fix it in the web UI: https://github.com/organizations/$owner/settings/installations/$INST_ID" >&2
    exit 1
  fi
  if [ "$perms" != "$want" ]; then
    echo "refusing: $APP_SLUG permissions are $perms; they must be exactly $want." >&2
    echo "Fix it in the web UI: the app's settings (Permissions & events), then accept the change on the installation." >&2
    exit 1
  fi
  ok "$APP_SLUG installed on selected repositories with contents write, issues write, metadata read"
}

# ---- 2 environment (R2, R7) ---------------------------------------------------------

env_desired='{"can_admins_bypass":false,"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true},"reviewers":0,"wait_timer":0}'
env_body='{"wait_timer":0,"reviewers":[],"can_admins_bypass":false,"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'

step_env() {
  echo "== 2 env =="
  local have pol ids path="repos/$repo/environments/$ENV_NAME"
  if [ "$ENV_EXISTS" -eq 0 ]; then
    act "PUT $path $(jq -c . <<<"$env_body")" gh_json PUT "$path" "$env_body"
    act "POST $path/deployment-branch-policies {\"name\":\"main\",\"type\":\"branch\"}" \
      gh_json POST "$path/deployment-branch-policies" '{"name":"main","type":"branch"}'
    ENV_EXISTS=1
    return 0
  fi
  have="$(jq -cS '{can_admins_bypass, deployment_branch_policy,
      reviewers: ([(.protection_rules // [])[] | select(.type == "required_reviewers") | (.reviewers // [])[]] | length),
      wait_timer: ([(.protection_rules // [])[] | select(.type == "wait_timer") | .wait_timer] | add // 0)}' <<<"$ENV_JSON")"
  if [ "$have" = "$(jq -cS . <<<"$env_desired")" ]; then
    ok "environment $ENV_NAME has a custom branch policy, no admin bypass, no reviewers, no wait"
  else
    act "PUT $path $(jq -c . <<<"$env_body")" gh_json PUT "$path" "$env_body"
  fi
  read_json "$path/deployment-branch-policies" || true
  pol="$READ_OUT"
  [ -n "$pol" ] || pol='{"branch_policies":[]}'
  # every policy that is not exactly the branch `main` goes; `main` is added if missing
  ids="$(jq -r '(.branch_policies // [])[] | select(.name != "main" or .type != "branch") | .id' <<<"$pol")"
  local id
  for id in $ids; do
    act "DELETE $path/deployment-branch-policies/$id" gh_delete "$path/deployment-branch-policies/$id"
  done
  if jq -e 'any((.branch_policies // [])[]; .name == "main" and .type == "branch")' <<<"$pol" >/dev/null; then
    ok "environment $ENV_NAME allows exactly the branch main"
  else
    act "POST $path/deployment-branch-policies {\"name\":\"main\",\"type\":\"branch\"}" \
      gh_json POST "$path/deployment-branch-policies" '{"name":"main","type":"branch"}'
  fi
}

# ---- 3 key (R8, R9, R10) --------------------------------------------------------------

store_key() { gh secret set "$SECRET_NAME" --env "$ENV_NAME" --repo "$repo" <"$KEYPATH"; }
remove_key_file() { rm -f "$KEYPATH"; }

prove_key() { # prove_key KEYPATH: the key is the app's, and the app sees only this repo
  local got names
  JWT="$(make_jwt "$1")" || { echo "refusing: could not sign with that key; nothing stored" >&2; return 1; }
  api GET "$API/app" "$JWT"
  if [ "$HTTP" != "200" ]; then
    JWT=""
    echo "refusing: GET /app answered HTTP $HTTP; nothing stored" >&2
    return 1
  fi
  got="$(jq -r '.id // empty' "$TMPD/body")"
  rm -f "$TMPD/body"
  if [ "$got" != "$APP_ID" ]; then
    JWT=""
    echo "refusing: this key belongs to a different app than $APP_SLUG; nothing stored" >&2
    return 1
  fi
  api POST "$API/app/installations/$INST_ID/access_tokens" "$JWT"
  JWT=""
  if [ "$HTTP" != "201" ]; then
    echo "refusing: minting an installation token answered HTTP $HTTP; nothing stored" >&2
    return 1
  fi
  TOKEN="$(jq -r '.token // empty' "$TMPD/body")"
  rm -f "$TMPD/body"
  if [ -z "$TOKEN" ]; then
    echo "refusing: no installation token came back; nothing stored" >&2
    return 1
  fi
  api GET "$API/installation/repositories" "$TOKEN"
  if [ "$HTTP" != "200" ]; then
    revoke_token
    echo "refusing: reading the installation's repositories answered HTTP $HTTP; nothing stored" >&2
    return 1
  fi
  names="$(jq -r '[.repositories[].full_name] | sort | join(",")' "$TMPD/body")"
  rm -f "$TMPD/body"
  revoke_token
  if [ "$names" != "$repo" ]; then
    echo "refusing: the installation reaches [$names], not only $repo; nothing stored." >&2
    echo "Fix it in the web UI: https://github.com/organizations/$owner/settings/installations/$INST_ID" >&2
    return 1
  fi
  return 0
}

step_key() {
  echo "== 3 key =="
  local path=""
  if [ "$ENV_SECRET" -eq 1 ] && [ "$rotate" -eq 0 ]; then
    ok "environment secret $SECRET_NAME exists in $ENV_NAME"
    note "No key at hand, so the installation's repositories are not checked here."
    note "Confirm that only $repo is selected: https://github.com/organizations/$owner/settings/installations/$INST_ID"
  elif [ "$dry" -eq 1 ]; then
    echo "would: read the key path, prove it with GET /app and the repository list, then gh secret set $SECRET_NAME --env $ENV_NAME --repo $repo (key on stdin)"
    ENV_SECRET=1
  else
    printf 'path to the app private key (.pem): '
    read -r path || path=""
    path="${path/#\~/$HOME}"
    if [ -z "$path" ] || [ ! -f "$path" ]; then
      echo "refusing: no such file" >&2
      exit 1
    fi
    if ! head -n 1 "$path" | grep -Eq '^-----BEGIN (RSA )?PRIVATE KEY-----'; then
      echo "refusing: that file is not a PEM private key" >&2
      exit 1
    fi
    prove_key "$path" || exit 1
    ok "the key belongs to $APP_SLUG and the installation reaches only $repo"
    KEYPATH="$path"
    act "gh secret set $SECRET_NAME --env $ENV_NAME --repo $repo (key read from the file on stdin)" store_key
    ENV_SECRET=1
    offer "delete the key file" remove_key_file
  fi
  if [ "$ENV_SECRET" -eq 1 ] && [ "$(repo_secret_present)" -eq 1 ]; then
    note "leak path: a repository-level secret $SECRET_NAME exists; any branch workflow can read it."
    offer "delete the repository-level secret $SECRET_NAME" gh secret delete "$SECRET_NAME" --repo "$repo"
  fi
}

# ---- 4 variable (R11) -----------------------------------------------------------------

main_release_declares_env() {
  local out
  read_json "repos/$repo/contents/.github/workflows/release.yml?ref=main" || return 1
  out="$(jq -r '.content // empty' <<<"$READ_OUT" | openssl base64 -d 2>/dev/null)" || return 1
  grep -Eq "^    environment: ${ENV_NAME}[[:space:]]*\$" <<<"$out"
}

step_variable() {
  echo "== 4 variable =="
  if [ "$VAR_VAL" = "$APP_ID" ] && [ "$ENV_SECRET" -eq 1 ]; then
    ok "$VAR_NAME is $APP_ID"
    return 0
  fi
  if [ "$ENV_SECRET" -eq 0 ]; then
    VAR_WAIT=1
    note "waits: $VAR_NAME is set only once the $ENV_NAME environment secret exists."
    return 0
  fi
  if ! main_release_declares_env; then
    VAR_WAIT=1
    note "waits: main's release.yml does not declare 'environment: $ENV_NAME' yet; merge the PR that does, then rerun."
    return 0
  fi
  act "gh variable set $VAR_NAME --body $APP_ID --repo $repo" \
    gh variable set "$VAR_NAME" --body "$APP_ID" --repo "$repo"
  VAR_VAL="$APP_ID"
}

# ---- rulesets ------------------------------------------------------------------------------

# find_ruleset NAME: sets RS_ID (empty when absent) and RS_JSON from the repository's own rulesets
RS_ID="" RS_JSON=""
find_ruleset() {
  local list
  list="$(gh api "repos/$repo/rulesets" </dev/null)"
  RS_ID="$(jq -r --arg n "$1" \
    '[.[] | select(.name == $n and (.source_type // "Repository") == "Repository")][0].id // empty' <<<"$list")"
  RS_JSON=""
  if [ -n "$RS_ID" ]; then
    RS_JSON="$(gh api "repos/$repo/rulesets/$RS_ID" </dev/null)"
  fi
}
project='{name, target, enforcement, conditions, rules, bypass_actors}'

load_main() {
  find_ruleset "$RS_HISTORY"
  MAIN_ID="$RS_ID"
  MAIN_JSON="$RS_JSON"
  MAIN_BYPASS=0
  MAIN_DEFERRED=0
  if [ -n "$MAIN_ID" ]; then
    MAIN_BYPASS="$(jq '(.bypass_actors // []) | length' <<<"$MAIN_JSON")"
    if jq -e 'any((.rules // [])[]; .type == "required_status_checks")' <<<"$MAIN_JSON" >/dev/null; then
      MAIN_DEFERRED=1
    fi
  fi
}

# ---- 5 history (R12) ---------------------------------------------------------------------------

step_history() {
  echo "== 5 history =="
  local body
  load_main
  if [ -z "$MAIN_ID" ]; then
    body='{"name":"protect main","target":"branch","enforcement":"active","conditions":{"ref_name":{"include":["~DEFAULT_BRANCH"],"exclude":[]}},"rules":[{"type":"deletion"},{"type":"non_fast_forward"}],"bypass_actors":[]}'
    act "POST repos/$repo/rulesets $(jq -c . <<<"$body")" gh_json POST "repos/$repo/rulesets" "$body"
    return 0
  fi
  if [ "$MAIN_DEFERRED" -eq 1 ]; then
    note "deferred: '$RS_HISTORY' still holds a required_status_checks rule; its bypass stays,"
    note "and the require step moves both. Removing the bypass now would refuse the app's release push."
    return 0
  fi
  body="$(jq "$project | .bypass_actors = []
    | (.rules // []) as \$r
    | .rules = (\$r + ([\"deletion\", \"non_fast_forward\"]
        | map(. as \$t | select(any(\$r[]; .type == \$t) | not) | {type: \$t})))" <<<"$MAIN_JSON")"
  if [ "$(jq -S . <<<"$body")" = "$(jq -S "$project" <<<"$MAIN_JSON")" ]; then
    ok "'$RS_HISTORY' holds deletion and non_fast_forward with no bypass actor"
  else
    act "PUT repos/$repo/rulesets/$MAIN_ID $(jq -c . <<<"$body")" gh_json PUT "repos/$repo/rulesets/$MAIN_ID" "$body"
    ASSUME_MAIN_CLEAN=1 # a dry run read the live state, which the write did not change
  fi
}

# ---- 6 tags (R13) ----------------------------------------------------------------------------------

step_tags() {
  echo "== 6 tags =="
  local body
  body='{"name":"protect release tags","target":"tag","enforcement":"active","conditions":{"ref_name":{"include":["refs/tags/v*"],"exclude":[]}},"rules":[{"type":"deletion"},{"type":"update"}],"bypass_actors":[]}'
  find_ruleset "$RS_TAGS"
  if [ -z "$RS_ID" ]; then
    act "POST repos/$repo/rulesets $(jq -c . <<<"$body")" gh_json POST "repos/$repo/rulesets" "$body"
    return 0
  fi
  if jq -e '.target == "tag" and .enforcement == "active"
        and .conditions.ref_name.include == ["refs/tags/v*"]
        and ([.rules[].type] | sort) == ["deletion", "update"]
        and ((.bypass_actors // []) | length) == 0' <<<"$RS_JSON" >/dev/null; then
    ok "'$RS_TAGS' holds deletion and update on refs/tags/v* with no bypass actor"
  else
    act "PUT repos/$repo/rulesets/$RS_ID $(jq -c . <<<"$body")" gh_json PUT "repos/$repo/rulesets/$RS_ID" "$body"
  fi
}

# ---- 7 require (R14) ----------------------------------------------------------------------------------

release_pushed_by_app() { # the newest v* tag's commit has a push run triggered by the app
  local tags tag sha runs
  tags="$(gh api --paginate "repos/$repo/tags?per_page=100" </dev/null | jq -s 'add // []')"
  tag="$(jq -r '.[].name | select(test("^v[0-9]"))' <<<"$tags" | sort -V | tail -1)"
  sha="$(jq -r --arg t "$tag" '.[] | select(.name == $t) | .commit.sha' <<<"$tags")"
  if [ -z "$tag" ] || [ -z "$sha" ]; then
    note "waits: no v* tag exists to prove a release was pushed by the app."
    return 1
  fi
  runs="$(gh api "repos/$repo/actions/runs?head_sha=$sha&event=push" </dev/null)"
  if jq -e --arg l "${APP_SLUG}[bot]" 'any(.workflow_runs[]; .triggering_actor.login == $l)' <<<"$runs" >/dev/null; then
    return 0
  fi
  note "waits: $tag ($sha) has no push-event run triggered by ${APP_SLUG}[bot]."
  note "A GITHUB_TOKEN push triggers none, so that release was not pushed by the app. Rerun after an app-pushed release (--force skips this check)."
  return 1
}

require_body() {
  jq -n --argjson id "$APP_ID" '{name: "require ci-ok", target: "branch", enforcement: "active",
    conditions: {ref_name: {include: ["~DEFAULT_BRANCH"], exclude: []}},
    rules: [{type: "required_status_checks", parameters: {
      strict_required_status_checks_policy: true, do_not_enforce_on_create: false,
      required_status_checks: [{context: "ci-ok"}]}}],
    bypass_actors: [{actor_id: $id, actor_type: "Integration", bypass_mode: "always"}]}'
}

step_require() {
  echo "== 7 require =="
  local body exists=0 correct=0
  load_main
  if [ "$ASSUME_MAIN_CLEAN" -eq 1 ] && [ "$dry" -eq 1 ]; then MAIN_BYPASS=0; fi
  find_ruleset "$RS_REQUIRE"
  if [ -n "$RS_ID" ]; then
    exists=1
    if jq -e --argjson id "$APP_ID" '
        any((.rules // [])[]; .type == "required_status_checks"
            and .parameters.strict_required_status_checks_policy == true
            and any((.parameters.required_status_checks // [])[]; .context == "ci-ok"))
        and ((.bypass_actors // []) | length) == 1
        and .bypass_actors[0].actor_type == "Integration" and .bypass_actors[0].actor_id == $id
        and .bypass_actors[0].bypass_mode == "always"' <<<"$RS_JSON" >/dev/null; then
      correct=1
    fi
  fi
  if [ "$correct" -eq 1 ] && [ "$MAIN_DEFERRED" -eq 0 ]; then
    ok "'$RS_REQUIRE' requires ci-ok with the app as its only bypass actor"
    return 0
  fi
  # preconditions: only when a write is needed
  if [ "$ENV_SECRET" -eq 0 ]; then
    echo "refusing: the $ENV_NAME environment secret $SECRET_NAME does not exist." >&2
    exit 1
  fi
  if [ -z "$VAR_VAL" ] && [ "$dry" -eq 0 ]; then
    if [ "$VAR_WAIT" -eq 1 ]; then
      note "waits: $VAR_NAME is not set yet (see step 4); the require step follows it."
      return 0
    fi
    echo "refusing: $VAR_NAME is not set." >&2
    exit 1
  fi
  if [ "$MAIN_ID" != "" ] && [ "$MAIN_BYPASS" -gt 0 ] && [ "$MAIN_DEFERRED" -eq 0 ]; then
    echo "refusing: '$RS_HISTORY' still has a bypass actor; run the history step first." >&2
    exit 1
  fi
  if [ "$force" -ne 1 ] && ! release_pushed_by_app; then
    return 0
  fi
  body="$(require_body)"
  if [ "$exists" -eq 0 ]; then
    act "POST repos/$repo/rulesets $(jq -c . <<<"$body")" gh_json POST "repos/$repo/rulesets" "$body"
  elif [ "$correct" -eq 0 ]; then
    act "PUT repos/$repo/rulesets/$RS_ID $(jq -c . <<<"$body")" gh_json PUT "repos/$repo/rulesets/$RS_ID" "$body"
  fi
  if [ "$MAIN_DEFERRED" -eq 1 ]; then
    local main_body
    main_body="$(jq "$project | .bypass_actors = []
      | .rules |= map(select(.type != \"required_status_checks\"))" <<<"$MAIN_JSON")"
    act "PUT repos/$repo/rulesets/$MAIN_ID $(jq -c . <<<"$main_body")" gh_json PUT "repos/$repo/rulesets/$MAIN_ID" "$main_body"
  fi
}

preflight
step_app
step_env
step_key
step_variable
step_history
step_tags
step_require
echo "done."

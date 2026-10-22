#!/usr/bin/env bash
# Row fr-ops-seal-no-plaintext: a failing encrypt command leaves the target
# byte-identical and no plaintext anywhere in the repo or $TMPDIR; success replaces
# the target; an interrupted seal cleans up; the helpers never print a secret.
# The ops profile is a fixture fr-profiles.yaml (`ops: true`) plus FR_PROFILE and
# KUBERNETES_SERVICE_HOST as container evidence.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$here/_common.sh"

work="$(mktemp -d)"
export TMPDIR="$work/tmp"; mkdir -p "$TMPDIR"
export FR_PROFILE=ops KUBERNETES_SERVICE_HOST=10.0.0.1
py="$(candidate_python)"

git init -q -b main . || fail "git init"
mkdir -p .devcontainer
cat > .devcontainer/fr-profiles.yaml <<'YAML'
profiles:
  ops: {purpose: operate, secrets: [], ops: true}
default: ops
YAML
printf 'old-ciphertext\n' > secret.enc
git add -A && git commit -qm seed || fail "seed commit"
PLAIN="PLAINTEXT-MARKER-$$"

no_leftovers() {
  if grep -rq -- "$PLAIN" . 2>/dev/null; then fail "plaintext found in the repo ($1)"; fi
  if grep -rq -- "$PLAIN" "$TMPDIR" 2>/dev/null; then fail "plaintext found in TMPDIR ($1)"; fi
  [ -z "$(find . "$TMPDIR" -name '.seal-*' 2>/dev/null)" ] || fail "temp files left behind ($1)"
}

# --- refused outside an ops profile ---------------------------------------------------------
out="$(printf '%s' "$PLAIN" | env -u FR_PROFILE fr ops seal --encrypt 'cat {in} > {out}' --target secret.enc 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'fr isolation up --profile' "$out" "seal refuses outside an ops profile"
[ "$(cat secret.enc)" = "old-ciphertext" ] || fail "a refused seal touched the target"

# --- a failing encrypt command ----------------------------------------------------------------
out="$(printf '%s' "$PLAIN" | fr ops seal --encrypt 'cat {in} > /dev/null; echo partial > {out}; exit 3' --target secret.enc 2>&1)"; RC=$?
[ "$RC" -ne 0 ] || fail "a failing encrypt command exited 0"
[ "$(cat secret.enc)" = "old-ciphertext" ] || fail "the target changed on failure"
no_leftovers "after a failure"
# an empty {out} is a failure too
out="$(printf '%s' "$PLAIN" | fr ops seal --encrypt 'true' --target secret.enc 2>&1)"; RC=$?
[ "$RC" -ne 0 ] || fail "an empty {out} exited 0"
[ "$(cat secret.enc)" = "old-ciphertext" ] || fail "the target changed on an empty {out}"
no_leftovers "after an empty out"

# --- success replaces the target ---------------------------------------------------------------
out="$(printf '%s' "$PLAIN" | fr ops seal --encrypt 'rev < {in} > {out}' --target secret.enc 2>&1)"; RC=$?
require_exit 0 "$out"
[ "$(cat secret.enc)" = "$(printf '%s' "$PLAIN" | rev)" ] || fail "the target was not replaced"
no_leftovers "after success"

# --- an interrupted seal cleans up ------------------------------------------------------------------
before="$(cat secret.enc)"
printf '%s' "$PLAIN" | "$py" -c 'from fr.cli import app; app()' ops seal --encrypt 'sleep 30' --target secret.enc >"$work/int.out" 2>&1 &
pid=$!
for _ in $(seq 1 100); do
  [ -n "$(find . "$TMPDIR" -name '.seal-out-*' 2>/dev/null)" ] && break
  sleep 0.1
done
[ -n "$(find . "$TMPDIR" -name '.seal-out-*' 2>/dev/null)" ] || { kill "$pid" 2>/dev/null; fail "the seal never reached its encrypt command"; }
kill -TERM "$pid"
wait "$pid"; RC=$?
[ "$RC" -ne 0 ] || fail "an interrupted seal exited 0"
[ "$(cat secret.enc)" = "$before" ] || fail "the target changed on interruption"
no_leftovers "after SIGTERM"

# --- a planted symlink is refused ----------------------------------------------------------------------
printf 'victim' > "$work/victim"; ln -s "$work/victim" link.enc
out="$(printf '%s' "$PLAIN" | fr ops seal --encrypt 'echo x > {out}' --target link.enc 2>&1)"; RC=$?
require_exit 2 "$out"
expect_grep 'symlink' "$out" "a symlinked target is refused"
[ "$(cat "$work/victim")" = "victim" ] || fail "the symlink's destination changed"

# --- the helpers never print a secret ---------------------------------------------------------------------
out="$(fr ops secret --from "printf '%s' $PLAIN" -- sh -c 'cat > got.txt' 2>&1)"; RC=$?
require_exit 0 "$out"
refuse_grep "$PLAIN" "$out" "secret printed the value"
[ "$(cat got.txt)" = "$PLAIN" ] || fail "the value did not reach the command's stdin"
rm -f got.txt

echo "ok: fr-ops-seal"

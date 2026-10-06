# Sourced by tests/scenarios/model-binding-*.sh (after _common.sh) — never run
# on its own, and underscore-prefixed so tests/integration/test_scenarios.py's
# "every scenario has a test" check ignores it.
#
# Puts a stub `opencode` first on PATH, scripted per model from files the
# scenario writes, so a walk is deterministic and spends nothing:
#
#   $STUB/catalogue-<provider>.txt   what `opencode models <p> --verbose` prints
#   $STUB/table                      `<model> <state>` lines for `opencode run --model=<model>`
#   $STUB/calls.log                  every model `opencode run` was asked about
#
# States: live | notfound[:<hint>] | unsupported | error. A model not in the
# table is live. The three failure outputs have the shapes captured from the
# real CLI in tests/fixtures/bindings/ (`unsupported` is the one transcribed from
# super-fr#591); `error` is the stream a server error leaves, with nothing on
# stderr to say why.
#
# Every scenario that sources this gets a throwaway HOME and XDG_CONFIG_HOME, so
# nothing reads or writes the operator's config or caches.

stub_reset() {
  [ -n "${STUB:-}" ] && rm -rf "$STUB"   # each case gets a fresh HOME: no cache or snapshot carries over
  STUB="$(mktemp -d)"
  trap 'rm -rf "$STUB"' EXIT
  export HOME="$STUB/home" XDG_CONFIG_HOME="$STUB/home/.config"
  mkdir -p "$HOME" "$XDG_CONFIG_HOME/fr" "$STUB/bin"
  : > "$STUB/table"; : > "$STUB/calls.log"
  rm -f "$STUB"/catalogue-*.txt
  cat > "$STUB/bin/opencode" <<'STUB_SH'
#!/usr/bin/env bash
stub="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$1" = models ]; then cat "$stub/catalogue-$2.txt" 2>/dev/null; exit 0; fi
model=""
while [ $# -gt 0 ]; do case "$1" in --model=*) model="${1#--model=}";; esac; shift; done
echo "$model" >> "$stub/calls.log"
state="$(awk -v m="$model" '$1 == m { print $2 }' "$stub/table")"
case "${state:-live}" in
  live)
    echo '{"type":"text","part":{"type":"text","text":"OK"}}' ;;
  notfound*)
    hint="${state#notfound}"; hint="${hint#:}"
    msg="ProviderModelNotFoundError: Model not found: $model."
    [ -n "$hint" ] && msg="$msg Did you mean: $hint?"
    echo "timestamp=2026-01-01T00:00:00.000Z level=ERROR message=failed error=\"$msg\"" >&2
    echo '{"type":"error","error":{"name":"UnknownError","data":{"message":"Unexpected server error."}}}'
    exit 1 ;;
  unsupported)
    echo "Error: The requested model is not supported." >&2
    exit 1 ;;
  *)
    echo '{"type":"error","error":{"name":"UnknownError","data":{"message":"Unexpected server error."}}}' ;;
esac
STUB_SH
  chmod +x "$STUB/bin/opencode"
  export PATH="$STUB/bin:$PATH"
}

# stub_model <provider> <name> <family> <release_date> <price> [status]: one
# catalogue block in the shape `opencode models <p> --verbose` prints (a
# `provider/id` line, then a JSON object); <price> is split input:output 1:5.
stub_model() {
  local out="$STUB/catalogue-$1.txt" in_cost out_cost
  in_cost="$5"; out_cost="$(( $5 * 5 ))"
  { printf '%s/%s\n' "$1" "$2"
    printf '{\n  "id": "%s",\n  "providerID": "%s",\n  "status": "%s",\n' "$2" "$1" "${6:-active}"
    printf '  "capabilities": {"toolcall": true},\n  "family": "%s",\n' "$3"
    printf '  "cost": {"input": %s, "output": %s},\n  "release_date": "%s"\n}\n' "$in_cost" "$out_cost" "$4"
  } >> "$out"
}

# stub_state <model> <state>: script `opencode run --model=<model>`.
stub_state() { printf '%s %s\n' "$1" "$2" >> "$STUB/table"; }

# bind_models <harness> <tier=model>...: write the user models.yaml.
bind_models() {
  local harness="$1"; shift
  { printf '%s:\n' "$harness"; for kv in "$@"; do printf '  %s: %s\n' "${kv%%=*}" "${kv#*=}"; done; } \
    >> "$XDG_CONFIG_HOME/fr/models.yaml"
}

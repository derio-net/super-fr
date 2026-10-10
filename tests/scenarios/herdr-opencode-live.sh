#!/usr/bin/env bash
# Operator-led client-live walk. Never sends input or mutates production state.
set -euo pipefail
cat <<'WALK'
OWED: operator-led herdr client-live walk (Refs #1089).
Use a disposable repository, scope and named sessions inside the real herdr client.
Never use a production batch; preserve any source transcripts until inspected.
Record installed fr/herdr/OpenCode versions and redacted pane/name/branch evidence.

1. Dispatch a disposable OpenCode batch with an explicit provider/model. Observe
   ready identity, brief uptake and the stable primary-checkout foreground cwd.
2. From ANOTHER pane, preview batch replace with --reason; observe no keys/writes.
   Act with --yes: Claude→OpenCode, OpenCode→Claude, then a model-only change.
   Verify original dispatch time, reservation, branch/workspace, PR, pane and name.
3. Observe working/blocked refusal, unsent draft and command-overlay refusal.
   Do not clear a draft or answer any approval/exit dialog to make the test pass.
4. Preview/act fr-herdr restart-idle. Observe fresh managed OpenCode recovery,
   current conflict hand-back, close-out pickup gates and delivered-draft HOLD.
   Verify status, messaging, focus and deduplication still address the same item.
5. Induce target startup failure ONLY in disposable state. Observe source/target/
   shell diagnostics, unchanged launch metadata and a visible pending attempt.
   Inspect and use replace --repair --reason <inspection> --yes; confirm no launch
   or prompt replay. Uncertain submission cannot be certified from model alone.
6. Save a redacted observation log for EVERY check. Leave Ready unchecked on any
   failure/missing observation. Restore/close only the disposable sessions you own.

This script only prints the walk; passing instruction tests are NOT live evidence.
WALK
case "${1:-}" in
  "") exit 3 ;; # printing instructions is not a passing client-live walk
  --record-verdict)
    [ -t 0 ] || { echo 'Operator verdict requires an interactive terminal.' >&2; exit 2; }
    read -r -p 'Observed EVERY check? Type PASS or FAIL: ' verdict
    read -r -p 'Path to the redacted observation log: ' log
    [ -f "$log" ] && [ -s "$log" ] || { echo 'Nonempty observation log required.' >&2; exit 2; }
    [ "$verdict" = PASS ] || { echo 'Live walk failed or remains owed.' >&2; exit 1; }
    echo "operator verdict: PASS; evidence: $log (record via acceptance CLI)"
    ;;
  *) echo 'Usage: herdr-opencode-live.sh [--record-verdict]' >&2; exit 2 ;;
esac

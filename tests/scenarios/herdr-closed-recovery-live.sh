#!/usr/bin/env bash
# Post-merge Tester walk. This script NEVER launches clients or changes panes/state.
set -euo pipefail
instructions() {
cat <<'WALK'
OWED: post-merge Tester closed-session recovery walk, operator-owned.
OPERATOR GATE: explicitly authorize a disposable repository/scope and fixture
sessions BEFORE any fixture harness launch. Never select a real paused org batch,
its triage state, a production pane, or any org driver. No six-batch takeover.

1. On the merged candidate, record redacted installed fr/herdr/OpenCode versions.
   Create only a disposable local git repository, branch, scope and batch/run.
   Dispatch that fixture with explicit OpenCode provider/model and --auto. Keep
   its existing isolation workspace, dirty file, cursor, journal and original audit.
   Choose a pending operator brainstorm gate or running unit; do not answer it.
2. From a DIFFERENT control pane, close ONLY that fixture's source pane manually.
   Record original item/pane/name, branch, dispatch time and version reservation.
   Use the fixture's exact --dir and --checkout plus --repo (or its fixture --org).
   Preview: fr triage batch replace <fixture-id> --recover --harness opencode
   --model openai/gpt-6.1-sol --reason <closed-fixture> <fixture-scope-options>.
   Observe zero allocations/launches/inputs/state writes and the printed HOLD.
3. After separate explicit operator approval, repeat that exact command with --yes.
   Observe a NEW herdr-allocated pane, canonical unchanged item name, stable primary
   checkout cwd, --auto and explicit provider/model, a fresh observable session id,
   ONE reconstruction brief, and acknowledge/report-only HOLD. Record terminal
   readiness and rendered safe empty input (no overlays/draft/trust dialog bypass).
   Verify dirty work, branch/workspace, cursor, records, journal, members, dependencies,
   reservation and ORIGINAL dispatch/history unchanged. Confirm no unit was abandoned
   or rebound, no gate answered, no PR approved/readied/merged and no driver restarted.
4. Repeated --recover refuses the surviving target. Preview/act managed restart ONLY
   for this fixture; HOLD must precede conflict or unfinished/delivered continuation.
   Keep pending gates intact. Release ONLY by a separate instruction to that session;
   recovery/repair itself never grants continuation and restarts begin held again.
5. In a SECOND disposable fixture, interrupt after allocation/preparation or inject a
   controlled target-start failure. Preserve the target; do not clean it blindly.
   Inspect source-keyed recovery intent and fresh GLOBAL pane-list/tab-list join.
   Explicit --repair --reason <inspection> --yes sends NO launch/input. Uncertain
   submission cannot be certified without persisted uptake and matching session id.
   For confirmed aborted failure a NEW allocation needs a NEW explicit recovery act.
6. Save redacted evidence for every check; close only the disposable sessions you own.
   Missing/failing evidence leaves triage-closed-recovery-live walk-owed. A passing
   automated instruction test is NOT a live pass. Record the real verdict with the
   acceptance/walk CLI and pass the post-merge Tester gate only after all checks pass.
WALK
}
case "${1:-}" in
  "") instructions; exit 3 ;;
  --record-verdict) ;;
  *) echo 'Usage: herdr-closed-recovery-live.sh [--record-verdict]' >&2; exit 2 ;;
esac
if ! { exec 3<>/dev/tty; } 2>/dev/null || [ ! -t 3 ]; then
  instructions
  echo 'Interactive operator verdict required; live walk remains owed.' >&2
  exit 3
fi
instructions >&3
printf 'Did you authorize disposable fixtures and observe EVERY check? Type PASS or FAIL: ' >&3
IFS= read -r verdict <&3
printf 'Path to a nonempty redacted evidence log: ' >&3
IFS= read -r log <&3
[ "$verdict" = PASS ] && [ -f "$log" ] && [ -s "$log" ] || exit 1
echo "operator verdict: PASS; evidence: $log (record via acceptance/walk CLI)"

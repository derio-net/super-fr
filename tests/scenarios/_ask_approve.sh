# Shared by the stealth scenarios (sourced, never run on its own; needs _common.sh).
#
# Under stealth `git.push` and `git.pr` are always `ask` (spec 2026-11-28-alacarte-settings
# R7, R9): `fr push` of code and `fr pr create` refuse once with a request, and go ahead
# only on an operator approval fr can verify in the session's transcript. A scenario has no
# operator and no harness, so `fr_approved` stands in for both, the way a session does it:
# it records the decision with the exact `fr journal add` line the request prints, and
# answers the request in a Claude Code transcript built from the CAPTURED
# `AskUserQuestion` exchange (tests/fixtures/transcripts/claude-code-askuserquestion.jsonl,
# claude-code-session.NOTE.md says how it was taken). Only the question text, the answer, the ids and the
# timestamps are edited; the shape is the capture's.

ASK_ROOT="$(mktemp -d)"
ASK_SESSION="scenario-ask-session"
ASK_FIXTURE="$here/../fixtures/transcripts/claude-code-askuserquestion.jsonl"

# ask_transcript <request-id>: append a question naming <request-id>, answered with
# exactly `Approve <request-id>`, to the scenario session's transcript.
ask_transcript() {
  local py
  py="$(candidate_python)"
  mkdir -p "$ASK_ROOT/scenario"
  "$py" -P - "$ASK_FIXTURE" "$ASK_ROOT/scenario/$ASK_SESSION.jsonl" "$1" "$ASK_SESSION" <<'PY' \
    || fail "write the approval transcript for $1"
import datetime
import json
import sys

src, dst, rid, session = sys.argv[1:5]
question, answer = [json.loads(line) for line in open(src) if line.strip()][:2]
now = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
text = f"May fr write to the remote? request {rid}"
asked = {
    "question": text,
    "header": "Approve",
    "multiSelect": False,
    "options": [
        {"label": f"Approve {rid}", "description": "fr goes ahead"},
        {"label": "Decline", "description": "fr does not"},
    ],
}
tool_id = f"toolu_{rid}"
question["message"]["content"][0]["id"] = tool_id
question["message"]["content"][0]["input"]["questions"] = [asked]
answer["message"]["content"][0]["tool_use_id"] = tool_id
answer["message"]["content"][0]["content"] = (
    f'Your questions have been answered: "{text}"="Approve {rid}"'
)
answer["toolUseResult"] = {"questions": [asked], "answers": {text: f"Approve {rid}"}}
question["uuid"], answer["uuid"] = f"q-{rid}", f"a-{rid}"
answer["sourceToolAssistantUUID"] = question["uuid"]
for row in (question, answer):
    row["timestamp"] = now
    row["sessionId"] = session
with open(dst, "a") as out:
    for row in (question, answer):
        out.write(json.dumps(row) + "\n")
PY
}

# fr_approved <var> <fr args...>: like run_fr; when the command stops on an ask request,
# approve it (journal line + transcript answer) and run it again as that session.
fr_approved() {
  local __var="$1"; shift
  local __out __rid __cmd
  __out="$(fr "$@" 2>&1)"; RC=$?
  __rid="$(printf '%s\n' "$__out" | sed -n 's/.*(git\.[a-z]*: ask): request \([^ ]*\)\.$/\1/p' | head -1)"
  if [ "$RC" -eq 2 ] && [ -n "$__rid" ]; then
    __cmd="$(printf '%s\n' "$__out" | sed -n 's/^ *\(fr journal add .*\)$/\1/p' | head -1)"
    [ -n "$__cmd" ] || fail "the request names no journal line: $__out"
    ask_transcript "$__rid"
    ( export CLAUDECODE=1 CLAUDE_CODE_SESSION_ID="$ASK_SESSION" FR_TRANSCRIPT_ROOT="$ASK_ROOT"
      eval "$__cmd" ) >/dev/null 2>&1 || fail "record the approval: $__cmd"
    __out="$(CLAUDECODE=1 CLAUDE_CODE_SESSION_ID="$ASK_SESSION" FR_TRANSCRIPT_ROOT="$ASK_ROOT" \
      fr "$@" 2>&1)"; RC=$?
  fi
  printf -v "$__var" '%s' "$__out"
}

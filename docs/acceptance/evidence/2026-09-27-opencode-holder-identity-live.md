# Live run — who holds an OpenCode dispatch (gh#537, gh#530)

Captured 2026-09-27 on OpenCode 1.18.32 (model `github-copilot/gpt-6-luna`), driven from a
Claude Code session through a herdr pane, against PR #736's branch before merge.

## Set-up

- A scratch fr repo with a one-step workflow: `implement`, `kind: agent`,
  `agent: super-fr:fr-phase-executor`, `tier: mechanical`. Run `r1` was started in a
  host-worktree workspace (`FR_ISOLATION_TARGET=worktree`).
- The repo's `.opencode/plugins/` re-exported the branch's `packages/fr-opencode-plugin`,
  and a wrapper that ran the branch's `fr` (`uv run --project <worktree> fr`) was put first
  on the pane's PATH.
- The #537 condition was reproduced deliberately. A herdr pane inherits herdr's
  environment, not Claude Code's, so OpenCode was launched with `CLAUDECODE=1`,
  `CLAUDE_CODE_CHILD_SESSION=1` and a marked fake `CLAUDE_CODE_SESSION_ID` exported.
  `CLAUDE_PID` was set to the herdr process, a real ancestor further out than OpenCode,
  which is where Claude Code sits when it launches OpenCode.

## What happened

**1. The old `fr` reproduced #537.** OpenCode's shell tool resolved `fr` to the globally
installed 4.26.5 ahead of the wrapper. So the first `fr run advance r1` ran the OLD
detection and recorded:

```
agent_type=super-fr:fr-phase-executor harness=claude-code
session=probe-fake-claude-session model=claude-haiku-4-5-20251001
```

That is the issue's defect, live: a Claude Code harness, a borrowed Claude session, and
the claude-code tier's model, for work OpenCode dispatched.

**2. Inside that same shell, the branch's detection named OpenCode.** Called directly:

```
detect= opencode
ancestry= [20798, 20797, 20783, 108, 96393, 72936]   # 108 = opencode, 72936 = the Claude stand-in
```

The shell's environment carried `OPENCODE=1`, `OPENCODE_PID=108` (its direct parent),
`CLAUDECODE=1` and `CLAUDE_PID=72936`.

**3. The plugin's child claim landed while the unit was held (#530).** The plugin spawns
`fr` from the OpenCode process, whose PATH had the wrapper first. Three seconds after
dispatch, the cursor read:

```
agent=ses_f1c464775ffeTfsJ1YGq0KTZEv agent_type=fr-phase-executor-mechanical
harness=opencode model=github-copilot/claude-haiku-4.5 returned=None
```

The child's own first command, `fr run status r1`, printed:

```
HELD BY agent ses_f1c464775ffeTfsJ1YGq0KTZEv (opencode, github-copilot/claude-haiku-4.5) since …
```

**4. Branch code end to end.** Next came `<wrapper> fr run advance r1 --redispatch`
followed by a second dispatch. The old attempt closed `abandoned`, and the new one opened
as:

```
agent=None agent_type=super-fr:fr-phase-executor harness=opencode session=None
model=github-copilot/claude-haiku-4.5
```

About six seconds later the child claimed it:
`agent=ses_f1c41c8a0ffeUo1MPX04nPUgBJ agent_type=fr-phase-executor-mechanical`.

**5. OpenCode's own store agrees** (`opencode.db`, `session` table):

```
ses_f1c41c8a0ffeUo1MPX04nPUgBJ | parent ses_f1c465d24ffe… | fr-phase-executor-mechanical | github-copilot/claude-haiku-4.5
ses_f1c464775ffeTfsJ1YGq0KTZEv | parent ses_f1c465d24ffe… | fr-phase-executor-mechanical | github-copilot/claude-haiku-4.5
```

Every field the gh#537 table showed disagreeing now agrees: session, agent and harness.

## Limits

- One OpenCode version, one host (macOS), one launch shape (Claude Code outside, OpenCode
  inside). The pids were real processes, but the Claude Code parent was a stand-in, not a
  Claude Code process.
- The claim is fail-open. An `fr` on OpenCode's PATH too old to know `--open-unit` claims
  nothing, silently. Step 1 is the same class of trap in the shell: the `fr` a harness's
  shell resolves is not necessarily the one its plugins run.

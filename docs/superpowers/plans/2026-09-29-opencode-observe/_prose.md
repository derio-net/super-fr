# fr observes OpenCode sessions — implementation plan

Spec: `docs/superpowers/specs/2026-09-29-opencode-observe-design.md`.

## Shape

Three agentic phases, one per independently reviewable ask:

1. **Protocol and run session (skeleton).** `fr.run.observed`: the
   `ObservedSession` protocol, a Claude Code backend that wraps today's JSONL
   readers with no behaviour change (plus `returned` = the dispatch's
   tool_result in the parent transcript), an OpenCode backend over opencode.db
   scoped to one session (with the unscoped fallback that keeps
   `deliver-tests-provenance` enforced without the plugin), the harness-keyed
   `current_session`, the attempt recording the OpenCode session (which fills
   the Cost table through the existing `sessions_of`), and the plugin's
   `shell.env` export. The smoke is the fixture plus a trivial protocol test,
   CI green.
2. **Reviewer identity and returns.** One `agent_name` normaliser at the three
   comparison sites; reviewer ids verified on OpenCode; the holder fill; the
   coverage-block equality check at spec-review; the findings-block check at
   review-phase (several reviewers, prescribed ids); fr-goal §2/§6 prose.
3. **Operator answers, visual witness, parity.** Rounds from OpenCode's
   `question` tool; no default `answered_by`; honest `gates`/`check` wording;
   the visual witness keyed on the owing session; parity rows to `partial`
   plus `run-session-identity`; fr-goal "Harness — questions".

Phases 2 and 3 both depend only on phase 1; they run serially under fr-goal.

## Notes for the executor

- The fixture is COMPOSED (build.py), shapes copied from the live capture
  recorded in the spec's Background; never commit an operator database
  (spec-review s3, resolved unconfirmed).
- No artifact kind's `current_version` moves (spec §H). If you find one must,
  stop and journal it: the number is chosen at the pre-ready merge with
  `origin/main`, not in this branch.
- Do not name any member issue (#823/#797/#809/#816) as a `tracking_issue`.
- Both mirror generators (`sync-opencode.py`, `sync-hermes.py`) after any
  skill edit.

# Driver sessions — implementation plan

Spec: `docs/superpowers/specs/2026-10-06-driver-sessions-design.md` (batch `driver-sessions`:
#964, #878, #1029, one PR).

Three agentic phases, one per independently reviewable ask:

1. **fr-herdr restart-idle** (#964, runner side; skeleton).
   - The first task captures the live herdr surfaces the engine parses. It only reads
     operator panes, and presses keys only in a scratch tab it creates.
   - Then the pure `classify`/`kept_args`, the restart sequence and the `fr-herdr` console
     script.
   - Last, the install path that puts `fr-herdr` on PATH, and the candidate-walk scenario.
2. **Driver restart** (#964, driver side): the `SessionRestarter` protocol, the two config
   fields with the facts schema 6 bump, and the once-per-pass restart after `post_merge`. It is
   split from phase 1 for review size.
3. **Idle sessions and #878** (#1029, #878): the pure `idle_session` rule, the driver's
   once-per-process report, the board's needs-you card, and the herdr-only refusal text and
   fr-triage skill paragraph.

No phase names a member issue as `tracking_issue` (delivery rule).

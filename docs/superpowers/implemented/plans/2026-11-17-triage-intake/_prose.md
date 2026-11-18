# Triage intake trust and driver correctness — plan

Implements spec `2026-11-17-triage-intake-design.md` (batch triage-intake: #1252, #1213,
#1406, #1299) in three agentic phases, run serially in one workspace.

1. **Issue-intake trust gate (R1-R8).** The security boundary, and the skeleton: the
   smoke is the touched suites on the unchanged tree plus the `ready-fr` label and the
   change fragment, pushed so the draft PR's CI runs. Then the pure rule
   (`fr/triage/intake.py`), facts schema 15 with at most one association read per repo,
   body withholding for every written issue, the `untrusted` set, refusals in the batch
   verbs and dispatch, the driver's counted `blocked` hold in both snapshot builders, the
   quoted brief, the label ensure step and the docs.
2. **The driver fetches every pass (R9).** `merge_ctx` re-fetches and re-checks per pass,
   holds a repo whose fetch fails for the rest of that pass, follows each pass's config
   for `version` and method, and the close-out hand-back goes through the hold.
3. **Cancel and gate-tracker fixes (R10-R12).** An undefined removal label counts as
   removed on the gh CLI client; the cancel dry run names the `--checkout` that `--yes`
   needs; `close_gate_trackers` reports every exception instead of raising.

No phase names a member issue as `tracking_issue`.

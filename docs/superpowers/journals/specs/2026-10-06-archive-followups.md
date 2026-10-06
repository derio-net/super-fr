# Journal: 2026-10-06-archive-followups

<!-- fr:journal kind=discovery scope=spec id=operator-brief created=2026-10-06T17:20:22+00:00 input=true -->
### operator-brief · discovery · Operator brief (verbatim) — batch archive-followups

/fr-goal Archive does its own follow-ups: price closed sessions, retarget matrix refs, offer issues for open ends

Batch `archive-followups` of derio-net/super-fr: 3 issues, delivered as ONE pull request.

## super-fr#930: fr archive: refresh earlier closeouts' unpriced usage sessions automatically
Every archived usage file carries the close-out's own session unpriced; `fr usage backfill` fixes it by hand.

## super-fr#528: fr archive should retarget matrix refs it invalidates — 60 warnings had accumulated across 12 specs
Archive moves specs but neither archive nor `repair_repo` retargets matrix refs; acceptance check retains an archive-twin warning fallback.
Note: Batch after the super-fr#544 safety work: retarget same-repo refs and regenerate reports only after successful archive. take 10 (#817, OpenCode + GitLab, fr 4.35.0): archive left the matrix levels ref to the plan stale, so fr acceptance check failed after closeout.

## super-fr#458: fr archive: offer to open GitHub issues for open ends the run left behind (journal findings, rework items)
Archive moves journals and runs but does not turn remaining open ends into tracker issues.
Note: Product enhancement, not a broken invariant. Reconsider after the deferred journal path has usage evidence.

## Why these belong together
Wave 9 feature 4: close-outs leave these to fix by hand.

## Delivery rules
- Work on branch `feat/batch-archive-followups`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#930
  Closes derio-net/super-fr#528
  Closes derio-net/super-fr#458
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=decision scope=spec id=q1-refresh-when created=2026-10-06T17:20:22+00:00 -->
### q1-refresh-when · decision · Usage refresh runs when an archive moves anything

Operator chose: only invocations that stage moves refresh; a no-op archive leaves the tree clean.

<!-- fr:journal kind=decision scope=spec id=q2-no-status-nag created=2026-10-06T17:20:22+00:00 -->
### q2-no-status-nag · decision · No fr status reminder for unpriced usage

Operator chose: out of scope; the message points at the next fr archive / fr usage backfill.

<!-- fr:journal kind=decision scope=spec id=q3-retarget-all-moved created=2026-10-06T17:20:22+00:00 -->
### q3-retarget-all-moved · decision · Retarget every path archive moved

Operator chose: specs, journals, plan dirs (and files in them), runs, usage — same-repo only, after a successful archive.

<!-- fr:journal kind=decision scope=spec id=q4-plan-ref-stays-error created=2026-10-06T17:20:22+00:00 -->
### q4-plan-ref-stays-error · decision · Stale plan ref stays an error; twin warning reworded

Operator chose: no plan archive twin; the spec/journal twin warning says a ref survived an archive fr did not perform.

<!-- fr:journal kind=decision scope=spec id=q5-open-ends-findings created=2026-10-06T17:20:22+00:00 -->
### q5-open-ends-findings · decision · Open ends = open + out-of-scope findings

Operator chose: folded state open or out-of-scope in spec/plan/debug journals archive moves; rework origin_items and spec-section heuristics dropped.

<!-- fr:journal kind=decision scope=spec id=q6-flag-else-tty-prompt created=2026-10-06T17:20:22+00:00 -->
### q6-flag-else-tty-prompt · decision · --issues/--no-issues, else TTY prompt, else list only

Operator chose: --issues (all) / --issues ids / --no-issues; no flag → y/N/select prompt on a TTY, list-only non-interactive; tracking none lists only; never blocks the archive.

<!-- fr:journal kind=decision scope=spec id=q7-brief-routes-via-archive created=2026-10-06T17:20:22+00:00 -->
### q7-brief-routes-via-archive · decision · Closeout brief routes filing through fr archive --issues

Operator chose: the brief lists out-of-scope findings and one fr archive --branch <b> --issues <ids> command instead of per-finding manual journal resolve lines.

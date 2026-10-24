# Exit-gates release verification

The release mechanism must not need its own final release before its Tester gate
can be verified. Use two explicitly separated evidence stages. This document
changes the verification sequence, not the release predicate or gate ownership.
An approved plan is not a passing walk.

## A. Real disposable-repository rehearsal

The operator first authorizes the exact disposable repository, fixture resources,
push/workflow budget, real PR merges, fixture gate writes and cleanup boundary.
Setup permission alone does not authorize any of those later effects. Never use
the real org batches, scope state or a production driver as fixtures.

Before execution, review and retain:

- The super-fr source commit under test and hashes of release.yml, release.py,
  release-status/label decision code, installer/channel code, version/fragment
  tooling and staged-suite inputs. Pin the full tested source closure, not just
  the workflow file. Changes to that closure require a new equivalence review.
- The disposable repository's valid final baseline, version surfaces, tag/commit
  times, pending fragment and actual fixture PR merge history. Importing unrelated
  super-fr merge history or tags can invalidate the fixture's ledger; do not hide
  failed or incomplete reads.
- All fixture-only substitutions (repository origin, credentials, release lookup
  and install prefix). None may change gate eligibility, RC/final selection,
  fragment consumption, staged-tree checks or the full staged suite. If a faithful
  rehearsal cannot run without changing these, stop and revise the plan for review.
- The authorized workflow event and inputs. A push can trigger publication too;
  do not enable or seed auto-triggering workflows under setup-only permission.
  Disable unrelated fixture workflows and bound the expected runs/cost beforehand.

Walk the normal path against real GitHub state:

1. Merge an approved fixture PR with a real pending change fragment and an unpassed
   post-merge gate. Capture the actual merged-PR labels and release-status result.
2. Authorize the ordinary workflow run with **no version input/override**. Capture
   its full staged-suite outcome, RC commit/tag and GitHub pre-release metadata.
   Verify fragments remain pending. Unknown gate truth cannot count as successful
   evidence of the known held-gate case.
3. Complete the fixture's actual verification. Separately authorize and record its
   gate pass; retain the evidence/comment and matching passed-label transition.
4. Authorize the ordinary next run, again with no version input. Capture the full
   staged-suite result, final commit/tag, non-prerelease publication and fragment
   consumption. Verify the release-status waiting list is empty.
5. In disposable install prefixes, verify explicit RC selection and default final
   selection resolve the fixture's actual releases. If current bootstrap code
   cannot target the fixture without a behavior-changing edit, report that gap;
   an install from production does not prove selection of the fixture final.

Retain redacted raw API outputs, workflow logs, before/after Git and fragment
state, install outputs, UTC, source identities and hashes. The Tester reviews
this proof and source equivalence before recording `exit-gates-release-gating`
walked. Missing evidence leaves it `walk-owed`. Passing the fixture gate neither
passes #1195 nor any other original super-fr PR.

## B. Actual super-fr final follow-through

Only after the original gates have independently and legitimately passed may an
operator authorize the normal super-fr release workflow, or let its scheduled
run proceed. Do not remove labels or use an explicit version to escape a hold.

Observe and retain the actual release-status result, successful full staged-suite
run at the final version, release commit/tag, non-prerelease publication, consumed
fragments, explicit RC installer selection and default final installer selection.
Compare the source closure with the accepted rehearsal; intervening relevant
changes require review and, where needed, another rehearsal before the gate passes.

Issue #1207 retains this same-repository follow-through obligation. Do not resolve
its `test-plan-step-4` journal entry or close the issue based solely on rehearsal,
and do not claim the super-fr final was observed before it exists. Resolve it only
with the actual final/installer evidence. If publication or installation fails,
keep the obligation open and report/fix the release defect; never backdate a pass.

The matrix row and #1207 now track distinct milestones deliberately: the row proves
the pinned release mechanism before the self-held release; the issue preserves
the later operational observation of this repository's real final. All other
#1195 rows and original PR gates remain unchanged.

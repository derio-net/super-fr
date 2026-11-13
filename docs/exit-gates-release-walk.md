---
title: "Exit-gates release verification"
tldr: |
  The release mechanism must not need its own final release before its Tester gate can be verified. This page separates the two evidence stages.
standalone_style: broadsheet
covers:
  - scripts/release.py
  - packages/fr/src/fr/release_status.py
reviewed: 2026-11-12 acceptance-fragments phase 2, its readers now fold per-feature fragments instead of reading matrix.yaml; nothing this page describes changed
---

# Exit-gates release verification

The release mechanism must not need its own final release before someone can check its
Tester gate. Use two explicitly separated evidence stages. This document
changes the verification sequence, not the release predicate or gate ownership.
An approved plan is not a walk that passed.

## A. Real disposable-repository rehearsal

The operator first authorizes the exact disposable repository, fixture resources,
push/workflow budget, real PR merges, fixture gate writes and cleanup boundary.
Setup permission alone does not authorize any of those later effects. Never use
the real org batches, scope state or a production driver as fixtures.

Before execution, review and keep:

- The super-fr source commit under test and hashes of release.yml, release.py,
  release-status/label decision code, installer/channel code, version/fragment
  tools and staged-suite inputs. Pin the full tested source closure, not only
  the workflow file. Changes to that closure need a new equivalence review.
- The disposable repository's valid final baseline, version surfaces, tag/commit
  times, pending fragment and actual fixture PR merge history. Unrelated super-fr merge
  history or tags that you import can make the fixture's ledger invalid. Do not hide
  failed or incomplete reads.
- All fixture-only substitutions (repository origin, credentials, release lookup
  and install prefix). None of them may change gate eligibility, RC/final selection,
  fragment consumption, staged-tree checks or the full staged suite. If a faithful
  rehearsal cannot run without a change to these, stop and revise the plan for review.
- The authorized workflow event and inputs. A push can trigger publication too.
  Under setup-only permission, do not enable or seed workflows that an event (such as a push) starts automatically.
  Disable unrelated fixture workflows, and set a limit on the expected runs/cost beforehand.

Walk the normal path against real GitHub state:

1. Merge an approved fixture PR with a real pending change fragment and a post-merge gate that did not pass.
   Capture the actual merged-PR labels and release-status result.
2. Authorize the ordinary workflow run with **no version input/override**.
   Capture its full staged-suite outcome, RC commit/tag and GitHub pre-release metadata.
   Make sure that the fragments stay pending. Unknown gate truth cannot count as
   successful evidence of the known held-gate case.
3. Complete the fixture's actual verification. Separately authorize and record its gate pass.
   Keep the evidence/comment and the passed-label transition that matches it.
4. Authorize the ordinary next run, again with no version input. Capture the full
   staged-suite result, final commit/tag, non-prerelease publication and fragment consumption.
   Make sure that the release-status list of PRs that wait is empty.
5. In disposable install prefixes, make sure that explicit RC selection and default final
   selection resolve the fixture's actual releases.
   Current bootstrap code can be unable to target the fixture without an edit that changes behavior.
   If so, report that gap.
   An install from production does not prove selection of the fixture final.

Keep redacted raw API outputs, workflow logs, before/after Git and fragment
state, install outputs, UTC, source identities and hashes. The Tester reviews
this proof and source equivalence. Only then does the Tester record `exit-gates-release-gating`
walked. If evidence is absent, the row stays `walk-owed`. A pass of the fixture gate does not
pass #1195 or any other original super-fr PR.

## B. Actual super-fr final follow-through

Only after the original gates have independently and legitimately passed may an
operator authorize the normal super-fr release workflow, or let its scheduled
run continue. Do not remove labels or use an explicit version to escape a hold.

Observe and keep the actual release-status result and the successful full staged-suite
run at the final version. Also keep the release commit/tag, non-prerelease publication, consumed
fragments, explicit RC installer selection and default final installer selection.
Compare the source closure with the accepted rehearsal. Relevant changes since then
need review and, where necessary, another rehearsal before the gate passes.

Issue #1207 keeps this same-repository follow-through obligation. Do not resolve
its `test-plan-step-4` journal entry, or close the issue, on the rehearsal alone.
Do not claim that someone observed the super-fr final before it exists. Resolve it only
with the actual final/installer evidence. If publication or installation fails,
keep the obligation open and report/fix the release defect. Never backdate a pass.

The matrix row and #1207 now track distinct milestones deliberately. The row proves
the pinned release mechanism before the self-held release. The issue keeps
the later operational observation of this repository's real final. All other
#1195 rows and original PR gates stay unchanged.

# Journal: 2026-09-28-ui-visual-evidence

<!-- fr:journal kind=discovery scope=spec id=input-batch-prompt created=2026-09-28T19:15:38+00:00 input=true -->
### input-batch-prompt · discovery · Operator input: fr-goal batch prompt (ui-evidence-2)

UI evidence is visual: screenshots actually opened, and every named interaction exercised

Batch `ui-evidence-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#779: Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised
Take 9: UI evidence was a Playwright script's pass/fail; no screenshot was ever opened and the named interactions (−, slider drag, the 20 cap, range labels) were never exercised. The scorer found four defects visible in one screenshot or drag; the plain comparison arm opened 6 screenshots.
Note: Operator-prioritised. Feature (fr-goal), batch `ui-evidence`: for a user-visible requirement, evidence names the screenshots actually opened (observable in the transcript) and each named control used at its limits.

## Why these belong together
Retry of the batch cancelled on 2026-09-28 at its question gate (#783): dispatch only after question-order (#783) merges. Wave 6, operator-prioritised. Take 9's browser check was a script's pass/fail: no screenshot opened, -, slider drag, the 20 cap and the range labels never tried, and four defects visible in one screenshot shipped. For a user-visible requirement, evidence at implement/review/deliver names the screenshots the agent opened (observable in the transcript) and the controls it used at their limits. Edits fr-execute and fr-goal prose and possibly an evidence reader; rebase against requirements-gate if both touch fr-goal SKILL.md.

## Delivery rules
- Work on branch `feat/batch-ui-evidence-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#779
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-779 created=2026-09-28T19:15:38+00:00 input=true -->
### input-issue-779 · discovery · Operator input: super-fr#779 title and body

Browser check isn't visual: UI evidence is a script's pass/fail; no screenshot is ever opened and named interactions go unexercised

## What happened

The brief of the super-fr-3 feature-C recording asks: "Before delivering, the developer has checked basket mode in a browser (accepted, not accepted, staff check, back to single article) against the single-article view." In take 9 (fr 4.29.2), the executor wrote a Playwright script (`src/test/browser/basket.cjs`, run through `docker exec` because the devcontainer doesn't publish the demo port) and ran it 4 times; the orchestrator ran it again after the review fixes, and the closeout once more. **No screenshot was ever opened**: the only attempt to read one used the wrong directory and wasn't retried. The script never exercised −, the slider drag, the 20 cap, the range labels or any styling.

The scorer's browser check then found: the card-click side effect, a reading outside the ranges not drawn at all, the chart torn down on every slider move, the stale legend. All visible in one screenshot or one drag.

The plain comparison arm, given the same brief, opened 6 screenshots before delivering (take 8).

## Expected

When a requirement or acceptance row is user-visible UI, its evidence at `implement-phase` / `review-phase` / `deliver` includes:

- screenshots the agent actually opened (an image read of the file, observable in the transcript), for each state the requirement names, and
- the interactions the requirements name (each control used at least once, including its limits),

rather than a script's pass/fail alone. fr-execute / fr-goal say so in the browser-check step.

<!-- fr:journal kind=discovery scope=spec id=input-script-preference created=2026-09-28T19:15:38+00:00 input=true -->
### input-script-preference · discovery · Operator input: mid-brainstorm addendum (capture script preferred)

add that, if a script can be written to reliably retrieve the screenshots mechanically instead of driving via the agent, it should be preferred. That way the token cost is only paid once and each rerun only costs a script invocation (and viewing the images of course).

<!-- fr:journal kind=decision scope=spec id=d1-visual-row-flag created=2026-09-28T19:15:38+00:00 -->
### d1-visual-row-flag · decision · A UI requirement is marked on its acceptance row

Q1 answer: flag on the acceptance row (`visual`, beside `verify: post-merge`). Plan phases already link rows, so fr knows which phases and delivery owe visual evidence. Not a Requirements-grammar tag, not agent judgement.

<!-- fr:journal kind=decision scope=spec id=d2-transcript-verified created=2026-09-28T19:15:38+00:00 -->
### d2-transcript-verified · decision · fr verifies from the transcript that screenshots were opened

Q2 answer: evidence names the screenshot files; fr refuses unless each was opened with an image read since the unit opened, in the transcript of the agent that owes it (this session or a subagent it dispatched). Unreadable transcript -> recorded unobserved, like tests=.

<!-- fr:journal kind=decision scope=spec id=d3-reviewer-drives created=2026-09-28T19:15:38+00:00 -->
### d3-reviewer-drives · decision · The review-phase reviewer drives the UI itself

Q3 answer: the dispatched reviewer opens its own screenshots and tries the named controls at their limits itself; reading the executor's screenshots is not enough.

<!-- fr:journal kind=decision scope=spec id=d4-interactions-on-row created=2026-09-28T19:15:38+00:00 -->
### d4-interactions-on-row · decision · Interactions are named on the row and covered in the record

Q4 answer: the visual row lists its controls and limits; the evidence record maps each to a screenshot taken after using it; fr refuses a name with no screenshot. Coverage only, not image content.

<!-- fr:journal kind=decision scope=spec id=d5-fresh-at-deliver created=2026-09-28T19:15:38+00:00 -->
### d5-fresh-at-deliver · decision · deliver takes fresh screenshots

Q5 answer: review fixes land after phase screenshots, so the orchestrator opens new ones of the delivered build, as it re-runs the full suite itself.

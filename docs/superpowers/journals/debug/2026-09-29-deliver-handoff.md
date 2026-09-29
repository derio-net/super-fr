# Journal: 2026-09-29-deliver-handoff

<!-- fr:journal kind=repro scope=debug id=2022f287d070 created=2026-09-29T11:08:53+00:00 -->
### 2022f287d070 · repro · deliver: orchestrator readied its own MR; closeout line not relayed; suite runs before push

take 10 (#817, OpenCode + GitLab, fr 4.35.0). Run A: orchestrator fixed review findings, re-dispatched its reviewer, ticked 'explicit review ok' in the Ready checklist and ran `glab mr update --ready` (#814). Run B: deliver printed `closeout: … fr pickup --run <id>`; the final message did not relay it (#814). Run 2026-09-28-feat-batch-ui-evidence-2 (#789): §8 runs the ~10 min local suite, then pushes, so CI and the local suite never overlap (#799). Repro by reading: fr-goal SKILL.md §8 (lines 108-110) and `fr run resolve --step deliver` stdout order (tests/unit/test_run_cli.py pins closeout < pickup < push).

<!-- fr:journal kind=hypothesis scope=debug id=9e3febd2bcab created=2026-09-29T11:08:54+00:00 -->
### 9e3febd2bcab · hypothesis · One root cause: §8 never fixes who owns each deliver act, or the order they happen in

Three observed symptoms, one surface: (a) the Ready checklist names 'explicit review ok' but not its owner, and says the orchestrator marks ready 'ONLY when all three hold', so an orchestrator reads its own dispatched reviewer as the ok; (b) §8 orders verify (full suite) before the PR open/push, with no reason to; (c) fr's deliver handoff prints closeout → pickup → 'push it', so the LAST line an orchestrator acts on is the push, and the prose ('git push, relay that line') puts the relay mid-sentence, never as the turn's last message.

<!-- fr:journal kind=root-cause scope=debug id=9596ebaa641f created=2026-09-29T11:13:00+00:00 -->
### 9596ebaa641f · root-cause · Deliver's handoff contract fixed neither ownership nor order

fr-goal §8 granted the orchestrator the ready transition ('ONLY when all three hold: mark it ready') with an ownerless 'explicit review ok'; ordered the local suite before the push for no reason; and fr's `_closeout_handoff_lines` printed closeout → pickup → push, so the push was the last instruction and the closeout the one dropped. Confirmed by reading SKILL.md §8 and by the existing test pinning closeout < pickup < push.

<!-- fr:journal kind=finding scope=debug id=deliver-handoff created=2026-09-29T11:13:01+00:00 state=fixed -->
### deliver-handoff · finding [fixed] · Operator owns the ok and ready; push first; closeout last

run_cmd.py `_closeout_handoff_lines`: push/NOT-committed line first, closeout pair last. fr-goal §8: push + open/refresh draft PR before the full suite; Ready-checklist is the operator's; never tick, never mark ready; closeout relayed as the final line. fr-debugging §4: same relay rule, PR stays draft. Manifest comment corrected. Tests (red first, commit on PR #828): test_run_cli closeout-last asserts ×3; test_fr_goal_journal §8 guards ×4.

<!-- fr:journal kind=review scope=debug id=fb350d0a3c2d created=2026-09-29T11:15:05+00:00 -->
### fb350d0a3c2d · review · Independent review: code correct; three §8 wording findings, all fixed

Reviewer (separate context) confirmed `_closeout_handoff_lines` puts the closeout pair last in all three branches and that no other test depends on the old order. In scope, fixed: stale 'once the PR exists' wording; garbled 'git push-it sha' line missing the NOT-committed variant; the hand-off sat under the 'Devcontainer mode' label though it applies in every mode. Out of scope, not changed: fr-execute §42 'take the PR out of draft for fr:pr-ready' is the dispatched runner's label lifecycle, not the fr-goal orchestrator.

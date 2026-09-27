# Journal: 2026-09-27-pr-body-cost

<!-- fr:journal kind=repro scope=debug id=b871f47369cb created=2026-09-27T19:28:22+00:00 -->
### b871f47369cb · repro · deliver's PR Cost table shows only the first capture's steps

Seen on PR #678 (gh#680): the Cost table showed brainstorm 6 turns and '—' for every later step, while the usage file committed by the same deliver had turns for spec-review/plan/implement/deliver. Repro: a run whose usage file holds only a resolve:brainstorm capture, then render_pr_body at deliver — later steps render '—'.

<!-- fr:journal kind=root-cause scope=debug id=2e10c7d3bf6b created=2026-09-27T19:28:23+00:00 -->
### 2e10c7d3bf6b · root-cause · render reads a stale file; the live read is only a no-file fallback

_deliver_pr_gate (run_cmd.py) renders pr-body.md via pr_body._cost BEFORE resolve writes deliver's capture (_capture_usage after _complete_step). _cost reads load_run_usage and only falls back to recompute_entries (a live transcript read) when NO file exists, so the resolve:brainstorm capture written by the first resolve on this host always wins over fresh transcripts. Secondary, not a defect in fr: a live Claude Code session has no cost-state record until it ends, so dollars are honestly None in-flight; the table rendered a bare '—' with no reason.

<!-- fr:journal kind=finding scope=debug id=f-live-cost created=2026-09-27T19:42:40+00:00 state=fixed -->
### f-live-cost · finding [fixed] · PR body Cost table folds a live reading of this host's sessions over the usage file

fr.usage.capture: capture() split into build_capture (pure, in memory) + writer; new live_usage() upserts this host's fresh capture into the loaded file without writing. pr_body._cost uses it, so steps completed after the last capture show their turns; the old no-file-only fallback to recompute_entries is gone from the render. When turns exist but no dollars, the table notes that a harness may write session cost only at session end. Pinned by tests/unit/test_pr_body_cost.py (failing first, committed before the fix). Not changed: deliver's capture still runs after the gate, so a refused deliver writes only pr-body.md.

<!-- fr:journal kind=review scope=debug id=ef3234ae9ed2 created=2026-09-27T19:46:48+00:00 -->
### ef3234ae9ed2 · review · independent review: no findings

feature-dev:code-reviewer read capture.py, pr_body.py, cost.py, file.py and the tests against five checks: capture() still behaves the same, the no-file and no-session cases, other hosts' and migrated captures, the dropped note, and harness-neutrality scope. No high-confidence issues. Caveat: the reviewer had no shell; the full suite was run separately (6689 passed; one OpenCode live-plugin timeout that passes when run alone). Out of scope and filed: #756 (the closeout capture did not refresh usd).

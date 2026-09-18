# Comparison — three runs at super-fr#429

Same brief, same harness (`opencode --auto`), same model
(`github-copilot/gpt-5.6-terra`, default effort), same base commit
(`9bb2248`). Filled from measurement only.

| | A — fr-goal | B — plain | C — plain + "plan first" |
|---|---|---|---|
| PR | [#479](https://github.com/derio-net/super-fr/pull/479) (draft) | [#478](https://github.com/derio-net/super-fr/pull/478) | [#480](https://github.com/derio-net/super-fr/pull/480) |
| Diff | 37 files, +1826/−113 | 18 files, +345/−35 | 21 files, +467/−85 * |
| Sessions | 14 (13 subagents) | 1 | 1 |
| Cost | **$7.59** | **$1.07** | **$0.97** |
| Tokens in / out | 825k / 87k | 170k / 14k | 138k / 14k |
| Cache read | 19.9M | 2.2M | 2.1M |
| Wall time | **56 min** | 78 min | 105 min |
| Recording | 95 min | 97 min | 108 min |
| Operator turns after the brief | **0** | 0 | **3** |
| CI | ✗ typecheck | ✓ all green | ✗ test |
| New test functions | **12** (4 files) | 3 (2 files) | 3 (2 files) |
| Spec / plan / run cursor / journal | **all four** | none | none |

\* C measured from its setup commit, not `main`: its branch carries the
experiment's own removal of `.opencode/`, which would otherwise read as
−1721 lines it never wrote.

## Did they do the job

All three delivered the **same CLI surface** — `fr journal update`,
`fr acceptance set-status`, `fr acceptance add-level`, identical flags — because
`answers.md` dictated it. That is the answer sheet working as intended: it moves
the comparison off API taste and onto process and quality.

Probed in scratch repos against each arm's own build:

| Checklist row | A | B | C |
|---|---|---|---|
| 1–3 journal update flips state, rewrites marker **and** heading, `check` clears | ✓ | ✓ | ✓ |
| 4 duplicate `--id` on `add` no longer silent (exits 2) | ✓ | ✓ | ✓ |
| 5–6 acceptance `set-status` / `add-level` exist | ✓ | ✓ | ✓ |
| 9 unknown `--id` errors (exits 2) | ✓ | ✓ | ✓ |
| 8 down-transition / `failing` requires `--note` | **✗** | **✗** | **✗** |
| 17 CI green | ✗ | ✓ | ✗ |

**Row 8 is the interesting failure: no arm implemented it**, though it is
`answers.md` row 3 and was given identically to all three. The pipeline did not
catch it either — A's spec, plan, per-phase review and self-review all passed
over a requirement that was stated up front. Whatever fr-goal buys, "cannot drop
a stated requirement" is not it.

## Where they silently disagreed

`--note` on `acceptance set-status`:

- **A appends** — `f"{old.notes}\n{note}"`
- **B and C replace** — `note if note is not None else current.notes`

This is exactly the ambiguity **C stopped to ask about** (for the journal verb).
All three append on the journal side; two of three quietly chose the opposite
behaviour for the acceptance side, and nothing surfaced the divergence. One real
question, asked once, would have settled both.

## Reading the cost

A costs **7×** B or C and produces **5×** the diff, of which a large part is the
spec, plan, run cursor and journal that B and C never wrote. A was also the
**fastest in wall time** (56 min vs 78 and 105) despite 13 subagents, because
delegated work runs while the orchestrator waits, and its cache-read dominates
the bill (19.9M) — the cost shape #464 describes.

## Caveats that must travel with these numbers

1. **A never asked its batched Q&A, and could not.** fr-goal specifies its one
   operator gate as an `AskUserQuestion` call — a Claude Code tool absent on
   OpenCode — so the gate could not fire (super-fr#436). A is therefore fr-goal
   *minus its only operator touchpoint*. C's three operator turns are its
   harness being able to ask, not a better method.
2. **#429 is unusually well specified.** It proposes the exact command shapes,
   so even a working gate had little to ask.
3. **`gh` was unauthenticated in all three arms** (no `gh` config inside the
   clean `XDG_CONFIG_HOME`), so no arm gets credit or blame for opening a PR.
4. **B's and C's clones had the repo's fr instruction mirrors regenerated
   mid-run** when they ran `scripts/sync-opencode.py`. OpenCode never loaded
   them, but they were readable from that point.
5. One feature, one model, one harness, n=1 per arm.

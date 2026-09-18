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
`fr acceptance set-status`, `fr acceptance add-level`, identical flags.

Not because of `answers.md`: that sheet was never delivered to a run except its
row 9, which run C asked for. **The convergence comes from issue #429 itself**,
which proposes the shapes verbatim:

```
fr acceptance set-status <id> --status ci|scheduled|skipped|not-implemented|failing [--note ...]
fr acceptance add-level  <id> --level unit=<repo>:<path>
fr journal update --id <id> --state open|fixed|refuted [--note ...]
```

The tell is the inconsistency all three reproduced: acceptance takes the row id
**positionally** while journal takes it as **`--id`** — exactly as the issue
writes them. A well-specified issue, not the pipeline and not the operator,
fixed the API. That removes API taste from the comparison, but it also means
this experiment cannot say anything about how the arms handle an *under*
-specified brief — arguably the case where planning matters most.

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

## Bugs: are A's review findings present in B and C?

A's reviewer raised **9 findings, all fixed before delivery** (5 in the
acceptance phase, 4 in the journal phase). I probed each arm's own build for
the three most consequential. They are not hypothetical: **B and C shipped
them.**

| A's finding | A | B | C |
|---|---|---|---|
| `journal update --scope bogus` → clean error, not `KeyError` | ✓ exit 2, clean message | **✗ unhandled `KeyError` traceback** | **✗ unhandled `KeyError` traceback** |
| duplicate entry ids must not be rewritten ambiguously | ✓ exit 2, refuses | **✗ silently updates 1 of 2** | **✗ rewrites both entries** |
| `set-status` must not destroy the matrix's comments/structure | ✓ comments intact, note appended | **✗ corrupts the file** | **✗ refuses a valid file** |

### The matrix bug, precisely

The repo's real `matrix.yaml` carries a comment on line 23:

```
# Add rows with `fr acceptance add` (schema-validated append). Keep `rows:`
```

The actual `rows:` key is on line 28. **B and C both split the file on the
first literal `"rows:"`** — B via `read_text().split("rows:", 1)[0]`, C via
`original.partition("rows:")` — and so cut the document inside that comment.

- **B writes the result.** `org:`, `repo:` and `rows:` are destroyed; the file
  parses as a **list**, and B's *own* `fr acceptance check` then rejects the
  file it just wrote: `matrix top level must be a mapping, got list`. B also
  reflowed unrelated rows' notes, and replaced the target row's note instead of
  appending.
- **C fails closed.** Same split, but it validates before writing, so it exits 2
  and leaves the file untouched. Unusable rather than destructive.
- **A does neither.** It edits by source span (`yaml.compose` + `end_mark`
  offsets), so comments and layout survive — the shape its reviewer demanded in
  `acceptance-row-comments-lost`.

This is the clearest result in the experiment. A CI-gated, hand-commented,
tracked file is exactly the kind of artifact a one-shot agent damages, and the
damage is invisible until something reads the file back. B's suite is green;
its own tests never fed it the repo's real matrix.

### Row 8: my scoring error, not their miss

I first recorded this as "no arm implemented `--note` required on a
down-transition, though it was given to all three identically". **That was
wrong, and the correction matters more than the original claim.**

`answers.md` is a *response* document. Its content reaches a run only when that
run asks the matching question. Checked against what was actually said:

- the seed prompts contain **no** mention of notes;
- issue #429 proposes `--status <s> [--note ...]` — **optional**, in brackets;
- the only operator utterances ever made are run C's three, in
  `corrections.md`, none of which state the rule.

So the requirement existed **only in the operator's private sheet** and was
never delivered to anyone. All three implemented exactly what the issue
specified. Checklist row 8 tested for something no arm could have known, and it
is withdrawn as a defect; it stays as a row only to record that the requirement
never travelled.

The causal chain is the interesting part, and it runs straight back to the gate:

> A's Q&A gate could not fire (`AskUserQuestion` absent on OpenCode, super-fr#436)
> → A asked nothing → the sheet was never consulted → an operator-owned
> constraint never reached the work.

An unasked question costs exactly one dropped requirement here. That is the
clearest argument in the experiment *for* the gate — and it only became visible
because the gate was broken.


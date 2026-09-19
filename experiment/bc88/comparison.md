# Comparison — blog-craft #88, two arms

Same brief, same harness (`opencode --auto`), same model, same base
(`2874f35`). Arm P ran in the prepared clean room; **arm G's first attempt was
aborted and restarted** (see `run-anchors.md`) — these are the restart's numbers.

| | P — plain + "plan first" | G — `/fr-goal` |
|---|---|---|
| PR | [#89](https://github.com/derio-net/blog-craft/pull/89) (ready) | [#90](https://github.com/derio-net/blog-craft/pull/90) (draft) |
| Diff | 14 files, +342/−34 | 17 files, +528/−17 |
| Sessions | 1 (0 subagents) | 1 (**0 subagents**) |
| Cost | **$1.01** | **$1.19** |
| Tokens in / out | 109k / 13.7k | 96k / 14.2k |
| Cache read | 2.66M | 3.83M |
| Session span | 24.6 min | **17.0 min** |
| Operator questions | **1** | **4** (batched gate) |
| Artifacts | none | spec, 4-phase plan, 2 journals, run cursor |
| Unit suite (local) | 1249 pass | 1245 pass |
| `smoke-update` (local) | **23 pass, 2 FAIL** | **25 pass, 0 fail** |
| CI | ✗ the 2 failures above | ✗ version bump missing |
| Version bump | ✅ pyproject, plugin.json, marketplace, CHANGELOG | ❌ |
| Skill docs + OpenCode mirror | ❌ | ✅ both |

## The result that matters

**Arm P shipped two regressions.** `smoke-update.sh` fails on
`site_dir mapping missed blog/scripts` and `vendored script not actually
replaced`. Both assertions exist **at the base commit** — they are blog-craft's
own pre-existing tests, broken by the change. Reproduced locally, not just read
off CI.

**Arm G's code is clean.** 1245 unit tests and 25/25 smoke pass locally. Its CI
red is a *process* gate — `ERROR: shipped-surface changes require a version
bump` — which fired before the tests ever ran. So "both are red" is true and
misleading: one is broken, the other is undeclared.

Neither is finishable as-is. P needs its regressions fixed; G needs one version
bump.

## Where they agreed

Both invented the **same** mechanism, independently: a consumer-owned
`.blog-craft.overrides.yaml`, reusing the existing `blog_craft_version` base
snapshot (11 refs each) rather than inventing a second base. Arm G put that name
to the operator as gate question 3 and got approval; arm P chose it unasked.
Same destination, one of them checked first.

## Cost: the 7× is gone, and the reason is the harness

In the super-fr experiment fr-goal cost 7× the plain arm and ran 13 subagents.
Here it cost **1.2×** and ran **zero**. That is not fr-goal behaving differently
— it is `fr harness parity` footnote [5]: *no isolation-argument dispatch
primitive on OpenCode*, so fr-goal's documented fallback **runs phases inline**.
The subagent fan-out that drove the old bill does not exist on this harness.

Arm G was also the faster of the two (17.0 vs 24.6 min).

## Harness validation — the second deliverable

- **`answered_by: operator` is recorded in arm G's run cursor.** The 4.5.x gate
  fix works end to end: the batched Q&A fired on OpenCode (4 questions, capped
  at 4, recommended-first, turn ended), a human answered, and the cursor proves
  it. In the previous experiment this gate *could not fire at all* (#436
  instance 2) and the run asked nothing.
- **0 subagents matches the declared `subagent-dispatch: absent [5]`.** The
  matrix predicted the observed behaviour.
- **Cast length is not runtime.** Both casts read ~700 min against session spans
  of 17–25 min: the OpenCode TUI repaints about once a second, so
  `--idle-time-limit 2` never engages and the file spans however long the window
  stayed open. Use the db session span. This also invalidates the "recording
  length" row in the earlier super-fr comparison.

## Caveats

1. Arm G's first attempt ran outside the clean room and was discarded; its
   $1.11 is excluded.
2. Arm P asked one question, G four — but G's were *elicited by the gate*, so
   this measures the mechanism, not the model's inclination.
3. One feature, one model, one harness, n=1 per arm.

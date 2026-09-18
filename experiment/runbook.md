# Dual-run recording runbook

Two runs at the same feature, same harness, same model, same brief. One with
`/fr-goal`, one without. Fills P1/P3 of the plan.

| | Run A | Run B |
|---|---|---|
| Treatment | `/fr-goal <seed prompt>` | seed prompt, no `fr-*` |
| Harness | `opencode --auto` | `opencode --auto --pure` |
| Model | `github-copilot/gpt-5.6-terra`, default effort | same |
| Branch | whatever fr-goal picks | `experiment/vanilla-429` |
| Base | `RECORD_SHA` (pin below) | same `RECORD_SHA` |

**Feature: issue #429** — `fr acceptance` and `fr journal` can create state but
not update it. #431 is its duplicate. Chosen because it has real design
questions (so the Q&A gate has something to ask), several natural phases,
checkable acceptance rows, and it touches nothing the run itself stands on.

Record `RECORD_SHA=<pending>` and `opencode --version` at record time. Terra is
`github-copilot/gpt-5.6-terra`; record the exact string the session reports.

## Order: run B first

The operator learns the problem by watching run A. Running B first keeps
fr-goal's framing of the design out of the corrections given to the plain run.

## Making run B actually plain

On this host a plain session does not stay plain. Three layers push it back
into the fr workflow, and each needs its own answer:

| Layer | What it does | Neutralised by |
|---|---|---|
| `.opencode/plugins/fr-isolation-required.ts` (repo) | blocks edits outside an fr workspace | `--pure` ("run without external plugins") |
| `opencode.json` -> `.opencode/instructions/*.md` (repo) | 7 rule files, incl. the fr-plan and fr-worktree overrides | removed in run B's clone (a deliberate, logged deviation) |
| `~/.config/opencode` (global) | 25 skills, 19 commands, incl. the `fr-*` mirrors | `XDG_CONFIG_HOME` pointed at a clean dir |

`AGENTS.md` **stays**. It is the repo's own maintainer documentation, which any
real repository has and any competent agent would read. Removing it would stack
the comparison.

`XDG_DATA_HOME` is also redirected per run, which isolates each run's session
storage — that is what makes `opencode stats` exact per run rather than
lifetime. Credentials are copied in, so neither run re-authenticates.

```bash
# --- one-off, before recording -----------------------------------------
export RUN_ROOT=~/experiment-429            # outside any fr-enabled repo
export RECORD_SHA=<pin from origin/main>

# run B: clean clone, repo-level OpenCode wiring removed
git clone https://github.com/derio-net/super-fr "$RUN_ROOT/vanilla"
git -C "$RUN_ROOT/vanilla" checkout -b experiment/vanilla-429 "$RECORD_SHA"
rm -rf "$RUN_ROOT/vanilla/.opencode" "$RUN_ROOT/vanilla/opencode.json"

# clean config + isolated storage for each run; copy credentials, drop MCP
for r in A B; do
  mkdir -p "$RUN_ROOT/cfg-$r/opencode" "$RUN_ROOT/data-$r/opencode"
  cp ~/.local/share/opencode/auth.json "$RUN_ROOT/data-$r/opencode/"
done
# run A keeps super-fr's OpenCode skills/commands; run B gets none
cp -R ~/.config/opencode/skills ~/.config/opencode/commands \
      ~/.config/opencode/instructions "$RUN_ROOT/cfg-A/opencode/"
printf '{"$schema":"https://opencode.ai/config.json"}\n' \
  | tee "$RUN_ROOT/cfg-A/opencode/opencode.json" > "$RUN_ROOT/cfg-B/opencode/opencode.json"
```

Neither config declares an MCP server: the host's global config has one
(`gebit-mcp`) and leaving it in one run only would be an uncontrolled variable.

**Dry-run this before recording.** Start each run, ask it "what skills and
instructions are loaded?", and confirm run B lists none of the `fr-*` ones.
That check is cheap and the whole comparison rests on it.

## Recording

`brew install asciinema` (not currently installed).

```bash
# run B first
XDG_CONFIG_HOME=$RUN_ROOT/cfg-B XDG_DATA_HOME=$RUN_ROOT/data-B \
  asciinema rec --idle-time-limit 2 --title "vanilla #429" \
    -c "opencode --auto --pure $RUN_ROOT/vanilla" experiment/vanilla.cast

# run A, from a normal checkout; fr-goal makes its own workspace
XDG_CONFIG_HOME=$RUN_ROOT/cfg-A XDG_DATA_HOME=$RUN_ROOT/data-A \
  asciinema rec --idle-time-limit 2 --title "fr-goal #429" \
    -c "opencode --auto" experiment/fr-goal.cast
```

`--idle-time-limit 2` collapses thinking pauses, which is what makes a
multi-hour run watchable. The TUI takes the model from config, so set it there
or switch with `/models` on the first frame — either way, on camera.

Both runs open **draft** PRs. Only the better one merges, and `Closes #429,
#431` only takes effect then.

## Measuring

Per run, after it ends:

```bash
XDG_DATA_HOME=$RUN_ROOT/data-<r> opencode stats            # tokens, cost
XDG_DATA_HOME=$RUN_ROOT/data-<r> opencode export <session> # full transcript
```

- **Target hit:** `acceptance.md`, scored from the delivered PR alone. Never shown to either run.
- **Operator effort:** `corrections.md` — count, and how early they cluster.
- **Wall time:** cast duration; **model cost:** `opencode stats`.
- **Quality:** `uv run pytest -q`, `ruff check`, `mypy`, coverage delta, review findings fixed/refuted/missed.
- **Maintainability:** LOC and files changed, and which artifacts exist (spec, plan, run cursor, journal).

The comparison table is filled from measurements only. No presumed winner.

## Annotating afterwards

Run A documents itself; run B does not. Align everything to **UTC** first:

| Source | Becomes |
|---|---|
| run-cursor `at:` per step | chapters — brainstorm, Q&A, spec, plan, phase N, review, deliver |
| journal entries | call-outs at that timestamp |
| git commits, PR events | markers |
| cast header `timestamp` (epoch) + event offsets | the clock everything maps onto |

**Journal `created=` is local time with no offset** — an entry written at
07:02 UTC reads `created=...T09:02:02`. Convert before aligning, or every
call-out lands two hours out.

Run B yields only commits and a transcript. That sparseness is a result, not a
gap in the method.

## Expect this, and keep it

Run A will hit the very bug it is fixing: at fr-goal step 8, `fr journal check`
cannot close the findings the run itself opened. It uses the *installed* `fr`,
not the code being written, so this is friction, not a hazard — and it is the
best annotation moment in the recording.

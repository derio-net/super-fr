# Dual-run recording runbook

Two runs at the same feature, same harness, same model, same brief. One with
`/fr-goal`, one without. Fills P1/P3 of the plan.

| | Run A | Run B | Run C |
|---|---|---|---|
| Treatment | `/fr-goal <seed prompt>` | `prompts/goal.md`, no `fr-*` | `prompts/goal-planned.md` — plan first, then implement |
| Harness | `opencode --auto` | `opencode --auto --pure` | `opencode --auto --pure` |
| Model | `github-copilot/gpt-5.6-terra`, default effort | same | same |
| Branch | whatever fr-goal picks | `experiment/vanilla-429` | `experiment/vanilla-planned-429` |
| Base | `RECORD_SHA` | same | same |

Run C exists because run B one-shotted the work: no planning pass, no
questions. That leaves fr-goal being compared against an agent that never
planned, which flatters it. Run C asks for the plan *in the prompt* and gives
nothing else, so the remaining difference between C and A is what the tooling
adds over a well-phrased instruction.

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
# MUST live under ~/Docs/projects: ~/.gitconfig has
#   [includeIf "gitdir:~/Docs/projects/**"] -> personal identity
# and everything outside it falls back to the WORK identity. The first run was
# cloned to ~/experiment-429 and committed as ioannis.dermitzakis@gebit.de.
export RUN_ROOT=~/Docs/projects/experiment-429
export RECORD_SHA=<pin from origin/main>

# run B: clean clone, repo-level OpenCode wiring removed
# ssh, NOT https: the keychain's https credential for github.com belongs to
# `clawdia-ai-assistant`, not you, so gh/git act as the wrong account.
for arm in vanilla vanilla-planned; do
  git clone git@github.com:derio-net/super-fr.git "$RUN_ROOT/$arm"
  git -C "$RUN_ROOT/$arm" checkout -b "experiment/${arm}-429" "$RECORD_SHA"
  rm -rf "$RUN_ROOT/$arm/.opencode" "$RUN_ROOT/$arm/opencode.json"
  # commit the removal, so the PR can be scored against this commit rather
  # than main and the setup deviation never pollutes the measured diff
  git -C "$RUN_ROOT/$arm" commit -q -am "experiment setup: remove OpenCode wiring"
done

# clean config + isolated storage for each run; copy credentials, drop MCP
for r in A B C; do
  mkdir -p "$RUN_ROOT/cfg-$r/opencode" "$RUN_ROOT/data-$r/opencode"
  cp ~/.local/share/opencode/auth.json "$RUN_ROOT/data-$r/opencode/"
done
# run A keeps super-fr's OpenCode skills/commands; run B gets none
cp -R ~/.config/opencode/skills ~/.config/opencode/commands \
      ~/.config/opencode/instructions "$RUN_ROOT/cfg-A/opencode/"
for r in A B C; do
  printf '{"$schema":"https://opencode.ai/config.json"}\n' > "$RUN_ROOT/cfg-$r/opencode/opencode.json"
done
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

Each run writes its own `opencode.db` under its `XDG_DATA_HOME`, so per-run
accounting is exact rather than lifetime. The `session` table carries
`parent_id`, `agent`, `cost`, `tokens_*` and `time_created/updated`, so
**subagents are child rows with their own cost, tokens and wall time** — a sum
over the run's db includes every subagent, and a `GROUP BY parent_id` splits
orchestrator from delegated work.

```bash
DB=$RUN_ROOT/data-<r>/opencode/opencode.db
sqlite3 -readonly "file:$DB?mode=ro" "
SELECT COUNT(*) sessions, SUM(parent_id IS NOT NULL) subagents,
       ROUND(SUM(cost),2) cost, SUM(tokens_input) tin, SUM(tokens_output) tout,
       SUM(tokens_cache_read) cache_read FROM session;"
XDG_DATA_HOME=$RUN_ROOT/data-<r> opencode export <session>   # full transcript
```

Reading the db while a run is live is safe read-only; do not open it writable.

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

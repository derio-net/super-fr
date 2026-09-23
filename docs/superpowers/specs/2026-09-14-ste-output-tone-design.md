# super-fr chattiness — reporting contract, artifact lint, opt-in STE style — design

Status: revised (fr-brainstorming, 2026-09-15). First version 2026-09-14.
Branch: `feat/ste-output-tone`
Operator decisions: §4 (d1–d11). d2 is superseded by d7.

This spec is written in the style it specifies.

## 1. Goal

The operator reports that super-fr is too "chatty". The first version of this
spec answered with a forced Simplified Technical English (STE) output style and
a global rule. Review showed three problems with that answer (§3). It reached
every session. It needed exceptions for other skills and for Claude Code
settings. Its effect stayed non-deterministic.

This revision starts from the problem. It asks where the words come from, and
it changes what super-fr controls:

1. **Reporting contract.** fr-goal and fr-debugging speak to the operator only
   at gates, blocks and delivery. Each update is the result, then the next step.
2. **Row presentation.** New acceptance rows reach the operator as one table.
3. **Artifact lint.** `fr journal add` and `fr plan self-review` warn on long
   sentences and filler words. Nothing fails.
4. **Opt-in STE style.** The STE output style stays, but the operator selects
   it. super-fr never forces a style.

### Non-goals

- super-fr does not force an output style or install a tone rule (d7).
- The `fr` CLI messages and the hook messages do not change (d1).
- PR body sections and the skill announce lines do not change (d8).
- Explainers, blog posts, READMEs and code comments do not change.
- The lint never fails a command (d9).
- super-fr does not change or disable other plugins (d3).
- super-fr does not ship the ASD dictionary or claim STE certification (d5).

## 2. Background — verified 2026-09-14 and 2026-09-15

### Where the words come from (baseline, d10)

Measured over the 11 most recent super-fr Claude Code sessions on the operator
Mac, with the script in Appendix A:

| Measure | Value |
|---|---|
| Assistant messages / tool calls | 308 / 563 |
| Words in end-of-turn replies | 8,956 (68%) |
| Words next to tool calls (narration) | 4,198 (31%) |
| Words in Insight blocks | 281 (2%) |
| Skill announce lines | 2 |
| Words per tool call | 23.4 |

Two gaps make these numbers indicative, not exact. The transcripts do not
record the harness's "user hasn't heard from you" nudges. And the current
session holds fewer words than its visible replies. The direction is still
clear: most words sit in end-of-turn reports, not in announce lines.

### What super-fr prescribes

- Nine skills have one `**Announce at start:**` line each.
- fr-goal says "Blocked → stop, say what you tried, ask", and it has no rule
  for updates between steps. So each step and phase ends with a report.
- fr-debugging §2 says "stop, state what you found / tried, and ask" at its two
  hard stops. It has no rule for other updates.
- fr-brainstorming §3 ends the brainstorm by "presenting the rows to the
  operator with a one-line defense each". fr-acceptance presents mid-flight
  additions "with a one-line defense". In practice each defense grows into a
  paragraph.
- fr-goal §7 lists the PR body sections. The operator keeps these (d8).

### Harness facts

- **Precedence is not deterministic.** An output style is part of the system
  prompt. Rules and CLAUDE.md load at session start in every project,
  subagents included. Skills load when they are invoked. Hook
  `additionalContext` arrives as extra context. The model weighs them together.
- **Output styles.** A plugin can ship `output-styles/*.md`.
  `force-for-plugin: true` overrides the user's `outputStyle` setting, and the
  only way to stop it is to disable the plugin. Without that field, the user
  selects the style in `/config`. Output styles do not reach subagents (forks
  excepted). Sources: https://code.claude.com/docs/en/output-styles,
  https://code.claude.com/docs/en/sub-agents.
- **The explanatory plugin is a hook.**
  `explanatory-output-style@claude-plugins-official` injects SessionStart
  `additionalContext` that asks for Insight blocks and permits longer replies.
- **blog-craft ships no output style and no context hook.** Its voice rules
  (`educational-writing`, `explainers`, `post-rewrite`) live in skills.
- **Licence.** ASD-STE100 Issue 9 is free to obtain but permits reproduction
  only with written authority from ASD.
- **Skill line cap.** Skills have a 120-line cap
  (`tests/unit/test_skill_validation.py`). fr-goal is at 120 lines, so a new
  sentence must replace text.
- **`fr plan self-review` exit codes.** It exits 1 only when an issue has
  severity `error` (`packages/fr/src/fr/commands/plan_cmd.py`). A `warn` issue
  prints and exits 0. So `fr run advance` keeps `plan-review` green.

## 3. Principle — change what super-fr controls, deterministically

The first version put a prompt in front of every session and then tried to
limit it with exceptions. Each exception changed the probability of a result,
not the result. That is the whack-a-mole the operator described.

This revision follows three rules:

- **A tone is a user preference.** The harness owns it. super-fr offers a
  style; it does not select one.
- **super-fr's own output is super-fr's job.** The skills ask for reports and
  presentations. Changing that text removes words at the source, with no
  competing instruction.
- **Artifacts fr writes are checked by fr, in code.** A lint in `fr` sees only
  fr's files. So it cannot affect other skills, other repos or chat replies.

## 4. Operator decisions

Asked 2026-09-14:

- **d1 — Scope.** Agent replies and skill-prescribed text; CLI and hook messages
  out of scope. (Scope of the reporting contract and row tables in this
  revision. The opt-in style keeps its own scope text, §5.D.)
- **d2 — Activation.** Forced style plus shipped rule. *Superseded by d7.*
- **d3 — Explanatory plugin.** Keep the Insight blocks, in STE, with no longer
  replies. It now applies only when the operator selects the STE style.
- **d4 — Test Plan.** Operator walk after merge, plus CI tests.
- **d5 — No dictionary** (agent decision, licence). Paraphrased principles only.

Asked 2026-09-15:

- **d6 — Reframe.** Chattiness problem first. The skill audit and the artifact
  lint are prerequisites, not follow-ups. Extend this spec and branch in place.
- **d7 — Repurpose.** Remove the `ste-output-tone` rule and its wiring, the
  fr-phase-executor STE line, and `force-for-plugin`. Keep the STE style as
  opt-in, with its tests. Keep the hermetic test fix `97e0b32` in this branch.
- **d8 — Skill audit.** Remove mid-run status reports (fr-goal, fr-debugging)
  and per-row presentation (fr-brainstorming, fr-acceptance). Keep PR body
  sections and announce lines.
- **d9 — Lint.** Warn only, in `fr journal add` and `fr plan self-review`. The
  plan's spec is checked by the same function.
- **d10 — Measure and reports.** Record the baseline (§2). Re-measure after
  merge. fr-goal updates are the result in 1–3 lines, then the next step.
- **d11 — Short, not obscure** (2026-09-23). A cap on length invites packed,
  jargon-dense updates. The plain-word rules of §5.D reach only an operator who
  selects the style, so the contract carries its own clarity sentence (§5.A).

## 5. Design

### A. Reporting contract (d8, d10)

**fr-goal** (`plugins/super-fr/skills/fr-goal/SKILL.md`). Replace "Blocked →
stop, say what you tried, ask." with:

> **Operator updates** only at the Q&A gate, a block or failure, and delivery.
> Each update is the result in 1–3 lines, then the next step. Evidence goes to
> the journal and the PR body, not the chat. Blocked → stop, give the result,
> ask.

Both skills also carry one clarity sentence (d11), after "then the next step":

> Short means split, not packed: plain words, name what an id refers to, keep
> the "because".

The file stays at or below 120 lines. Reflow other paragraphs to make room;
do not remove content.

**fr-debugging** (`plugins/super-fr/skills/fr-debugging/SKILL.md`, §2). Add
the same contract after the two hard stops. The hard stops keep "stop, state
what you found / tried, and ask", now as the result then the question.

### B. Row presentation (d8)

**fr-brainstorming** §3: replace "presenting the rows to the operator with a
one-line defense each" with "presenting the rows as one table — `id | claim |
level | defense`, one short line per cell".

**fr-acceptance**, "Mid-flight additions": replace "with a one-line defense"
with "as one table row each (`id | claim | level | defense`)".

The explainer `docs/explainers/01-fr-goal.md:329` says the agent "presents
these rows and a short defense for each". A table with a defense column keeps
that true, so the explainer does not change.

### C. Artifact lint (d9)

New module `packages/fr/src/fr/prose_lint.py`:

- `MAX_SENTENCE_WORDS = 25`.
- `FILLER_WORDS`: `just`, `really`, `basically`, `actually`, `simply`,
  `I think`, `it seems`.
- `lint_prose(text: str) -> list[ProseIssue]`. A `ProseIssue` has a `kind`
  (`long-sentence` or `filler`), a word count (long sentences), and a short
  excerpt.
- Before it counts, the lint removes text that is not prose:
  - YAML front matter (LF or CRLF);
  - fenced code blocks, also indented, with `~~~` or with 4+ backticks;
  - `BEGIN <label>` embed blocks, which end only at a bare `END` or at
    `END <label>`;
  - HTML comments, headings (`#` to `######` and a space) and table rows.
- It splits the rest into items at blank lines and list markers (`-`, `*`,
  `+`, `1.`, `1)`). It flattens each item to one line, then removes inline
  code, double-quoted strings and URLs. So a quote or a code span that wraps
  across lines is removed whole. A quoted string that ends with `.`, `!` or
  `?` keeps that mark.
- It splits each item into sentences at `.`, `!` or `?`, also when a closer
  follows the mark (`**`, `)`, `"`, `` ` ``, `_`).
- A word is a whitespace-separated token that contains a letter or a digit. So
  a path counts as one word, and a lone `-` counts as none.
- A filler word matches only as a whole word, not inside a path or a
  hyphenated word.
- The 20-word limit for instructions is not checked. Code cannot tell an
  instruction from a description.

**`fr journal add`** (`packages/fr/src/fr/commands/journal_cmd.py`). After it
writes a new entry, lint the title and the body. Print at most five warnings
to stderr, each on one line and labelled `title:` or `body:`, then `… N more`. The exit code does not change. A duplicate id
is refused (exit 2) before anything is written, so it lints nothing.

**`fr plan self-review`** (`packages/fr/src/fr/plan_ops.py`). New
`_prose_issues(plan)`, called from `self_review`. It lints:

- the text of each step that is not ticked `x` (the manual-verb detector uses
  the same exemption, so historical plans stay quiet);
- the plan's `_prose.md`;
- the plan's spec, when it is a same-repo path that resolves.

It returns one `ReviewIssue(severity="warn")` for each source that has issues,
with the count and the first two excerpts, printed on one line. So a long
document gives one line, not a flood.

A tripwire test keeps `FILLER_WORDS` equal to the quoted list in the STE
style's "Words" section. Thus the style and the lint cannot drift apart.

### D. Opt-in STE style (d7)

`plugins/super-fr/output-styles/simplified-technical-english.md` keeps its
text. Its frontmatter loses `force-for-plugin`. It keeps
`keep-coding-instructions: true`. The operator selects it in `/config`. The
description names the plugin, so the operator knows where it comes from.

The shared-block markers stay: the tests use them to find the text.

### E. Removals (d7)

- `plugins/super-fr/rules/ste-output-tone.md` — deleted.
- `scripts/install.sh` — the rule's `cp` and `echo` lines, and the `rm` line in
  `--uninstall` (its echo returns to the earlier text).
- `scripts/sync-hermes.py` `SHIPPED_RULE_NAMES` and `SHIPPED_RULES` in
  `tests/unit/test_tripwire_hermes_rules_sync.py` (with its docstring) — back
  to four rules.
- `.opencode/instructions/ste-output-tone.md` and the Hermes SOUL block —
  regenerated by `scripts/sync-opencode.py` and `scripts/sync-hermes.py`, which
  delete a mirror whose source is gone.
- `AGENTS.md` — the rule leaves the canonical rule list.
- `plugins/super-fr/agents/fr-phase-executor.md` — the STE sentence is removed;
  the section ends as before.
- `tests/unit/test_ste_output_tone.py` — the rule, identity and executor tests
  are removed. The style test asserts that `force-for-plugin` is absent.
- `docs/acceptance/matrix.yaml` — `hermes-rules-soul-block` names four shipped
  rules again.

The rule was never released: it existed only on this branch, and no release of
`main` up to 4.14.3 carried it. No consumer machine has it, so no uninstall
cleanup is needed.

### F. Tests (new)

- `tests/unit/test_prose_lint.py`:
  - a long sentence is found;
  - each strip rule in §5.C removes its text;
  - a filler word is found, and a quoted filler word is ignored;
  - a 25-word sentence passes, and a 26-word sentence warns.
- `tests/unit/test_journal_add_prose_warning.py`:
  - a long body prints a warning and exits 0;
  - a clean entry prints nothing;
  - a duplicate id is refused (exit 2) and prints nothing;
  - output stops after five lines.
- `tests/unit/test_self_review_prose.py`: warnings for a pending step, for
  `_prose.md` and for the spec; a ticked step is exempt; prose warnings do not
  change the exit code.
- `tests/unit/test_reporting_contract.py`: fr-goal and fr-debugging contain the
  contract sentence and the clarity sentence (d11); fr-brainstorming and
  fr-acceptance contain the table form;
  fr-goal no longer contains "say what you tried".
- The tripwire for `FILLER_WORDS` against the style text.

### G. Release

Minor bump to **4.18.0**: new warnings, a new opt-in style, and changed skill
behaviour. `main` reached 4.17.1 while this branch was open, so this branch
takes the next minor.

## 6. Risks and mitigations

- **The lint is noisy on existing specs.** Old specs were not written in STE.
  The self-review prints one line per source, and warnings never fail.
- **Warnings get ignored.** Possible. The lint is a nudge by d9. Promoting it
  to an error later is a one-word change and a new decision.
- **Fewer updates hide progress.** The run file, the journal and
  `fr run status` still show every step. Blocks and failures still report at
  once.
- **Short updates become obscure.** A length cap pushes toward noun stacks,
  bare ids and dropped reasons. The clarity sentence (d11) asks for splitting,
  not packing. No code can detect obscurity, so Test Plan step 3 is a human
  read.
- **fr-goal line cap.** The contract replaces one sentence and the text is
  reflowed. `test_skill_validation.py` enforces the cap.
- **Measurement gaps.** The script misses nudges and may miss compacted text.
  The re-measure uses the same script, so the comparison is like for like.
- **The explainer drifts.** §5.B checks the one sentence it has on rows. The
  plan re-checks it after the skill edits.

## 7. Test Plan

Pre-merge (CI): the tests in §5.F, the existing skill-validation, drift and
install tests, and `fr validate artifacts`.

Post-merge (operator-driven):

1. Update the plugin: `claude plugin update super-fr@derio-net--super-fr`.
   Restart Claude Code.
2. In `/config`, make sure that "Output style" is not forced to "Simplified
   Technical English". Select it once, send one message, and examine the reply.
   Then select your normal style again.
3. Run `/fr-goal` on a small goal. Make sure that the agent speaks only at the
   Q&A, at a block or failure, and at delivery. Make sure that each update is
   the result, then the next step. Make sure that it reads plainly: no
   unexplained ids or jargon, and each decision keeps its reason. When it
   presents new acceptance rows, make
   sure that they arrive as one table, not a paragraph for each row.
4. Run Appendix A over that session. Compare words per tool call and the
   end-of-turn share with the baseline in §2.
5. In any fr repo, run `fr journal add --scope spec --slug <any> --kind
   discovery --title x --body '<a 30-word sentence>'`. Make sure that a warning prints and the exit code is 0.
6. If a check fails, record the reply text or the output in a follow-up issue.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-14-ste-output-tone | `derio-net/super-fr` | `2026-09-14-ste-output-tone` | — |

## 8. Acceptance rows (born here; presented at spec review)

The three rows of the first version are retired: they were born on this branch
and never merged. `ste-style-forced-in-claude-code`,
`ste-rule-reaches-every-harness` and `ste-insight-blocks-kept-short` are
replaced by:

| id | capability | acceptance | level |
|---|---|---|---|
| `ste-style-opt-in` | output-tone | An operator can select a Simplified Technical English output style in `/config`, and super-fr never forces a style. | unit + operator walk |
| `fr-goal-reports-result-and-next-step` | output-tone | During fr-goal and fr-debugging runs, the operator gets updates only at gates, blocks and delivery, each as the result then the next step. | unit (skill text) + operator walk |
| `acceptance-rows-presented-as-table` | output-tone | New acceptance rows reach the operator as one short table, not a paragraph per row. | unit (text) + operator walk |
| `journal-add-warns-on-long-prose` | output-tone | `fr journal add` warns, without failing, when an entry has a sentence over 25 words or a filler word. | unit |
| `plan-self-review-warns-on-long-prose` | output-tone | `fr plan self-review` warns, without failing, on long sentences and filler words in pending steps, the plan prose and its spec. | unit |

## Appendix A — chattiness measurement

Run from any directory. Pass the transcript files to measure, newest first.
Transcripts live in `~/.claude/projects/<project-key>/*.jsonl`.

```python
import json, re, sys

W = lambda s: len(re.findall(r"[\w'-]+", s))
rows = []
for path in sys.argv[1:]:
    msgs, order, explanatory = {}, [], 0
    for line in open(path):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if "explanatory' output style" in json.dumps(e):
            explanatory = 1
        if e.get("type") != "assistant":
            continue
        m = e.get("message") or {}
        mid = m.get("id") or e.get("uuid")
        if mid not in msgs:
            msgs[mid] = {"text": "", "tools": 0}
            order.append(mid)
        for c in m.get("content") or []:
            if c.get("type") == "text":
                msgs[mid]["text"] += " " + c.get("text", "")
            elif c.get("type") == "tool_use":
                msgs[mid]["tools"] += 1
    narr = sum(W(msgs[i]["text"]) for i in order if msgs[i]["tools"])
    final = sum(W(msgs[i]["text"]) for i in order if not msgs[i]["tools"])
    insight = sum(W(x) for i in order
                  for x in re.findall(r"★ Insight.*?`─{20,}`", msgs[i]["text"], re.S))
    calls = sum(msgs[i]["tools"] for i in order)
    rows.append((len(order), calls, narr, final, insight, explanatory))

msgs, calls, narr, final, insight = (sum(r[k] for r in rows) for k in range(5))
words = narr + final
print(f"messages={msgs} tool_calls={calls} narration={narr} end_of_turn={final} insight={insight}")
print(f"end_of_turn_share={100 * final // max(1, words)}% words_per_tool_call={words / max(1, calls):.1f}")
```

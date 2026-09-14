# Simplified Technical English output tone — design

Status: draft (fr-brainstorming, 2026-09-14)
Branch: `feat/ste-output-tone`
Operator decisions: §4 (d1–d4). Agent decision: d5.

This spec is written in the style it specifies.

## 1. Goal

The operator reports that super-fr is too "chatty". Agent replies and the text
that skills make the agent write must use **Simplified Technical English**
(STE). STE is a published standard: ASD-STE100, Issue 9, January 2025.

Result: short sentences, active voice, one instruction per sentence, no filler.
The operator gets this without any setting change.

### Non-goals

- The `fr` CLI messages and the hook messages do not change (d1).
- Docs, explainers, specs, plans and code comments do not change.
- super-fr does not ship the ASD dictionary and does not claim STE
  certification (d5).
- super-fr does not change or disable other plugins (d3).

## 2. Background — verified 2026-09-14

- **No tone guidance exists.** A search of `plugins/`, `scripts/`,
  `packages/fr/src`, `.claude/` and the live specs finds no rule, style or skill
  text about tone or length.
- **Claude Code plugin output styles.** A plugin can ship `output-styles/*.md`.
  The frontmatter field `force-for-plugin: true` applies the style whenever the
  plugin is enabled. It overrides the user's `outputStyle` setting. If more than
  one enabled plugin forces a style, the first plugin loaded wins.
  `keep-coding-instructions: true` keeps the built-in engineering instructions.
  Source: https://code.claude.com/docs/en/output-styles. Local Claude Code is
  2.1.270.
- **Output styles do not reach subagents** (forks excepted). Subagents do load
  every CLAUDE.md level, including user rules. Source:
  https://code.claude.com/docs/en/sub-agents. `fr-phase-executor` is a subagent.
- **OpenCode and Hermes have no output styles.** OpenCode reads
  `.opencode/instructions/*.md` by glob, but only through this repo's own
  `opencode.json`. No installer delivers `.opencode/instructions` to consumer
  machines (`scripts/install.sh` copies OpenCode skills and commands only).
  This gap is older than this spec and applies to every shipped rule. Consumer
  delivery is a follow-up, not part of this spec (phase 3 review). Hermes reads the
  managed rules block in `~/.hermes/SOUL.md`, built from
  `SHIPPED_RULE_NAMES` in `scripts/sync-hermes.py`.
- **The explanatory plugin is a hook, not a style.**
  `explanatory-output-style@claude-plugins-official` is enabled on the operator
  Mac. Its `hooks-handlers/session-start.sh` injects SessionStart
  `additionalContext`. That text asks for "Insight" blocks and says "you may
  exceed typical length constraints". It does not use `force-for-plugin`, so it
  does not collide with a forced super-fr style.
- **Licence.** ASD-STE100 is free to obtain. Issue 9 permits reproduction only
  with written authority from ASD. (MIT-licensed prior art,
  `danyuchn/asd-ste100-skill`, records the same constraint and ships no word
  list.)
- **Skill line cap.** Six shipped skills are at the 120-line cap
  (`tests/unit/test_skill_validation.py`). Per-skill tone text cannot fit.

## 3. Principle — one text, two carriers

The STE instructions exist as one text. Two carriers deliver it:

1. a forced plugin output style, for the Claude Code main thread;
2. a shipped rule, for subagents and Hermes, and for OpenCode sessions inside
   this repo (§2: no installer delivers OpenCode instructions to consumers).

In both files, the shared text is between the lines `<!-- ste-shared:start -->`
and `<!-- ste-shared:end -->`. A test makes the two marked blocks identical.
Thus the carriers cannot drift apart.

## 4. Operator decisions (asked once, 2026-09-14)

- **d1 — Scope.** Agent chat replies, plus the text that skills make the agent
  write: announcements, status reports, PR bodies, journal entries,
  phase-executor returns. The CLI and hook messages are out of scope.
- **d2 — Activation.** A forced plugin output style plus a shipped rule.
- **d3 — Explanatory plugin.** Operator: "can we only keep the Insight blocks?
  If not, keep both". It is possible (§2). The style keeps Insight blocks,
  writes them in STE, and cancels the permission to exceed length limits.
- **d4 — Test Plan.** An operator walk after merge, plus CI tests.
- **d5 — No dictionary** (agent decision, forced by the licence). The text
  paraphrases the STE writing-rule principles. It does not copy rule text or
  the approved-word list.

## 5. Design

### A. The shared text

The text has these sections. The wording is final in the plan, not here.

- **Scope.** A closed list: replies, status updates, skill announcements, PR
  bodies, journal entries, subagent results. Do not apply to files that the
  agent edits: code, comments, docs, specs, plans, CLI and hook messages. Do
  not apply to commit messages.
  Copy code, commands, paths, identifiers, quoted output and quoted words of
  the operator exactly. If the operator, a skill or a caller gives a format or
  exact words, use them; write only the agent's own sentences in STE.
- **Words.** Use common words. Use one word for one meaning, and use the same
  term for the same thing every time. Use a simple verb, not a phrasal verb or
  a noun made from a verb ("check", not "carry out a check"). Technical names
  are permitted. Do not use filler, hedges or intensifiers ("just", "really",
  "basically", "I think", "it seems").
- **Sentences.** Maximum 20 words in an instruction. Maximum 25 words in a
  description. Commands and paths go in code spans and do not count as words.
  One instruction in each sentence. Use the active voice. Use simple tenses
  (no progressive: STE excludes it). Use the imperative for instructions. Put a
  condition before the instruction ("If the test fails, do X").
- **Structure.** Start with the result. Use a numbered list for sequential
  steps and a bulleted list for other items. Maximum six sentences in a
  paragraph. Do not use a preamble, a summary of the reply itself, or a closing
  offer.
- **Warnings.** Start with the instruction, then give the risk. Keep all the
  content of error reports, security warnings and confirmations for destructive
  actions.
- **Insight blocks.** If another prompt asks for Insight blocks, keep them.
  Write each point as one STE sentence, with a maximum of three points. Insight
  blocks do not make a reply longer. Ignore the other prompt's permission to
  "exceed typical length constraints"; these rules take precedence. (Say
  "prompt", not "instruction": in §5.A "instruction" is a sentence type.)

### B. Carrier 1 — output style

New file `plugins/super-fr/output-styles/simplified-technical-english.md`:

```yaml
name: Simplified Technical English
description: Short, clear replies based on ASD-STE100 writing rules
keep-coding-instructions: true
force-for-plugin: true
```

The body is the shared text. Claude Code discovers `output-styles/` by
convention, so `plugin.json` does not change. `install.sh` already copies the
whole plugin tree with rsync, so no install line is necessary.

### C. Carrier 2 — rule

New file `plugins/super-fr/rules/ste-output-tone.md`. Its body is the shared
text, after a short header that names the standard and the licence limit.

Wiring. Every item has a drift test today, so each item fails CI if it is
missing:

- `scripts/install.sh`: one `cp` line with the other rules, and one `rm` line
  in `--uninstall` (`test_install_copies_rules.py`).
- `.opencode/instructions/ste-output-tone.md`: generated by
  `scripts/sync-opencode.py`, which uses a glob
  (`test_tripwire_opencode_instructions_sync.py`).
- `scripts/sync-hermes.py` `SHIPPED_RULE_NAMES` and `SHIPPED_RULES` in
  `tests/unit/test_tripwire_hermes_rules_sync.py`; then regenerate
  `.hermes/SOUL.d/super-fr-rules.md`.
- `AGENTS.md`: add the rule to the list of canonical rules.

### D. Phase executor

`plugins/super-fr/agents/fr-phase-executor.md`, section "What you return": add
one line that tells the agent to write the result in STE, as the
`ste-output-tone` rule specifies. The rule already loads in Claude Code
subagents. The line also covers harnesses where it does not load.

### E. Tests (new)

`tests/unit/test_ste_output_tone.py`:

1. The style file exists, and its frontmatter has `force-for-plugin: true` and
   `keep-coding-instructions: true`.
2. Both files have exactly one `ste-shared` marker pair, and the two marked
   blocks are identical.
3. The shared text contains each section heading of §5.A as an exact line.
   The Insight section names the length permission, says Insight blocks do
   not make a reply longer, and says these rules take precedence.
4. Normalize whitespace and require balanced double quotes. Read the filler
   list from the "Words" bullet itself. Remove every double-quoted string; the
   remaining text contains no word from that list. (This keeps the text
   consistent with itself.)
5. `fr-phase-executor.md` refers to `ste-output-tone`.
6. The Scope section excludes edited files and defers to a format or exact
   words that the operator, a skill or a caller gives.
7. No sentence of the shared text has more than 25 words (headings, code spans
   and quoted examples excluded). A second test proves that the splitter
   catches a fake 30-word sentence, so the guard can fail. The 20-word limit
   for instructions needs a reader: a test cannot tell an instruction from a
   description.

### F. Release

This is a new mandatory behaviour, so the version bump is **minor**
(`scripts/bump-version.py minor`). No explainer describes the reply tone.
The PR body records this under the explainers-currency rule.

## 6. Risks and mitigations

- **The forced style overrides an output style that the operator selected.**
  Accepted in d2. To stop it, disable super-fr. The style description in
  `/config` names the plugin.
- **The rule applies in every project** on a machine where super-fr is
  installed, not only in fr-enabled repos. This is the same reach as the
  plugin. Accepted.
- **Another plugin that forces a style loads first.** Then our style does not
  apply, but the rule still does. The Test Plan checks the real result.
- **The installed Claude Code does not support `force-for-plugin`.** Then the
  style is only selectable in `/config`, but the rule still applies. Test Plan
  step 2 finds this condition.
- **Hook context asks for longer replies.** The shared text cancels that
  permission explicitly (§5.A, Insight blocks).
- **Short sentences can remove necessary detail.** The text keeps all content
  of errors and warnings, and it permits lists for complex information.
- **Token cost.** In the Claude Code main thread, both carriers load: the style
  (about 400 words) and the rule in `~/.claude/rules/` (about 460 words). This
  adds approximately 1,100 input tokens to each request. The copies are
  identical, so behaviour does not change. The prompt cache absorbs most of the
  cost. Subagents load only the rule.

## 7. Test Plan

Pre-merge (CI): the tests in §5.E, and the existing drift tests in §5.C.

Post-merge (operator-driven):

1. Update the plugin: `claude plugin update super-fr@derio-net--super-fr`.
   Restart Claude Code.
2. In `/config`, make sure that "Output style" shows
   "Simplified Technical English".
3. In any fr-enabled repo, run `/super-fr:fr-progress`.
4. Examine the reply against this checklist:
   - no sentence has more than 25 words (20 for an instruction);
   - active voice, one instruction in each sentence;
   - no preamble, no closing offer, no filler words;
   - if the explanatory plugin is enabled, Insight blocks have a maximum of
     three one-sentence points.
5. If a check fails, record the reply text in a follow-up issue.

## Implementation Plans

| Plan | Repo | File | Depends on |
|---|---|---|---|
| 2026-09-14-ste-output-tone | `derio-net/super-fr` | `2026-09-14-ste-output-tone` | — |

## 8. Acceptance rows (born here; presented at spec review)

| id | capability | acceptance | level |
|---|---|---|---|
| `ste-style-forced-in-claude-code` | output-tone | With super-fr enabled, Claude Code replies use the STE style, and the operator selects nothing. | unit + operator walk |
| `ste-rule-reaches-every-harness` | output-tone | The STE rule installs for Claude Code and Hermes, loads in OpenCode sessions inside this repo, and reaches the phase executor. | unit + tripwire |
| `ste-insight-blocks-kept-short` | output-tone | When another plugin asks for Insight blocks, the blocks stay, in STE, and replies do not get longer. | operator walk |

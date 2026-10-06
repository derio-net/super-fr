---
name: fr-audit
description: >
  Use when asked what a run or session cost, where the money went, whether a
  process change made the pipeline cheaper, or to compare runs before and after
  a change; when asked for an audit page or an architecture page of the fr
  pipeline; or when a PR body needs its usage table.
---

# fr-audit

**Announce at start:** "I'm using fr-audit to audit <runs or sessions>."

The numbers are not yours to compute. `fr usage` reads the harness's own session
store, deduplicates it, classifies every tool call and splits the harness's own
dollar figure. Your job is choosing what to compare and saying what the split
means. Never add a figure by hand, never price tokens yourself, and never write
`0` where the report says `—`.

## The engine

| Command | Does |
|---|---|
| `fr usage collect --run <id>` | every session a run cursor records, normalized into `$HOME/.cache/fr/usage/` |
| `fr usage collect --session <id> [--harness opencode\|hermes]` | one session (default harness: claude-code) |
| `fr usage report --run <id> [--run <id>…] --format table` | per model, activity, sub-activity and step |
| `fr usage report --session <id>… --format html -o <file>` | the same as one self-contained page |

Both are read-only: they read a run cursor and the harness store, and write only
under the cache, anywhere, even with a stale cursor. `report` reads any uncollected
session live. Pass `--repo <path>` when the cursor lives in another checkout.

## Choosing what to compare

- **One run:** `--run <id>`. The step table shows which pipeline step spent what.
- **Before and after a process change:** collect a comparable run on each side (same
  shape, harness, size); report separately, then side by side. One run per side is an
  anecdote; say so.
- **A sample:** name the sessions and report them together; pooled shares weight each
  session by its dollars.

A session another host ran comes back `unavailable` and renders `—`: an absence, not a
cheap session. Never drop it from the comparison silently or count it as zero.

## Reading the split

- **Dollars are the harness's.** Each model's harness figure is divided over that
  model's messages by price-weighted tokens with fixed ratios (input 1, cache write
  1.25 for 5 min / 2 for 1 h, cache read 0.1, output 5). The split always sums back to
  the harness total. What no message carries lands in `other / unattributed`.
- **Activities.** *paperwork* is fr's own bookkeeping: specs, plans, journals, run
  cursors, the acceptance matrix, their checks, and learning the CLI (`--help`).
  *implementation* is code read, code written and verification (tests, lint). *other*
  is version control, orchestration, chores and narration (a message with no tool call).
- **Context carry vs generation.** Most of a long session's dollars are cache reads,
  the whole context re-read on every turn. The context carried is the multiplier: a
  turn late in a long session costs far more than the same turn early. Output is
  the small part.
- **Turns are the cost unit.** An extra round trip re-reads everything. A
  bookkeeping step that takes six turns costs six context re-reads, however little
  it writes. When paperwork looks expensive, count its turns before blaming its size:
  the report's `turns` columns do (By activity, By step). A turn is one assistant
  message, counted once for each activity its tool calls touched, so activity turns
  can sum past the message count; step turns cannot.
- **Coarse sessions.** A `coarse attribution` note means the harness keeps one token count
  per message (Hermes): token-weighted split. State that caveat when comparing.
- **source.** `exact` is the billed figure, `estimated` the harness's estimate, `none` no
  figure. Carry it into any claim.

## Pages

Four triage pages (`fr triage render`, `origins render`, `architecture render`, `history render`) answer: "What do I do next?" (board), "Where do defects come from?" (origins), "What is the system?" (architecture), and "How did we get here?" (history). Each holds hand-written analysis in fragments (`board/manifest.yaml`, etc.): the next render rebuilds generated sections and erases any hand edits to pages.
**Audit page (measured).** `fr usage report --session <id>… --format html -o
$HOME/.cache/fr/usage/<name>.html`. Report the pooled shares and the per-session
range, name the sessions, and state what was unavailable.

**Architecture page (detailed).** The engine builds it: `fr triage architecture render --repo
<owner/repo> [--checkout <clone>] [--now-ref <ref>]` writes `architecture.html` into the
triage state directory (the usual `fr triage` scope options), and nothing else. Its sections
are generated, so you never type a figure into it: the summary and measured
sections (subsystem cards, size table),
then your fragments. You supply three inputs, all in the state directory:

- `subsystems.yaml`: a `subsystems:` list, each with `name`, `path` (globs; `*` spans `/`),
  `then_ref` (the git ref "then" is measured at) and `themes` (the judgement themes that place
  an open issue on it); an issue whose theme maps nowhere lands under *Other*. Lines: every line
  of every text file the globs match; binary files, symlinks and submodules are not counted, and
  a moved file moves its lines. Each commit is named; a figure not taken is `—`.
- `architecture/<name>.html`: authored fragments (diagrams, narrative, inline SVG), using the
  page's tokens (`var(--accent)`, `var(--ink)`). Close every tag; self-closing only on void
  elements and SVG shapes. Refused, by name, with nothing written: `<script>`, `<style>`, `<link>`,
  `<iframe>`, `<object>`, `<embed>`, `<meta>`, `<base>`, `<form>`, `<html>`, `<head>`, `<body>`,
  a page-level `<title>` (`<svg><title>` is fine), `on*` attributes and `javascript:` or
  `data:text/html` URLs. That is all the check does, so a fragment must carry no untrusted
  text: HTML-escape any issue title or other outside text yourself.
- `architecture/manifest.yaml`: an ordered list of generated section names
  (`summary`, `subsystems`, `size-table`) and fragment file names. A listed file that does not exist is reported
  and shown on the page; a generated section you do not name is appended, with a note on
  the page, before the fragments; with no manifest every generated section shows. (The timeline, waves,
  filings and origins now live on the history and origins pages respectively.)

**Measured versus projected is the rule.** The verb's sections are measurements. Everything
you author is the future state, design: for each step the spec changes, state the turns it removes
or adds and why, derive it from the measured figures, and label every such figure a projection
(in the fragment itself). A projection presented as a measurement is the defect this skill
exists to prevent. When the change ships, render again and put the measured figure beside the
projection; keep both.

Refresh the inputs first when you want a current page: `fr triage render` stores a snapshot, and
`fr triage origins collect` plus the `fr-origins` skill provide the origins data. **Publishing
stays yours**: fr writes a file under `$HOME/.cache/fr/triage/<scope>/`; copy or host it
wherever the operator publishes, after redacting any third-party identity it carries.

## Red flags

- A share quoted with no session list or no `source`.
- `—` turned into `0`, or an unavailable session left out of the denominator's story.
- A dollar figure computed from a list price. fr knows only ratios.
- A before/after claim from runs of different shape or harness, unstated.
- Session ids, paths or model names pasted into a public artifact unredacted.

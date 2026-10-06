---
name: fr-origins
description: >
  Use when asked where a repo's recent bugs came from, to classify the issues filed in a
  window by origin (latent, regression, new feature, leftover, gap, duplicate), to build a
  defect-origins page, or to explain which process change would have prevented them.
---

# fr-origins

**Announce at start:** "I'm using fr-origins to classify the issues filed in <repo or group> since <date>."

You can already read an issue and the code it names. A classification done in chat dies with the session; `fr triage origins` keeps it in a file, so a re-run costs only the issues that arrived.

## State: two files, two owners

Everything lives in the scope's triage state directory, the same one `fr triage` uses (`$HOME/.cache/fr/triage/<scope>/`; `--dir D` overrides). Pass the same scope options to every command: `--repo OWNER/REPO`, a comma-separated group `--repo A/B,C/D`, or `--org OWNER`.

| File | Written by | Holds |
|---|---|---|
| `origins-facts.json` | `fr triage origins collect --since DATE` | the issues created since the date: labels, state and reason, closing PRs, hours to close |
| `origins.yaml` | **you** | one classification per issue, plus the `causes:` the conclusion links to batches |
| `origins.html` | `fr triage origins render` | the page, built from both (and `judgements.yaml`, only to resolve batch ids) |

Never write the facts yourself. The state is outside every repo and is never committed.

## The loop (a re-run of it is the sync)

1. **Collect.** `fr triage origins collect --repo OWNER/REPO --since YYYY-MM-DD`. A window wider than one page of issues or PRs is refused (exit 2), naming a `--since` it does cover and the limit flag (`--issue-limit`, `--pr-limit`) to raise instead: narrow the window and report the narrower one, or raise the limit to keep it. A warning that the repo list hit its limit means repos may be missing; say so in your report.
2. **Check.** `fr triage origins check --repo OWNER/REPO` lists **unclassified** issues (your work queue) and classifications for issues **not in the facts** (a typo, or a window that moved; never pruned for you; fix the key or leave it). It always exits 0.
3. **Classify the unclassified**, from the issue body and the code, as below.
4. **Render.** `fr triage origins render --repo OWNER/REPO` writes `origins.html`. A figure the data cannot support shows as an em dash, never a zero; do not paper over one.
5. **Conclude.** Fill `causes:` and link each to the batch that addresses it (`fr triage batch list` names them; a batch id that does not exist is shown as unresolved, so fix it rather than leave it).

## origins.yaml

```yaml
schema: 1
issues:
  widgets#12:                   # <repo-name>#<n>, lowercase
    category: leftover          # latent | regression | new-feature | leftover | gap | duplicate
    source: pipeline            # pipeline | recording | hand
    pr: owner/repo#98           # the PR it relates to (optional; a regression REQUIRES one)
    severity: med               # low | med | high
    reason: one line, why this category
    evidence: optional, what you read to be sure
causes:                         # optional
  - title: Feature work lands half-done
    categories: [new-feature, leftover]
    batches: [finish-widgets]   # batch ids from judgements.yaml
    process_change: what to do differently, one line
```

## Classification discipline

- **Category is what the defect IS**, not who noticed it. **latent**: it was always there and nothing changed it. **regression**: a change broke something that worked, and you can name the PR that did. **new-feature**: a defect in something recently added. **leftover**: work a PR should have finished and did not (a skipped edge, a TODO, a mirror not regenerated). **gap**: a missing capability or test nobody had claimed. **duplicate**: the same defect as another issue; name that one in `reason` (nothing checks this: it is prose-only discipline, so re-read each duplicate's reason before you render).
- **Source is who found it**: `pipeline` (a gate, review or test in the run), `recording` (a person watching a live run or demo), `hand` (someone using the product).
- **Read the evidence.** Open the body and the code or the PR diff it names; never infer a category from the title alone. A title that says "broken after the change" is a hypothesis, not a regression.
- **A regression names its PR.** If you cannot find the PR that broke it, it is latent or a gap; say which and why.
- **A bad `origins.yaml` fails every verb that reads it.** One invalid entry (a regression with no `pr:`, say) makes `check` and `render` exit 2 until you fix it; nothing is skipped or partly rendered.
- **Hunt duplicates.** Compare each new issue against the rest of the window before you give it a category of its own; a duplicate counts once as a duplicate, not twice as a defect.
- **Say plainly what you did not verify.** Put "not checked against the code" in `evidence` rather than leave a guess looking like a finding, and list those issues in your report.
- Severity is the damage if it ships, not how annoying the report was.

## Privacy

State is outside every repo. For a repo or org that is not the operator's own, keep the page and both files local: no pasting them into an issue, a PR, a spec or a journal, and no publishing.

## Publishing the page

`origins.html` is one self-contained file; nothing in fr publishes it. Open it with `--open`, or hand it to whatever page-publishing tool your harness offers: that choice is yours, and the page needs no change for it. Report the path, the counts by category and source, what you did not verify, and the causes with their batches.

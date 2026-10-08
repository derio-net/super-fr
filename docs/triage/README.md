# Triage state for this repo

`fr triage` keeps its state in the scope's state directory: the workspace's
`.fr/triage-state/<scope>/` (kept out of git through `info/exclude`), or
`~/.cache/fr/triage/<scope>/` when run outside a clone; a scope with a state repo also keeps
a durable copy on the orphan branch `refs/heads/fr-triage/<scope-id>`. Neither is reviewed, so this folder
remains the reviewed copy for `derio-net/super-fr`: what is
needed to regenerate the four triage pages (the backlog page `triage.html`, the
defect-origins page, the architecture page and the history page), and the history that
cannot be regenerated.

## What is here

`derio-net--super-fr/` holds inputs and history only:

| Path | Written by | Why it is kept |
|---|---|---|
| `judgements.yaml` | the `fr-triage` skill, plus the `batch` verbs | tiers, themes, batches and their events; the board and the subsystem cards read it |
| `origins.yaml` | the `fr-origins` skill | one classification per issue since 2026-09-22; the 09-24 → 09-29 entries are the 2026-10-02 page's, imported |
| `subsystems.yaml` | by hand | the architecture page's 15 subsystem cards: globs, `then_ref`, themes |
| `<page>/manifest.yaml` | by hand | per page (`board/` for `triage.html`, `origins/`, `architecture/`, `history/`): the section order, generated sections and authored fragments interleaved |
| `<page>/*.html` | `authored-src/build.py`, or by hand | the authored fragments a manifest lists; they travel with the state |
| `snapshots/` | `fr triage render` | one per render; the backlog page's "Since last report" and the history page's timeline. Not reproducible |
| `authored-src/` | by hand | the sources of the built fragments (below) |

Left out on purpose, because fr rebuilds them: `facts.json`, `origins-facts.json` and the
rendered pages (`triage.html`, `origins.html`, `architecture.html`, `history.html`, and
the batch Kanban `board.html`). `fr triage state export|import` copies exactly the rest.

### authored-src/

- `pipeline.py` draws the pipeline-and-driver diagram with open issues pinned on steps, into
  `architecture/pipeline.html`. The pins are a table in the script; the build stops if a
  pinned issue has closed, so refresh the table first.
- `build.py` runs `pipeline.py` and writes the three dated fragments into `history/`: the
  2026-10-02 closing order with its outcome (looked up with `gh`), the 2026-10-02 origins
  analysis, and the history to 2026-10-02.
- `old/` are the three hand-built pages published on 2026-10-02, the only source of their
  diagrams and analysis. `extracted/` holds their sections with styles inlined, made by
  running `extract.js` in a browser on those pages; `build.py` reads these, not `old/`.

## Regenerating the pages

```bash
uv run fr triage state import --from docs/triage --repo derio-net/super-fr
fr triage collect --repo derio-net/super-fr --pr-limit 1000
fr triage origins collect --repo derio-net/super-fr --since 2026-09-22
fr triage check --repo derio-net/super-fr          # unranked: judge with the fr-triage skill
fr triage origins check --repo derio-net/super-fr  # unclassified: the fr-origins skill
python3 .fr/triage-state/derio-net--super-fr/authored-src/build.py   # the state directory
fr triage render --repo derio-net/super-fr
fr triage origins render --repo derio-net/super-fr
fr triage architecture render --repo derio-net/super-fr --now-ref origin/main
fr triage history render --repo derio-net/super-fr
uv run fr triage state export --to docs/triage --repo derio-net/super-fr
```

The state directory stays the working copy because `fr triage batch drive` writes `judgements.yaml`
on every pass. `.fr/triage.yaml` sets `export: {path: docs/triage}`, so the driver exports
the state as a PR once a wave finishes and merges it when green; export by hand after a
triage session.

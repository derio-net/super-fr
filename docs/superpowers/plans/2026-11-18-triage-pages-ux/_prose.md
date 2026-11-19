# Triage pages UX — plan

Implements spec `2026-11-18-triage-pages-ux` (derio-net/super-fr#1544) in four agentic phases, one per independently reviewable ask:

1. **Names, split and stamp** (R1–R5): the page registry becomes the one source of page files and fragment dirs; `fr triage backlog`/`batches` with the old commands as aliases; the Backlog splits into Backlog and Issues; every page states its render time. Skeleton: its first task is the smoke.
2. **Shared folds, links and tabs** (R8, R9, R11–R13, R16, R17): one `fold` component, one page CSS/script pair on every page (which fixes the stacked Architecture diagrams), forge and wave links, the Waves kind filter and History's PR column.
3. **Batches and Origins** (R10, R14, R15, R18): collapsible remembered columns, the wave cutoff, Origins' group folds, state filter and PR detail from the merged PRs `origins collect` now keeps.
4. **The driver keeps pages current** (R6, R7): callable page writers, `_write_pages` after the board, and a snapshot at each wave's finish.

Each phase ends with a browser check over fixture-rendered pages (where it touches UI) and a full suite run logged after its last code commit.

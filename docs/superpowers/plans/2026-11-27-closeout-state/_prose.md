# Close-outs and batches never stuck as started or Running

Two phases, one per issue of batch `closeout-state`.

**Phase 1 (#1601, skeleton).** The take-back after a failed close-out dispatch gets its own guard in both starts. A failing take-back joins the dispatch error in the one line `_dispatch_failed` reports, so `--once` exits 1 and the driver keeps going. The per-batch start writes through the non-printing `_save`, so `_fail` prints no second line. `fail_text` in `drive_errors.py` is the one reader of a `_fail` exit's message.

**Phase 2 (#1626).** `left_scope(batch, facts)` (repo missing from `facts.repos`, the repo list not truncated) gives the derived stage `left-scope`. It is closed out: it owes and releases no claims, the pass ignores it, it counts as terminal for waves, `drive` asks for no checkout of its repo, and the board puts it in Done with the pill `repo left this scope` and no Jump. `batch focus` refuses and names `batch cancel <id> --orphaned`, which appends only the cancel event. `docs/explainers/fr-triage.md` describes both.

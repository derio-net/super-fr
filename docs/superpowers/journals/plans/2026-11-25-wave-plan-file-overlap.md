<!-- fr:journal-schema=4 -->
# Journal: 2026-11-25-wave-plan-file-overlap

<!-- fr:journal kind=decision scope=plan id=plan-overlap-one-paragraph created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-one-paragraph · decision · A card's overlap sentences render as one paragraph (phase 1)

The spec asks for one `<p class="overlap">` per card detail, so a card in several overlaps joins its sentences with spaces inside that one paragraph, instead of one paragraph per overlap.

<!-- fr:journal kind=discovery scope=plan id=plan-overlap-checkout-paths-optional created=2026-11-25T15:44:18+00:00 phase=1 -->
### plan-overlap-checkout-paths-optional · discovery · The driver's checkout map holds optional paths (phase 1)

`checkout_paths` is `dict[str, Path | None]`, so `write_board` and `source_for_clones` take `Mapping[str, Path | None]`; a None value reads as no clone of the repo.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the check command change is one call and one print block; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-25T15:44:18+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs, fragment and acceptance moves only; no code to refactor

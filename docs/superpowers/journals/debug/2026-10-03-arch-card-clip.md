# Journal: 2026-10-03-arch-card-clip

<!-- fr:journal kind=repro scope=debug id=6002fa93f6f6 created=2026-10-03T21:02:52+00:00 -->
### 6002fa93f6f6 · repro · Subsystem card content overflows its card at 400px on a long unbreakable title

Rendered the architecture page (test fixture `_page()`) with three issue titles carrying a 120-char unbreakable test-name token, then measured it in headless Chrome at a 400x800 viewport. The `Other` card is 366px wide with a 972px scrollWidth, and `main` is 989px wide in a 400px viewport. `html { overflow-x: hidden }` stops the page scrolling, so the title is clipped instead. This matches #901 (454px of content in a 366px card).

<!-- fr:journal kind=hypothesis scope=debug id=6fe99424f609 created=2026-10-03T21:02:52+00:00 -->
### 6fe99424f609 · hypothesis · Nothing in a subsystem card gives an unbreakable token a break opportunity

`article.subsystem` has `min-width: 0`, so the grid track holds at 366px, but neither the card nor its `li`/`h3`/`.src` declares `overflow-wrap`. An unbreakable token's min-content width therefore spills out. Only `code`, `header.mast h1` and `.cards li` carry `overflow-wrap: anywhere` on this page, while the board page sets it on every text-bearing row. Test: inject `article.subsystem { overflow-wrap: anywhere; }` into the rendered page and re-measure.

<!-- fr:journal kind=root-cause scope=debug id=1cbacb9ddc74 created=2026-10-03T21:02:53+00:00 -->
### 1cbacb9ddc74 · root-cause · article.subsystem lacks overflow-wrap: anywhere, so long tokens in its li/h3/.src cannot wrap

Confirmed: with the one injected rule, the same page measures `main` at 400px and every card at 366/366 (scrollWidth = clientWidth). It is one cause: the card is the only container of unwrappable free text on the page without the rule (the table already scrolls inside `.scroll`, and `.cards li` already wraps). The rule goes on the card rather than on `li` alone because the subsystem name (`h3`) and the path list (`.src`) are free text too and would clip the same way.

<!-- fr:journal kind=finding scope=debug id=b93774c4d649 created=2026-10-03T21:15:18+00:00 state=fixed -->
### b93774c4d649 · finding [fixed] · overflow-wrap: anywhere on article.subsystem; pinned by test_a_long_unbreakable_token_wraps_inside_its_subsystem_card

Source: one declaration added to `article.subsystem` in `packages/fr/src/fr/triage/architecture.py`'s `CSS`. Test first: `tests/unit/test_triage_architecture.py::test_a_long_unbreakable_token_wraps_inside_its_subsystem_card` (parses the rule's declarations, as the board's `.num` test does) failed on `overflow-wrap` before the fix and passes after. Live: the same long-title render at 400px in headless Chrome went from `main` 989px / `Other` card scrollWidth 972 in 366 to `main` 400px with every card 366/366. Full suite: 8088 passed, 105 skipped.

<!-- fr:journal kind=review scope=debug id=3178da55fbd5 created=2026-10-03T21:15:19+00:00 -->
### 3178da55fbd5 · review · Self-review of a one-declaration CSS fix; no findings

Diff reviewed: one CSS declaration, a test, and a patch fragment. Checked that `anywhere` (not `break-word`) is the right value: the card is a grid item, and only `anywhere` lowers the min-content contribution that grid sizing uses, which is also why the board page uses it. The scoped tables on this page stay in their `.scroll` wrapper, untouched. No independent reviewer was dispatched for a change this size. No findings raised.

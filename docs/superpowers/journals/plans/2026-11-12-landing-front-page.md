<!-- fr:journal-schema=3 -->
# Journal: 2026-11-12-landing-front-page

<!-- fr:journal kind=decision scope=plan id=landing-no-bar-placeholder created=2026-11-12T09:34:31+00:00 phase=1 -->
### landing-no-bar-placeholder · decision · Landing skeleton has no {{bar}} placeholder (phase 1)

The plan listed a {{bar}} placeholder in landing.html, but R8 has insert_bar add the bar to every page including the landing, after the body open tag. A second insertion point would put two bars on the front page, so the skeleton has none; its body carries class landing so bar.css can sit flush there.

<!-- fr:journal kind=discovery scope=plan id=bar-inside-body-padding created=2026-11-12T09:34:31+00:00 phase=1 -->
### bar-inside-body-padding · discovery · The blog-craft body padding put the bar inside the page margin (phase 1)

Blog-craft pages set body padding 3rem 1.25rem, so a plain nav landed inset and crowded the title (seen in the first screenshots). bar.css now uses negative margins to sit flush above the article and a .landing override for the landing, whose body has no padding.

<!-- fr:journal kind=discovery scope=plan id=suite-env-limits created=2026-11-12T09:34:31+00:00 phase=1 -->
### suite-env-limits · discovery · Full suite not fully runnable here: slow npm installs, seven environment failures (phase 1)

tests/integration/test_install*.py, test_scenarios.py and test_bootstrap_sh.py run install.sh, whose npm install of the devcontainers CLI times out in this sandbox (minutes per test, so hours in total); they were excluded from the logged run. The logged run (14663 passed, 132 skipped, 7 failed) fails only tests unrelated to this phase and consistent with the sandbox: four read-only-file or unwritable-cache tests that cannot fail as uid 0 (test_bindings_catalogue, test_bindings_probe, test_artifact_atomic, test_validate_artifacts) and three isolation container verb CLI tests (test_isolation_container_verbs). No file this phase touched is involved; CI is the authority for the excluded and failing tests.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-12T09:34:31+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

file move and link re-pointing only

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-12T09:34:31+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

copy and a repo-level test only; no code to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t6 created=2026-11-12T09:34:31+00:00 phase=1 -->
### no-refactor-p1-t6 · discovery · no-refactor-because P1.T6 (phase 1)

guidance, matrix and mirror regeneration only; no code to clean

<!-- fr:journal kind=review scope=plan id=p1-review created=2026-11-12T09:39:42+00:00 phase=1 -->
### p1-review · review · Phase 1 code review: requirements R1-R12 met, two low findings (phase 1)

A separate reviewer read the spec, the plan and the diff, ran the focused tests (376 passed) and ruff (clean), built the site with the pinned renderer (29 pages) and took its own screenshots. It found every requirement implemented and tested, the build refusals firing before any file is written, front-matter values escaped, bar links right at each route depth, no script tags, no sideways scroll at 390px, light-scheme contrast above 4.5:1, and the landing copy's spot-checked claims true. It raised p1-r1 and p1-r2, both in scope and both fixed.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-12T09:39:42+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · Top bar wraps its last link onto a second row at 390px (phase 1)

scripts/site/bar.css: at phone width the GitHub link dropped under the site name, which read as an accident.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-12T09:39:42+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · The copied palette is only checked for --ink (phase 1)

scripts/build-site.py extract_theme_css required only --ink, while the site stylesheets read twelve more properties. A renderer that renamed one would have built a landing with unset colours or fonts instead of failing.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-12T09:39:42+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: Top bar wraps its last link onto a second row at 390px (phase 1)

The phone-width rule tightens the gap and type size; the fresh 390px screenshots of the landing and a guide show all five items on one row, with scrollWidth 390.

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-12T09:39:42+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: The copied palette is only checked for --ink (phase 1)

THEME_PROPERTIES names every property the stylesheets read; extract_theme_css raises BuildError naming any that are missing. One test refuses a theme missing each of five properties, another pins the tuple to the var() names in scripts/site/*.css.

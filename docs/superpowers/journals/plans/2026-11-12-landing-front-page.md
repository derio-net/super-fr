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

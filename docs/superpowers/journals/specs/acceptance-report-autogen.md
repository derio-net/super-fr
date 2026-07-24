# Journal: acceptance-report-autogen

<!-- fr:journal kind=decision scope=spec id=dec-1-commit created=2026-07-24T17:21:55 -->
### dec-1-commit · decision · Commit report.html (un-gitignore), enforce sync

Non-interactive VK card: chose committed+tripwire over local-only regen. 'Always create/update the corresponding html file' reads as a maintained versioned artifact.

<!-- fr:journal kind=decision scope=spec id=dec-2-linkmode created=2026-07-24T17:21:55 -->
### dec-2-linkmode · decision · Committed report uses local link-mode

GitHub renders committed .html as source; local relative links resolve from a checkout. CI artifact keeps github links.

<!-- fr:journal kind=decision scope=spec id=dec-3-enforce created=2026-07-24T17:21:55 -->
### dec-3-enforce · decision · Unit tripwire in existing test job, not a new CI step

Mirrors test_tripwire_opencode_skills_sync.py; lowest churn.

<!-- fr:journal kind=decision scope=spec id=dec-4-regenfail created=2026-07-24T17:21:55 -->
### dec-4-regenfail · decision · add: never roll back a valid row on render failure

Warn + rely on tripwire backstop.

<!-- fr:journal kind=review scope=spec id=rev-collisions created=2026-07-24T17:21:55 -->
### rev-collisions · review · Spec review: 2 expected test collisions, design sound

test_acceptance_init asserts report.html gitignored (flip in TDD); LinkBuilder has 2 call sites (probe=True default keeps compat). No design change.

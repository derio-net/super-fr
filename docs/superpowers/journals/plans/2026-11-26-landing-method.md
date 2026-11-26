<!-- fr:journal-schema=4 -->
# Journal: 2026-11-26-landing-method

<!-- fr:journal kind=decision scope=plan id=landing-hold-budget created=2026-11-26T13:51:43+00:00 phase=1 -->
### landing-hold-budget · decision · triage_batch_cmd.py module budget moved from 8225 to 8250 (phase 1)

_landing_hold (about 20 lines) must sit in the driver because it calls merge_ctx; the pure parts (landing_refusal, REBASE_WARNING) live in queue_exec.py. The budget stays within 400 lines of the module.

<!-- fr:journal kind=discovery scope=plan id=batch-merge-method-hold-exit created=2026-11-26T13:51:43+00:00 phase=1 -->
### batch-merge-method-hold-exit · discovery · batch merge --method with a disallowed method now exits 1 with queue-held, not 2 (phase 1)

R2 makes an unchoosable method a held plan instead of a raise, so test_batch_merge_uses_the_method_it_is_given_or_the_repos_default now expects exit 1 and the held reason.

<!-- fr:journal kind=discovery scope=plan id=writing-standard-unchecked created=2026-11-26T13:51:43+00:00 phase=1 -->
### writing-standard-unchecked · discovery · the writing-standard check of the edited pages was not run locally (phase 1)

scripts/check-writing-standards.sh needs a pinned blog-craft checkout; CI's site-build job runs it. Edited pages: fr-wave-driver.md, fr-exit-gates.md (plain-language), cloud-setup.md, merge-protection.md (ste).

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t2 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t2 · discovery · no-refactor-because P1.T2 (phase 1)

land_push's refspec loop is now one line; nothing more to clean beyond the shared landing_refusal

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t3 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t3 · discovery · no-refactor-because P1.T3 (phase 1)

the cloud check reuses choose_method_source and landing_refusal; the queue block reader is a sibling of the merge_method reader, nothing to merge further

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

logged_prs is now a thin wrapper over logged_pr_dates; nothing else to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-26T13:51:43+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

docs and config only; stamps follow the page text

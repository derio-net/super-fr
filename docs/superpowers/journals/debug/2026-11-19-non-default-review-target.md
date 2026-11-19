<!-- fr:journal-schema=4 -->
# Journal: 2026-11-19-non-default-review-target

<!-- fr:journal kind=root-cause scope=debug id=default-ref-used-as-review-target created=2026-11-19T08:48:37+00:00 -->
### default-ref-used-as-review-target · root-cause · Lens review always diffs against remote default instead of the intended merge target

Observed in a self-hosted GitLab consumer (identities redacted): a management change targets an independent non-default branch with a real common ancestor, while origin/master is unrelated. lenses.accumulate.lens_set drops all run context except journal slugs; lens_set_for unconditionally calls rules.default_ref, which uses git.remote_default_ref. pr create accepts --base but only passes it to create_pr and persists the PR URL, not a review target. Therefore review cannot use the intended target before MR creation and raises no merge-base against master. Correct behavior needs an explicit durable run target consumed by the review diff and aligned with MR creation, preserving fail-closed missing-ref/ambiguity and baseline lens protections. No consumer refs or gate outcomes were changed to bypass the defect.

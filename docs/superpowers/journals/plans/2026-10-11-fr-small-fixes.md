# Journal: 2026-10-11-fr-small-fixes

<!-- fr:journal kind=discovery scope=plan id=p1-d-fake-state-case created=2026-10-12T15:43:37+00:00 phase=1 -->
### p1-d-fake-state-case · discovery · FakeGhClient stores the state string as given (phase 1)

The fake keeps whatever state edit_issue_state received, and GithubTracker previously passed lowercase closed. It now passes CLOSED and the fake refuses anything but OPEN or CLOSED; the existing done test asserts CLOSED.

<!-- fr:journal kind=discovery scope=plan id=p1-d-models-handler created=2026-10-12T15:43:37+00:00 phase=1 -->
### p1-d-models-handler · discovery · ModelsError handled by one decorator, with resolve --record handled inside the advance (phase 1)

fr.commands.common.models_errors_exit wraps advance and the five fr models commands. run start warns in place. resolve --record catches inside _advance_after_record, so the applied record is reported. No harness means no models.yaml read, as before.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-10-12T15:43:37+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

release fragment, acceptance rows and quality gate; no code to refactor

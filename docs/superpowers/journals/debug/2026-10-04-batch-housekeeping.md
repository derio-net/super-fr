# Journal: 2026-10-04-batch-housekeeping

<!-- fr:journal kind=ruled-out scope=debug id=single-root-cause created=2026-10-04T04:52:51+00:00 -->
### single-root-cause · ruled-out · Batch is not one root cause

Batch premise 'ONE root cause' ruled out on investigation. Members touch six unrelated subsystems with independent causes: #746 PATH/zsh fr-binary identity (design ask); #455 fr-worktree-create.sh agent-* mimic skips .worktreeinclude; #456 plugins/super-fr/scripts/fr-statusline-segment.sh latency (unmeasured); #619 scripts/install-validator-wrapper.sh retirement (deletion); #805/#806 isolation/scaffold.py:697 safe_dump drops comments + #794 nits; #648/#646 triage collect join_open defaults + live_reservations scope; #691 explainer 01-fr-goal.md L583-587 still says provenance is typed, default agent. Per batch rule, stopping to ask before fixing.

<!-- fr:journal kind=decision scope=debug id=scope-decision created=2026-10-04T05:07:32+00:00 -->
### scope-decision · decision · Operator scope decision

Operator chose: one PR fixing the eight mechanical members (#455 #456 #619 #805 #806 #648 #646 #691), each journalled per cause with its own failing test; #746 is a design ask, excluded from Closes, routed to its own fr-goal run.

<!-- fr:journal kind=root-cause scope=debug id=rc-805 created=2026-10-04T05:12:12+00:00 -->
### rc-805 · root-cause · #805: scaffold round-trips fr-profiles.yaml

_update_profiles_yaml (fr/isolation/scaffold.py) rebuilt the file with yaml.safe_load + safe_dump, which carry no comments, so every scaffold dropped operator comments.

<!-- fr:journal kind=finding scope=debug id=fix-805 created=2026-10-04T05:12:14+00:00 state=fixed -->
### fix-805 · finding [fixed] · #805 fixed by line surgery

New _edit_profiles_text replaces/appends only the profile entry and the default: line, drops service/legacy keys by line, and verifies the result re-reads to the intended data, else falls back to the old dump. Tests: test_init_scaffold.py::test_adding_a_profile_keeps_every_comment, ::test_rescaffolding_a_profile_replaces_only_its_entry (red first).

# Journal: 2026-10-04-batch-plan-and-records

<!-- fr:journal kind=finding scope=debug id=f-multi-cause created=2026-10-04T04:53:16+00:00 state=open -->
### f-multi-cause · finding [open] · Batch has six independent root causes, not one

Investigation on origin/main a11aa07f confirms the members are live but share no cause: #653 advance never creates .records/ and the brief copies step.evidence (incl. derived 'findings', run_cmd.py:2846/3270) verbatim; #525 ~50 unescaped rich interpolations of exceptions (e.g. plan_cmd.py:453,489 parse errors); #502 plan_ops dumps whole phase YAML via PyYAML; #763 parse_journal catches only KeyError (journal/model.py:356); #639 journal add has no artifact-existence check; #675 help text plan_cmd.py:156; #661 test literal, deliberate. Per the batch's debugging rule, stopped to ask before fixing.

<!-- fr:journal kind=root-cause scope=debug id=rc-653 created=2026-10-04T05:03:32+00:00 -->
### rc-653 · root-cause · #653: advance never makes .records/; derived evidence listed in two drifting copies

record/apply.py mkdirs only at apply, so a heredoc into the printed path fails. The brief copies step.evidence verbatim (run_cmd.py _build_brief/_build_member_brief) incl. derived 'findings'; record/template.py keeps its own _DERIVED copy which already lacks 'single-phase'. The template's journal comment never mentions phase|global for plan scope, though record/apply.py:326 refuses an untagged plan entry.

<!-- fr:journal kind=root-cause scope=debug id=rc-525 created=2026-10-04T05:03:40+00:00 -->
### rc-525 · root-cause · #525: exception text interpolated into Rich markup

Repro: a phase with tag: "[/red]" -> fr plan self-review dies with MarkupError (plan_cmd.py:453 prints the parse error via f-string with markup on). Same shape at ~50 except-handler sites in commands/.

<!-- fr:journal kind=root-cause scope=debug id=rc-502 created=2026-10-04T05:03:49+00:00 -->
### rc-502 · root-cause · #502: every plan_ops writer safe_loads and re-dumps the whole phase file

tick/complete_phase/set_tracking_issue/clear_tracking_issue: yaml.safe_load -> mutate -> _yaml_dump(whole doc). Any style the dumper would not emit is normalised on every tick.

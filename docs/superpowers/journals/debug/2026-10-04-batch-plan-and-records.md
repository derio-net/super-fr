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

<!-- fr:journal kind=root-cause scope=debug id=rc-763 created=2026-10-04T05:03:56+00:00 -->
### rc-763 · root-cause · #763: parse_journal catches KeyError only

JournalEntry's model_validator raises ValueError (pydantic ValidationError) for a scope-invalid token; parse_journal (journal/model.py:356) converts only KeyError to JournalParseError. int(phase) on a hand-typed phase= has the same escape.

<!-- fr:journal kind=root-cause scope=debug id=rc-639 created=2026-10-04T05:04:04+00:00 -->
### rc-639 · root-cause · #639: journal add never checks the slug names an artifact

commands/journal_cmd.py add writes journal_path(root, scope, slug) unconditionally. Constraint found: standalone fr-brainstorming records the --input brief BEFORE the spec exists, so the check must admit that entry and any already-existing journal.

<!-- fr:journal kind=root-cause scope=debug id=rc-675 created=2026-10-04T05:04:10+00:00 -->
### rc-675 · root-cause · #675: --phases-file help predates one-phase plans

plan_cmd.py:156 says the skeleton marker is for the first agentic phase; since #674 it is owed only with 2+ agentic phases. #661 is not a defect: the duplicate header literal is a deliberate anti-tautology pin.

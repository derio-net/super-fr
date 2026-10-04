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

<!-- fr:journal kind=ruled-out scope=debug id=ro-502-plan-ops created=2026-10-04T05:12:51+00:00 -->
### ro-502-plan-ops · ruled-out · #502: plan_ops.tick is not the CLI's tick path

First fix targeted plan_ops.tick/complete_phase. fr plan edit --tick/--complete-phase build a StepRecord and go through record/apply.py _plan_writes, which also re-dumps the whole phase file (overlay.put(..., _yaml_dump(data))). plan_ops.tick/complete_phase have no production caller. Corrected root cause: the record engine's _plan_writes; the splice must be text-in/text-out so the engine's in-memory overlay can use it, and the pinning test must go through the CLI.

<!-- fr:journal kind=finding scope=debug id=fx-525 created=2026-10-04T05:44:28+00:00 state=fixed -->
### fx-525 · finding [fixed] · #525 fixed: exception text escaped at 61 sites

escape(str(e)) at each except-bound interpolation into a markup-on console.print (authored [red] unchanged). Pinned by tests/unit/test_plan_cmd.py::test_a_parse_error_quoting_rich_markup_is_reported_not_raised (self-review AND proportionality crashed) and the AST tripwire tests/unit/test_tripwire_rich_exception_markup.py.

<!-- fr:journal kind=finding scope=debug id=fx-502 created=2026-10-04T05:44:32+00:00 state=fixed -->
### fx-502 · finding [fixed] · #502 fixed: ticks rewrite only the state: block

plan_ops.rewrite_phase_text splices the changed top-level block, trusted only if it parses back to the intended doc. Wired into record/apply.py _plan_writes (the real CLI path) and the plan_ops writers. Pinned by tests/unit/test_record_verbs.py::test_plan_edit_rewrites_only_the_state_block_it_changes (RED with the engine change reverted) plus plan_ops tests.

<!-- fr:journal kind=finding scope=debug id=fx-653 created=2026-10-04T05:44:36+00:00 state=fixed -->
### fx-653 · finding [fixed] · #653 fixed: brief/template read one derived set; advance makes .records/

fr.workflow.artifacts.DERIVED_EVIDENCE shared by gate, brief and template; brief lists caller evidence only; _record_brief mkdirs the records dir; plan-journal template names phase|global. Pinned in test_run_cli.py and test_record_template.py.

<!-- fr:journal kind=finding scope=debug id=fx-763 created=2026-10-04T05:44:39+00:00 state=fixed -->
### fx-763 · finding [fixed] · #763 fixed: hand-edited token is a named JournalParseError

parse_journal converts ValueError (and a non-numeric phase=) to JournalParseError naming the entry. Pinned by test_journal_model.py::test_a_hand_edited_token_invalid_for_its_entry_is_a_parse_error.

<!-- fr:journal kind=finding scope=debug id=fx-639 created=2026-10-04T05:44:42+00:00 state=fixed -->
### fx-639 · finding [fixed] · #639 fixed: journal add refuses an orphan spec/plan slug

_orphan_refusal: debug, an existing journal, and a spec --input brief are admitted. Orphan journal deleted. Three older spec journals with no spec (scaffold-batch-574-576-569, triage-open-prs, uninstall-installed-rules) left in place: outside the brief's authorised deletion. Pinned by test_journal_cmd.py::TestAddRefusesAnOrphanSlug.

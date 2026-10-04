# Journal: 2026-10-04-batch-plan-and-records

<!-- fr:journal kind=finding scope=debug id=f-multi-cause created=2026-10-04T04:53:16+00:00 state=open -->
### f-multi-cause · finding [open] · Batch has six independent root causes, not one

Investigation on origin/main a11aa07f confirms the members are live but share no cause: #653 advance never creates .records/ and the brief copies step.evidence (incl. derived 'findings', run_cmd.py:2846/3270) verbatim; #525 ~50 unescaped rich interpolations of exceptions (e.g. plan_cmd.py:453,489 parse errors); #502 plan_ops dumps whole phase YAML via PyYAML; #763 parse_journal catches only KeyError (journal/model.py:356); #639 journal add has no artifact-existence check; #675 help text plan_cmd.py:156; #661 test literal, deliberate. Per the batch's debugging rule, stopped to ask before fixing.

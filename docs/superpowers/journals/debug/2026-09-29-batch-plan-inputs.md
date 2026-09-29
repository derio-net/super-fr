# Journal: 2026-09-29-batch-plan-inputs

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-29T11:09:46+00:00 -->
### repro · repro · take 10 (#817): stray 'none.', question-worded unobservable message on reviewer gate, scratch .records/ yaml refused as 'must be migrated', unexplained tier: hard

Members #813 #812 #815, fr 4.35.0 on OpenCode + GitLab. See the issues for transcripts.

<!-- fr:journal kind=root-cause scope=debug id=rc-815-none created=2026-09-29T11:09:46+00:00 -->
### rc-815-none · root-cause · proportionality asks section: _bullets([]) returns ['none.'] when every phase has its own ask

packages/fr/src/fr/proportionality.py:222 reuses _bullets, whose empty sentinel suits list sections but dangles after the count line.

<!-- fr:journal kind=root-cause scope=debug id=rc-815-unobservable created=2026-09-29T11:09:47+00:00 -->
### rc-815-unobservable · root-cause · _why_unobservable() is gate-agnostic and hard-codes 'questions'

run_cmd.py:242; called by the operator-gate (:1233) and the reviewer gate (:2254).

<!-- fr:journal kind=root-cause scope=debug id=rc-812-records created=2026-09-29T11:09:48+00:00 -->
### rc-812-records · root-cause · record locator claims every *.records/*.yaml; trigger words an unreadable artifact as 'must be migrated'; fr-plan names no scratch home

registry.py:444 locator; trigger.py:581 _will_not_act_here shared wording; skills/fr-plan/SKILL.md.

<!-- fr:journal kind=root-cause scope=debug id=rc-813-tier created=2026-09-29T11:09:49+00:00 -->
### rc-813-tier · root-cause · fr-plan lists tiers without criteria and self-review asks no reason for tier above standard

skills/fr-plan/SKILL.md:80. A policy gap, not a code defect.

# Journal: 2026-09-29-batch-plan-inputs

<!-- fr:journal kind=repro scope=debug id=repro created=2026-09-29T11:09:46+00:00 -->
### repro · repro · take 10 (#817): stray 'none.', question-worded unobservable message on reviewer gate, scratch .records/ yaml refused as 'must be migrated', unexplained tier: hard

Members #813 #812 #815, fr 4.35.0 on OpenCode + GitLab. See the issues for transcripts.

<!-- fr:journal kind=root-cause scope=debug id=rc-815-none created=2026-09-29T11:09:46+00:00 -->
### rc-815-none · root-cause · proportionality asks section: _bullets([]) returns ['none.'] when every phase has its own ask

packages/fr/src/fr/proportionality.py:222 reuses _bullets, whose empty sentinel suits list sections but dangles after the count line.

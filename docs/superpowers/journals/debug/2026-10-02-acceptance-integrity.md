# Journal: 2026-10-02-acceptance-integrity

<!-- fr:journal kind=repro scope=debug id=7450e8a5efc5 created=2026-10-02T17:38:25+00:00 -->
### 7450e8a5efc5 · repro · #470: insert_row emits an invalid matrix when rows are flush-left

Reproduced in-process: a matrix whose `rows:` items are flush-left (`- id:`, PyYAML's default dump) fails `yaml.safe_load` after `fr.acceptance.edit.insert_row` — on BOTH paths (same-capability insert and new-capability append). `render_row_block` unconditionally prefixes every line with two spaces, so the new item is indented deeper than its siblings and parses as a continuation of the previous row's mapping.

<!-- fr:journal kind=hypothesis scope=debug id=2bd438baedc7 created=2026-10-02T17:38:27+00:00 -->
### 2bd438baedc7 · hypothesis · The batch does not share one root cause

Investigation of the 8 members finds at least five independent causes, each in a different place: (1) #470 render_row_block hardcodes a 2-space item indent (edit.py); (2) #531 split_ref carries the #L fragment through and check.py strips it for existence only — no anchor validation exists; (3) #769 set_status_cmd's commit subject is always '{old} → {new}' (acceptance_cmd.py:486); (4) #655 record engine _check_drops never compares drops against additions, while the CLI does (acceptance_cmd.py:443); (5) #654/#656 wording + missing test on _refuse_unknown_levels/merge_levels; (6) #663/#676 are matrix-data chores, not code. They share a SURFACE (the acceptance edit helpers), not a cause. Per the brief's debugging rule, stopping to ask before fixing any.

# Journal: 2026-09-27-spec-ref-followups

<!-- fr:journal kind=repro scope=debug id=4e183a611430 created=2026-09-27T19:28:36+00:00 -->
### 4e183a611430 · repro · Two red tests pin #749 and #750

test_repair_does_not_warn_ambiguous_about_a_ref_it_keeps_verbatim: repair on a plan whose spec: is ../sibling/docs/superpowers/specs/x-design.md, with x-design.md in both specs/ and implemented/specs/, leaves the file byte-identical but warns 'ambiguous — resolved to the active one'. test_canonical_spec_ref_escape_test_reads_the_path_token: canonical_spec_ref on a backtick-annotated escaping ref returns 'x-design.md' (the local same-slug spec) instead of the value verbatim.

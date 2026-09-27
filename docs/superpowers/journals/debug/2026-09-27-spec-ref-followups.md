# Journal: 2026-09-27-spec-ref-followups

<!-- fr:journal kind=repro scope=debug id=4e183a611430 created=2026-09-27T19:28:36+00:00 -->
### 4e183a611430 · repro · Two red tests pin #749 and #750

test_repair_does_not_warn_ambiguous_about_a_ref_it_keeps_verbatim: repair on a plan whose spec: is ../sibling/docs/superpowers/specs/x-design.md, with x-design.md in both specs/ and implemented/specs/, leaves the file byte-identical but warns 'ambiguous — resolved to the active one'. test_canonical_spec_ref_escape_test_reads_the_path_token: canonical_spec_ref on a backtick-annotated escaping ref returns 'x-design.md' (the local same-slug spec) instead of the value verbatim.

<!-- fr:journal kind=root-cause scope=debug id=c285b0ef7bd0 created=2026-09-27T19:28:38+00:00 -->
### c285b0ef7bd0 · root-cause · The verbatim decision lives inside canonical_spec_ref and reads the raw value

canonical_spec_ref decides verbatim-vs-rewrite inline, so (a) repair._repair_meta cannot ask for that decision and warns about ambiguity from resolve_spec_ref before canonical_spec_ref keeps the ref verbatim (#749); (b) the lexical escape test and the outside-SPEC_ROOTS file test join the RAW value onto repo_root, while resolution goes through refs._token — so the escape test treats the leading backtick as part of a directory name ('`..' is a plain name, not a parent step) and judges the ref in-repo, while resolution strips it and finds the local same-slug spec (#750). One cause: the decision is not a named predicate over the extracted path token.

<!-- fr:journal kind=finding scope=debug id=fix-verbatim-predicate created=2026-09-27T19:39:48+00:00 state=fixed -->
### fix-verbatim-predicate · finding [fixed] · Name the verbatim decision as refs.keeps_spec_ref_verbatim, over the path token

refs.keeps_spec_ref_verbatim holds the four verbatim tests (cross-repo, lexical escape, unresolved, existing file outside SPEC_ROOTS), each reading refs._token(value) — the same token resolution reads. canonical_spec_ref delegates to it; repair._repair_meta asks it before _warn_ambiguous and skips a verbatim spec: ref. Pinned by test_repair_does_not_warn_ambiguous_about_a_ref_it_keeps_verbatim (#749) and test_canonical_spec_ref_escape_test_reads_the_path_token (#750). archive.py untouched.

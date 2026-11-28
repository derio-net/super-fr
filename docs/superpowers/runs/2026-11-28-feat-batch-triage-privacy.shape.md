```
packages/fr/src/fr/triage/
  admit.py            ~ canonical_comment: login lowercased, [bot] stripped, "" → ghost; UTC
                        %Y-%m-%dT%H:%M:%SZ or ""; id or -1                                     R1
                      + pinned(comment, pr_authors): not OWNER/MEMBER/COLLABORATOR and not a
                        pr_author → pinned (the viewer is not exempt)                          R1
                      ~ content_digest(title, body, *, comments, pinned_authors): sha256 over
                        json {"v":2,title,body,comments:[[login,time,id,body]…]} sorted       R1
                      ~ parse_admit: v == 2 only; v1 / malformed → None → no-marker reason     R2
                      ~ admit_marker human line names outside comments                         R3
  admit_recheck.py    + live_admission: issue + comments read live, digest with the repo's
                        pr_authors                                                             R3 R5
                      ~ recheck_admitted: comment read fails → dispatch refused (fail closed)  R5
  collect.py          ~ _comment_facts: content_digest from the comments read for admission,
                        None when unread                                                       R4
                      + _withhold_untrusted_pr_titles: prs, gated_prs, batch_prs, judged_prs,
                        issue.prs; kept only for claim_trusted(config_for(pr.repo), viewer)    R6
                      ~ finished_prs: MERGED, or CLOSED while the repo's open-PR list was not
                        cut at pr_limit; else view again (counted in viewed)                   R10
  model.py            ~ FACTS_SCHEMA 21 → 22; load < 22: admit_read False, withhold text and
                        PR titles again                                                        R4 R6
  privacy.py          + repo_patterns: owner/name[.git] | name#\d+ (skipped when a public
                        look-for repo shares the name), (?<![\w.-]) … (?![\w-])(?!\.\w), ci   R8
                      + carried_text_leaks · carried_files (REF_FILES walk) · durable_files
                        (state_sync durable set) · refusal_file (file, repo, remedy; no text)   R8
                      ~ guard_state(…, carried=): public state repo and a non-public look-for
                        repo → scan; unreadable file refuses; org scope with no facts →
                        VisibilityUnreadable naming `fr triage collect`                        R8 R9
  render.py · kanban_render.py ~ PR cards/lines: key, URL, "title withheld"                    R7
packages/fr/src/fr/commands/
  triage_admit_cmd.py ~ preview lists pinned comments in the untrusted block (visible chars,
                        hidden-char warning); --yes --digest re-reads; read failure → exit 2
                        before any write                                                       R3
  triage_cmd.py       ~ check text: key, URL, "title withheld" (JSON: empty title)             R7
  triage_batch_cmd.py ~ dispatch_batch → recheck_admitted; squash subject pr.title or
                        batch.title                                                            R5 R7
  triage_state_cmd.py ~ export: guard_state(carried=durable_files(...))                        R8
tests/unit/ test_triage_{admit,collect,collect_carry,collect_partial,batch_dispatch,privacy,
            pr_title_withheld,model,lane_owners}.py · scenario fixtures → facts schema 22
docs/explainers/fr-triage.md · skills/fr-triage/SKILL.md (+ mirrors) · .changes/ minor fragment
```

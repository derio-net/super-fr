```
scripts/
  install.sh          ~ warn(): stderr + warnings file (subshell-safe); all 17 WARNING sites   R2
                      ~ fr models apply: stderr captured; non-zero → WARNING with exit code,
                        ≤12 lines + "… N more lines", remedy; exit 0 → stderr passed through   R1
                      ~ closing block: "fr version: …" | "fr: not on PATH" | "unknown (…)",
                        then "Warnings (N):" + each, or "No warnings."                           R2
                      ~ cleanup_tmps (EXIT): rm both temp files; on failure repeat warnings,
                        "install.sh failed (exit n)" stays last                                  R2
  bootstrap.sh        ~ channel_tags: ls-remote status kept → "ERROR: could not list release tags" R3
                      ~ installable_tags: ls-tree (absent → skip) · show (fail → ERROR naming
                        tag + git's message) · marker via here-string, no pipe                    R3 R4
                      ~ INSTALLABLE computed once, checked, on non-main paths only               R3
packages/fr/src/fr/
  forge_body.py       + CONTROL, read_failure(url, exc): url and reason redacted (lazy import),
                        control/bidi stripped, first line, bounded                               R5 R6
  run/adopt.py        ~ default_pr_state(warn=) · adopt_run(warn=) forwards it                   R5
  commands/run_cmd.py ~ adopt_cmd: warn → stderr                                                 R5
  commands/migrate_cmd.py ~ adoption loop: warn → stderr                                         R5
  commands/push_cmd.py~ refuse_closed_pr: prints read_failure, then fails open                   R6
  debt/render.py      ~ source_category: fullmatch on the exception's message (DOTALL) →
                        "not supported on <backend> (<issue>)" | "not supported by this forge"   R7
  commands/debt_cmd.py~ issue_cmd: "unavailable: <source>: <reason>" on stderr; _CONTROL from
                        forge_body                                                               R8
tests/  integration/test_install_{opencode_agents,channels}.py · unit/test_{forge_body,run_adopt,
        git_policy_push,debt_render,debt_engine,debt_issue}.py
docs/reference/install.md ~ closing warnings, unreadable-tag stop · .changes/ patch fragment
```

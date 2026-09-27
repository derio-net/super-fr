# Journal: 2026-09-27-triage-theme-comparison

<!-- fr:journal kind=repro scope=debug id=896bfdeaabc8 created=2026-09-27T08:59:06+00:00 -->
### 896bfdeaabc8 · repro · Theme spellings 'Docs'/'docs '/'docs' treated as distinct themes

super-fr#724. A debug batch whose members' judgements carry theme 'Docs' and 'docs ' makes `fr triage batch create --skill debug` print the mixed-themes one-root-cause warning, and `fr triage batch suggest` splits those issues into separate theme suggestions (or drops them when each spelling has one member). Repro: judgements.yaml with two open issues, themes 'Docs' and 'docs', then `fr triage batch suggest` — no theme suggestion is printed.

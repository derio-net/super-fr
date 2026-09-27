# Journal: 2026-09-27-triage-theme-comparison

<!-- fr:journal kind=repro scope=debug id=896bfdeaabc8 created=2026-09-27T08:59:06+00:00 -->
### 896bfdeaabc8 · repro · Theme spellings 'Docs'/'docs '/'docs' treated as distinct themes

super-fr#724. A debug batch whose members' judgements carry theme 'Docs' and 'docs ' makes `fr triage batch create --skill debug` print the mixed-themes one-root-cause warning, and `fr triage batch suggest` splits those issues into separate theme suggestions (or drops them when each spelling has one member). Repro: judgements.yaml with two open issues, themes 'Docs' and 'docs', then `fr triage batch suggest` — no theme suggestion is printed.

<!-- fr:journal kind=root-cause scope=debug id=ffaa13acf4bf created=2026-09-27T08:59:07+00:00 -->
### ffaa13acf4bf · root-cause · Judgement.theme is free text compared as a raw string in both callers

`mixed_themes` (packages/fr/src/fr/triage/batch.py:392) builds a set of raw `theme` values, and `suggest` (batch.py:481-484) keys a dict on the raw `theme`. Neither normalises case or surrounding whitespace, so spellings the author means as one theme compare unequal. The same cause explains both symptoms, so this is one root cause, as the batch assumed. A whitespace-only theme also counts as a real theme in `suggest` (it is truthy).

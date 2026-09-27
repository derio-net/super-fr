# Journal: 2026-09-27-triage-theme-comparison

<!-- fr:journal kind=repro scope=debug id=896bfdeaabc8 created=2026-09-27T08:59:06+00:00 -->
### 896bfdeaabc8 · repro · Theme spellings 'Docs'/'docs '/'docs' treated as distinct themes

super-fr#724. A debug batch whose members' judgements carry theme 'Docs' and 'docs ' makes `fr triage batch create --skill debug` print the mixed-themes one-root-cause warning, and `fr triage batch suggest` splits those issues into separate theme suggestions (or drops them when each spelling has one member). Repro: judgements.yaml with two open issues, themes 'Docs' and 'docs', then `fr triage batch suggest` — no theme suggestion is printed.

<!-- fr:journal kind=root-cause scope=debug id=ffaa13acf4bf created=2026-09-27T08:59:07+00:00 -->
### ffaa13acf4bf · root-cause · Judgement.theme is free text compared as a raw string in both callers

`mixed_themes` (packages/fr/src/fr/triage/batch.py:392) builds a set of raw `theme` values, and `suggest` (batch.py:481-484) keys a dict on the raw `theme`. Neither normalises case or surrounding whitespace, so spellings the author means as one theme compare unequal. The same cause explains both symptoms, so this is one root cause, as the batch assumed. A whitespace-only theme also counts as a real theme in `suggest` (it is truthy).

<!-- fr:journal kind=finding scope=debug id=theme-key created=2026-09-27T09:06:58+00:00 state=fixed -->
### theme-key · finding [fixed] · theme_key is the one theme comparison point; mixed_themes and suggest group through it

packages/fr/src/fr/triage/batch.py: `theme_key` (strip + casefold) and `_by_theme` (groups keys by it, sorted by key, blank themes dropped, first member's stored spelling shown). Red first: test_mixed_themes_treats_one_theme_spelled_two_ways_as_one, test_mixed_themes_keeps_the_stored_spelling_and_ignores_blank_themes, test_suggest_groups_one_theme_spelled_several_ways failed on assertions with theme_key present but unwired; all pass now, full suite 6569 passed. Side effect caught by the red test: a whitespace-only theme used to form its own suggestion group.

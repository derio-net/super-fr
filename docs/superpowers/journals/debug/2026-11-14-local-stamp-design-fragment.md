<!-- fr:journal-schema=4 -->
# Journal: 2026-11-14-local-stamp-design-fragment

<!-- fr:journal kind=repro scope=debug id=repro-1 created=2026-11-14T19:05:28+00:00 -->
### repro-1 · repro · deliver passes with local rows unstamped when the feature fragment is <slug>-design.yaml (gh#1456)

Stealth walk on 7.0.0-rc.8: fr run resolve --step deliver passed; fr acceptance status then lists the feature's rows [local, unstamped]. The fragment was created by rc.3, before #1451, as <slug>-design.yaml.

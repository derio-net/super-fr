# Journal: 2026-09-19-presentation-v2

<!-- fr:journal kind=decision scope=spec id=v2-spine-not-catalogue created=2026-09-19T16:28:36 -->
### v2-spine-not-catalogue · decision · The recorded run is the spine; the four angles annotate it

v1 failed by growing outward from the subject (14 upgrades in build order). Four angles x N upgrades would reproduce that in tidier buckets. Instead one real /fr-goal run carries the narrative and each angle attaches to the moment where it is visible. Consequence: the angles are not peers -- Security bookends, Quality and Continuity interleave, Extensibility surfaces once -- and that ranking matches what an audience whose next action is 'one issue tomorrow' actually needs.

<!-- fr:journal kind=finding scope=spec id=v2-unshipped-extensibility-claims created=2026-09-19T16:28:55 state=open -->
### v2-unshipped-extensibility-claims · finding [open] · Three Extensibility items are not operator-reachable and must not be claimed

Verified against docs/acceptance/matrix.yaml 2026-09-19. multi-repo-spec-fanout: not-implemented, 'fake-runner-only and operator-unobservable'. dispatch-unit-declared-by-shape: not-implemented, only unit:phase is reachable through a shipped path. GitLab/Gitea adapters: unit-verified and reachable from fr apply, but 'not yet proven against a live instance'. The talk promises 'use it immediately', so the first claim that fails when a listener tries it destroys the promise. Coda is restricted to phase executors, model tiers, and the three harnesses. Resolve when either the rows flip or the coda copy is written excluding them.

<!-- fr:journal kind=decision scope=spec id=v2-public-source-private-render created=2026-09-19T16:28:55 -->
### v2-public-source-private-render · decision · Deck source is public and generic; the rendered deck is private

Two separable problems. Repo hygiene: the internal repo is never named here, assets live outside the repo behind a manifest. Content exposure: the real leak is code on screen (file contents, function names, domain) which no gitignore fixes and which sed over a cast cannot reliably redact -- a name can split across write boundaries amid escape sequences. Resolved by scope, not by tooling: the rendered deck is internal-only. The build fails loudly on a missing manifest asset so a checkout without the private assets cannot silently render an incomplete deck. Carries forward v1's constraint that the authoring session is not cleared for the operator's board.

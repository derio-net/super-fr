# Multi-backend git-host adapters: GitLab + Gitea support

Spec: `docs/superpowers/specs/2026-07-09-multi-backend-git-host-adapters-design.md`

## Why

`fr` only speaks GitHub today, and the coupling is deeper than the one
`GhClient` seam it was designed around — fr-vk's bridge bypasses it with raw
`gh` subprocess calls in two places, the isolation lifecycle has its own
separate `gh` calls through the `Runner` callable, fr-dispatch's agent prompts
hardcode GitHub wording, and `fr` writes GitHub-only artifacts (devcontainer
feature, CI workflow template) into every repo it scaffolds. This plan adds
GitLab (`glab`) and Gitea (`tea`) as first-class backends reaching every one
of those surfaces, per the operator's "full pipeline" scope decision.
Bitbucket is explicitly out of scope (no official CLI, no Data Center issue
tracker, a deprecated Cloud Issue-Tracker REST API — see the spec's research).

## Shape of the change

Two new CLI-wrapper packages inside `fr` (`fr/glab.py` + `fr/real_glabclient.py`,
`fr/tea.py` + `fr/real_teaclient.py`), structured to mirror `fr/gh.py` +
`fr/real_ghclient.py` exactly so a reviewer can diff the three. The existing
`GhClient` Protocol stays named `GhClient` (it's already backend-neutral in
shape; renaming ~30 import sites buys nothing). A new `fr._hosts` module
resolves which backend a repo uses (explicit config, falling back to a
git-remote-hostname heuristic, falling back to "github" — today's only
behavior, unchanged for every repo that configures nothing), and a new
`fr.hostclient.client_for()` factory is the one place that turns "which
backend" into "which client instance," replacing every hardcoded
`RealGhClient()` construction.

## Phase order and why

1. **Foundation** — backend detection + config schema + cross-backend URL
   parsing. Everything else depends on this; it's pure refactor + one new
   small module, lowest risk, unblocks phases 2 and 3 in parallel conceptually
   (sequenced 2-then-3 here since dependencies are backward-only by number).
2. **GitLab adapter**, 3. **Gitea adapter** — independent of each other,
   both depend only on Phase 1.
4. **Host-client factory + `pr_status_by_url` + CLI wiring** — needs all
   three adapters to exist so the factory has something to dispatch to. This
   is also where `fr apply` becomes genuinely usable against a GitLab/Gitea
   repo — the two tracking-capability acceptance rows land here.
5. **fr-vk bypass fixes** — depends on Phase 4's factory + `pr_status_by_url`.
   Also consolidates fr-vk's five duplicated card-title regexes into one
   shared parser/builder (`fr_vk/_cardref.py`) while touching those same three
   files anyway — a from Family A "same bug class, five copies" the original
   research pass flagged, folded in here rather than deferred.
6. **fr-dispatch prompt genericization** — only depends on Phase 1 (the
   backend/tag vocabulary). Includes a regression test proving
   `fr_dispatch.tick()`'s label-stamp calls needed *zero* code change (they
   already run through the injected `GhClient` parameter) — a correction to
   the original research pass worth locking in as a test, not just a spec
   sentence.
7. **Isolation lifecycle genericization** — depends on 1 (detection) and 2/3
   (needs to know the glab/tea command shapes). This is the *second* seam
   (the `Runner` callable, deliberately separate from `GhClient`) — kept
   separate here too, per the spec's explicit reasoning, rather than merged.
8. **Scaffold backend-awareness + docs** — devcontainer CLI-install step,
   acceptance-report CI template (two genuinely different shapes: Gitea
   Actions reuses GitHub's YAML schema in a different directory; GitLab CI is
   a different schema entirely), the fr-init interview question, and README
   updates. Last agentic phase — by now every backend actually works, so docs
   describe shipped behavior, not aspiration.
9. **[manual] Real-CLI verification** — back-loaded, blocks nothing before
   it. Fakes and documented JSON shapes prove our shaping logic is internally
   consistent; they cannot prove `glab`/`tea`'s real binaries emit what we
   assumed. The PR ships with this phase deliberately unimplemented; whoever
   has (or sets up) GitLab/Gitea credentials runs it and records the outcome
   directly in `09.yaml` via `fr plan edit --tick ... --note`.

## Acceptance linkage

- `multibackend-gitlab-tracking`, `multibackend-gitea-tracking` -> Phase 4
- `multibackend-vk-dispatch` -> Phase 5
- `multibackend-isolation-lifecycle` -> Phase 7
- `multibackend-scaffold` -> Phase 8

## Non-goals (see spec for the full reasoning)

Bitbucket; renaming `GhClient`; unifying CI/pipeline status vocabularies
beyond fr's existing 4-value contract; anything about GitHub Enterprise
Server beyond what the `host:` config key already threads through.

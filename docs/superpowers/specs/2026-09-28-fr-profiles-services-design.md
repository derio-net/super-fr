# fr-profiles services — forge, ci and tracking as `{type, host}` (#774 step 1)

**Date:** 2026-09-28
**Issue:** derio-net/super-fr#774 (step 1 of 2; step 2, the Jenkins and Jira
adapters, the cross-forge tracker and per-service credentials, is filed as
derio-net/super-fr#795, linked from #774)
**Builds on:** #787 (gh#775, `fr.acceptance.ci.ci_config`), merged as 7e154122
**Run:** `2026-09-28-feat-batch-service-split-2`

## Requirements

| id | requirement | source |
|---|---|---|
| R1 | `.devcontainer/fr-profiles.yaml` declares three nested services, `forge`, `ci` and `tracking`, each a mapping with its own `type` and optional `host` (type-specific keys kept beside them). Valid types in step 1: forge `github`/`gitlab`/`gitea`; ci `none`/`github-actions`/`gitlab-ci`/`gitea-actions`; tracking `none` or the forge's own type. `jenkins` and `jira` are refused with a message naming the follow-up issue. | input "the forge / ci / tracking schema ({type, host} each)"<br>input "**Nested rather than flat keys** (`forge_type`, `forge_host`, …): each service keeps its type-specific settings together"<br>decision q4-no-adapter |
| R2 | An undeclared `ci` or `tracking` resolves to the forge's own (`gitlab` → `gitlab-ci` / `gitlab`); a service's `host` defaults to the forge host when its type is the forge's own and is required otherwise. Every forge consumer (`detect_backend`, `host_for`, `client_for`) resolves through the `forge` service with today's behaviour. | input "defaults derived from today's backend: key"<br>input "`host` defaults to the forge host when the type is the forge's own, and is required otherwise."<br>decision q1-defaults |
| R3 | fr-profiles is a registered artifact kind (`profiles`, version 2). The CLI-entry gate migrates a version-1 file (top-level `backend:`/`host:`) to the nested shape at the first fr command, with the gate's usual refusals; the migration writes `forge` from the old keys, `ci` as detected (§3.C) and `tracking` as the forge's own. A structure validator fails closed on an unknown type, a missing required host, or a leftover top-level `backend:`/`host:`. | decision q1-defaults<br>decision q3-shape<br>decision q9-migration<br>decision r2q1-blast-radius<br>decision r2q2-migrated-ci |
| R4 | `fr acceptance init` and the `ci` acceptance status follow the declared `ci` service: `type: none` scaffolds no pipeline and refuses a move into `ci`; a pipeline type scaffolds that type's template and allows `ci`. | input "acceptance init / the ci status following the declared ci service (building on acceptance-init-no-ci, #775)"<br>decision q2-base-787 |
| R5 | Under `ci: {type: none}`, fr-goal's Ready checklist reads "local suite green (evidence: <log>)" instead of "CI green", and fr-goal / fr-acceptance say the local suite is the gate. | input "deliver doesn't wait for or cite a pipeline, and the skills say \"the local suite is the gate\"."<br>decision q7-no-ci-delivery |
| R6 | Under `tracking: {type: none}`: out-of-scope findings stay `out-of-scope` (journal, PR body, closeout hand-off); the closeout brief prints no "open an issue" / `deferred --tracked-by` lines; `fr apply --yes` and `fr triage batch dispatch` refuse naming `tracking: none`; the scaffolded acceptance pipeline omits the weekly debt-issue step; no skill tells an agent to file an issue. | input "switches off every issue path: out-of-scope findings go into the run's journal, the PR body and the closeout hand-off instead of a tracker, and no skill tells an agent to file an issue."<br>decision q5-no-tracker-findings<br>decision q6-issue-cmds |
| R7 | `fr services` (read-only, `--json`) prints each resolved service with its type, host and source (`declared`, `default`, or `legacy` for an unmigrated file); it is in `READ_ONLY_COMMANDS`. | decision q8-surface |
| R8 | `fr init scaffold` writes the nested shape and gains `--ci` / `--tracking` (`auto` by default). `auto` detects each service; when detection is inconclusive the command refuses with the flag to pass, and the fr-init skill asks the operator. | decision r2q3-init-flags |

## Deferred from input

| input | reason |
|---|---|
| "The Jenkins and Jira adapters. A large piece of work, but it's the shape a company on Jira + Jenkins + GitLab needs." | Step 2 of #774; filed as a follow-up issue linked from #774 before this PR merges (brief's delivery rule). |
| "- the top-level `backend:` + `host:` stay as shorthand for `forge`;" | Superseded by decision q3-shape: the shorthand is migrated to `forge:` at the first fr command rather than kept (R3). |
| "Each service allows `type: none`." | Step 1 scopes `none` to ci and tracking, as the brief does ("type: none for ci and tracking"); a repo always has a forge for fr to work against, so `forge: none` is not part of this change. |
| "Credentials stay out of the file: per service, the env var name the devcontainer profile's secrets provide." | Only an adapter that calls a non-forge service needs a credentials key; step 1 adds none, so the key arrives with the adapters. |

## Design

### 3.A The shape

```yaml
schema_version: 2
profiles: {...}          # unchanged
default: dev             # unchanged
forge:
  type: gitlab           # github | gitlab | gitea
  host: gitlab.example.com
ci:
  type: none             # none | github-actions | gitlab-ci | gitea-actions
tracking:
  type: gitlab           # none | <forge.type>   (step 1)
```

Model: `fr/services/model.py` — `ForgeService`, `CiService`, `TrackingService`
(pydantic, `extra="allow"` so type-specific keys such as a future `job:` or
`project:` round-trip untouched), and `Services(forge, ci, tracking)` where each
resolved value carries `source: declared | default | legacy`.

Why tracking is limited to `none` or the forge's own type in step 1: fr files
issues through the forge client (`apply.py:76`, `hostclient.client_for`). A
GitLab tracker behind a GitHub forge would need issue creation routed through a
separate tracker client, which is exactly the adapter seam step 2 builds. ci
has no such limit: a pipeline type only selects a template file and allows the
`ci` status, so a GitLab-CI mirror of a GitHub repo is already expressible.

Refusal messages for `jenkins` / `jira` (and a cross-forge tracker) name
derio-net/super-fr#795, the follow-up, so the reader learns where the work
lives.

### 3.B Resolution — `fr/services/resolve.py`

`resolve_services(repo_root) -> Services` is the only reader of the three
services; `profiles_config` stays the raw reader it is.

1. **forge** — `forge.type`/`forge.host` when declared; else, for a version-1
   file, `backend:`/`host:` (`source: legacy`); else today's origin-hostname
   inference and `github` fallback (`source: default`).
2. **ci** — declared; else, for a version-1 file, the migration's own
   detection (§3.C, fr's scaffold discounted — `source: legacy`), so `fr
   services` shows the same value before and after the migration; else the
   forge's own pipeline type **if** `fr.acceptance.ci.ci_config` finds a CI
   config, else `none` (`source: default`). The last branch is #787's
   behaviour unchanged, and after the migration it is reached only by a repo
   with no fr-profiles.yaml at all. It keeps the raw probe (no discount) so
   `fr acceptance init --with-ci` there still yields a repo whose `ci` status
   is allowed, exactly as #787 shipped it.
3. **tracking** — declared, else the forge's own type.
4. **host** — declared, else the forge host when the type is the forge's own;
   a non-native type with no host is a validation error (§3.D).

A version-1 file is still READ (`source: legacy`): the read-only commands
(`isolation`, `status`, `services`, …) are exempt from the migration gate and
must keep working on an unmigrated repo. Reading the old shape is not keeping
it as a feature — nothing writes it, and the validator refuses it at version 2.

`fr._hosts.detect_backend`, `declared_host` and `host_for` become thin
wrappers over `resolve_services(...).forge` — `declared_host` returns
`forge.host` when its source is `declared` or `legacy` and None otherwise, so
`client_for`'s declared-host warning (`hostclient.py:125`, gh#486) keeps its
provenance after the migration removes the top-level `host:` (signatures unchanged, so every caller the
explorer mapped — `hostclient.py:66,124`, `isolation/local.py:1286,2599,2754`,
`acceptance_cmd.py` — is untouched). `backend_for_url` is URL-driven and stays
as is.

`fr.acceptance.ci` (#787's seam) gains `ci_active(root) -> CiService` answered
by the resolver; `ci_config` stays as the disk probe the resolver and the
migration both use. `SCAFFOLD_PATHS` / the templates are re-keyed from forge
backend to ci type (`github-actions`, `gitea-actions`, `gitlab-ci`).

### 3.C Detection — what "has CI" means offline

Before #787, `fr acceptance init` scaffolded a pipeline regardless of whether
the repo had CI (operator, answering r2q2: "aren't ci configs created regardless
so far? If so, how can the migration know if the config is active?"). So a CI
file's presence alone is weak evidence. The migration (and `fr init --ci auto`)
therefore discounts the one case fr itself caused:

- **GitHub / Gitea**: the workflows directory's only YAML file is
  `acceptance-report.yml` → fr's own scaffold, not CI.
- **GitLab**: `.gitlab-ci.yml` whose only job key is `acceptance-report` (no
  `include:`, which could pull real jobs) → fr's own scaffold, not CI.

Anything else found by `ci_config` counts as CI. Whether pipelines actually
*run* is knowable only from the forge; the migration never calls the network
(it runs at the CLI-entry gate, often offline or in a pod). The residual risk —
a project whose real CI is solely fr's acceptance job — migrates to `ci: none`,
and is fixed with a one-line edit; `fr services` shows it.

`fr init scaffold --ci auto` uses the same offline test, and treats "only fr's
own scaffold" as **inconclusive** (refuse, name `--ci`). `--tracking auto`
asks the forge whether issues are enabled (new `issues_enabled() -> bool |
None` on the gh / glab clients; tea returns None): enabled → forge's own,
disabled → `none`, unknown → inconclusive. The fr-init skill turns an
inconclusive refusal into a question to the operator (r2q3).

### 3.D Artifact kind, migration, validator

Per `.claude/rules/artifact-versioning.md`, in one PR:

1. **Kind** `profiles` in `fr/artifacts/registry.py`: `locator=".devcontainer/fr-profiles.yaml"`,
   `current_version=2`, stamp `schema_version` (top-level yaml key, the shared
   `_read_yaml_stamp`/`_write_yaml_stamp`). An unstamped file reads as
   `PRE_FRAMEWORK_VERSION` (1), i.e. the flat shape.
2. **Frozen legacy reader** `fr/services/legacy.py`: `ProfilesV1` (closed-world
   over the keys a v1 file carries — `profiles`, `default`, `backend`, `host`),
   vocabulary inlined, source pinned by `FROZEN_CLASS_SHA256`. The migration and
   the resolver's legacy branch read v1 only through it. A v1 file with keys it
   does not know is refused (per-artifact failure, file byte-identical) rather
   than guessed at.
3. **SchemaMigration 1 → 2** `fr/artifacts/profiles_services.py`, imported by
   `fr/artifacts/__init__.py`: builds the new body in memory — drops the
   top-level `backend:`/`host:` lines, appends `forge:` (type from `backend`,
   else origin inference; `host` when declared), `ci:` (§3.C) and `tracking:`
   (forge's own) — and writes once through `write_text_atomic`. Every other
   line (profiles, comments, ordering) is kept byte-for-byte. It recognises a
   body already wholly in the v2 shape (crash window) and lets the runner stamp.
4. **Validator** `validate_profiles` in `fr/artifacts/structure.py` (reached by
   `ArtifactKind.validate`, run by `fr validate artifacts`): unknown or refused
   type, missing required host, a top-level `backend:`/`host:` at version 2, a
   duplicate key (the shared strict loader).

Entry-gate behaviour is unchanged (r2q1): on the default branch and in
non-interactive contexts it refuses and prints `fr migrate artifacts --yes`.
This repo's own `.devcontainer/fr-profiles.yaml` is migrated in this PR by
running that command, never by hand.

**Stated risk:** an `fr` older than this release reading a migrated file finds
no `backend:` and falls back to origin inference — correct for SaaS hosts,
wrong for a self-hosted GitLab/Gitea. Lockstep install (one plugin version per
machine) is the mitigation; the release note says so.

### 3.E Consumers

| consumer | today | after |
|---|---|---|
| `acceptance/scaffold.init` | `ci_config(root, backend)` / `--with-ci` | `ci_active(root)`: `none` → no pipeline + notice naming `fr services`; pipeline type → that type's template. `--with-ci` never writes fr-profiles.yaml: with a declared `ci: {type: none}` it refuses (the declaration wins, and the message says to change it); with no fr-profiles.yaml it scaffolds as #787 shipped. |
| `record/apply._no_ci_reason` | disk probe | `ci_active(root).type == "none"` → refuse a move into `ci`, message naming `ci: {type: none}` |
| scaffolded pipeline's debt-issue step (and the rule template's CI bullet that promises it, `scaffold.py:360-366`) | always | kept only when the tracking type is the ci type's own platform (`github-actions`↔`github`, `gitlab-ci`↔`gitlab`, `gitea-actions`↔`gitea`); omitted, with a notice, under `tracking: none` or a ci on another platform — the pipeline never files issues on a system that is not the tracker |
| `run/closeout.py:93,192-200` | "file an issue for each out-of-scope finding" | under `tracking: none`: "out-of-scope findings stay recorded in the journal and PR body; no tracker is configured" and no `deferred --tracked-by` lines |
| `fr apply --yes` / `fr triage batch dispatch` | create issues / comments | refuse, exit 2, naming `tracking: {type: none}` in `.devcontainer/fr-profiles.yaml` |
| `fr triage collect` | reads the forge | unchanged (reads, never files) |

### 3.E.1 `fr init scaffold` and the gate

`init` is in `READ_ONLY_COMMANDS` (`trigger.py:77-86`), so the gate never runs
before it. `fr init scaffold` therefore owns the profiles file's version
itself: on an existing version-1 file it runs the same 1 → 2 migration
function in process first (a v1 file it cannot migrate is refused, untouched),
then merges its keys into the nested shape, and it always writes
`schema_version: 2`. `init` stays exempt; the tuple's docstring and the pinned
exemption test are updated in the same diff to say that `init` writes only the
fr-profiles artifact, always at its current version, never a stale one.

### 3.F `fr services`

`commands/services_cmd.py`, registered as `fr services`. Plain output:

```
forge     gitlab          gitlab.example.com   declared
ci        none            —                    declared
tracking  gitlab          gitlab.example.com   default (forge's own)
```

`--json` emits the same as an object keyed by service. Added to
`fr.artifacts.trigger.READ_ONLY_COMMANDS` (it reads, never writes an
artifact), with the pinned exemption test updated in the same diff.

### 3.G Skills and docs

- `fr-goal`: the Ready checklist and closeout prose branch on `fr services`
  (ci none → "local suite green (evidence: <log>)"; tracking none → no issue
  filing, findings stay out-of-scope).
- `fr-acceptance`: "the local suite is the gate" under `ci: none`; the `ci`
  status needs a declared or detected CI service.
- `fr-goal`, every passage that assumes CI or an issue tracker, each branched
  on `fr services`: the walking skeleton's "CI green on a trivial test"
  (ci none → the local suite on a trivial test), the review-resolution
  `deferred --tracked-by <issue>` guidance (tracking none → leave it
  `out-of-scope`), the Ready checklist, and the closeout's "open the issue"
  step. A prose test pins each branch's wording.
- `fr-init`: interview asks ci / tracking when `--ci/--tracking auto` refuses
  as inconclusive; documents the nested shape.
- `README.md` backend/host section rewritten for the services; explainers
  checked per `explainers-currency.md`.
- Mirrors regenerated with BOTH `sync-opencode.py` and `sync-hermes.py`.
- Change fragment `.changes/feat-batch-service-split-2.yaml`, `bump: minor`.

## Test Plan

Unit (CI): resolver precedence per service and source; host defaulting and the
required-host refusal; jenkins/jira/cross-forge tracker refusals naming the
follow-up; migration fixtures (github with real CI, gitlab with fr-only
`.gitlab-ci.yml` → `ci: none`, gitea, no backend key, self-hosted host, CRLF,
comments preserved, crash-window v2 body, unknown v1 key refused byte-identical);
the migration chain reachable 1 → 2; validator refusals; `acceptance init` and
`set-status ci` under each ci type; closeout / apply / triage dispatch under
`tracking: none`; `fr services` plain and `--json`; `fr init scaffold --ci/--tracking`
auto and inconclusive paths, including `fr init scaffold` over a v1 file
(migrated in process, stamped 2); exempt commands (`isolation`, `status`,
`services`) resolving an unmigrated v1 file with `source: legacy`, and the
legacy ci value equal to what the migration writes; `issues_enabled` on each
client (gh, glab, and tea returning None → inconclusive); `declared_host` /
`client_for`'s declared-host warning after migration; the debt-issue step
kept or omitted per ci/tracking platform; `acceptance init --with-ci` refused
under a declared `ci: none`; the fr-goal prose branches (R5 Ready-checklist
wording, skeleton, `deferred`, closeout); this repo's own migrated
fr-profiles validating.

Post-merge (operator): on a scratch GitLab project with no CI and issues
disabled, `fr init scaffold` → `fr services` shows `ci none`, `tracking none`;
`fr acceptance init` writes no pipeline; an fr-goal run's closeout prints no
issue-filing lines.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-28-fr-profiles-services | `derio-net/super-fr` | `2026-09-28-fr-profiles-services` | — |

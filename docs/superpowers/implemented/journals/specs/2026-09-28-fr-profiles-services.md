# Journal: 2026-09-28-fr-profiles-services

<!-- fr:journal kind=discovery scope=spec id=input-batch-brief created=2026-09-28T20:11:03+00:00 input=true -->
### input-batch-brief · discovery · Operator input: batch service-split-2 brief (verbatim)

/fr-goal fr-profiles: forge, ci and tracking as {type, host} services with none allowed (#774 step 1)

Batch `service-split-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request.

## super-fr#774: fr-profiles: split `backend` into forge / ci / tracking services, each with its own type and host (`none` allowed; Jenkins, Jira)
`backend:` in fr-profiles.yaml answers "gh, glab or tea?" but fr uses it for forge, CI (acceptance init's pipeline file) and tracker (findings, closeout, triage). Real setups differ: GitLab + Jenkins + Jira, or a demo repo with no CI or tracker.
Note: Operator-prioritised. Batch `service-split-2` (#774 step 1, after #783 and acceptance-init-no-ci); file the Jenkins/Jira adapters as a follow-up before its PR merges, since it closes #774.

## Why these belong together
Retry after question-order (#783). #774 step 1 only: the forge / ci / tracking schema ({type, host} each), defaults derived from today's backend: key, type: none for ci and tracking, and acceptance init / the ci status following the declared ci service (building on acceptance-init-no-ci, #775). Before merging, file the Jenkins and Jira adapters as a follow-up issue linked from #774, since this PR closes #774.

## Delivery rules
- Work on branch `feat/batch-service-split-2`.
- Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges:
  Closes derio-net/super-fr#774
- Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels.

<!-- fr:journal kind=discovery scope=spec id=input-issue-774 created=2026-09-28T20:11:03+00:00 input=true -->
### input-issue-774 · discovery · Operator input: super-fr#774 body (verbatim)

## What happened

`.devcontainer/fr-profiles.yaml`'s top-level `backend:` (resolved by `fr._hosts.detect_backend`) answers one question, "gh, glab or tea?", but fr uses it for three different things:

1. **forge**: PRs/MRs, merges, verify-merge (`hostclient.client_for`, `PR_COMMANDS`);
2. **CI**: which pipeline file `fr acceptance init` scaffolds (`acceptance/scaffold.py` `init(..., backend)`: `.gitlab-ci.yml` for gitlab), and what `ci` status means;
3. **project management / tracker**: where issues are filed and followed up (fr-goal's out-of-scope findings, closeout, `fr triage`, the `Tracker` seam in `fr/tracker/model.py`, which has only a GitHub implementation).

Real setups don't line up: a company on self-hosted GitLab (forge) with Jenkins (CI) and Jira (issues), or a demo repo with no CI and no issue tracking at all. In the super-fr-3 recordings the conflation shows up as:

- take 9 scaffolded `.gitlab-ci.yml` on a project with no CI, marked rows `ci`, and the stray edits blocked closeout (#775);
- take 5's closeout filed its findings as GitLab project issues in an org that doesn't use them; every prompt since carries "Don't open any issues: this org doesn't use GitLab project issues".

## Proposal

Split the one key into three services, each with its **own type and host**. The hosts are usually different: GitLab at `gitlab.corp`, Jenkins at `ci.corp`, Jira at `corp.atlassian.net`. Each service allows `type: none`.

```yaml
forge:                    # PRs/MRs, merges, verify-merge
  type: gitlab            # github | gitlab | gitea
  host: gitlab.example.com
ci:                       # pipelines: scaffold, status, deliver's evidence
  type: jenkins           # none | github-actions | gitlab-ci | gitea-actions | jenkins
  host: ci.example.com
  job: team/agentic-playground        # type-specific, e.g. Jenkins job path
tracking:                 # issues: out-of-scope findings, closeout follow-ups, triage
  type: jira              # none | github | gitlab | gitea | jira
  host: example.atlassian.net
  project: SCO                        # type-specific, e.g. Jira project key
```

- **Nested rather than flat keys** (`forge_type`, `forge_host`, …): each service keeps its type-specific settings together (Jenkins job, Jira project key and transitions, credentials env var), and adding a service later doesn't add keys at the top level.
- **Defaults keep today's files working:**
  - the top-level `backend:` + `host:` stay as shorthand for `forge`;
  - `ci` and `tracking` default to "the forge's own" (`gitlab` → `gitlab-ci` / `gitlab` issues, on the forge host) unless declared;
  - `host` defaults to the forge host when the type is the forge's own, and is required otherwise.
- **`ci: {type: none}`** switches off every CI path: no pipeline scaffold (#775), no `ci` acceptance status, deliver doesn't wait for or cite a pipeline, and the skills say "the local suite is the gate".
- **`tracking: {type: none}`** switches off every issue path: out-of-scope findings go into the run's journal, the PR body and the closeout hand-off instead of a tracker, and no skill tells an agent to file an issue.
- **`jenkins` and `jira` are the next adapters,** behind the existing seams:
  - the `Tracker` protocol (`fr/tracker/model.py`) already names Jira's per-project transitions;
  - `artifacts/trigger.py` already recognises `JENKINS_URL`.
  - Credentials stay out of the file: per service, the env var name the devcontainer profile's secrets provide.

**Suggested order:**
1. The schema, the defaults, and `type: none` for `ci` and `tracking`. That's enough for the demo repo, and it replaces the AGENTS.md and prompt workarounds.
2. The Jenkins and Jira adapters. A large piece of work, but it's the shape a company on Jira + Jenkins + GitLab needs.

<!-- fr:journal kind=decision scope=spec id=q1-defaults created=2026-09-28T20:11:03+00:00 -->
### q1-defaults · decision · Undeclared ci/tracking resolve to the forge's own; the file is migrated to the new structure at first run

Operator: forge's own (option 1), 'but migration must happen at first run.'

<!-- fr:journal kind=decision scope=spec id=q2-base-787 created=2026-09-28T20:11:03+00:00 -->
### q2-base-787 · decision · Pause this run until #787 (acceptance-init-no-ci) merges, then build on it

Operator chose 'Pause until #787 merges' over building on main or stacking on the draft branch.

<!-- fr:journal kind=decision scope=spec id=q3-shape created=2026-09-28T20:11:03+00:00 -->
### q3-shape · decision · At the first fr command with the new version, the yaml is rewritten to the nested forge/ci/tracking structure

Operator: 'at the first fr command with the new version, update the yaml to the new structure. There is precedent.' The shorthand backend/host is migrated away rather than kept alongside forge:; a malformed service fails the structure validator (q9).

<!-- fr:journal kind=decision scope=spec id=q4-no-adapter created=2026-09-28T20:11:03+00:00 -->
### q4-no-adapter · decision · jenkins and jira are rejected by the schema until their adapters ship

Operator chose 'Reject until adapters': step 1 accepts only none plus the forge-native types.

<!-- fr:journal kind=decision scope=spec id=q5-no-tracker-findings created=2026-09-28T20:11:03+00:00 -->
### q5-no-tracker-findings · decision · Under tracking none, findings stay out-of-scope; closeout drops the file-an-issue/deferred lines; journal model unchanged

<!-- fr:journal kind=decision scope=spec id=q6-issue-cmds created=2026-09-28T20:11:03+00:00 -->
### q6-issue-cmds · decision · Under tracking none, fr apply --yes and triage batch dispatch refuse naming tracking: none; the acceptance template omits the debt-issue step; triage collect still reads the forge

<!-- fr:journal kind=decision scope=spec id=q7-no-ci-delivery created=2026-09-28T20:11:03+00:00 -->
### q7-no-ci-delivery · decision · Under ci none, the Ready checklist reads 'local suite green (evidence: <log>)' and fr-goal/fr-acceptance prose says the local suite is the gate

<!-- fr:journal kind=decision scope=spec id=q8-surface created=2026-09-28T20:11:03+00:00 -->
### q8-surface · decision · New read-only `fr services` verb (with --json) prints each resolved service and its source; added to READ_ONLY_COMMANDS

<!-- fr:journal kind=decision scope=spec id=q9-migration created=2026-09-28T20:11:03+00:00 -->
### q9-migration · decision · fr-profiles becomes a registered artifact kind: stamp, SchemaMigration flat->nested, structure validator; the CLI-entry gate migrates it

<!-- fr:journal kind=decision scope=spec id=r2q1-blast-radius created=2026-09-28T20:11:03+00:00 -->
### r2q1-blast-radius · decision · Accept the entry gate's usual refusals (default branch, non-interactive) for the fr-profiles kind; no special case

<!-- fr:journal kind=decision scope=spec id=r2q2-migrated-ci created=2026-09-28T20:11:03+00:00 -->
### r2q2-migrated-ci · decision · Migration writes ci as detected: forge's own if a CI config exists that is not solely fr's scaffolded acceptance template, else none

Operator chose 'Detected' and asked: 'aren't ci configs created regardless so far? If so, how can the migration know if the config is active?' Answer recorded in the spec: before #787 fr scaffolded the CI file regardless, so presence alone proves nothing; the offline migration discounts a config that is solely fr's own acceptance template; activity (pipelines actually running) is only knowable from the forge, which the migration does not call.

<!-- fr:journal kind=decision scope=spec id=r2q3-init-flags created=2026-09-28T20:11:03+00:00 -->
### r2q3-init-flags · decision · fr init scaffold gains --ci/--tracking; both are detected, and when detection is inconclusive the operator is asked

Operator: option 1, 'but both should be detected and if not, the user should be asked'.

<!-- fr:journal kind=decision scope=spec id=gate-question-rounds-brainstorm created=2026-09-28T20:11:06+00:00 -->
### gate-question-rounds-brainstorm · decision · Operator gate `brainstorm` took two question rounds

Trigger: design-risk. Round 1 chose an artifact-kind migration and #787's disk detection; checking the entry gate (trigger.py:429 default-branch refusal) and #787's scaffold-regardless history raised the blast radius and the migrated ci value

<!-- fr:journal kind=finding scope=spec id=s1 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s1 · finding [open] (reviewer: in scope) · Input span 'backend:/host: stay as shorthand for forge' is neither a requirement nor deferred

check: traceability
evidence: input-issue-774 "- the top-level `backend:` + `host:` stay as shorthand for `forge`;"; decision q3-shape
scope: in — the input-coverage partition cannot close without it; traceability findings are always in scope.
resolution: dropped
q3-shape overrode this span (the shorthand is migrated away, not kept) and R3 cites q3, but the span itself is neither quoted in ## Requirements nor listed under ## Deferred from input, so the literal input is silently contradicted. Fix: add a Deferred row quoting it, reason "superseded by decision q3-shape: migrated to `forge:` at first run".

<!-- fr:journal kind=finding scope=spec id=s2 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s2 · finding [open] (reviewer: in scope) · 'Each service allows type: none' is narrowed to ci/tracking with no deferral for forge

check: traceability
evidence: input-issue-774 "Each service allows `type: none`."; spec R1 (forge types github/gitlab/gitea only), §3.A
scope: in — a literal input span is dropped for the forge service; traceability findings are always in scope.
resolution: dropped
The brief says "type: none for ci and tracking", so leaving forge none out of step 1 is defensible, but the issue's blanket sentence is neither quoted nor deferred. Fix: defer the span, or add it to R1.

<!-- fr:journal kind=finding scope=spec id=s3 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s3 · finding [open] (reviewer: in scope) · R1 narrows tracking to 'none or the forge's own type'; input and q4 allow the forge-native tracker types

check: traceability
evidence: input "type: jira # none | github | gitlab | gitea | jira"; decision q4-no-adapter "step 1 accepts only none plus the forge-native types"; spec R1, §3.A
scope: in — narrows an accepted range the operator decided; traceability findings are always in scope.
resolution: reinterpreted
R1 additionally refuses a cross-forge tracker (e.g. gitlab tracking behind a github forge) on an implementation reason the operator was never asked about. Resolve unconfirmed with a note, or accept all three forge-native types.

<!-- fr:journal kind=finding scope=spec id=s4 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s4 · finding [open] (reviewer: in scope) · Undeclared ci default: R2/q1 say 'forge's own', §3.B.2 makes it conditional on a disk probe (else none)

check: traceability
evidence: spec R2; decision q1-defaults; spec §3.B step 2
scope: in — the design changes a default the requirement and decision fix; traceability findings are always in scope.
resolution: reinterpreted
§3.B.2 adds a probe condition in neither R2 nor q1, and diverges from the migration's §3.C discount, so a v1 repo whose only CI file is fr's .gitlab-ci.yml shows `ci gitlab-ci (legacy)` before migration and `ci none` after. Resolve unconfirmed with a note, or match R2 literally.

<!-- fr:journal kind=finding scope=spec id=s5 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s5 · finding [open] (reviewer: in scope) · §3.E: `fr acceptance init --with-ci` writing `ci:` into fr-profiles.yaml has no requirement behind it

check: traceability
evidence: spec §3.E row acceptance/scaffold.init "(it writes `ci:` explicitly on success)"; no R-row covers it
scope: in — user-visible behaviour (a registered artifact rewritten by acceptance init) introduced only in the Design.
resolution: invented
Resolve unconfirmed stating what gets written, or drop the side effect so --with-ci only scaffolds the pipeline.

<!-- fr:journal kind=finding scope=spec id=s6 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s6 · finding [open] (reviewer: in scope) · `_hosts.declared_host` is not rerouted through the forge service, so client_for's gh-486 warning dies after migration

check: codebase
evidence: packages/fr/src/fr/_hosts.py:198-209; packages/fr/src/fr/_hosts.py:233; packages/fr/src/fr/hostclient.py:125-126
scope: in — the migration this spec adds removes the top-level `host:` this function reads.
Fix: declared_host returns forge.host when its source is declared (or legacy); add it to the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s7 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s7 · finding [open] (reviewer: in scope) · `fr init` is gate-exempt (READ_ONLY_COMMANDS) yet R8 makes it write the now-registered profiles artifact; stamp and v1 handling unspecified

check: codebase
evidence: packages/fr/src/fr/artifacts/trigger.py:77-86; packages/fr/src/fr/isolation/scaffold.py:617-642; spec R8, §3.D.1-2
scope: in — registering fr-profiles as an artifact kind is what makes `fr init scaffold` an exempt writer of a registered artifact.
Unspecified: (a) the v2 stamp init writes, (b) init over an existing v1 file (mixed body), (c) the READ_ONLY_COMMANDS criterion. Fix: init migrates (or refuses) a v1 file, always stamps, and the exemption rationale is updated in the same diff.

<!-- fr:journal kind=finding scope=spec id=s8 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s8 · finding [open] (reviewer: in scope) · Debt-issue step is keyed by ci template, so a cross-forge ci files issues on a non-tracker

check: consistency
evidence: spec §3.A, §3.B, §3.E debt-issue row; packages/fr/src/fr/acceptance/scaffold.py:326-347, :154-172, :257-281
scope: in — the inconsistency is between two design choices of this spec.
With forge github, ci gitlab-ci, tracking github, the debt issue lands in GitLab, which is not the tracker. Fix: omit the step unless the ci type is the tracker's native pipeline; same for the RULE_TEMPLATE CI bullets (scaffold.py:360-366).

<!-- fr:journal kind=finding scope=spec id=s9 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s9 · finding [open] (reviewer: in scope) · Refusal messages must name the follow-up issue number, but the follow-up is only required 'before this PR merges'

check: consistency
evidence: spec header; R1; §3.A
scope: in — an ordering gap inside this spec's own delivery.
Fix: file the follow-up before the phase that writes the refusal and record its number in the spec, or name #774.

<!-- fr:journal kind=finding scope=spec id=s10 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s10 · finding [open] (reviewer: in scope) · §3.G skill/rule edits do not cover every CI-gate and issue-filing instruction R5/R6 switch off

check: consistency
evidence: plugins/super-fr/skills/fr-goal/SKILL.md:67; plugins/super-fr/skills/fr-goal/SKILL.md:94; plugins/super-fr/skills/fr-goal/SKILL.md:107; packages/fr/src/fr/acceptance/scaffold.py:360-366
scope: in — R5/R6 promise these paths are switched off and the design enumerates only part of them.
Fix: list each passage in §3.G with its branch on `fr services`, plus a prose-level test.

<!-- fr:journal kind=finding scope=spec id=s11 created=2026-09-28T20:19:10+00:00 state=open review_scope=in -->
### s11 · finding [open] (reviewer: in scope) · Test Plan omits design surfaces: legacy read / `source: legacy`, `issues_enabled` per adapter, declared_host, R5 prose

check: consistency
evidence: spec §3.B, §3.C, R5, ## Test Plan
scope: in — the Test Plan and Design disagree.
Add a line for each.

<!-- fr:journal kind=review scope=spec id=spec-review created=2026-09-28T20:19:10+00:00 -->
### spec-review · review · independent spec review: 11 findings

input-coverage:
```input-coverage
| span | coverage |
|---|---|
| "/fr-goal fr-profiles: forge, ci and tracking as {type, host} services with none allowed (#774 step 1)" | R1 |
| "Batch `service-split-2` of derio-net/super-fr: 1 issues, delivered as ONE pull request." | context |
| "## super-fr#774: fr-profiles: split `backend` into forge / ci / tracking services, each with its own type and host (`none` allowed; Jenkins, Jira)" | context |
| "`backend:` in fr-profiles.yaml answers "gh, glab or tea?" but fr uses it for forge, CI (acceptance init's pipeline file) and tracker (findings, closeout, triage). Real setups differ: GitLab + Jenkins + Jira, or a demo repo with no CI or tracker." | context |
| "Note: Operator-prioritised. Batch `service-split-2` (#774 step 1, after #783 and acceptance-init-no-ci); file the Jenkins/Jira adapters as a follow-up before its PR merges, since it closes #774." | context |
| "## Why these belong together" | context |
| "Retry after question-order (#783). #774 step 1 only:" | context |
| "the forge / ci / tracking schema ({type, host} each)," | R1 |
| "defaults derived from today's backend: key," | R2 |
| "type: none for ci and tracking," | R1 |
| "and acceptance init / the ci status following the declared ci service (building on acceptance-init-no-ci, #775)." | R4 |
| "Before merging, file the Jenkins and Jira adapters as a follow-up issue linked from #774, since this PR closes #774." | deferred |
| "## Delivery rules - Work on branch `feat/batch-service-split-2`. - Open a draft PR as soon as the spec is committed. Its body contains these lines, one per member, so every member closes when it merges: Closes derio-net/super-fr#774 - Do not name any member issue as a phase `tracking_issue` in the plan: the bridge would then own that issue's `fr:` labels." | context |
| "## What happened" | context |
| "`.devcontainer/fr-profiles.yaml`'s top-level `backend:` (resolved by `fr._hosts.detect_backend`) answers one question, "gh, glab or tea?", but fr uses it for three different things:" | context |
| "1. **forge**: PRs/MRs, merges, verify-merge (`hostclient.client_for`, `PR_COMMANDS`);" | context |
| "2. **CI**: which pipeline file `fr acceptance init` scaffolds (`acceptance/scaffold.py` `init(..., backend)`: `.gitlab-ci.yml` for gitlab), and what `ci` status means;" | context |
| "3. **project management / tracker**: where issues are filed and followed up (fr-goal's out-of-scope findings, closeout, `fr triage`, the `Tracker` seam in `fr/tracker/model.py`, which has only a GitHub implementation)." | context |
| "Real setups don't line up: a company on self-hosted GitLab (forge) with Jenkins (CI) and Jira (issues), or a demo repo with no CI and no issue tracking at all. In the super-fr-3 recordings the conflation shows up as:" | context |
| "- take 9 scaffolded `.gitlab-ci.yml` on a project with no CI, marked rows `ci`, and the stray edits blocked closeout (#775);" | context |
| "- take 5's closeout filed its findings as GitLab project issues in an org that doesn't use them; every prompt since carries "Don't open any issues: this org doesn't use GitLab project issues"." | context |
| "## Proposal" | context |
| "Split the one key into three services, each with its **own type and host**." | R1 |
| "The hosts are usually different: GitLab at `gitlab.corp`, Jenkins at `ci.corp`, Jira at `corp.atlassian.net`." | context |
| "Each service allows `type: none`.`" | deferred |
| "``yaml forge: # PRs/MRs, merges, verify-merge type: gitlab # github \| gitlab \| gitea host: gitlab.example.com ci: # pipelines: scaffold, status, deliver's evidence type: jenkins # none \| github-actions \| gitlab-ci \| gitea-actions \| jenkins host: ci.example.com job: team/agentic-playground # type-specific, e.g. Jenkins job path tracking: # issues: out-of-scope findings, closeout follow-ups, triage type: jira # none \| github \| gitlab \| gitea \| jira host: example.atlassian.net project: SCO # type-specific, e.g. Jira project key`" | R1 |
| "``- **Nested rather than flat keys** (`forge_type`, `forge_host`, …): each service keeps its type-specific settings together (Jenkins job, Jira project key and transitions, credentials env var), and adding a service later doesn't add keys at the top level." | R1 |
| "- **Defaults keep today's files working:**" | R2 |
| "- the top-level `backend:` + `host:` stay as shorthand for `forge`;" | deferred |
| "- `ci` and `tracking` default to "the forge's own" (`gitlab` → `gitlab-ci` / `gitlab` issues, on the forge host) unless declared;" | R2 |
| "- `host` defaults to the forge host when the type is the forge's own, and is required otherwise." | R2 |
| "- **`ci: {type: none}`** switches off every CI path: no pipeline scaffold (#775), no `ci` acceptance status," | R4 |
| "deliver doesn't wait for or cite a pipeline, and the skills say "the local suite is the gate"." | R5 |
| "- **`tracking: {type: none}`** switches off every issue path: out-of-scope findings go into the run's journal, the PR body and the closeout hand-off instead of a tracker, and no skill tells an agent to file an issue." | R6 |
| "- **`jenkins` and `jira` are the next adapters,** behind the existing seams:" | deferred |
| "- the `Tracker` protocol (`fr/tracker/model.py`) already names Jira's per-project transitions;" | context |
| "- `artifacts/trigger.py` already recognises `JENKINS_URL`." | context |
| "- Credentials stay out of the file: per service, the env var name the devcontainer profile's secrets provide." | deferred |
| "**Suggested order:**" | context |
| "1. The schema, the defaults, and `type: none` for `ci` and `tracking`." | R1, R2, R4, R6 |
| "That's enough for the demo repo, and it replaces the AGENTS.md and prompt workarounds." | context |
| "2. The Jenkins and Jira adapters. A large piece of work, but it's the shape a company on Jira + Jenkins + GitLab needs." | deferred |
```
Spans s1 and s2 were `missing` in the reviewer's return; the spec now defers both under ## Deferred from input, so they read `deferred`. The issue's yaml fence is split across adjacent spans ("`" + "``") so it does not close this block early.

<!-- fr:journal kind=finding scope=spec id=s1-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s1 -->
### s1-resolved · finding [fixed] · resolves s1: Input span 'backend:/host: stay as shorthand for forge' is neither a requirement nor deferred

Added a ## Deferred from input row quoting the shorthand span, reason: superseded by decision q3-shape (migrated to forge: at the first fr command, R3).

<!-- fr:journal kind=finding scope=spec id=s2-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s2 -->
### s2-resolved · finding [fixed] · resolves s2: 'Each service allows type: none' is narrowed to ci/tracking with no deferral for forge

Added a ## Deferred from input row quoting 'Each service allows `type: none`.', reason: step 1 scopes none to ci and tracking as the brief does; forge: none is not in this change.

<!-- fr:journal kind=finding scope=spec id=s3-resolved created=2026-09-28T20:19:10+00:00 state=open resolves=s3 unconfirmed=true -->
### s3-resolved · finding [unconfirmed] · resolves s3: R1 narrows tracking to 'none or the forge's own type'; input and q4 allow the forge-native tracker types

Built: step 1 accepts tracking none or the forge's own type; a cross-forge tracker (e.g. gitlab issues behind a github forge) is refused with a message naming #795, because fr files issues through the forge client and routing them elsewhere is the step-2 tracker seam. R1 text unchanged.

<!-- fr:journal kind=finding scope=spec id=s4-resolved created=2026-09-28T20:19:10+00:00 state=open resolves=s4 unconfirmed=true -->
### s4-resolved · finding [unconfirmed] · resolves s4: Undeclared ci default: R2/q1 say 'forge's own', §3.B.2 makes it conditional on a disk probe (else none)

Built: an undeclared ci resolves to the forge's own pipeline type only when a CI config is on disk (#787's ci_config probe), else none — reached after the migration only by a repo with no fr-profiles.yaml. A still-v1 file resolves ci with the migration's own discounted detection (source: legacy), so fr services shows the same value before and after migrating. R2 text unchanged.

<!-- fr:journal kind=finding scope=spec id=s5-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s5 -->
### s5-resolved · finding [fixed] · resolves s5: §3.E: `fr acceptance init --with-ci` writing `ci:` into fr-profiles.yaml has no requirement behind it

Side effect removed: `fr acceptance init --with-ci` never writes fr-profiles.yaml; under a declared ci: none it refuses (the declaration wins), with no fr-profiles.yaml it scaffolds as #787 shipped (§3.E).

<!-- fr:journal kind=finding scope=spec id=s6-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s6 -->
### s6-resolved · finding [fixed] · resolves s6: `_hosts.declared_host` is not rerouted through the forge service, so client_for's gh-486 warning dies after migration

§3.B: declared_host joins detect_backend and host_for as wrappers over the forge service, returning forge.host for source declared/legacy, so client_for's gh#486 warning keeps its provenance; added to the Test Plan.

<!-- fr:journal kind=finding scope=spec id=s7-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s7 -->
### s7-resolved · finding [fixed] · resolves s7: `fr init` is gate-exempt (READ_ONLY_COMMANDS) yet R8 makes it write the now-registered profiles artifact; stamp and v1 handling unspecified

New §3.E.1: fr init scaffold migrates a v1 file in process with the same 1->2 function (refusing one it cannot migrate, untouched), merges into the nested shape and always stamps schema_version: 2; init stays exempt with the READ_ONLY_COMMANDS docstring and the pinned test updated in the same diff.

<!-- fr:journal kind=finding scope=spec id=s8-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s8 -->
### s8-resolved · finding [fixed] · resolves s8: Debt-issue step is keyed by ci template, so a cross-forge ci files issues on a non-tracker

§3.E: the debt-issue step and the rule template's CI bullet are kept only when the tracking type is the ci type's own platform; omitted with a notice under tracking none or a ci on another platform.

<!-- fr:journal kind=finding scope=spec id=s9-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s9 -->
### s9-resolved · finding [fixed] · resolves s9: Refusal messages must name the follow-up issue number, but the follow-up is only required 'before this PR merges'

Follow-up filed as derio-net/super-fr#795 and linked from #774 before any implementation; the spec header and §3.A now name it.

<!-- fr:journal kind=finding scope=spec id=s10-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s10 -->
### s10-resolved · finding [fixed] · resolves s10: §3.G skill/rule edits do not cover every CI-gate and issue-filing instruction R5/R6 switch off

§3.G now lists every fr-goal passage (skeleton 'CI green', deferred --tracked-by guidance, Ready checklist, closeout 'open the issue'), each branched on fr services, with a prose test pinning each branch.

<!-- fr:journal kind=finding scope=spec id=s11-resolved created=2026-09-28T20:19:10+00:00 state=fixed resolves=s11 -->
### s11-resolved · finding [fixed] · resolves s11: Test Plan omits design surfaces: legacy read / `source: legacy`, `issues_enabled` per adapter, declared_host, R5 prose

Test Plan extended: legacy v1 read with source: legacy and legacy ci == migrated ci, issues_enabled per client (tea None), declared_host/client_for warning, debt-step platform rule, --with-ci refusal, init over v1, fr-goal prose branches.

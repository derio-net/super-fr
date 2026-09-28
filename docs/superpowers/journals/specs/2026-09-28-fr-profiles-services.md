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

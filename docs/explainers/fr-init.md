---
title: "fr-init: Teaching a Repo How to Run Isolated"
date: 2026-11-11
draft: false
tldr: |
  An isolated workspace needs to know what to install and which credentials to let in.
  fr-init scans your repo, asks you the few things a scan cannot answer, and commits
  one or more devcontainer profiles, with the secrets themselves kept off the repo.
standalone: true
standalone_style: broadsheet
covers:
  - plugins/super-fr/skills/fr-init/SKILL.md
  - packages/fr/src/fr/commands/init_cmd.py
  - packages/fr/src/fr/commands/services_cmd.py
reviewed: 2026-11-13 init's writers refuse in a stealth workspace (placement-resolver p4-r3)
---

## Overview: the profile is the contract

[fr-isolation](fr-isolation.md) runs every build inside a container, and a container has
to be built from something. A **profile** is that something: a devcontainer definition
committed under `.devcontainer/<profile>/`, plus a record of which secret *names* the
profile expects. The values never enter the repo. They live in a file on your machine,
`~/.config/fr/secrets/<repo>/<profile>.env`, and are passed to the container when it
starts.

You reach for fr-init when a repo has no profile yet, or when you want a second one. The
usual trigger is a hard stop: in devcontainer mode, `fr isolation up` has nothing to
build and the brainstorm will not start without one. (A docker-less host that sets
`FR_ISOLATION_TARGET=worktree` isolates with the worktree alone and does not need a
profile.)

Unlike most fr skills, this one is interactive on purpose. What credentials a run may see
is a decision that belongs to you, so the skill is exempt from the unattended contract.
Inside an [fr-goal](01-fr-goal.md) run, a missing profile pauses the run, you do the
interview, and the run resumes.

## A worked example

A Python repo with a Node front end, where you want a day-to-day profile and a separate
one that can deploy:

```bash
fr init scaffold --repo . --profile dev --purpose "day-to-day development" \
    --tool uv --tool node --default
fr init scaffold --repo . --profile admin --purpose "deploys and forge writes" \
    --secret GH_TOKEN --secret KUBECONFIG_B64
```

The first call writes `.devcontainer/dev/devcontainer.json`, adds the profile to
`.devcontainer/fr-profiles.yaml`, marks it the default, and commits both (on the quiet
placement it writes them and leaves the commit to you). The second adds
a profile that expects two secret names. For each secret, scaffold writes a commented
placeholder into the host-only env file and never overwrites a value you have already
put there.

Then fill the placeholders, and start a workspace:

```bash
$EDITOR ~/.config/fr/secrets/<repo>/admin.env
fr isolation up --branch feat/something --profile admin
```

Leaving `--profile` off uses the default, which is why the default should be the
least-privileged one: that is what unattended runs get.

## What the skill does, in order

**1. Scan first.** Before asking anything it reads what the repo already says: manifests
and lockfiles for languages, CI workflows for what gets installed, any existing
`.devcontainer/`, the origin remote for the forge, `.env*` patterns and CI secret names
for the credential surface, and the Makefile or scripts for how people run things here.
The interview confirms and fills gaps; it never asks something the scan answered.

**2. Interview, at most four questions a round.** An unanswered round is a stop, not a
prompt to guess. The topics:

- the **backend**: GitHub, GitLab or Gitea (skipped when the remote makes it obvious;
  a self-hosted host is confirmed with `--host`);
- the **profiles** you want: one `dev`, or a split such as read-only for review and admin
  with deploy credentials. Profiles differ by credentials first and tools second;
- the **tools** to install, checked against the set `fr init scaffold --help` lists
  (`docker-in-docker`, `go`, `java`, `kubectl`, `maven`, `node`, `python`, `rust`,
  `terraform`, `uv`). For Java, confirm the major version, because scaffold's own
  detection reads only version files and the POM;
- the **secret names** per profile. Names only, never values. It does not ask for a
  forge token by default: push and pull request creation run on the authenticated host,
  so the container needs none for the standard pipeline;
- the **working patterns**, the test, build and run commands worth recording as the
  profile's purpose.

**3. Scaffold.** One `fr init scaffold` call per profile, as above. A tool is
`<tool>` or `<tool>@<version>`; an unknown tool is refused, and `--feature <ref>` takes a
raw devcontainer feature for a toolchain the list lacks. The forge CLI is installed to
match the backend. Pass `--backend` (and `--host` for a self-hosted instance) on every
call for a non-GitHub forge.

**4. Hand back.** The skill tells you which placeholder files to fill. Scaffold has
already committed the profile, because `fr isolation up` builds from the committed tree;
two cases leave the commit to you. On the quiet placement fr makes no commit on a product
branch, so scaffold writes the files and tells you to commit them, and when `.devcontainer`
is git-ignored it warns and commits nothing. Add
`--no-commit` to write the files only, for example when you must open a pull request to
get them onto a protected branch. In a stealth workspace (a run whose records live in a
separate tracking repository) `fr init scaffold`, `fr init agents` and `fr init
validator-wrapper` refuse before writing anything: no fr file
may reach a stealth target.

## Services: forge, CI, tracking

`.devcontainer/fr-profiles.yaml` also records three services for the repo: `forge`, `ci`
and `tracking`, each with a type and an optional host. `fr services` prints what resolved
and where each value came from (`--json` for machines). Scaffold takes
`--ci none|github-actions|gitlab-ci|gitea-actions|auto` and
`--tracking none|github|gitlab|gitea|auto`. When `auto` cannot decide, it exits 2 and
names the flag to pass, and you re-run it explicitly instead of accepting a guess.

## Limits

- fr-init sets up *how* work is isolated, not whether a run is safe. The credentials you
  grant a profile are the credentials its runs can use.
- Adding a profile later is one more `scaffold` call; the per-profile folder layout
  needs no migration.
- It writes no secret values. If the env file is empty, the container simply gets no
  secrets, which is normal for a default profile.

## Where to go next

- [fr-isolation](fr-isolation.md) uses the profile you just made.
- [fr-brainstorming-and-plan](fr-brainstorming-and-plan.md) is where most runs start once
  a profile exists.

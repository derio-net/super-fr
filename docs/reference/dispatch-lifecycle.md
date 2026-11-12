---
title: "Dispatch labels and the per-repo plan profile"
tldr: |
  The labels a dispatched phase carries as it moves from queued to done, the gate that stops you dispatching work the runner cannot see, and the optional plan-config file.
standalone_style: broadsheet
covers:
  - packages/fr-dispatch/src/**
  - packages/fr/src/fr/commands/repos_cmd.py
  - packages/fr/src/fr/repos.py
  - packages/fr/src/fr/labels.py
  - packages/fr/src/fr/item_state.py
  - packages/fr/src/fr/commands/apply_cmd.py
  - scripts/validate-plans.sh
reviewed: 2026-11-12 vk compat removal, only label wording in two comments changed, the page already says fr:ready
---

# Dispatch labels and the per-repo plan profile

`fr apply --to <runner>` turns each phase of a merged plan into a tracking issue and hands
ready phases to a runner, which opens one PR per phase. The walkthrough is in
[fr-dispatch](../explainers/fr-dispatch.md); this page is the reference for what the
labels mean.

## The label lifecycle

A runner is the program that picks up queued phases and works them (VibeKanban's `vk`
adapter, for one). It wakes on a timer; each wake is a tick. A queued phase carries exactly
one lifecycle label, derived from the issue and its PRs on every tick:

```
fr:ready ──→ fr:in-progress ──→ fr:pr-ready ──→ (issue closed)
   │
   └─ fr:blocked   while phases it depends on are not complete
```

Two more labels are markers, not states. `fr:synced` is the bookkeeping stamp that says a
phase was handed to the runner, so it is never handed over twice. `manual` marks a
human-only phase, which is never routed to an agent. An issue created without `--to` is
tracking-only and carries no lifecycle label.

All of this is what the defaults give you. A repo's forge settings (`.fr/settings.yaml`
on its default branch, `fr settings show`) can switch writes off by kind:

- **`forge.labels: off`**: neither `fr apply` nor the bridge writes any of these labels,
  including `fr:synced`. The bridge's dedup snapshot is then the only thing that stops a
  phase being handed over twice.
- **`forge.issues: off`**: no tracking issue is created or closed, and the bridge's
  close-on-merge backstop closes nothing.

If the bridge cannot read a repo's settings, it refuses that repo's writes and reports
the failure. It never falls back to the defaults.

## The reachability gate

`fr apply --yes --to <runner>` refuses unless the plan and its spec are merged to the
default branch. The runner works from its own checkout of that branch, so anything not
there would be invisible to it. The refusal exits 2 and lists the unreachable paths.

## The optional plan profile

A repo can add `docs/superpowers/plan-config.yaml` to set the plan filename pattern, the
required headers and the allowed status values. Only `scripts/validate-plans.sh` reads it,
and it falls back to defaults when the file is absent, so a repo works without one.

To add the file to several repos you already have checked out, without cloning anything:

```bash
fr repos sync owner/one owner/two          # dry-run preview (the default)
fr repos sync owner/one owner/two --yes    # write plan-config.yaml in place
```

Repos are found through `$FR_REPOS_DIR` or `~/repos/<name>` (a missing checkout is a
warning, not a failure), or through a manifest at `$FR_REPOS_MANIFEST` or
`~/.config/fr/repos.yaml`. Names you pass are appended to that manifest unless you add
`--no-save`, and `--force` overwrites a file that already exists. `fr repair` and `fr migrate`
also tidy this file, removing keys the toolchain no longer reads.

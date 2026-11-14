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
reviewed: 2026-11-12 placement-resolver phase 2, artifact directories now come from fr.artifacts.paths; the paths and behaviour this page describes are unchanged
---

# Dispatch labels and the per-repo plan profile

`fr apply --to <runner>` turns each phase of a merged plan into a tracking issue. It hands
ready phases to a runner, which opens one PR for each phase. The walkthrough is in
[fr-dispatch](../explainers/fr-dispatch.md). This page is the reference for what the
labels mean.

## The label lifecycle

A runner is the program that picks up queued phases and works them (VibeKanban's `vk`
adapter, for one). It wakes on a timer, and each wake is a tick. A queued phase carries
exactly one lifecycle label. On every tick, the label is derived from the issue and its PRs:

```
fr:ready ──→ fr:in-progress ──→ fr:pr-ready ──→ (issue closed)
   │
   └─ fr:blocked   while phases it depends on are not complete
```

Two more labels are markers, not states. `fr:synced` is the record stamp that says a
phase was handed to the runner, so the phase is never handed over twice. `manual` marks a
human-only phase, which is never routed to an agent. An issue made without `--to` is
tracking-only and carries no lifecycle label.

All of this is what the defaults give you. A repo's forge settings (`.fr/settings.yaml`
on its default branch, `fr settings show`) can switch writes off by kind:

- **`forge.labels: off`**: the bridge writes none of these labels, and not `fr:synced`
  either. The bridge's dedup snapshot is then the only thing that stops a second handover
  of a phase.
- **`forge.issues: off`**: the bridge makes and closes no tracking issue, and its
  close-on-merge backstop closes nothing.

Under either of these two, `fr apply --yes` stops (exit 2) and names the setting.

If the bridge cannot read the settings of a repo, it does not write to that repo, and it
reports the failure. It never falls back to the defaults.

## The reachability gate

`fr apply --yes --to <runner>` stops unless the plan and its spec are merged to the
default branch. The runner works from its own checkout of that branch, so it cannot see
anything that is not there. The command then exits 2 and lists the paths that the runner
cannot reach.

## The optional plan profile

A repo can add `docs/superpowers/plan-config.yaml` to set the plan filename pattern, the
required headers and the allowed status values. Only `scripts/validate-plans.sh` reads it.
The script falls back to defaults when the file is absent, so a repo works without one.

To add the file to several repos that you already have checked out, with no clone:

```bash
fr repos sync owner/one owner/two          # dry-run preview (the default)
fr repos sync owner/one owner/two --yes    # write plan-config.yaml in place
```

fr finds repos through `$FR_REPOS_DIR` or `~/repos/<name>`, or through a manifest at
`$FR_REPOS_MANIFEST` or `~/.config/fr/repos.yaml`. An absent checkout is a warning, not a
failure. With `--yes`, the names that you pass are appended to that manifest, unless you
add `--no-save`. `--force` overwrites a file that already exists. `fr repair` and `fr migrate`
also tidy this file: they remove keys that the toolchain no longer reads.

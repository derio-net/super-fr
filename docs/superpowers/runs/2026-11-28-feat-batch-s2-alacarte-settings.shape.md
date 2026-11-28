```
packages/fr/src/fr/settings/
  model.py     ~ schema 3: Workflows.disabled, Forge.pr_sections (PrSections
                 {proportionality, cost, settle}); a raw `workflows` / `forge.pr_sections`
                 key needs `schema: 3`; an unknown pr_sections key names the three
  load.py      ~ _stealth forces git.push / git.pr to ask (source `stealth`, explicit auto
                 -> contrary); _repo_file's quiet message corrected
  check.py     ~ + unknown-disabled-shape, every-shape-disabled; driven-triage message
                 names the triage keys as the fix
  render.py    ~ init renders list defaults as YAML lists, #schema: 3, stealth push/pr ask
packages/fr/src/fr/workflow/
  available.py + refuse_disabled (fails closed on unreadable settings; names the file
                 the value lives in, the shapes left and `--workflow`)
  resolve.py   ~ discover_names moved here from workflow_cmd
packages/fr/src/fr/commands/run_cmd.py, run/steps.py, run/adopt.py
               ~ refuse_disabled at start, `shape:` rebind and adopt (not advance,
                 resolve, reshape, nor --supersede onto the run's own shape)
packages/fr/src/fr/record/pr_body.py, run/deliver.py
               ~ required_sections(settings): an off section is neither rendered nor required
packages/fr/src/fr/commands/push_cmd.py
               ~ stealth: a push that moves nothing -> "nothing to push", exit 0, no ask
packages/fr/src/fr/git_policy/push.py
               + push_moves_remote (live ls-remote, never remote-tracking refs)
packages/fr/src/fr/config/change.py
               ~ config-change PRs read the tracking file's own git.pr (config_pr)
plugins/super-fr/skills/{fr-goal,fr-debugging}/SKILL.md (+ mirrors)
               ~ stealth: no per-phase push, first push at deliver open
tests/scenarios/alacarte-settings.sh, _ask_approve.sh   + candidate walk of the 3 rows
tests/unit/test_{workflow_available,pr_body_sections,settings_stealth,...}.py  + / ~
docs/reference/workflow-shapes.md, docs/explainers/{01-fr-goal,fr-debugging}.md  ~
.changes/feat-batch-s2-alacarte-settings.yaml           + bump: minor
```

```
binding a run to a shape:

fr run start <shape> ─┐
brainstorm `shape:` ──┼─> refuse_disabled(shape) ─ disabled? ─> WorkflowError
fr run adopt ─────────┘        (settings unreadable -> WorkflowError: fail closed)
advance / resolve / reshape ──> never checked (a started run keeps going)

stealth push:

fr push ─> push moves the remote? (read live: commits it adds, or the branch tip moves)
             ├ no ─> "nothing to push", exit 0, nothing asked
             └ yes ─> content scan + subject check ─> ask (Approve <id>) ─> push ─> consume
```

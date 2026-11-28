# S1 follow-ups: the end of the transition, configuration argv from the tip, test sites, the repos home

Batch `s1-followups` (super-fr#1698, #1699, #1700, #1701): the leftovers S1 (spec
`2026-11-19-event-driven-a-la-carte`, PR #1696) filed in its own configuration code.

## Background

S1 moved every repo configuration file into `.fr/` and, under quiet and stealth, onto a
configuration branch. It kept a transition (its R6, R13, R16): an old path is read with a
notice, the old settings copy (root `settings.yaml` on `fr`, `<target-dir>/settings.yaml` on
stealth's tracking branch) is written in step with the new one, and the per-kind
`FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR` and `FR_SHIPPED_LENSES_DIR` keep
working. Its owed entry `s1-refuse-old-paths` (#1698) ends all of that "in the first minor
release after the one that ships S1", detected by fr's own version.

S1's change fragment (`.changes/feat-event-driven-a-la-carte.yaml`, `bump: minor`) is still
pending: only `9.1.0-rc.N` candidates are cut, so S1 ships as **9.1.0** and the transition
ends in the **9.2** line. The operator chose a version gate in the code (decision
`q1-version-gated`), so this PR may merge before or after 9.1.0's final.

Today's readers of old paths:

- Python: `fr.config.space.legacy` / `located` (`packages/fr/src/fr/config/space.py:410-462`),
  the old switch `fr.placement.quiet._read_legacy` (`quiet.py:179`) and the stealth one, the
  legacy writes `quiet.write_legacy` (`quiet.py:1318`, called from the settings write at
  `quiet.py:1304`) and `stealth.write_legacy_target` (`stealth.py:906`), the lag and mismatch
  refusals (`quiet.legacy_lags`, `lag_refusal`, `mismatch_refusal`), `fr settings sync`
  (`commands/settings_cmd.py:478`, `quiet.sync_plan`/`sync_legacy`), and the per-kind shipped
  variables (`fr._shipped._legacy_dir`, `_shipped.py:128`).
- Shell: the edit-gate decision library `plugins/super-fr/hooks/lib/fr-isolation-decision.sh`
  (`FR_SWITCH_OLD`, line 386; the `.fr-isolation-allow` fallback, line 971), which the Claude
  Code hook and the Hermes hook both source; the OpenCode plugin
  (`packages/fr-opencode-plugin/src/marker.ts:213` and `:465`); and `scripts/validate-plans.sh`
  (the old `docs/superpowers/plan-config.yaml`, lines 89-97).

#1699 (p3-r6): S1's phase 4 (review p4-r3) already routes every repo workflow shape and
strategy through `fr.config.degraded.usable_bytes` (`workflow/resolve.py:119`,
`verification/resolve.py:116`), so under quiet and stealth the whole manifest, every argv
included, comes from the protected configuration branch's fetched tip, or the shipped one is
used. What is left: the walk exports only `argv[0]` from the tip (`verification/walk.py:368-401`,
`:484`), so a later argv element naming a `.fr/` file runs the checkout's copy; and a
`kind: cli` step's `run:` (`commands/run_cmd.py:6421-6445`) is a shell string run in the
product checkout, so a `.fr/` path in it runs an unreviewed file.

#1700 (p5-r4): about 40 lines in some 20 test files still set the per-kind variables.

#1701 (l-tests-r6): `fr.repos.DEFAULT_MANIFEST = Path.home() / ...` (`packages/fr/src/fr/repos.py:26`)
is evaluated at import; `commands/repos_cmd.py:43-47` uses it when `FR_REPOS_MANIFEST` is unset.

## Requirements

R1. One definition decides whether the transition has ended: `fr.config.transition.refusing()`,
true when fr's own release line (major, minor) is at or above `9.2`, or when the environment sets
`FR_OLD_PATHS=refuse` (an operator ending the transition early). No setting or variable keeps
the transition open past 9.2. Every Python reader below asks it, and nothing else compares a
version for this purpose.

R2. When the transition has ended, a reader that finds a configuration file only at its old
path (every `fr.artifacts.paths.CONFIG_KINDS` kind and the profile declarations, under every
placement) refuses: exit 2, naming the old path, the new path and `fr migrate artifacts --yes`.
Under quiet and stealth the old file the configuration branch's absence let a reader read is
refused the same way. Before the end the readers behave exactly as S1 left them.

R3. `fr migrate artifacts` reads and moves the old paths at every version: the refusal never
strands a repo that has not migrated.

R4. When the transition has ended, fr writes only the new settings file under quiet and stealth
(`fr-config:.fr/settings.yaml`, `<branch>-config:<target-dir>/.fr/settings.yaml`), never the old
copy; no reader reads the old copy, so the refusals for two differing copies and for a lagging
copy no longer fire; and a repo whose switch exists only at the old location is refused naming
`fr migrate artifacts --yes`. fr never deletes or rewrites the old copy.

R5. When the transition has ended, `fr settings sync` is gone from `fr settings --help` and,
invoked, exits 2 saying fr no longer keeps an old settings copy, so there is nothing to sync.

R6. When the transition has ended, a set `FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR`
or `FR_SHIPPED_LENSES_DIR` refuses the command that resolves that kind: exit 2, naming the
variable and `FR_SHIPPED_DEFAULTS_DIR/<kind>/` as its replacement.

R7. When the transition has ended, the shell readers stop reading old paths too: the edit gate
on Claude Code, Hermes (both through `fr-isolation-decision.sh`) and OpenCode no longer reads the
old `.fr-isolation-allow` or the old switch `origin/fr:settings.yaml` (or its stealth
counterpart), and drops the deny note about two differing switches; `validate-plans.sh` no longer
reads the old `docs/superpowers/plan-config.yaml`. They decide the end from their own release
version (the plugin's `plugin.json`, the OpenCode plugin's `package.json`) by the same rule as R1,
including `FR_OLD_PATHS=refuse`; a version they cannot read counts as ended. The hooks print
nothing about it; `validate-plans.sh` prints one line naming `fr migrate artifacts --yes` when it
ignores an old file. The `.fr-isolation-allow` name stays protected from an allowlist exemption.

R8. The gate's `9.2` is written once per language (Python, the shell library and
`validate-plans.sh`, TypeScript), and a test fails when they disagree, and when, while S1's change
fragment is still pending, `9.2` is not the minor line after the release that fragment will be in.

R9. Every test of transition behaviour states which side of the gate it tests (it forces the gate
or reads `refusing()` and asserts that side's behaviour), so a release that moves fr's version
into 9.2 turns none of them red. `tests/scenarios/config-homes.sh` asserts the side of the gate
its installed candidate is on.

R10. Under quiet and stealth, every element of a rendered walk argv (install or scenario, not
only `argv[0]`) that names a path in the configuration space runs from the exported, fetched,
protected tip, as `argv[0]` already does; under `repo` nothing changes.

R11. Under quiet and stealth, a `kind: cli` step whose rendered `run:` names a path under `.fr/`
is refused before it runs: exit 2, naming the step and the path, saying a shell command cannot be
pointed at the reviewed tip. Under `repo` nothing changes.

R12. Tests pin S1's whole-manifest guard: under quiet or stealth a repo workflow shape and a
repo strategy are taken from the fetched tip when the configuration branch is enforced (even when
the checkout's copy differs), and the shipped one is used when it is not.

R13. No test outside the ones that test the per-kind variables themselves sets
`FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR` or `FR_SHIPPED_LENSES_DIR`; the others
use `FR_SHIPPED_DEFAULTS_DIR`. A tripwire test enforces it.

R14. `fr repos sync`'s default manifest is `$HOME/.config/fr/repos.yaml` as `HOME` is when the
command runs, not when `fr.repos` was imported; `FR_REPOS_MANIFEST` still wins.

R15. The rules and pages that describe the transition (`plugins/super-fr/rules/fr-isolation-required.md`,
its repo mirror `.claude/rules/fr-isolation-required.md`, `AGENTS.md`, and every `.fr/docs.yaml`
page that names an old path, `fr settings sync` or a per-kind variable) say it ends in fr 9.2 and
what refuses then.

R16. The dormant transition code (the readers' pre-9.2 branches, `fr settings sync`, the old-copy
writers, the per-kind variables) is owed removal once a 9.2 final has shipped: an `owed` spec-journal
entry records it, filed at deliver.

## Design

### A. The gate (`fr/config/transition.py`, new)

```python
REFUSE_FROM: Final = (9, 2)          # S1 ships in 9.1; the transition is one minor line
ENV: Final = "FR_OLD_PATHS"          # only "refuse" means anything

def refusing() -> bool:
    if os.environ.get(ENV) == "refuse":
        return True
    return _line(fr.__version__) >= REFUSE_FROM   # an unparseable version: True

def old_path_refusal(old, new) -> TransitionError   # the one message (R2)
```

`_line` reads major and minor through the same PEP 440 / `-rc.N` spelling `fr.version_floor` reads,
so every 9.2 pre-release is already past the gate. Tests force either side by monkeypatching
`refusing` or `fr.__version__` (R9); the environment variable can only end the transition, never
extend it.

### B. Python readers

- `fr.config.space.legacy`: when `refusing()` and only the old path exists, raise
  `TransitionError` (a `SettingsError` subclass, so every command already turns it into exit 2)
  instead of the notice. `located`'s quiet/stealth branch that reads an old committed file while
  the configuration branch is absent takes the same path. `fr.config.migrate` and the artifact
  locators of the relocation kinds keep their own old-path reads (R3): they never go through
  `legacy`.
- `fr.placement.quiet` / `stealth`: `write_settings` skips `write_legacy` / `write_legacy_target`
  when `refusing()`; `_read_legacy` and the stealth reader return nothing to the switch readers,
  except to name the refusal when the new switch is absent and the old one present (R4);
  `legacy_lags`, `lag_refusal` and `mismatch_refusal` are not consulted.
- `fr settings sync`: registered `hidden=True` when `refusing()` at import of the command group,
  and its body checks `refusing()` first and exits 2 (R5).
- `fr._shipped._legacy_dir`: when `refusing()` and the variable is set, raise naming the
  replacement (R6); `env_dirs`' callers already surface resolver errors as exit 2.

### C. Shell readers

`fr-isolation-decision.sh` gains `_fr_transition_ended`: `FR_OLD_PATHS=refuse`, else the
`"version"` of `../../.claude-plugin/plugin.json` relative to the library, compared on
major.minor against `FR_REFUSE_FROM=9.2`; unreadable → ended. When ended, `_fr_read_switch`
reads only `FR_SWITCH_NEW`, the allowlist lookup reads only `.fr/isolation-allow`, and
`FR_SWITCH_DIFFER_NOTE` is never added. `marker.ts` mirrors it with its own `package.json`
version and `REFUSE_FROM = [9, 2]`. `validate-plans.sh` resolves its version the same way
(`plugins/super-fr/.claude-plugin/plugin.json` beside the marketplace `scripts/`) and skips the
old plan-config when ended, printing one line. One test (`tests/unit/test_transition_gate.py`)
reads all four literals and the pending fragment (R8).

### D. Configuration argv (#1699)

- `walk.render_template`: after rendering, every element `e` with `in_space(e)` (not only
  `argv[0]`) becomes `_program(e, ...)`'s exported path; `_protected` checks every element, so
  the protection question is asked before anything runs.
- `run_cmd` `kind: cli`: under quiet/stealth (`config_space(repo_root).placement != "repo"`), the
  rendered command is split with `shlex.split`; a token that is, or starts with, `.fr/` or `./.fr/`
  refuses with exit 2 before `run_step`. A command `shlex` cannot split is refused the same way
  under quiet/stealth (it cannot be shown to name no `.fr/` path).
- Pin tests (R12) against a stub forge answering enforced and free-plan 403, with the checkout's
  copy differing from the tip.

### E. Tests and the repos home

- #1700: every per-kind-variable site in `tests/` moves to `FR_SHIPPED_DEFAULTS_DIR` pointing at
  a tree with a `<kind>/` subdirectory, except `tests/unit/test_shipped_defaults_resolve.py`'s tests
  of the per-kind variables themselves, which now test both sides of the gate. The tripwire
  greps `tests/` for the three names and allows only that file (R13). The transcript fixture
  `tests/fixtures/transcripts/claude-code-session.jsonl` is captured data and is exempt.
- #1701: `fr.repos.default_manifest() -> Path` reads `Path.home()` per call; `DEFAULT_MANIFEST` is
  removed; `repos_cmd._manifest_path` calls it (R14).

## Design shape

```
packages/fr/src/fr/
  config/transition.py        + refusing(), REFUSE_FROM=(9,2), FR_OLD_PATHS, TransitionError
  config/space.py             ~ legacy()/located(): refuse past the gate (was: notice)
  placement/quiet.py          ~ write_settings: no write_legacy past the gate; old switch unread
  placement/stealth.py        ~ same for <target>/settings.yaml
  commands/settings_cmd.py    ~ `sync` hidden + exit 2 past the gate
  _shipped.py                 ~ per-kind FR_SHIPPED_*_DIR: refuse past the gate (was: notice)
  verification/walk.py        ~ every .fr/ argv element from the exported tip (was: argv[0])
  commands/run_cmd.py         ~ kind:cli run: naming .fr/ under quiet/stealth → exit 2
  repos.py                    ~ DEFAULT_MANIFEST → default_manifest() at call time
plugins/super-fr/hooks/lib/
  fr-isolation-decision.sh    ~ _fr_transition_ended (plugin.json, 9.2): drop old allow + old switch
packages/fr-opencode-plugin/src/marker.ts   ~ same, from package.json
scripts/validate-plans.sh     ~ old plan-config unread past the gate
tests/
  unit/test_transition_gate.py          + the four 9.2 literals agree; 9.2 = minor after S1's release
  unit/test_tripwire_shipped_env.py     + no per-kind FR_SHIPPED_*_DIR outside its own tests
  ~20 files                             ~ FR_SHIPPED_<KIND>_DIR → FR_SHIPPED_DEFAULTS_DIR
  scenarios/config-homes.sh             ~ asserts the side of the gate its candidate is on
  scenarios/s1-followups.sh             + FR_OLD_PATHS=refuse: every refusal, sync retired, argv guard
rules + docs                  ~ "ends in fr 9.2"
```

## Verification

strategy: candidate
- s1-old-paths-refused: candidate — a scenario runs the installed candidate with `FR_OLD_PATHS=refuse` in fixture repos holding old paths under each placement, and migrates them
- s1-old-settings-copy-retired: candidate — the scenario's quiet fixture writes settings with the gate ended and finds no old copy written, and `fr settings sync` exits 2
- s1-shell-readers-refuse: candidate — the scenario runs the candidate's hook library and `validate-plans.sh` with the gate ended against an old allowlist, an old switch and an old plan-config
- s1-config-argv-from-tip: candidate — the scenario walks under quiet with a stub forge answering enforced and a scenario argv naming a `.fr/` file, and advances a repo shape whose `kind: cli` step names `.fr/`
- repos-manifest-home-at-call: none — a unit test in CI changes `HOME` after import; no installed behaviour beyond it
gate: developer

## Out of scope

- Removing the dormant transition code: owed after 9.2 ships (R16).
- Default-branch protection under `repo` (#1697): a different trust question, not caused here.

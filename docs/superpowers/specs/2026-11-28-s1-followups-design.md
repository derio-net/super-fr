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

Today's readers and writers of the old forms (spec review sr-4, sr-5 corrected these names):

- Python, old paths: `fr.config.space.legacy` / `located` (`packages/fr/src/fr/config/space.py:410-462`).
  Two movers read the old plan-config themselves: `fr repos sync` (`commands/repos_cmd.py:65-97`,
  `located` at :83, writing the new file and removing the old at :93-96) and `fr repair`
  (`repair.py:337`).
- Python, the old settings copy: the switch readers that fall back to it are `quiet._read`
  (`placement/quiet.py:191-217`) and `fr.settings.load._stealth` (`settings/load.py:324-375`);
  `quiet._read_legacy` (`quiet.py:179`) reads only the old copy (tests, `fr settings init`). The
  writers are `quiet.write_switch` (`quiet.py:1251`, calling `write_legacy` at :1304) and
  `stealth.write_target_settings` (`stealth.py:862`, calling `write_legacy_target` at :906, defined
  at :1006), both reached through `fr.config.space.write_settings` (`space.py:273-303`). The
  refusals about the old copy: `legacy_lags`, `lag_refusal`, `mismatch_refusal` (`quiet.py:239-290`),
  the half-written checks (`quiet.py:420-436`; `settings_cmd.py:145-149, 216-229, 254-266, 441-447`),
  the migration's refusal naming `fr settings sync` (`artifacts/config_migration.py:216-219`), and
  `fr settings sync` itself (`settings_cmd.py:460-478`, `quiet.sync_plan`/`sync_legacy`).
  `quiet.switch_texts` and `stealth.target_settings_texts` are also read by `fr.config.migrate`
  (`config/migrate.py:363, 433-435`).
- Python, shipped defaults: `fr._shipped._legacy_dir` (`_shipped.py:128`), reached by each kind's
  resolver (`workflow/resolve.py:96`, `verification/resolve.py:47`, `lenses/resolve.py:30`), each of
  which raises its own error type. The lens resolver's "no shipped lens manifests" message offers
  `FR_SHIPPED_LENSES_DIR` (`lenses/resolve.py:46`).
- Shell: the edit-gate decision library `plugins/super-fr/hooks/lib/fr-isolation-decision.sh`
  (`FR_SWITCH_OLD` :386, `_fr_read_switch` :415, the switch-based fr-enabled test :443-468,
  `FR_SWITCH_DIFFER_NOTE` :756, the `.fr-isolation-allow` fallback :971), sourced by the Claude Code
  hook and by the Hermes hook, which `fr hermes install` copies to `~/.hermes/super-fr-hooks/`
  (`hermes.py:360`) away from any `plugin.json`; the OpenCode plugin (`packages/fr-opencode-plugin/src/marker.ts:211-241`,
  `:464-465`), delivered by `scripts/deliver-opencode-plugin.sh:138-140` as its `.ts` files only (no
  `package.json`); and `scripts/validate-plans.sh:89-100` (the old `docs/superpowers/plan-config.yaml`),
  byte-identical to the wheel copy `fr/data/validate-plans.sh` that `fr validate plans` runs. The
  script already reads `fr settings paths --shell` (`validate-plans.sh:66`).

#1699 (p3-r6): S1's phase 4 (review p4-r3) already routes every repo workflow shape and strategy
through `fr.config.degraded.usable_bytes` (`workflow/resolve.py:119-124`, `verification/resolve.py:125`),
so under quiet and stealth the whole manifest, every argv included, comes from the protected
configuration branch's fetched tip, or the shipped one is used. What is left: the walk exports
only `argv[0]` from the tip (`verification/walk.py:368-401`, `:480-485`), so another element
naming a `.fr/` file (relative, after `{repo}`/`{worktree}`, or embedded as `--x=.fr/y`) runs the
checkout's copy; and a `kind: cli` step's `run:` (`commands/run_cmd.py:6421-6445`) is a shell
string run in the product checkout, so a `.fr/` path anywhere in it runs an unreviewed file.

#1700 (p5-r4): 42 lines in 20 test files still set the per-kind variables.

#1701 (l-tests-r6): `fr.repos.DEFAULT_MANIFEST = Path.home() / ...` (`packages/fr/src/fr/repos.py:26`)
is evaluated at import; `commands/repos_cmd.py:43-47` uses it when `FR_REPOS_MANIFEST` is unset.

## Requirements

R1. One Python definition decides whether the transition has ended: `fr.config.transition.refusing()`,
true when fr's own release line (major, minor) is at or above `9.2`, or when the environment sets
`FR_OLD_PATHS=refuse` (an operator ending the transition early). No setting or variable keeps the
transition open past 9.2. Every Python reader below asks it; the shell and TypeScript readers apply
the same rule to their own release version (R7).

R2. When the transition has ended, a reader that finds a configuration file only at its old path
(every `fr.artifacts.paths.CONFIG_KINDS` kind and the profile declarations, under every placement)
refuses: exit 2, naming the old path, the new path and `fr migrate artifacts --yes`. Under quiet and
stealth the old committed file that the configuration branch's absence let a reader read is refused
the same way. Before the end the readers behave exactly as S1 left them.

R3. The movers read and move the old forms at every version, so the refusal never strands a repo:
`fr migrate artifacts` (including its reads of the old switch), `fr settings init --quiet` creating
`fr-config` from the old switch, `fr repos sync` moving the old plan-config, and `fr repair`.

R4. When the transition has ended, under quiet and stealth: fr writes only the new settings file
(`fr-config:.fr/settings.yaml`, `<branch>-config:<target-dir>/.fr/settings.yaml`), never the old
copy; the switch readers (`quiet._read`, `fr.settings.load._stealth`) do not read the old copy; no
refusal about the old copy fires (differing, lagging, absent or half-written), and no message names
`fr settings sync`; a repo whose switch exists only at the old location is refused naming
`fr migrate artifacts --yes`. fr never deletes or rewrites the old copy. Docstrings and stderr text
that promise the old copy is kept in step say so only for the pre-9.2 side.

R5. When the transition has ended, `fr settings sync` exits 2 saying fr no longer keeps an old
settings copy, so there is nothing to sync. It stays listed in `fr settings --help`, with a help
line that is the same on both sides of the gate and says it is retired in fr 9.2, so the generated
CLI tree does not change when the version crosses the gate.

R6. When the transition has ended, a set `FR_SHIPPED_WORKFLOWS_DIR`, `FR_SHIPPED_VERIFICATIONS_DIR`
or `FR_SHIPPED_LENSES_DIR` makes the command that resolves that kind exit 2, through that kind's own
error type, naming the variable and `FR_SHIPPED_DEFAULTS_DIR/<kind>/` as its replacement. No message
offers a per-kind variable on either side of the gate.

R7. When the transition has ended, the shell and TypeScript readers stop reading old forms: the edit
gate on Claude Code and Hermes (`fr-isolation-decision.sh`) and on OpenCode (`marker.ts`) no longer
reads the old `.fr-isolation-allow`, takes no placement from the old switch `origin/fr:settings.yaml`,
and adds no note about two differing switches; `validate-plans.sh` no longer reads the old
`docs/superpowers/plan-config.yaml`. Each decides the end from its own release version, read from a
version source that sits beside it in every delivered location: the plugin's `plugin.json` for the
Claude Code hooks, a `VERSION` file that `fr hermes install` writes beside the Hermes hook tree and
that `scripts/deliver-opencode-plugin.sh` writes into the delivered OpenCode plugin, and, for
`validate-plans.sh`, the `FR_OLD_PATHS_ENDED` key that `fr settings paths --shell` gains (R1's answer);
each also honours `FR_OLD_PATHS=refuse`. A version source that cannot be read counts as ended. The
hooks print nothing about it; `validate-plans.sh` prints one line naming `fr migrate artifacts --yes`
when it ignores an old file. The `.fr-isolation-allow` name stays protected from an allowlist exemption.

R8. When the transition has ended, a repo whose quiet switch exists only at the old location still
counts as fr-enabled to the edit gate (base-clone edits stay gated), but it is never taken as quiet
placement and its `fr`/`fr-config` worktrees are never write targets: the gate fails closed.

R9. The gate's `9.2` is written once per language (Python `fr.config.transition`, the shell library,
TypeScript `marker.ts`), and a test fails when they disagree, and when, while S1's change fragment is
still pending, `9.2` is not the minor line after the release that fragment will be in.

R10. A release that moves fr's version into 9.2 turns no test red. Every test of transition behaviour
states which side of the gate it tests: in-process Python tests force a side (monkeypatching
`refusing` or `fr.__version__`); shell and TypeScript tests force a side by the version source they
read (a fixture version file or plugin directory); subprocess and scenario tests force the ended side
with `FR_OLD_PATHS=refuse` and run a pre-9.2 side only while their fr is below 9.2, skipping it
otherwise. `tests/scenarios/config-homes.sh` asserts the side of the gate its installed candidate is
on. A test renders the generated CLI tree with the version forced into 9.2 and finds it unchanged.

R11. Under quiet and stealth, every element of a rendered walk argv (install or scenario) that is a
path in the configuration space, relative or absolute under the repo or worktree root, runs from the
exported, fetched, protected tip, as `argv[0]` already does; an element that holds a `.fr/` path
segment in any other form (`--x=.fr/y`) is refused before anything runs. Under `repo` nothing changes.

R12. Under quiet and stealth, a `kind: cli` step whose rendered `run:` holds a `.fr/` path segment
anywhere in the string is refused before it runs: exit 2, naming the step and the segment, saying a
shell command cannot be pointed at the reviewed tip. Under `repo` nothing changes.

R13. Tests pin S1's whole-manifest guard: under quiet or stealth a repo workflow shape and a repo
strategy are taken from the fetched tip when the configuration branch is enforced (even when the
checkout's copy differs), and the shipped one is used when it is not.

R14. Only the tests of the per-kind variables themselves set `FR_SHIPPED_WORKFLOWS_DIR`,
`FR_SHIPPED_VERIFICATIONS_DIR` or `FR_SHIPPED_LENSES_DIR`: `tests/unit/test_shipped_defaults_resolve.py`,
`tests/scenarios/config-homes.sh` and `tests/scenarios/s1-followups.sh`; every other test uses
`FR_SHIPPED_DEFAULTS_DIR`. "Sets" means an assignment, export, `setenv` or an environment-mapping key;
`unset` and `delenv` are hygiene and are allowed anywhere. A tripwire test enforces it; the captured
transcript `tests/fixtures/transcripts/claude-code-session.jsonl` is data and is exempt.

R15. `fr repos sync`'s default manifest is `$HOME/.config/fr/repos.yaml` as `HOME` is when the
command runs, not when `fr.repos` was imported; `FR_REPOS_MANIFEST` still wins.

R16. The rules and pages that describe the transition (`plugins/super-fr/rules/fr-isolation-required.md`,
its repo mirror `.claude/rules/fr-isolation-required.md`, `AGENTS.md`, and every `.fr/docs.yaml` page
that names an old path, `fr settings sync` or a per-kind variable) say it ends in fr 9.2 and what
refuses then.

R17. The dormant transition code (the readers' pre-9.2 branches, `fr settings sync`, the old-copy
writers, the per-kind variables, the version sources R7 adds) is owed removal once a 9.2 final has
shipped: an `owed` spec-journal entry records it, filed at deliver.

## Design

### A. The gate (`fr/config/transition.py`, new)

```python
REFUSE_FROM: Final = (9, 2)          # S1 ships in 9.1; the transition is one minor line
ENV: Final = "FR_OLD_PATHS"          # only "refuse" means anything

class TransitionError(SettingsError): ...   # every command already maps SettingsError to exit 2

def refusing() -> bool:
    if os.environ.get(ENV) == "refuse":
        return True
    return _line(fr.__version__) >= REFUSE_FROM   # an unparseable version: True

def old_path_refusal(old, new) -> TransitionError   # the one message (R2)
```

`_line` reads major and minor through the PEP 440 / `-rc.N` spellings `fr.version_floor` reads, so
every 9.2 pre-release is past the gate. `fr settings paths --shell` gains `FR_OLD_PATHS_ENDED=0|1`
(R7). The environment variable can only end the transition, never extend it; tests reach the open
side by monkeypatching in process or by a fixture version source (R10).

### B. Python readers and writers

- `fr.config.space.legacy`: when `refusing()` and only the old path exists, raise
  `old_path_refusal` instead of the notice. `located`'s quiet/stealth branch that reads an old
  committed file while the configuration branch is absent takes the same path. The movers (R3) do not
  call `located` for the old file: `repos_cmd` and `repair` read the old plan-config through a
  mover-only helper, `fr.config.space.old_path(root, kind)`, that never refuses.
- Old settings copy: `quiet._read` and `fr.settings.load._stealth` skip their old-copy fallback when
  `refusing()`, and, when the new switch is absent and the old one present, raise naming
  `fr migrate artifacts --yes`. `quiet.write_switch` and `stealth.write_target_settings` skip
  `write_legacy` / `write_legacy_target`; the differing, lagging, absent and half-written checks
  (`legacy_lags`, `lag_refusal`, `mismatch_refusal`, `half_written`, `finish_refusal`, `init_stealth`'s
  old-absent check) are not consulted, and no message names `SYNC_COMMAND`. `quiet.switch_texts`,
  `stealth.target_settings_texts`, `quiet._read_legacy` and `_create_from_old_switch` stay ungated for
  the movers.
- `fr settings sync`: its body checks `refusing()` first and exits 2; its registration and help line
  do not depend on the gate (R5).
- `fr._shipped._legacy_dir`: when `refusing()` and the variable is set, raise `LegacyEnvRefused`
  (a `TransitionError`); each resolver (`workflow`, `verification`, `lenses`) catches it and re-raises
  its own error type, which its commands already map to exit 2. The lens message names
  `FR_SHIPPED_DEFAULTS_DIR` only (R6).

### C. Shell and TypeScript readers

`fr-isolation-decision.sh` gains `_fr_transition_ended`: `FR_OLD_PATHS=refuse`, else the version from
`$lib/../../.claude-plugin/plugin.json` (Claude Code), else `$lib/../VERSION` (Hermes), compared on
major.minor against `FR_REFUSE_FROM=9.2`; neither readable means ended. When ended: the allowlist
lookup reads only `.fr/isolation-allow`; `_fr_read_switch` reads only `FR_SWITCH_NEW` for the
placement, but an old-only `FR_SWITCH_OLD` naming quiet still makes `_fr_placement_enabled` true
(gated, never a write target, R8); `FR_SWITCH_DIFFER_NOTE` is never added. `fr hermes install` writes
`VERSION` (fr's `__version__`) into `~/.hermes/super-fr-hooks/`. `scripts/deliver-opencode-plugin.sh`
writes `VERSION` (from `packages/fr-opencode-plugin/package.json`) into the delivered plugin, and
`marker.ts` reads it beside itself, with `REFUSE_FROM = [9, 2]` and the same rules. `validate-plans.sh`
reads `FR_OLD_PATHS_ENDED` from `fr settings paths --shell`; without a usable fr it counts as ended.
Tests per delivered location: the Claude Code plugin tree, the Hermes install tree and the delivered
OpenCode directory each read their version (R7). `tests/unit/test_transition_gate.py` reads the three
literals and the pending fragment (R9).

### D. Configuration argv (#1699)

A `.fr/` path segment is `(^|[^A-Za-z0-9_.-])\.fr/` in the string or element.

- `walk.render_template` / `_protected`: under quiet/stealth, before anything runs, every rendered
  element is classified: a path in the configuration space (relative, or absolute under the repo or
  worktree root, resolved to a repo-relative path) becomes `_program(...)`'s exported path; any other
  element holding a `.fr/` segment refuses (`WalkError`). `_protected` asks the protection question once
  for all of them. Under `repo` only today's `argv[0]` rule applies.
- `run_cmd` `kind: cli`: under quiet/stealth (`config_space(repo_root).placement != "repo"`), a rendered
  command holding a `.fr/` segment refuses with exit 2 before `run_step`. No shell parsing: the test is
  on the string, so `a;.fr/x`, `<.fr/x` and `--opt=.fr/x` are all caught.
- Pin tests (R13) against a stub forge answering enforced and free-plan 403, with the checkout's copy
  differing from the tip.

### E. Tests and the repos home

- #1700: every per-kind-variable site outside R14's three files moves to `FR_SHIPPED_DEFAULTS_DIR`
  pointing at a tree with a `<kind>/` subdirectory; `test_lenses_resolve.py`'s message assertion
  follows R6. `tests/unit/test_tripwire_shipped_env.py` scans `tests/` for assignments of the three
  names as R14 defines them.
- #1701: `fr.repos.default_manifest() -> Path` reads `Path.home()` per call; `DEFAULT_MANIFEST` is
  removed; `repos_cmd._manifest_path` calls it (R15).

## Design shape

```
packages/fr/src/fr/
  config/transition.py        + refusing(), REFUSE_FROM=(9,2), FR_OLD_PATHS, TransitionError
  config/space.py             ~ legacy()/located(): refuse past the gate (was: notice); + old_path() for movers
  settings/load.py            ~ _stealth: no old-copy fallback past the gate
  placement/quiet.py          ~ _read: no old-copy fallback; write_switch: no write_legacy; no sync/lag refusals
  placement/stealth.py        ~ write_target_settings: no write_legacy_target; no old-copy refusals
  commands/settings_cmd.py    ~ `sync` exits 2 past the gate (listed, help constant); init/paths: no sync hint
                                + `settings paths --shell` prints FR_OLD_PATHS_ENDED
  artifacts/config_migration.py ~ refusal no longer names `fr settings sync` past the gate
  _shipped.py                 ~ per-kind FR_SHIPPED_*_DIR: LegacyEnvRefused past the gate (was: notice)
  workflow|verification|lenses/resolve.py ~ map LegacyEnvRefused to their own error
  verification/walk.py        ~ every .fr/ element from the exported tip, other .fr/ forms refused
  commands/run_cmd.py         ~ kind:cli run: holding a .fr/ segment under quiet/stealth → exit 2
  commands/repos_cmd.py, repair.py ~ read the old plan-config through old_path() (movers)
  repos.py                    ~ DEFAULT_MANIFEST → default_manifest() at call time
  hermes.py                   ~ install writes VERSION beside the hook tree
plugins/super-fr/hooks/lib/
  fr-isolation-decision.sh    ~ _fr_transition_ended (plugin.json | ../VERSION, 9.2):
                                drop old allow + old switch placement; old-only switch stays gated
packages/fr-opencode-plugin/src/marker.ts   ~ same, from the delivered VERSION
scripts/deliver-opencode-plugin.sh          ~ writes VERSION into the delivered plugin
scripts/validate-plans.sh (+ wheel copy)    ~ FR_OLD_PATHS_ENDED: old plan-config unread past the gate
tests/
  unit/test_transition_gate.py          + the three 9.2 literals agree; 9.2 = minor after S1's release
  unit/test_tripwire_shipped_env.py     + no per-kind FR_SHIPPED_*_DIR set outside its own tests
  ~20 files                             ~ FR_SHIPPED_<KIND>_DIR → FR_SHIPPED_DEFAULTS_DIR
  scenarios/config-homes.sh             ~ asserts the side of the gate its candidate is on
  scenarios/s1-followups.sh             + FR_OLD_PATHS=refuse: every refusal, sync retired, argv guard
rules + docs                  ~ "ends in fr 9.2"
```

## Verification

strategy: candidate
- s1-old-paths-refused: candidate — a scenario runs the installed candidate with `FR_OLD_PATHS=refuse` in fixture repos holding old paths under each placement, and migrates them
- s1-old-settings-copy-retired: candidate — the scenario's quiet fixture writes settings with the gate ended and finds no old copy written, and `fr settings sync` exits 2
- s1-shell-readers-refuse: candidate — the scenario runs the candidate's hook library and `validate-plans.sh` with the gate ended against an old allowlist, an old-only switch and an old plan-config
- s1-config-argv-from-tip: candidate — the scenario walks under quiet with a stub forge answering enforced and a scenario argv naming a `.fr/` file, and advances a repo shape whose `kind: cli` step names `.fr/`
- repos-manifest-home-at-call: none — a unit test in CI changes `HOME` after import; no installed behaviour beyond it
gate: developer

## Out of scope

- Removing the dormant transition code: owed after 9.2 ships (R17).
- Default-branch protection under `repo` (#1697): a different trust question, not caused here.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-11-28-s1-followups | `derio-net/super-fr` | `2026-11-28-s1-followups` | — |

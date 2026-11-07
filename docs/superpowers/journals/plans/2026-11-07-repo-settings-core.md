<!-- fr:journal-schema=3 -->
# Journal: 2026-11-07-repo-settings-core

<!-- fr:journal kind=discovery scope=plan id=settings-policy-source created=2026-11-07T08:42:40+00:00 phase=1 -->
### settings-policy-source · discovery · load.py policy source: fully qualified ref by SHA; no HEAD fallback (phase 1)

load.py policy source: fully qualified ref by SHA; no HEAD fallback (plan step P1.T3.S1 corrected, security review). Remote default is refs/remotes/<remote>/<name> resolved once to a commit SHA and read with git show <sha>:path; without a remote the local default branch is refs/heads/<init.defaultBranch|main|master>; none found gives defaults with a note. HEAD and the working tree only feed the pending-edit note.

<!-- fr:journal kind=discovery scope=plan id=settings-yaml-on-off created=2026-11-07T08:42:40+00:00 phase=1 -->
### settings-yaml-on-off · discovery · PyYAML reads bare on/off as booleans (phase 1)

The documented values are the words on/off, but yaml.safe_load turns an uncommented `gates: off` into False. The model coerces True/False to on/off before validating, so the init file round-trips.

<!-- fr:journal kind=discovery scope=plan id=settings-driven-triage-definition created=2026-11-07T08:42:40+00:00 phase=1 -->
### settings-driven-triage-definition · discovery · R5 'driven triage scope' is read from .fr/triage.yaml keys (phase 1)

TriageConfig has no scope field, so push: ask is refused when the working-tree .fr/triage.yaml sets post_merge, export, version or post_merge_restart (the keys only the unattended batch driver acts on). Rules live in fr.settings.check.RULES as data.

<!-- fr:journal kind=discovery scope=plan id=settings-init-comment-convention created=2026-11-07T08:42:40+00:00 phase=1 -->
### settings-init-comment-convention · discovery · init prose uses ## so key lines uncomment by dropping one # (phase 1)

Prose lines start with ##, key lines with a single # followed by their indent, so removing one # from a key line yields valid YAML and prose stays a comment.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t1 created=2026-11-07T08:42:40+00:00 phase=1 -->
### no-refactor-p1-t1 · discovery · no-refactor-because P1.T1 (phase 1)

skeleton stubs only; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t4 created=2026-11-07T08:42:40+00:00 phase=1 -->
### no-refactor-p1-t4 · discovery · no-refactor-because P1.T4 (phase 1)

render, command and trigger edit were written minimal; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p1-t5 created=2026-11-07T08:42:40+00:00 phase=1 -->
### no-refactor-p1-t5 · discovery · no-refactor-because P1.T5 (phase 1)

a scenario script, a one-function test and a matrix row; nothing to clean

<!-- fr:journal kind=review scope=plan id=p1-review-1 created=2026-11-07T09:27:04+00:00 phase=1 -->
### p1-review-1 · review · Phase 1 code review: 5 low findings, all in scope, all fixed (phase 1)

Independent reviewer read the phase 1 diff (279d6c93..f769569f) against spec R2-R5. Policy source, closed model, coherence rules, init round-trip, trigger exemption, run-start refusal and conventions checked sound. Five low findings, fixed in 1442ec4fe..ca83576fd; full suite 14128 passed.

<!-- fr:journal kind=finding scope=plan id=p1-r1 created=2026-11-07T09:27:04+00:00 phase=1 state=open review_scope=in -->
### p1-r1 · finding [open] (reviewer: in scope) · load.py _show treats any git show failure as file absent (phase 1)

A corrupt object or git error on an existing .fr/settings.yaml silently yielded defaults.

<!-- fr:journal kind=finding scope=plan id=p1-r2 created=2026-11-07T09:27:04+00:00 phase=1 state=open review_scope=in -->
### p1-r2 · finding [open] (reviewer: in scope) · push-ask driven-triage check read the working tree and passed on parse error (phase 1)

A branch could edit .fr/triage.yaml to dodge the refusal; a malformed file passed.

<!-- fr:journal kind=finding scope=plan id=p1-r3 created=2026-11-07T09:27:04+00:00 phase=1 state=open review_scope=in -->
### p1-r3 · finding [open] (reviewer: in scope) · origin present but default unresolved fell back to a local branch (phase 1)

Unpushed local settings edits could act as policy; non-main origin/HEAD untested.

<!-- fr:journal kind=finding scope=plan id=p1-r4 created=2026-11-07T09:27:04+00:00 phase=1 state=open review_scope=in -->
### p1-r4 · finding [open] (reviewer: in scope) · schema: true passed Literal[1] (phase 1)

True == 1; closed model must refuse non-int.

<!-- fr:journal kind=finding scope=plan id=p1-r5 created=2026-11-07T09:27:04+00:00 phase=1 state=open review_scope=in -->
### p1-r5 · finding [open] (reviewer: in scope) · settings show truncated values to 40 chars (phase 1)

A long commit template was silently cut in the authoritative view.

<!-- fr:journal kind=finding scope=plan id=p1-r1-resolved created=2026-11-07T09:27:04+00:00 phase=1 state=fixed resolves=p1-r1 -->
### p1-r1-resolved · finding [fixed] · resolves p1-r1: load.py _show treats any git show failure as file absent (phase 1)

1442ec4fe: ls-tree distinguishes absent (None) from a read failure (SettingsError).

<!-- fr:journal kind=finding scope=plan id=p1-r2-resolved created=2026-11-07T09:27:04+00:00 phase=1 state=fixed resolves=p1-r2 -->
### p1-r2-resolved · finding [fixed] · resolves p1-r2: push-ask driven-triage check read the working tree and passed on parse error (phase 1)

e16758a77: .fr/triage.yaml read at the default-ref SHA via load.read_at_default; malformed file refuses; DRIVEN_TRIAGE_KEYS stated as the definition.

<!-- fr:journal kind=finding scope=plan id=p1-r3-resolved created=2026-11-07T09:27:04+00:00 phase=1 state=fixed resolves=p1-r3 -->
### p1-r3-resolved · finding [fixed] · resolves p1-r3: origin present but default unresolved fell back to a local branch (phase 1)

1442ec4fe: with a remote, only origin/HEAD then origin/<default> are read, else SettingsError with fetch/set-head hints; local fallback only with no remote. ca83576fd seeds origin/main in the cloud-triage scenario fixture.

<!-- fr:journal kind=finding scope=plan id=p1-r4-resolved created=2026-11-07T09:27:04+00:00 phase=1 state=fixed resolves=p1-r4 -->
### p1-r4-resolved · finding [fixed] · resolves p1-r4: schema: true passed Literal[1] (phase 1)

d4e2dd9bd: strict-int BeforeValidator refuses true and '1'.

<!-- fr:journal kind=finding scope=plan id=p1-r5-resolved created=2026-11-07T09:27:04+00:00 phase=1 state=fixed resolves=p1-r5 -->
### p1-r5-resolved · finding [fixed] · resolves p1-r5: settings show truncated values to 40 chars (phase 1)

25ccf734e: show prints full values.

<!-- fr:journal kind=decision scope=plan id=p2-disabled-wording created=2026-11-07T10:23:27+00:00 phase=2 -->
### p2-disabled-wording · decision · one constant, fr.settings.DISABLED, is the "disabled by repo setting" wording (phase 2)

Python surfaces read fr.settings.DISABLED / disabled_because(); the one shell hook (fr-acceptance-nag.sh) cannot import it, so test_one_wording_for_a_disabled_feature pins it to the constant and scans for any other spelling.

<!-- fr:journal kind=decision scope=plan id=p2-debt-disabled-source created=2026-11-07T10:23:27+00:00 phase=2 -->
### p2-debt-disabled-source · decision · debt reports acceptance-off as a read source with why=DISABLED, not unavailable (phase 2)

DebtReport schema 1 is frozen, so no field was added. The matrix source is state=read with why='disabled by repo setting'; render.py reads that to print the line and still prints 'No technical debt' when nothing else is owed.

<!-- fr:journal kind=discovery scope=plan id=p2-ledger-snapshot-repo created=2026-11-07T10:23:27+00:00 phase=2 -->
### p2-ledger-snapshot-repo · discovery · Checkout.snapshot_paths made a repo the settings loader could not resolve (phase 2)

The ledger read copies exit inputs into a fresh git repo with origin set and no refs; run_exit now asks disabled(root, 'gates'), and the loader refuses a remote whose default ref it cannot name. snapshot_paths now commits the copy and sets refs/remotes/origin/main + origin/HEAD, so the policy read there is the default branch's (.fr is already in EXIT_INPUTS). 45 fixture repos with an unreachable origin and no default ref (acceptance init, gate backfill, debt) needed tests.unit.settings_repo.seed_origin_default: the refuse-never-default principle reaches every command that now calls disabled().

<!-- fr:journal kind=discovery scope=plan id=p2-spec-policy-undecodable created=2026-11-07T10:23:27+00:00 phase=2 -->
### p2-spec-policy-undecodable · discovery · spec_policy_problems must tolerate an undecodable spec (phase 2)

test_exit_label_sync_points feeds a non-UTF-8 spec; the helper reads it, so UnicodeDecodeError is caught alongside OSError and left to the other validators to report.

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t1 created=2026-11-07T10:23:27+00:00 phase=2 -->
### no-refactor-p2-t1 · discovery · no-refactor-because P2.T1 (phase 2)

each guard is a one-line predicate call at an existing absence branch; nothing to clean

<!-- fr:journal kind=discovery scope=plan id=no-refactor-p2-t4 created=2026-11-07T10:23:27+00:00 phase=2 -->
### no-refactor-p2-t4 · discovery · no-refactor-because P2.T4 (phase 2)

a scenario script, one test registration and a matrix move; nothing to clean

<!-- fr:journal kind=review scope=plan id=p2-review-1 created=2026-11-07T11:44:31+00:00 phase=2 -->
### p2-review-1 · review · Phase 2 code review: 6 reviewer findings plus 1 orchestrator finding, all in scope, all fixed (phase 2)

Independent reviewer read 690740d77..17b27ac3f against R6-R8 and R15. The orchestrator reproduced a CI-checkout breakage separately (p2-o1). Fixes are c005700ae..c1b29e211. Full suite 14185 passed. A depth-1 PR-checkout simulation under CI passes, reading HEAD's committed tree. A security review of load.py tightened the bootstrap case to built-in defaults (spec decision settings-bootstrap-remote-2).

<!-- fr:journal kind=finding scope=plan id=p2-o1 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-o1 · finding [open] (reviewer: in scope) · A depth-1 CI PR checkout made fr acceptance check die with a SettingsError traceback (phase 2)

With no refs/remotes/origin/*, every disabled() call refused, which would turn this repo's acceptance-report job and every consumer's red on upgrade. Reproduced by simulating actions/checkout.

<!-- fr:journal kind=finding scope=plan id=p2-r1 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r1 · finding [open] (reviewer: in scope) · SettingsError surfaced as a raw traceback (exit 1) at most new call sites (phase 2)

status/digest, debt, plan_ops, proportionality, pr_body, archive, closeout, check, exit; triage ledger did not catch it.

<!-- fr:journal kind=finding scope=plan id=p2-r2 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r2 · finding [open] (reviewer: in scope) · A never-fetched remote blocked bootstrap writers (acceptance init/add, debt, archive, deliver) (phase 2)

seed_origin_default across fixtures masked the real state.

<!-- fr:journal kind=finding scope=plan id=p2-r3 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r3 · finding [open] (reviewer: in scope) · R15 incomplete: fr-plan, fr-spec-reviewer, fr-progress, fr-devops-gate did not read settings (phase 2)

fr-spec-reviewer would raise a missing Test Plan under test_plan: off.

<!-- fr:journal kind=finding scope=plan id=p2-r4 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r4 · finding [open] (reviewer: in scope) · spec_policy_problems elif reported only one problem (phase 2)

Two refuse cycles for a spec breaking both rules.

<!-- fr:journal kind=finding scope=plan id=p2-r5 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r5 · finding [open] (reviewer: in scope) · Test gaps in policy-off branches (phase 2)

spec-review/gates resolve, closeout_brief, digest/report/backfill/summary, _promote; weak pr_body/debt assertions.

<!-- fr:journal kind=finding scope=plan id=p2-r6 created=2026-11-07T11:44:31+00:00 phase=2 state=open review_scope=in -->
### p2-r6 · finding [open] (reviewer: in scope) · acceptance: off surface inconsistencies; nag hook spawned fr in every repo (phase 2)

check/summary said no matrix; staleness guard demanded rows; nag ordering regressed.

<!-- fr:journal kind=finding scope=plan id=p2-o1-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-o1 -->
### p2-o1-resolved · finding [fixed] · resolves p2-o1: A depth-1 CI PR checkout made fr acceptance check die with a SettingsError traceback (phase 2)

c005700ae, a8c242b44: R2 resolution order. In CI with no default ref, fr reads HEAD's committed tree and prints one notice, and EffectiveSettings.source is shown. Spec R2 amended (decision settings-ci-policy-source).

<!-- fr:journal kind=finding scope=plan id=p2-r1-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r1 -->
### p2-r1-resolved · finding [fixed] · resolves p2-r1: SettingsError surfaced as a raw traceback (exit 1) at most new call sites (phase 2)

de04e4703, 4096fb5f1: the root _FrGroup maps SettingsError to 'fr: settings: <msg>' and exit 2. The triage ledger turns it into TriageError. A subprocess test confirms there is no traceback.

<!-- fr:journal kind=finding scope=plan id=p2-r2-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r2 -->
### p2-r2-resolved · finding [fixed] · resolves p2-r2: A never-fetched remote blocked bootstrap writers (acceptance init/add, debt, archive, deliver) (phase 2)

a8c242b44, ef45816bd, e0b695b79: a remote with no tracking refs uses built-in defaults (never a local branch). acceptance init/add work. The seed_origin_default helper is removed and the fixtures exercise the real state.

<!-- fr:journal kind=finding scope=plan id=p2-r3-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r3 -->
### p2-r3-resolved · finding [fixed] · resolves p2-r3: R15 incomplete: fr-plan, fr-spec-reviewer, fr-progress, fr-devops-gate did not read settings (phase 2)

5e358e2b2: settings clauses added to fr-plan, fr-progress, fr-devops-gate and fr-spec-reviewer (which takes the settings output as input). Agents kind 2 to 3 with its migration. Mirrors regenerated. test_skills_read_settings guards R15.

<!-- fr:journal kind=finding scope=plan id=p2-r4-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r4 -->
### p2-r4-resolved · finding [fixed] · resolves p2-r4: spec_policy_problems elif reported only one problem (phase 2)

ca4de7bb6: every problem is reported.

<!-- fr:journal kind=finding scope=plan id=p2-r5-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r5 -->
### p2-r5-resolved · finding [fixed] · resolves p2-r5: Test gaps in policy-off branches (phase 2)

e237546b0: the listed branches are covered and the assertions strengthened.

<!-- fr:journal kind=finding scope=plan id=p2-r6-resolved created=2026-11-07T11:44:31+00:00 phase=2 state=fixed resolves=p2-r6 -->
### p2-r6-resolved · finding [fixed] · resolves p2-r6: acceptance: off surface inconsistencies; nag hook spawned fr in every repo (phase 2)

25d51858d: check, summary and status say disabled and exit 0. The staleness guard is silent under acceptance: off. The nag checks matrix.yaml first, and the OpenCode nag.ts port matches.

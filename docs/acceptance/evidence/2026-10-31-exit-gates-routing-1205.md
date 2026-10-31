# Accepted live driver-routing evidence: #1205

The independently accepted two-pass fixture walk proves the routing contract
of `exit-gates-driver-routing` (R13/R14, original Test Plan step 2). The dated
walk is **2026-10-31T06:34:40Z**, the completion second of the second actual
pass, under OpenCode with explicit configured model `openai/gpt-6.1-sol`.
This is not a backend-model attestation or successful `fr-goal` delivery.

References: [original #1205](https://github.com/derio-net/super-fr/issues/1205),
[#1195](https://github.com/derio-net/super-fr/pull/1195), and the public
fixture [issue #3](https://github.com/derio-net/super-fr-release-rehearsal-20261026/issues/3).
The native journal discharge of #1205 is separately authorized **before this
product evidence branch merges**. The proposed repository evidence is not yet
on product main; closing #1205 does not assert otherwise. Independent review
of this product branch, push and one draft PR remain coordinator-owned.

## Fixture chain and actual runtime

Repository: `derio-net/super-fr-release-rehearsal-20261026`, ID `1434822196`.
Four reviewed normal fixture merges were used; no fifth is authorized.

| Fixture PR | Head | Merge | Merged at (UTC) |
| --- | --- | --- | --- |
| [#4 setup](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/4) | `889400a2753f5c0139f3b0f685c5585aa4efcd3e` | `09ad7536d6fcfc134119f39508a11e87cc4d5364` | 2026-10-30T05:57:15Z |
| [#5 alignment](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/5) | `e241b95309cabb097ab7708691ccd8789e6bdbbe` | `2e554a69f8a0ac8a907402a79c33579f40cf92f4` | 2026-10-30T21:59:48Z |
| [#6 genuinely dispatched batch](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/6) | `e4b65108ed5c7449425f3cc27c0b07095790dcab` | `face5e98f67432063ad3010c19dbf54f9aa2614c` | 2026-10-31T05:03:51Z |
| [#7 first-hold evidence](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/7) | `35a95f1339f3944828e3baec6d97f5ce71f85584` | `a1631551d7605503a2c010db88499eecce6ad9dd` | 2026-10-31T05:32:25Z |

Both actual acting passes used the installed, unmodified **6.0.0rc15** native
`fr triage batch drive routing-1205 --once --keep-sessions --yes`, the dedicated
private queue and the genuine fixture primary checkout. All 362 runtime source
files matched release/tag commit `97db8586048da07a4c1a578d234b502efeecbdef`.
The genuine inherited identity pin was retained; no identity/migration bypass,
manual gate command or manual label swap was used. The synthetic fixture source
itself is not product-source-equivalence evidence.

One successful dispatch used target `ses_e71210cceffeiBPvi1x6z8VEG7`, `--auto`,
unfocused, with a genuine target-local answered operator question and one actual
read-only reviewer child `ses_e6fb0b02effe1D61HGm3FqPDsQ`. Its plan-prose finding
was fixed; no independent child rerun is claimed. Four native allocations in
total (three earlier failed attempts plus this success) were used; no more are
authorized. The target intentionally remains `deliver/running`, idle/unfocused,
with manual steps unticked and its genuine retention note untracked.

## First actual pass: held, open and not closed out

**2026-10-31T05:10:00.208701Z–05:10:17.873595Z**, exit **0**. Native effects were
only the existing claim-heartbeat refresh and addition of `fr:awaiting-live`.
PR #6 was merged with `verification:live` and `gate:tester`, not passed. Native
Needs you was `needs-tester`; its ledger cited `routing-1205-held-then-walked`
as unwalked, inherited Tester. Issue #3 stayed OPEN. Counts: merged 1, gated 1,
closing 0; one dispatch event, zero closeout records. The immediate nonacting
preview had no actions. Selected exact stdout is retained alongside this file.

Independent acceptance then authorized only the fixture row's historical first
hold walk at **2026-10-31T05:10:17Z**. PR #7 merged that walk before the second
pass. Its first-row CLI/autocommit execution narrative is **author-attested**:
the original raw invocation capture is not available. The reviewer verified
the resulting 550-row matrix (one changed, 549 unchanged), reports and first-hold
scope; this record does not upgrade that limitation into raw CLI evidence.

## Second actual pass: automatic pass from merged main

**2026-10-31T06:34:24.751529Z–06:34:40.990073Z**, exit **0**, exactly one second
acting call. The pre-pass default-branch ledger still held Tester but now read
the cited row as walked, inherited from the run's live kind. The reviewed native
plan SHA-256 was `1e4a56c98fe0714524e0262f369f6520f723e857780a24d307825c2b9f300eec`.

The driver automatically removed `gate:tester`, added `gate:tester-passed`,
and posted [comment 6540141711](https://github.com/derio-net/super-fr-release-rehearsal-20261026/pull/6#issuecomment-6540141711)
at **2026-10-31T06:34:38Z**:

```text
<!-- fr:gate-pass tester -->
The **tester** gate passed: every row the tester gate gates reads walked (routing-1205-held-then-walked)
```

Issue #3 remained OPEN with `fr:awaiting-live`, `fr:claimed`, `fr:in-progress`.
The actual pass still reported closing 0; executed closeout records remained
**zero**. The subsequent **dry run** proposed a closeout and reported closing 1;
it explicitly said nothing done. That proposal was **not executed**. There were
two actual acting passes total, not three. An earlier read-only identity probe
timed out at 30 seconds without an acting call; the later bounded read-only
probe succeeded before this one actual second pass.

The RC15 source route is default-branch rows via `_ledgers` / `_gated_rows`
(`commands/triage_batch_cmd.py`), `_gate_actions` (`triage/batch_drive.py`), then
the driver's `_pass_gate` and `verification.labels.pass_gate` (native comment
before label swap). This is automatic driver routing, not a direct invocation
of the callable as a substitute for the actual native drive command.

## Independent acceptance, receipts and limits

Reviewer `ses_e6fa16643ffewnUs94wY6erI1F` independently accepted the first hold,
then the held → walked-on-merged-main → automatic-pass chain and stop before
closeout, with no in-scope blockers. Checks covered 42 first-packet hashes,
33 completed-second-packet hashes, 28 recheck hashes, exact RC15 sources and
fresh forge corroboration. First-packet `act-once.py` mode 0644 was corrected
by the coordinator to 0600 without a content-hash change. Completed-second
manifest SHA-256: `4c406143e578e4aca9fd4874416c8749bd66e64d7a4fa209e52b7f2b0b949fc8`.

`2026-10-31-exit-gates-routing-1205/` retains three byte-exact native stdout
receipts, a labeled normalized ledger/effects projection, and source hashes.
Public PRs, merge heads and the native comment above supplement those receipts;
proof does not depend only on a private packet path. Fresh forge reads during
product preparation corroborate merged heads/comment/labels, but are not new
acting-pass observations or their timestamps. Local-only-state and unplaced-issue
warnings remain warnings, not prerequisites invented after acceptance.

Private additional packets live under
`/Users/derio/.cache/fr/coord/artifacts/derio-net-recovery-2026-10-14/release-control-2026-10-24/1205/`:
`first-routing-acting-pass-20261031T050853Z`,
`second-routing-acting-pass-COMPLETED-20261031T063332Z`, and
`second-routing-pass-recheck-20261031T063229Z`.
New product status/journal command captures are retained separately in
`product-routing-1205-evidence-preparation-20261031T070615Z/correct-host-route/`.
No credentials, environment values, unrelated panes or wholesale packet dumps
are included in this repository evidence.

This discharges **only original Test Plan step 2 / #1205**. #1204's earlier
walk/resolution is unchanged; #1206 collected-closeout and other outstanding
walks remain owed. Overall #1195 and #1217 Tester gates remain held. No full
suite, completed target delivery, closeout, original gate pass, release, cleanup,
extra fixture merge, allocation or further acting pass is claimed or authorized.

## Product recording and authorized native discharge

The product row was recorded once using the supported `uv run fr acceptance
set-status` inside the original `dev` isolation container: start
**2026-10-31T07:17:53.489781Z**, end **07:18:03.161902Z**, exit 0. It moved only
`exit-gates-driver-routing` to `walked`, appended the passing `live` /
`opencode` / `openai/gpt-6.1-sol` walk at **2026-10-31T06:34:40Z**, regenerated
all three reports, and committed the generated artifacts. No row was hand-edited.

The forge-writing operation used the logged-in **host** `gh` naturally through
the installed `/Users/derio/.local/bin/fr` from the same valid isolated worktree,
not host `uv run`. Its identity was RC15 and all 362 installed source files
matched the worktree/release closure before invocation. No credentials were
copied, token values printed, global credential settings changed, pin altered,
or identity/migration bypass used. Earlier container credential-route failures
are retained privately; they did not execute either mutation.

Exactly one native `fr journal resolve --scope spec --slug
2026-10-14-exit-gates --id test-plan-step-2 --state fixed --note <accepted public
fixture chain and proposed product evidence>` ran **07:18:41Z–07:18:51Z** on
2026-10-31, exit 0. It appended only
`test-plan-step-2-resolved-2` to the existing archived spec journal (record time
**07:18:43Z**), with the original journal byte-prefix and all prior entries
preserved. No active replacement journal was created.

The native command posted [discharge comment 6540531941](https://github.com/derio-net/super-fr/issues/1205#issuecomment-6540531941)
at **07:18:48Z** and closed **#1205 at 07:18:50Z**, as expressly authorized
before product evidence merge. Fresh before/after reads corroborate the exact
owed marker, original OPEN state, one new native discharge comment and CLOSED
state. This is an actual native effect, not a printed close suggestion or a
standalone manual `gh issue close`. The comment explicitly identifies the
product evidence as proposed and not yet merged.

Full command argv, stdout/stderr, exit and timing captures, matrix/journal
snapshots and pre/post hashes for both mutations are retained in the private
preparation archive named above. This new product recording does not inherit
the older fixture CLI-capture gap.

Local verification:

- `fr acceptance check`: **561 rows OK**; 19 walk-owed, 35 walked. Parsed
  comparison with base verifies exactly one changed row and **560 unchanged**.
  #1204's row is unchanged; #1206's row is still `walk-owed`.
- `fr acceptance report --check`: all three reports synchronized.
- `fr journal check --scope spec --slug 2026-10-14-exit-gates`: exit 0;
  step 3 / #1206 and step 4 / #1207 remain owed; the existing #1197 deferral
  remains. The scoped fold confirms only step 2 was newly discharged.
- `fr validate artifacts`: **34 artifacts valid**.
- `pytest tests/unit/test_journal_owed.py -q --no-cov`: **23 passed**; this is
  focused bookkeeping validation, not a full suite or another live walk.
- The three selected native stdout SHA-256 values match their source packets;
  the normalized projection preserves held/walked/automatic-pass/no-closeout
  distinctions. `git diff --check` passes. No product source/version/run changed.

Fresh product forge reads still show #1195 and #1217 with `gate:tester`, no
passed label; #1206 remains OPEN / `fr:owed`. No original gate was passed and
no additional forge write was performed beyond the one native #1205 discharge.
Independent product-branch review and draft publication are **not yet done**.

# Ops gate probes — implementation plan

Spec: `docs/superpowers/specs/2026-11-01-ops-gate-probes-design.md` (super-fr#1273).

Three agentic phases. Each one serves a separately reviewable ask:

1. **The gap** (R1–R5, R7), the skeleton. It covers:
   - the `Step` pointer and raw lines;
   - the `none:` acknowledgement, which is the `ops` artifact kind 1→2 with a stamp-only migration, the validator, and `fr migrate artifacts --yes`;
   - `fr.ops.gap`;
   - the advisory warnings at self-review and spec review;
   - stage 1's refusal on a scratch tree materialised from the PR head.

   Its first task is the smoke: the new candidate scenario wired into CI.
2. **Probes** (R6, R8–R10). It covers:
   - full probe output through the runner, plus the `output`/`evidence` fields;
   - stage 5's answer grammar and re-prompt loop;
   - pointed steps run through `fr ops status <id> --json`.
3. **Stubs and prose** (R11, R12): `fr ops stub`, the fr-plan and fr-devops-gate skills with their mirrors, `docs/ops.md`, and the change fragment (minor).

Files owned by the parallel runs are not touched: `fr/artifacts/trigger.py`, `fr/gates.py`, `fr/debt/`.

Long suites run only through `bash ~/.cache/fr/coord/testslot.sh -- <cmd>`. Run targeted tests per step.

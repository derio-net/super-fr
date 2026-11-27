# Queue follow-ups — implementation plan

Spec: `docs/superpowers/specs/2026-11-27-queue-followups-design.md` (batch `queue-followups`:
super-fr#1680, #1676, #1663, #1695).

Two agentic phases, one per independently reviewable ask group:

1. **Driver timing and probe** (R4–R8: #1695, #1676, #1663) — the skeleton. Its first task is the
   trivial #1695 fix plus the change fragment, pushed so CI is green on a trivial change before the
   larger work lands. Then the conflict probe's classification, the queue-landed close-out rule, the
   wave-wide wait, and the pacer's deadline.
2. **Approval lifecycle** (R1–R3: #1680) — `hard`: it changes the approval gate every queue merge
   relies on. Ended approvals, the new `Waiting` verdict, its board and readiness wording, and the
   void comment. It also carries the docs update.

Both phases touch `triage_batch_cmd.py` and `batch_drive.py`, which batch `closeout-state` (#1726)
also changes; whichever lands second resolves the queue's conflict hand-back.

No member issue is a phase `tracking_issue`.

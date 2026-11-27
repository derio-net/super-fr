# Split the wave-export and hand-back leaves out of triage/batch_drive.py

Spec: `docs/superpowers/specs/2026-11-27-triage-leaves-split-design.md` (super-fr#1516).

One agentic phase: a cut-and-paste refactor of `fr/triage/batch_drive.py` into three homes,
with no behaviour change.

- `fr/triage/batch_drive_types.py` (new, stdlib only): the value types the pass and its
  leaves share (`ChecksVerdict`, `ActionKind`, `LivePr`, `Admitted`, `Action`, `CONFLICTING`,
  `_wrong_base`). This module breaks the import cycle the export leaf would otherwise form.
- `fr/triage/batch_drive_export.py` (new): the wave-export section (§I step 3b).
- `fr/triage/handback_rules.py` (existing): the remaining hand-back decisions, beside the
  conflict and red decisions that moved there earlier.

`batch_drive.py` re-exports every moved name, so no caller changes. A new test pins the
import direction and the re-exports first (RED). The two purity guards widen to every module
of the pass, the module budget drops, and the four docs pages that cover the touched files
get their `reviewed` stamps.

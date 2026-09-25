# Flat agent-step evidence debt

This plan fixes issue #605 with a narrow state-source correction. Flat agent
units store dispatch attempts and evidence under `step/<id>`, while their
completion state remains on the parent `StepRecord`. Grouped members continue
to use unit-record state. Tests cover both the check and status reports, plus
the no-debt case when obligations are met.

The single small phase uses `skeleton-override-small-flat-step-fix`: splitting
this one-line state-source defect into a separate walking-skeleton phase would
add a dispatch and handoff without exercising a distinct runtime path.

# Herdr OpenCode lifecycle and batch replacement

Implement the reviewed spec's two independently reviewable asks. Phase 1 delivers
OpenCode launch/control/restart, with the walking smoke inside its first task.
Phase 2 delivers an audited, serialized replacement transaction and its CLI.
Both use hard tier because they mutate live terminal processes and depend on
crash-safe state coordination. No manual implementation phase is necessary:
the operator client-live walk is a pre-merge verification obligation.

Keep host control sessions in primary checkouts, branch work in isolation, and
durable run state as the recovery contract. Preserve Claude resume behavior.
Never manufacture a second dispatch to record replacement; never use a target
process alone as evidence its reconstruction prompt was accepted.

All builds/tests run through fr isolation exec; git/forge I/O and fr run resolve
run on the host. Any final suite log must be host-visible, outside step-record
directories and newer than the final code commit. Synthetic protocol scenarios
are not live interactive evidence. Real migration remains operator-driven through
client-live; leave Ready guard boxes unchecked and retain Refs #1089 while owed.

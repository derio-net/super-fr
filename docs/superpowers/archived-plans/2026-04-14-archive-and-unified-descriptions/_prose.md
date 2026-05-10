# Archive And Unified Descriptions Implementation Plan

## Phase 0: Impact audit across repos

### Task 1: Enumerate title/label/body consumers

- P0.T1.S1: Grep for slug-phase-tag title regex consumers

- P0.T1.S2: Grep for vk-ready / vk-synced / in-progress / pr-ready label consumers

- P0.T1.S3: Enumerate open Issues with old-format titles across derio-net repos

- P0.T1.S4: Confirm bridge is singleton

- P0.T1.S5: Check willikins transition script for title parsing

### Task 2: Write the audit report

- P0.T2.S1: Write the report

- P0.T2.S2: Commit the audit

## Phase 1: Dispatch output — titles, body, labels, validator

### Task 1: Body builder — tracking block and dash-prefixed deps

- P1.T1.S1: Add failing test for tracking block in body

- P1.T1.S2: Add failing test for dash-prefixed Blocked by

- P1.T1.S3: Update _build_issue_body signature and body composition

- P1.T1.S4: Update all existing tests for new signature

- P1.T1.S5: Update dispatch_cmd.dispatch() call site

### Task 2: Title builder — human-readable format

- P1.T2.S1: Add failing test for new title format

- P1.T2.S2: Update _build_issue_title signature

### Task 3: Structured labels on create

- P1.T3.S1: Add failing integration test for structured labels

- P1.T3.S2: Add structured labels in dispatch loop

### Task 4: Body validator

- P1.T4.S1: Write failing tests for validator

- P1.T4.S2: Implement the validator

- P1.T4.S3: Wire validator into dispatch apply loop

### Task 5: Remove quiet git-commit swallow

- P1.T5.S1: Write failing test for git commit failure propagation

- P1.T5.S2: Remove the silent except

### Task 6: Inject issue URL into tracking block after create

- P1.T6.S1: Write failing test that Issue body is updated with its own URL

- P1.T6.S2: Add gh.edit_issue_body helper

- P1.T6.S3: Call edit_issue_body after create in dispatch loop

## Phase 2: Archive-on-Complete in vk progress sync

### Task 1: Add plan.archive_to config key

- P2.T1.S1: Failing test for archive_to default and override

- P2.T1.S2: Add archive_to to PlanConfig

### Task 2: Archive flow in sync

- P2.T2.S1: Failing test — sync-to-Complete offers archive prompt

- P2.T2.S2: Failing test — dry-run shows "Would archive"

- P2.T2.S3: Failing test — destination collision refused

- P2.T2.S4: Implement _archive_plan helper in progress_cmd.py

- P2.T2.S5: Wire into sync() after Status write

### Task 3: Update spec index file path on archive

- P2.T3.S1: Failing test — spec index file: column reflects archive path

- P2.T3.S2: Implementation already handled

## Phase 3: vk dispatch migrate

### Task 1: Scaffold subcommand

- P3.T1.S1: Failing test — subcommand registered

- P3.T1.S2: Convert dispatch to a subcommand group

### Task 2: Migrate logic

- P3.T2.S1: Failing test — missing tracking comment aborts

- P3.T2.S2: Implement migrate — tracking-comment collection and validation

- P3.T2.S3: Failing test — dry-run prints diff

- P3.T2.S4: Implement dry-run flow

- P3.T2.S5: Failing test — --yes applies edits and aborts on gh failure

- P3.T2.S6: Implement --yes apply path

## Phase 4: Skill and documentation updates

### Task 1: Update vk-execute skill

- P4.T1.S1: Failing test — skill mentions pr-ready label and unified PR title

- P4.T1.S2: Update the skill

### Task 2: Update vk-dispatch skill

- P4.T2.S1: Document migrate and unified title

### Task 3: Update vk-progress skill

- P4.T3.S1: Document archive-on-Complete

## Phase 5: Operational migration

### Task 1: Verify bridge changes deployed

- P5.T1.S1: Confirm bridge-fail-loud plan is archived

- P5.T1.S2: Confirm the running bridge script matches the agent-images source

### Task 2: Migrate Frank hextra plan

- P5.T2.S1: Dry-run migrate

- P5.T2.S2: Apply migrate

- P5.T2.S3: Confirm bridge ingests phase 1, defers others

### Task 3: Migrate remaining open plans

- P5.T3.S1: Enumerate open plans across repos

- P5.T3.S2: Migrate each candidate

### Task 4: Verify bridge behavior end-to-end

- P5.T4.S1: Confirm dep-gating active across all repos

- P5.T4.S2: Mark this plan Complete

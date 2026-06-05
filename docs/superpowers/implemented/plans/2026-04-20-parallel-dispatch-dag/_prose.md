# Parallel Dispatch DAG Implementation Plan

## Phase 1: Parser, dispatch emission, structural validation

### Task 1: `Phase.depends_on` field + parser line extraction

- P1.T1.S1: Write failing tests for the parser's ` Depends on:**` extraction**

- P1.T1.S2: Run the tests to confirm they fail

- P1.T1.S3: Add `depends_on` to the `Phase` dataclass

- P1.T1.S4: Implement the parser extraction

- P1.T1.S5: Run the tests to confirm they pass

- P1.T1.S6: Quality gates

- P1.T1.S7: Commit

### Task 2: Writer round-trip for `**Depends on:**`

- P1.T2.S1: Write a failing round-trip test

- P1.T2.S2: Run the tests to confirm they fail

- P1.T2.S3: Emit ` Depends on:**` in the writer**

- P1.T2.S4: Run the tests to confirm they pass

- P1.T2.S5: Quality gates

- P1.T2.S6: Commit

### Task 3: Dispatch emits one `- Blocked by #N` per declared dep + `phased-dag.md` fixture

- P1.T3.S1: Create the fan-in/fan-out fixture

- P1.T3.S2: Write failing unit tests for multi-blocker body emission

- P1.T3.S3: Write a failing integration test for a fan-in dispatch

- P1.T3.S4: Run the tests to confirm they fail

- P1.T3.S5: Refactor `_build_issue_body` to accept `blocker_nums`

- P1.T3.S6: Update `dispatch_create` to compute `blocker_nums` from `depends_on`

- P1.T3.S7: Update `migrate` to use the same signature

- P1.T3.S8: Run the tests to confirm they pass

- P1.T3.S9: Quality gates

- P1.T3.S10: Commit

### Task 4: Body validator relaxation

- P1.T4.S1: Write failing tests for the relaxed validator

- P1.T4.S2: Run the tests to confirm they fail

- P1.T4.S3: Relax the validator

- P1.T4.S4: Run the tests to confirm they pass

- P1.T4.S5: Quality gates

- P1.T4.S6: Commit

### Task 5: Structural DAG validators in self-review and dispatch --dry-run

- P1.T5.S1: Write failing tests for `validate_dag`

- P1.T5.S2: Run the tests to confirm they fail

- P1.T5.S3: Implement `validate_dag`

- P1.T5.S4: Wire `validate_dag` into `vk plan self-review`

- P1.T5.S5: Wire `validate_dag` into `vk dispatch --dry-run`

- P1.T5.S6: Run the tests to confirm they pass

- P1.T5.S7: Quality gates

- P1.T5.S8: Commit

## Phase 2: Migration tooling, strict enforcement, execute, docs, version bump

### Task 1: `vk plan convert --add-deps` + `phased-no-deps.md` fixture

- P2.T1.S1: Create the no-deps fixture

- P2.T1.S2: Write failing unit tests

- P2.T1.S3: Write a failing integration test

- P2.T1.S4: Run the tests to confirm they fail

- P2.T1.S5: Implement `add_deps` in `convert.py`

- P2.T1.S6: Wire the `--add-deps` flag in `plan_cmd.py`

- P2.T1.S7: Run the tests to confirm they pass

- P2.T1.S8: Quality gates

- P2.T1.S9: Commit

### Task 2: Strict missing-line enforcement (live plans only)

- P2.T2.S1: Write failing tests

- P2.T2.S2: Run the tests to confirm they fail

- P2.T2.S3: Detection — track whether the line was present during parsing

- P2.T2.S4: Extend `validate_dag` to accept `plan_path` and enforce missing-line for live plans

- P2.T2.S5: Update self-review and dispatch --dry-run to pass `plan_path`

- P2.T2.S6: Run the tests to confirm they pass

- P2.T2.S7: Quality gates

- P2.T2.S8: Commit

### Task 3: `vk execute check-deps` reads the declared DAG

- P2.T3.S1: Write failing integration tests

- P2.T3.S2: Run the tests to confirm they fail

- P2.T3.S3: Rewrite `check_deps`

- P2.T3.S4: Run the tests to confirm they pass

- P2.T3.S5: Quality gates

- P2.T3.S6: Commit

### Task 4: `vk dispatch migrate` refusal guard

- P2.T4.S1: Write a failing integration test

- P2.T4.S2: Run the test to confirm it fails

- P2.T4.S3: Implement the guard in `migrate`

- P2.T4.S4: Run the test to confirm it passes

- P2.T4.S5: Quality gates

- P2.T4.S6: Commit

### Task 5: Skill docs + version bump 1.1.0

- P2.T5.S1: Update `skills/vk-plan/SKILL.md`

- P2.T5.S2: Update `skills/vk-dispatch/SKILL.md`

- P2.T5.S3: Update `skills/vk-execute/SKILL.md`

- P2.T5.S4: Bump the version in three files

- P2.T5.S5: Update the version test

- P2.T5.S6: Resync the lockfile

- P2.T5.S7: Verify the CLI reports the new version

- P2.T5.S8: Run the full test suite and quality gates

- P2.T5.S9: Commit

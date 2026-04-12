# Large Phased Plan

**Spec:** `docs/superpowers/specs/2026-02-15-big-feature.md`
**Status:** In Progress

**Goal:** A larger phased plan with multiple tasks per phase.

---

## Phase 1: Foundation [agentic]

### Task 1: Database schema

**Files:**
- Create: `migrations/001_init.sql`
- Test: `tests/test_schema.py`

- [ ] **Step 1: Write schema test**

Create `tests/test_schema.py` with table existence checks.

- [x] **Step 2: Create migration**

Write the SQL migration file.

- [x] **Step 3: Run migration**

Apply and verify.

### Task 2: Configuration loader

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

Test YAML loading with defaults.

- [ ] **Step 2: Implement config module**

Build the config loader.

## Phase 2: API Layer [agentic]

### Task 1: REST endpoints

**Files:**
- Create: `src/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write API tests**

Test endpoint responses.

- [ ] **Step 2: Implement endpoints**

Build the REST handlers.

### Task 2: Authentication middleware

**Files:**
- Create: `src/auth.py`
- Test: `tests/test_auth.py`

- [ ] **Step 1: Write auth tests**

Test token validation.

- [ ] **Step 2: Implement auth middleware**

Build the authentication layer.

## Phase 3: Deployment [manual]

### Task 1: CI/CD pipeline

- [ ] **Step 1: Create workflow file**

Write `.github/workflows/deploy.yml`.

- [ ] **Step 2: Configure secrets**

Set up repository secrets for deployment.

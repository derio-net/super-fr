# Loose-Format Flat Plan

**Spec:** `docs/superpowers/specs/example.md`
**Status:** Not Started

**Architecture:** A small Ansible role that ships one Python script.

**Tech Stack:** Ansible, Python, Molecule

**Goal:** Exercise the loose step-header format real plans use in the wild.

---

### Task 1: Scaffold the role [agentic]

**Files:**
- Create: `roles/demo/tasks/main.yml`
- Edit: `playbooks/site.yml`
- Test: `cd roles/demo && molecule test`

- [ ] **Step 1: Create `roles/demo/tasks/main.yml`** documenting the role.
  ```yaml
  ---
  - name: Hello
    ansible.builtin.debug:
      msg: hi
  ```

- [ ] **Step 2: Commit the scaffold.**
  ```bash
  git add roles/demo
  git commit -m "demo: scaffold"
  ```

### Task 2: Pre-flight verification [agentic]

- [ ] **Step 0.1: Dotted-label step**
  ```bash
  echo "checking prereq"
  ```

- [ ] **Step 0.2: Another dotted step**
  More prereq work.

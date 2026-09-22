# Scaffold batch: refuse unknown tools, JVM toolchain, per-arch host CLIs, mode from state

- **Date:** 2026-09-23
- **Status:** designed
- **Origin:** gh#574, gh#576, gh#569
- **Goal:** `fr init scaffold` never accepts input it cannot honour. It ships a
  JVM toolchain at the project's own Java version and installs glab/tea for the
  container's real architecture. `fr isolation` addresses a workspace by the
  mode it was created in, not by the caller's environment.

## 1. Problem

The three issues share one shape: **fr accepts input, reports success, and does
nothing useful with it.**

1. **gh#574.** `scaffold_profile` (`fr/isolation/scaffold.py`) splits `tools`
   into `known` and `unknown`. Unknown tools only reach a `notes:` string in
   `.devcontainer/fr-profiles.yaml`. The CLI still prints `scaffolded:` and
   exits 0. `--tool java --tool maven` wrote `"features": {}`, and the first
   `fr isolation exec -- mvn test` failed with `executable file not found`.
   `KNOWN_TOOL_FEATURES` has no JVM entry at all.
2. **gh#576.** `HOST_CLI_POST_CREATE` hardcodes `linux_amd64` assets and their
   amd64 checksums for glab 1.107.0 and tea 0.14.2. A profile scaffolded on an
   arm64 host runs an arm64 container. The download therefore installs the
   wrong binary, or fails a checksum with an error that says nothing about
   architecture. The source comment already calls this "a known gap". It also
   asks a human to remember to reconfirm the pins.
3. **gh#569.** `_target()` (`fr/commands/isolation_cmd.py`) picks the backend
   from `FR_ISOLATION_TARGET` on every command. A workspace created under
   `FR_ISOLATION_TARGET=worktree` records `profile="host"`. A later `exec`
   without that variable goes to the devcontainer target and fails:
   `.devcontainer/host/devcontainer.json not found`. Dispatched phase executors
   do not inherit the operator's environment, so on a docker-less workspace
   their first `exec` breaks.

## 2. Goal

- An unrecognised `--tool` fails loudly. It names the known set and writes
  nothing. An explicit `--feature <ref>` escape covers toolchains fr does not
  map.
- `--tool java`, `--tool maven` (Maven implies Java) and `--tool <t>@<version>`
  produce working features. When the Java version is not given explicitly, it
  is detected from the repo (pom.xml and version files).
- glab/tea postCreate resolves the architecture in the container, uses a
  per-arch checksum, and fails naming the architecture when it is unsupported.
  A scheduled workflow checks that every pinned asset still resolves to its
  checksum.
- Every `fr isolation` command that addresses an existing workspace takes that
  workspace's mode from its recorded state. `FR_ISOLATION_TARGET` is consulted
  only when no workspace exists to consult: `up`, `gc`, and a `verify-merge`
  whose workspace was already reaped.

Non-goals: validating a profile's free-text purpose against its features
(gh#574's "consider" item). Bumping the pinned glab/tea versions. Gradle, Ant
and Groovy (the java feature's other build tools stay unexposed until asked
for).

## 3. Design

### A. Tool resolution (gh#574)

`KNOWN_TOOL_FEATURES: dict[str, str]` becomes a table of `ToolSpec` entries:
feature ref, fixed options, and the option key a `@version` sets.

| tool | feature | fixed options | `@version` sets |
|---|---|---|---|
| uv, node, python, go, rust, terraform, docker-in-docker, kubectl | (unchanged refs) | — | `version` |
| java | `ghcr.io/devcontainers/features/java:1` | — | `version` |
| maven | `ghcr.io/devcontainers/features/java:1` | `installMaven: true` | `mavenVersion` |

- `--tool <name>[@<version>]`. A pure function `resolve_tools(tools, features)
  -> dict[ref, options]` runs **before any file is written**. Tools that map to
  the same feature merge their options, so `java` + `maven` produce a single
  java feature with Maven. The same option set to two different values (for
  example `java@17` + `java@21`) is refused. `installMaven` is a JSON boolean,
  as the feature's own manifest declares it.
- **Unknown tool → `IsolationError` (exit 2).** The message names the rejected
  tool, lists the sorted known set, and points at `--feature`. No
  devcontainer.json, no fr-profiles.yaml entry, no secrets file, no commit. The
  unknown-tool `notes:` path in `_update_profiles_yaml` is deleted, since
  nothing can reach it any more.
- **`--feature <ref>`** (repeatable) adds a raw devcontainer feature ref with
  `{}` options. The ref must be non-empty and contain no whitespace. Anything
  beyond that is the devcontainer CLI's business at `up` time.
- **Java version detection.** If the resolved features include the java
  feature and no `java@<v>` was given, `detect_java_version(repo_root) ->
  (version, source) | None` reads the first hit, in this order:
  1. `.java-version`;
  2. `.sdkmanrc` (`java=17.0.9-tem`);
  3. `.tool-versions` (`java temurin-17.0.9`);
  4. the root `pom.xml`: properties `maven.compiler.release`,
     `maven.compiler.target`, `maven.compiler.source`, `java.version`, then the
     `maven-compiler-plugin` `<release>` / `<target>`. One level of
     `${property}` indirection is resolved. XML namespaces are handled.

  Versions are normalised to the major (`1.8` → `8`, `17.0.9` → `17`). A hit is
  written as the feature's `version` and reported on stderr as `java 17 (from
  pom.xml maven.compiler.release)`. No hit keeps the feature default and warns
  `java version not detected — the java feature's default (latest) will be
  used; pass --tool java@<major> to pin it`. Explicit `@version` always wins.
- **Project notes** (README, CONTRIBUTING, CI workflows) require judgement, so
  they belong to the **fr-init skill**. Its interview confirms the Java version
  it found there, and the scan result, and passes it explicitly as
  `--tool java@<major>`. The skill text is updated with the new known set, the
  `@version` form, `--feature`, and this confirmation step. The OpenCode and
  Hermes mirrors are regenerated.

### B. Per-architecture host CLIs (gh#576)

`HOST_CLI_POST_CREATE` becomes data plus a renderer. `HostCliPin` holds the
name, version, per-arch asset URL, per-arch sha256 and the install recipe
(tarball or bare binary). Only `amd64` and `arm64` are carried. The checksums
were captured 2026-09-23 from each project's published `checksums.txt` for the
already-pinned versions:

| cli | arch | asset | sha256 |
|---|---|---|---|
| glab 1.107.0 | amd64 | `glab_1.107.0_linux_amd64.tar.gz` | `eb42f56e…d5ae2c` |
| glab 1.107.0 | arm64 | `glab_1.107.0_linux_arm64.tar.gz` | `8356e442…7b35ba` |
| tea 0.14.2 | amd64 | `tea-0.14.2-linux-amd64` | `be4ab135…a19cc3` |
| tea 0.14.2 | arm64 | `tea-0.14.2-linux-arm64` | `f201f6ba…b34568` |

The rendered snippet runs in a subshell. It resolves
`arch=$(dpkg --print-architecture 2>/dev/null || uname -m)` and normalises
`x86_64`→`amd64` and `aarch64`→`arm64`. A `case` selects the URL and checksum.
Any other architecture does `echo "<cli> <ver>: unsupported architecture
'<arch>' (supported: amd64 arm64)" >&2; exit 1` **before any download**. The
subshell is the last command of `postCreateCommand`, so its exit status is the
postCreate's status.

**Scheduled pin check.** `scripts/check-pinned-clis.py` imports the pins from
`fr.isolation.scaffold`. It downloads every (cli, arch) asset, compares sha256,
prints one line per asset and exits non-zero on any mismatch or fetch failure.
`.github/workflows/pinned-clis.yml` runs it weekly, on `workflow_dispatch`, and
on PRs that touch `scaffold.py` or the script. This replaces the comment's "a
human should reconfirm" with a check that fails on its own.

### C. Mode from state (gh#569)

- **The field.** `IsolationState` gains `target: Literal["devcontainer",
  "worktree", "external"] | None = None`. Each target's `up` writes its own
  value.
- **Where the state lives, and why legacy inference is permanent.** The state
  file is `<git-common-dir>/fr/isolation/<branch>.json` (`types.py`
  `state_path`). It is not a registered artifact kind, and the model is not
  `extra="forbid"`, so an older `fr` loads the new field without refusing. But
  an older `fr` on `PATH` also **rewrites** the file. `fr-session-bind.sh` →
  `sessions.attach` → `save_state` drops the key it does not know. So `target`
  can vanish from a new workspace at any time, and legacy inference is
  **permanently load-bearing**, not a transitional fallback.
- **Pure mode resolution.** `recorded_mode(state)` lives in
  `fr/isolation/types.py` and is pure:
  - `state.target` when set;
  - otherwise `profile == "host"` → `worktree`;
  - `profile == "external"` → `external`;
  - anything else → `devcontainer`.
- **Target construction.** `target_for_state(state, runner, gc_spawner)` lives
  in a new `fr/isolation/routing.py`, which imports all three target classes.
  - An `external` mode is adopted through `ExternalTarget.detect` as today. If
    no valid marker plus container evidence is found, it fails closed with an
    `IsolationError` naming the workspace. It never falls through to
    devcontainer.
  - The environment variable is never read here.
  - `isolation_cmd._target_for(root, state)` is the single monkeypatchable seam
    over it. `_target` (env-based) stays for the host-level commands.
- **Routed by the recorded mode:**
  - `exec`, `restart`;
  - `down --branch`, `down --worktree` (the path `fr-worktree-remove.sh` calls,
    which never sets the variable);
  - `down --all`, per workspace, including its `_down_refusal` probe;
  - `status`, per row, where the `--stats`/`--push-check` refusal also runs per
    row. A set containing any host or external workspace is refused naming it,
    same wording as today. `status` over zero workspaces selects no target at
    all;
  - `verify-merge` when the workspace exists.
- **Still on the environment variable** (only the host to go on): `up`, `gc`'s
  discovery and docker sweep, and `verify-merge` for an already reaped
  workspace.
- **gc's per-workspace teardown follows the recorded mode too.** In
  `local.py`'s gc, the reap sibling and its dry-run hazard probe are built
  with `type(self)(…)`. That is the sweeping class, not the workspace's, so a
  host-worktree sweep reaping a devcontainer workspace would skip
  `_teardown_container` and leak the container (the #354 leak). The sibling is
  now built through `routing.target_for_state`, with a function-local import to
  avoid the `hostworktree → local` cycle.
- **The background gc keeps its mode.** `_detached_gc_spawn` starts `python -m
  fr isolation gc` with the caller's environment. After this change, a `down`
  on a host-worktree workspace run *without* the variable (the exact #569 case)
  would therefore start a devcontainer sweep. On a docker-less pod,
  `_labelled_containers` would raise `FileNotFoundError` and kill it. So each
  target spawns gc with `FR_ISOLATION_TARGET` set to its own mode:
  `HostWorktreeTarget` → `worktree`, the devcontainer target → `devcontainer`.
- **`host` becomes a reserved profile name.** `fr init scaffold --profile host`
  is refused. Because legacy inference is permanent (above), this is what keeps
  a real devcontainer profile from ever being misrouted. It also retires the
  confusing `.devcontainer/host/devcontainer.json not found` message at its
  root.

### D. Housekeeping

- **Version:** minor bump (new `--feature` flag and `@version` syntax).
- **Code shape the change forces:**
  - `features` is typed `dict[str, dict[str, object]]`, since `installMaven`
    is a bool;
  - the `containerEnv` uv check keys on the *parsed* tool name, so it survives
    `uv@x`;
  - `init_cmd` prints its errors on stderr, matching the detection report;
  - the tests pinning the old notes path and `HOST_CLI_POST_CREATE`'s keys
    (`test_init_scaffold.py` ~334/484) are rewritten.
- **Prose:**
  - the `fr-init` skill: known set, `@version`, `--feature`, and the Java
    version confirmation;
  - the `fr-isolation` skill: `FR_ISOLATION_TARGET` selects the mode at `up`,
    and later commands follow the workspace's recorded mode;
  - AGENTS.md's `--tool` wording, if present;
  - both mirror generators (`sync-opencode.py` **and** `sync-hermes.py`);
  - the explainers, checked for scaffold/isolation-mode prose.
- **Acceptance:** rows are added (§5). The existing rows `multibackend-scaffold`
  and `isolation-host-worktree-e2e` get notes updated via `fr acceptance
  set-status` where their text now misdescribes behaviour.
- **Pin-check script:** run through `uv run`, so the `fr.isolation.scaffold`
  import resolves. Downloading and hashing each asset is the check itself.
  Comparing against upstream `checksums.txt` is not added, because a match
  there proves nothing the hash does not.

## 4. Risks

- **Java feature distro.** Not a risk. The feature's default `jdkDistro` is
  `ms`, and its own `install.sh` (lines 279-287 upstream) switches to `tem`
  when `ms` lacks the requested major (for example 8). No `jdkDistro` override
  is needed.
- **A failed postCreate leaves debris.** `local.py` raises on a non-zero
  `devcontainer up` before `save_state`, so the worktree and container remain
  with no fr state. This is not new. The unsupported-architecture exit makes it
  reachable on purpose, but only on architectures other than amd64 and arm64.
  Deferred to gh#578, not fixed here.
- **dpkg absent.** The `uname -m` fallback covers non-Debian images. Any other
  spelling fails naming itself. That failure is the intended one.
- **Scheduled check flakiness** (network). It fails the run, which GitHub
  notifies on. It does not gate merges outside PRs that touch the pins.
- **Mixed modes on one host.** A devcontainer workspace and a host-worktree
  workspace for the same repo are now each addressed correctly. Before this
  change, one of them was always wrong.

## 5. Test Plan

**In this PR:**

1. Unit `resolve_tools`: every entry in the tool table reaches `features`
   (parametrised over the table itself); java+maven merge into one feature with
   `installMaven: true`; `maven` alone implies java; conflicting `@version`s are
   refused; an unknown tool is refused and names the known set; `--feature`
   passes through.
2. Unit scaffold: `--tool nosuchtool` writes nothing (no devcontainer.json,
   fr-profiles.yaml, env file or commit) and exits 2; `--profile host` is
   refused.
3. Unit `detect_java_version`: each source, the precedence between them,
   `${prop}` indirection, a namespaced pom, `1.8`→`8`, none found; explicit
   `@version` overrides detection; the stderr report and warning.
4. Unit host-CLI snippet, **executed** under `sh` (what devcontainer runs
   `postCreateCommand` with: dash on the Ubuntu base image) with stub
   `dpkg`/`uname`/`curl`/`sha256sum`/`tar`/`sudo` on `PATH`:
   - amd64 and arm64 each select their own URL and checksum;
   - `x86_64` and `aarch64` normalise;
   - `s390x` exits non-zero, names `s390x`, and never calls `curl`;
   - a failing `sha256sum` fails the whole snippet.
5. Unit isolation CLI: with `FR_ISOLATION_TARGET` unset, `exec`, `restart`,
   `status`, `down --branch`, `down --worktree`, `down --all` and
   `verify-merge` on a `target="worktree"` state route to the host-worktree
   target.
   - The reverse case also holds: a devcontainer state is not rerouted when the
     env says worktree.
   - Legacy states with no `target` infer from `profile`, for `host`,
     `external` and a named profile.
   - An external state without a marker fails closed.
   - `status --stats` over a host row is refused.
   - `up` and `gc` still follow the env.
   - Existing tests the design changes are rewritten, not deleted: the
     bogus-env tests for `status` and `down --all` (`test_isolation_cmd.py`
     ~1411/1428) now assert that the env is ignored there, and still fail
     closed for `up`/`gc`. The stubs over `isolation_cmd._target` move to
     `_target_for` for the addressing commands.
5a. Unit gc: a reap sibling is built from the workspace's recorded mode, not
    the sweeper's class. The spawned gc carries the spawning target's
    `FR_ISOLATION_TARGET`.
5b. Unit `recorded_mode` is pure, and `IsolationState` round-trips `target`.
6. Integration `test_hostworktree_lifecycle`: `up` under
   `FR_ISOLATION_TARGET=worktree`, then `exec` with the variable removed,
   succeeds.
7. **Live, on this arm64 host, via `fr isolation exec`, output pasted in the
   PR:** a scratch repo with a `pom.xml` pinning Java 17, scaffolded with
   `--tool java --tool maven`, runs `mvn -v` and `java -version` (showing 17). A
   scratch profile with `--backend gitlab` runs `glab --version`, and one with
   `--backend gitea` runs `tea --version`, both arm64. `fr init scaffold --tool
   nosuchtool` shows the refusal. A host-worktree workspace runs `exec` without
   the variable.
8. `scripts/check-pinned-clis.py` run locally, all four assets OK.
9. Skill validation, neutrality and all three mirror tripwires green;
   `fr acceptance check` green; full suite green.

**Post-merge, operator-driven:**

10. Trigger `pinned-clis.yml` by `workflow_dispatch` on `main` and confirm the
    first scheduled run is green.

## 6. Evidence hygiene

The live proofs use scratch repos with fictional names under the session
scratchpad. glab and tea are fetched from their public upstream projects. The
Java/Maven repo that triggered gh#574 is third-party and is referenced only as
"a Java/Maven repo (identity redacted)", as the issue already does.

## Implementation Plans

| Plan | Repo | File | Depends on |
|------|------|------|------------|
| 2026-09-23-scaffold-batch-574-576-569 | `derio-net/super-fr` | `2026-09-23-scaffold-batch-574-576-569` | — |

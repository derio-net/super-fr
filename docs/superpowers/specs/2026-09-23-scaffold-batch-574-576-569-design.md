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

- `IsolationState` gains `target: Literal["devcontainer", "worktree"] | None =
  None`. `LocalWorktreeDevcontainerTarget.up` writes `"devcontainer"` and
  `HostWorktreeTarget.up` writes `"worktree"`. The state file lives under
  `~/.cache` and is not a registered artifact kind. The model is not
  `extra="forbid"`, so an older `fr` ignores the key instead of refusing.
- `_target_for(root, state)`: a valid external marker is checked first, as
  today. Otherwise `state.target` decides. A legacy state with `target=None`
  maps `profile == "host"` to worktree and anything else to devcontainer. The
  environment variable is never read.
- Routed through `_target_for`: `exec`, `restart`, `down`, `down --all` (per
  workspace, including its refusal probe), `status` (per row) and
  `verify-merge` when the workspace exists. Still on the environment variable:
  `up`, `gc` (a host-wide sweep, not tied to one workspace) and `verify-merge`
  for a reaped workspace. Each one has only the host to go on.
- **`host` becomes a reserved profile name.** `fr init scaffold --profile host`
  is refused. The legacy inference above therefore cannot misroute a real
  devcontainer profile. It also retires the confusing
  `.devcontainer/host/devcontainer.json not found` message at its root.

### D. Housekeeping

Minor version bump (new `--feature` flag and `@version` syntax). The fr-init
skill and both mirrors are updated. AGENTS.md's `--tool` wording is updated if
it still says "known tools map to features". The explainers are checked for
fr-init/scaffold prose. Acceptance rows are added (§5).

## 4. Risks

- **Java feature distro.** The feature's default `jdkDistro` (`ms`) may not
  ship every major. `8` in particular is not a Microsoft build. The live proof
  uses 17. The detection warning names the version, so a failure at `up` is
  attributable. Changing the distro is left to the operator through
  `--feature`.
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
4. Unit host-CLI snippet, **executed** under `bash` with stub `dpkg`/`curl`/
   `sha256sum`/`tar`/`sudo` on `PATH`: amd64 and arm64 each select their own
   URL and checksum; `x86_64`/`aarch64` normalise; `s390x` exits non-zero, names
   `s390x`, and never calls `curl`.
5. Unit isolation CLI: with `FR_ISOLATION_TARGET` unset, `exec`, `status`,
   `down`, `down --all`, `restart` and `verify-merge` on a `target="worktree"`
   state route to the host-worktree target. The reverse case also holds (a
   devcontainer state is not rerouted when the env says worktree). A legacy
   state with no `target` infers from its profile. `up` and `gc` still follow
   the env.
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

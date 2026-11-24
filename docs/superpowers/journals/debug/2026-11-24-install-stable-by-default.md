<!-- fr:journal-schema=4 -->
# Journal: 2026-11-24-install-stable-by-default

<!-- fr:journal kind=repro scope=debug id=65526d9e4f90 created=2026-11-24T13:16:06+00:00 -->
### 65526d9e4f90 · repro · install.sh from a main clone and the cloud setup script install the RC, not the latest stable

Operator ran `scripts/install.sh` in the base clone on `main` (HEAD `0bf258293 release: v9.0.0-rc.1`). `fr --identity` then reported `9.0.0rc1` from the clone, and `installed_plugins.json` listed super-fr `9.0.0-rc.1`. For the same tags, bootstrap.sh resolves the default to v8.2.0 and `--version RC` to v9.0.0-rc.1. `packages/fr/src/fr/data/cloud-setup.sh` runs `checkout -B main origin/main` and then install.sh, so cloud sessions get the RC too.

<!-- fr:journal kind=root-cause scope=debug id=5e87812ad7fc created=2026-11-24T13:16:07+00:00 -->
### 5e87812ad7fc · root-cause · Only bootstrap.sh resolves a channel; install.sh and cloud-setup.sh follow main, which the release bot makes an RC

Spec 2026-10-14-exit-gates R22 gave bootstrap.sh the channels (default = newest installable vX.Y.Z). R23 kept install.sh installing "the checkout it runs from" (main in sync with origin/main, or a detached v* tag). release.py commits `release: vX.Y.Z-rc.N` straight onto main while a gate is pending, so main HEAD is the RC. Any installer that follows main follows RCs: install.sh run in a clone on main, and cloud-setup.sh, which hard-codes main. bootstrap.sh also falls back to origin/main when no stable tag is installable.

<!-- fr:journal kind=decision scope=debug id=e19657cf647a created=2026-11-24T13:16:09+00:00 -->
### e19657cf647a · decision · Operator: every install path gets the latest stable by default; RC/main only via an explicit --version

Operator decisions (2026-11-24): (1) install.sh on main with no --version delegates to bootstrap's channel resolution: it installs the newest stable tag from bootstrap's managed checkout and leaves the clone untouched. `--version` takes bootstrap's values, and `--version main` installs the checkout itself. (2) The wave driver's post_merge becomes `./scripts/install.sh --version main` (it keeps dogfooding main, explicitly). (3) bootstrap.sh with no installable stable refuses instead of falling back to main. This amends exit-gates R22/R23.

<!-- fr:journal kind=finding scope=debug id=install-release-installs-main created=2026-11-24T13:23:24+00:00 state=fixed -->
### install-release-installs-main · finding [fixed] · A fourth path: the cloud driver's self-update installed main, not the release it named

`triage_drive_cmd._install_release(release)` checked that origin/main contained the release tag, then ran install.sh on main. So a reinstall of the latest stable release installed main HEAD, which is an RC while a gate is pending. Fixed: it runs origin/main's bootstrap.sh `--version <release>` from memory against the managed clone, which installs exactly that tag. The "tag must be on main" refusal existed only because install.sh installed nothing but main; bootstrap's own refusal (unknown or unmarked tag) replaces it. Pinned by tests/unit/test_triage_drift.py::test_install_release_installs_the_release_not_mains_newer_head.

<!-- fr:journal kind=finding scope=debug id=stable-by-default created=2026-11-24T13:23:26+00:00 state=fixed -->
### stable-by-default · finding [fixed] · Every install path installs the newest stable release unless --version asks for another

install.sh: a new channel block before the install lock. No --version on anything but a clean checkout detached at a v* tag delegates to bootstrap.sh (run from memory, FR_SRC_REMOTE = the clone's origin, FR_INSTALL_DELEGATED guards a loop). `--version main` installs the checkout under the existing preflight, and any other --version goes to bootstrap. bootstrap.sh: with no installable final it refuses and names `--version RC` / `--version main`; its main channel passes `--version main` to install.sh. cloud-setup.sh runs origin/main's bootstrap.sh instead of checking main out. .fr/triage.yaml post_merge is now `./scripts/install.sh --version main`. Tests: tests/integration/test_install_channels.py (install_sh_on_main_installs_the_newest_stable_release, _version_rc_, _forwards_other_flags_, _refuses_to_delegate_twice, cloud_setup_script_installs_the_newest_stable_release, no_marked_final_installs_nothing_..., main_channel_tells_install_sh_..., wave_drivers_post_merge_installs_main_explicitly). Red first: the install.sh test printed `Channel: main`.

<!-- fr:journal kind=review scope=debug id=86e0f1e147a3 created=2026-11-24T13:47:57+00:00 -->
### 86e0f1e147a3 · review · Independent review (code-reviewer subagent): nothing serious; 4 points fixed, the rest refuted or out of scope

Fixed: (1) `git tag --points-at | grep -q` under pipefail could lose git to SIGPIPE and read a tagged checkout as untagged; now read into a variable first. (2) FR_INSTALL_DELEGATED leaked into the whole install; unset after the hand-off. (3) stale test comments. (4) new test: --uninstall never delegates. Refuted: quoting `set -- ${arr[@]+"${arr[@]}"}`; the quoted form turns an empty array into one empty argument, and the spaced-argument test passes under macOS bash 3.2. Accepted as designed: a managed clone left detached at an RC installs that RC when its install.sh runs directly (the explicit tag-checkout path); bootstrap `--uninstall` with no stable release refuses (only a fork with no release reaches it; install.sh --uninstall in the clone still works). Out of scope, pre-existing: an ls-remote failure reads as "no installable release" (fails safe); an existing managed clone ignores FR_SRC_REMOTE.

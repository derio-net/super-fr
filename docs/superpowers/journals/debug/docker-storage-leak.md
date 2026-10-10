# Journal: docker-storage-leak

<!-- fr:journal kind=repro scope=debug id=178eaa209c0f created=2026-10-10T19:36:47+00:00 -->
### 178eaa209c0f · repro · Docker Desktop VM disk 90% full; 21.3 GB of volumes have zero links

Host: macOS, Docker Desktop. `docker run --rm alpine df -h /` → 58.4G size, 49.7G used, 5.7G free (90%). `docker system df`: images 15.11GB (12.16 reclaimable), containers 2.5GB (8 running, all live fr workspaces with valid .fr-isolation markers, created 2026-10-10 by the triage batch), **local volumes 21.34GB, 34 volumes, 0 active, 100% reclaimable**, build cache 1.38GB. Largest: `dind-var-lib-docker-0g3pv9…` = 18.74GB (created 2026-06-10, no labels, LINKS 0).

<!-- fr:journal kind=hypothesis scope=debug id=077b232f53a6 created=2026-10-10T19:36:51+00:00 -->
### 077b232f53a6 · hypothesis · Running containers are leaked workspaces

Mapped every container's devcontainer.local_folder label to its worktree.

<!-- fr:journal kind=ruled-out scope=debug id=8de6d6c027d2 created=2026-10-10T19:36:57+00:00 -->
### 8de6d6c027d2 · ruled-out · Running containers are leaked workspaces: ruled out

All 8 containers point at existing ~/.cache/fr/worktrees/<repo>/<branch> dirs with a .fr-isolation marker and a matching branch. They are live triage-batch workspaces (2.5 GB), not orphans. vsc-* images are likewise all referenced by a live container.

<!-- fr:journal kind=hypothesis scope=debug id=d969c18fcd0b created=2026-10-10T19:37:08+00:00 -->
### d969c18fcd0b · hypothesis · fr isolation down leaves the docker-in-docker named volume behind

packages/fr/src/fr/isolation/local.py _teardown_container (~L2002) and _label_reap (~L2425) run `docker stop` + `docker rm` (no -v) then rmi the image. Nothing removes volumes. The docker-in-docker feature (offered by scaffold.py TOOLS 'docker-in-docker') mounts a NAMED volume dind-var-lib-docker-${devcontainerId}; even `docker rm -v` never removes named volumes.

<!-- fr:journal kind=ruled-out scope=debug id=fbe6ffa789d3 created=2026-10-10T19:38:13+00:00 -->
### fbe6ffa789d3 · ruled-out · Anonymous volumes and reclaimable images are fr's: ruled out (small/unrelated)

13 anonymous volumes (~90 MB total; postgres PGDATA from 2026-09-13, a uid-10000 home from 2026-08-03) match compose/agent-image test runs, not vsc-* devcontainers. 12 GB reclaimable images are non-fr (two agent images at 3.6G and 2.8G, devcontainers/python 1.5G...). Every vsc-* image is referenced by a live container, so _sweep_dangling_images works.

<!-- fr:journal kind=root-cause scope=debug id=081430774521 created=2026-10-10T19:38:18+00:00 -->
### 081430774521 · root-cause · Container teardown never removes the workspace's docker-in-docker named volume

Evidence: the devcontainer CLI names the docker-in-docker volume dind-var-lib-docker-${devcontainerId}, where devcontainerId = base32(sha256(JSON{devcontainer.config_file, devcontainer.local_folder} sorted keys)), padded to 52. Recomputing it for candidate paths matched exactly: 18.74 GB volume 0g3pv9… = ~/.cache/fr/worktrees/<repo-a>/<branch-a> (.devcontainer/dev), and 310.9 MB volume 1b5li6… = ~/.cache/fr/worktrees/<repo-b>/<branch-b>. Both worktrees and containers are gone; the volumes stayed. The 18.7 GB volume holds the inner dockerd's whole /var/lib/docker (a project's 12-container Supabase stack, containerd snapshots). Cause: LocalTarget._teardown_container and _label_reap (packages/fr/src/fr/isolation/local.py) run `docker stop` + `docker rm` then rmi the image. No path removes volumes. Named volumes survive even `docker rm -v`. Result: ~19 of the 21.3 GB of dead volumes are fr leaks, roughly a third of the 58 GB Docker VM.

<!-- fr:journal kind=finding scope=debug id=6f9de3c8144a created=2026-10-10T19:58:35+00:00 state=fixed -->
### 6f9de3c8144a · finding [fixed] · Teardown now removes the workspace's own named volumes

local.py: new devcontainer_id() (the CLI's ${devcontainerId}; pinned by a test vector and verified to reproduce the real leaked volume name 0g3pv9…). _teardown_container and _label_reap read the container's volume mounts + id labels BEFORE docker rm, then docker volume rm every named volume whose name carries this workspace's devcontainerId (dind-var-lib-docker-<id>). Shared volumes (no id, e.g. 'vscode') are never touched. Best-effort and non-fatal, like image reclaim. rebuild() is untouched on purpose: it keeps the same devcontainerId, so dind state survives a rebuild. Tests written first and seen RED on behaviour (no volume rm issued): test_down_removes_the_workspace_dind_volume, test_gc_label_reap_removes_the_workspace_volume; plus test_devcontainer_id_matches_the_cli, test_down_volume_rm_failure_is_non_fatal. Out of scope: volumes already leaked before this fix (their worktrees are gone, so fr cannot prove ownership; operator cleans them up by hand).

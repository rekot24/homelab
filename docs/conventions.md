# Conventions

Standing rules for anything added to this server. Follow these for every
new service, not just the ones that already use them.

## File structure

- `~/projects/` — git-tracked code (cloned repos, work in progress)
- `/srv/<service-name>/` — runtime data for a service, bind-mounted into
  its container. Visible, consistent, easy to back up.
- `~/scripts/` — standalone utility scripts, not tied to one project
- `~/workspaces/` — `.code-workspace` files for VS Code Remote-SSH

## Docker

- **Always bind-mount to `/srv/<service-name>`, never use named volumes.**
  This was corrected once already (Gitea) — don't repeat the mistake.
- New folders under `/srv/` are created with `sudo mkdir`, which leaves
  them root-owned. Fix immediately with:
  ```bash
  sudo chown -R $USER:$USER /srv/<service-name>
  ```
  Do this *before* writing files into the folder, not after hitting
  permission errors.
- Shared inter-container network: **`homelab-net`**. Any container that
  needs to reach another (e.g. n8n → Postgres) joins this network:
  ```bash
  docker network connect homelab-net <container-name>
  ```
- Container names don't always match the image/service name. Check with
  `docker ps -a` before assuming — e.g. n8n's real container name is
  `n8n-n8n-1`, not `n8n`.

## Git / Gitea

- Active repos are mirrored from Gitea to GitHub on a 1-hour sync
  interval. This is also how Claude can read repo contents without
  needing separate access to the private Gitea instance — read the
  GitHub mirror.
- GitHub MCP access is **read-only** by project convention: Claude
  provides file contents for Joshua to commit manually, never pushes
  directly.

## Firewall

- UFW rules are added per service for whatever ports it exposes
  (e.g. 3000, 5678, 222 for Gitea/n8n/Gitea-SSH).

## SSH config files

- Numeric prefixes matter for sort order in `sshd_config.d/`. Use
  low numbers (`00-keys-only.conf`) rather than high ones (`99-...`)
  to guarantee load order — caught once when `99-` loaded after
  conflicting defaults.

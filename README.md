# Homelab

Central repo for Joshua's homelab: infrastructure, running services, and the
projects that live on top of them. One repo, one place, instead of tribal
knowledge scattered across chats.

## Hardware

- **Minisforum UM790 Pro** mini PC, hostname `homelab`
- Ubuntu Server 26.04.1 LTS, full-disk ext4, no LVM, no encryption
- User: `joshua3311`
- LAN: `192.168.0.115` (DHCP reservation, MAC `38:05:25:39:a5:31`)
- Tailscale: `100.109.2.31` — reachable from `home-pc`, `josh-laptop`,
  `joshs-s25-ultra` (phone) on the same tailnet

## Access

- SSH over Tailscale (key-based, ED25519). Phone access via Termius.
- Password SSH auth is disabled server-wide once all devices have keys
  added — see `docs/conventions.md`.
- tmux is installed for persistent sessions (`tmux new -A -s main`).

## Running services

| Service     | Container name | Port(s)         | Data path          | Notes |
|-------------|-----------------|------------------|---------------------|-------|
| Gitea       | `gitea-gitea-1` | 3000, 222 (ssh)  | `/srv/gitea`        | Self-hosted git, mirrors active repos to GitHub hourly |
| n8n         | `n8n-n8n-1`     | 5678             | `/srv/n8n`           | Automation/workflow engine |
| Postgres    | `postgres`      | 5432 (localhost) | `/srv/postgres/data` | `pgvector/pgvector:pg17`, database `life` |

All containers share the `homelab-net` Docker network (see conventions).

## Projects

- [`projects/life-intelligence-system/`](projects/life-intelligence-system/README.md) —
  email ingestion + self-reporting pipeline (active)
- `fish-farm-mgr-v2` — separate repo (`Rekot24/fish-farm-mgr-v2`), being
  migrated to run headless on this server

## Docs

- [`docs/conventions.md`](docs/conventions.md) — naming and structure rules
  used across every service on this box
- [`docs/state.md`](docs/state.md) — snapshot of what's actually running,
  updated manually for now

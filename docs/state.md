# State snapshot

Manually updated for now. Candidate for automation later — see the
"self-documenting infra" idea in `life-intelligence-system/README.md`.

**Last updated:** 2026-09-29

## Containers running

```
CONTAINER ID   IMAGE                      NAMES         PORTS
5d7cc6d79731   pgvector/pgvector:pg17     postgres      127.0.0.1:5432->5432/tcp
31fa93622350   docker.n8n.io/n8nio/n8n    n8n-n8n-1     0.0.0.0:5678->5678/tcp
e1f948b11227   gitea/gitea:latest         gitea-gitea-1 0.0.0.0:3000->3000/tcp, 222->22/tcp
```

## Docker networks

- `homelab-net` — Postgres + n8n confirmed connected and reachable
  (ping tested, sub-ms latency internally)

## Storage

- `/srv/postgres/data` — Postgres data dir
- `/srv/n8n` — n8n data dir
- `/srv/gitea` — Gitea data dir
- `/srv/takeout` — Handyman Gmail Takeout export (mbox, ~625MB,
  includes Mail+Spam+Trash combined — needs filtering at parse time)

## In progress

- `life-intelligence-system`: schema loaded, mbox extracted, parser
  script not yet written (see project README for status)

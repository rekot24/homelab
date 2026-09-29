# Life Intelligence System

Self-documenting/self-reporting layer for Joshua's life, starting with
email. The core idea: flip Obsidian's model — instead of a tool that
depends on manually typing notes in, ingest data automatically and have
the system generate the reports and "you might be missing this" flags.

## Why

Obsidian rarely got used because it required manual input. This starts
from the other direction: capture is automatic, and the reporting layer
is what does the work of surfacing things — not just storing them.

## Scope (v1: email only)

- **Account:** Skilled Handyman Gmail (first of several accounts planned)
- **Goal:** weekly report covering threads waiting on a reply, threads
  gone quiet where Joshua is waiting on someone else, buried deadlines,
  and top senders by volume (unsubscribe/cleanup candidates)
- **Triage philosophy:** not everything gets stored. Promotional email
  Joshua actually wants gets surfaced in reports; stalled ideas (emails
  to self, threads that trail off) get resurfaced periodically; pure
  junk is counted by sender, not stored message-by-message.

## Architecture

```
Gmail (Handyman) → Google Takeout (one-time backlog)
                  → n8n (ongoing daily sync, later)
                  → Postgres (source of truth)
                  → LLM tagging pass (local Ollama / Claude API)
                  → weekly report (markdown, viewable in Obsidian if wanted)
```

- **Postgres** is the source of truth — queryable, not just readable.
- **pgvector** extension is enabled from the start so semantic search
  ("find anything related to that plumbing quote") can be added later
  without a migration.
- Markdown reports are a *view* on the database, not the store itself.

## Status (as of 2026-09-29)

- [x] Postgres running (`pgvector/pgvector:pg17`), database `life`
- [x] Schema created: `accounts`, `threads`, `messages`, `tags`,
      `junk_sender_counts`, `reports` — see `schema.sql`
- [x] n8n connected to Postgres on `homelab-net`, connectivity confirmed
- [x] Handyman Gmail exported via Google Takeout (341MB zip →
      625MB mbox), extracted to `/srv/takeout` on the server
- [x] `scripts/parse_mbox.py` written — dry-run mode (print only) and
      insert mode (writes to `accounts`/`threads`/`messages`, dedup on
      `message_id`, excludes Spam/Trash via `X-Gmail-Labels`)
- [ ] **Next: run the dry-run pass against the real mbox, eyeball the
      output, then run the real insert pass.**
- [ ] LLM tagging pass (category, deadline extraction)
- [ ] First generated report

## Known constraints / decisions

- The mbox from Takeout combines Mail + Spam + Trash in one file —
  filtering has to happen in the parser, not before.
- Embeddings column (`vector(1536)`) exists on `messages` but stays
  NULL until semantic search is actually built — no rush on this.
- One-time backlog (Takeout) sidesteps Gmail API rate limits; n8n
  handles only new incoming mail going forward.

## Later (not v1)

- Additional accounts (personal email, etc.)
- Additional sources feeding the same reports: Calendar, Drive, GitHub,
  HouseCallPro
- Cleanup actions (bulk archive/label) once tagging is trusted —
  read-only until then

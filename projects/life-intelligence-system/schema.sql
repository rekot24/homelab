-- Life Intelligence System — Email Pipeline
-- Initial schema: accounts, threads, messages, tags
-- Run against the "life" database

CREATE EXTENSION IF NOT EXISTS vector;

-- One row per email account (Handyman Gmail first, others later)
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL UNIQUE,        -- e.g. 'handyman', 'personal'
    email_address TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One row per email thread
CREATE TABLE threads (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    gmail_thread_id TEXT NOT NULL,     -- Gmail's own thread id, for future API sync
    subject TEXT,
    last_message_at TIMESTAMPTZ,
    last_sender TEXT,                  -- who spoke last: helps flag "waiting on me" vs "waiting on them"
    message_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (account_id, gmail_thread_id)
);

CREATE INDEX idx_threads_last_message_at ON threads(last_message_at);
CREATE INDEX idx_threads_account ON threads(account_id);

-- One row per email message within a thread
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    gmail_message_id TEXT,
    sender TEXT NOT NULL,
    sender_domain TEXT,                -- extracted for fast "top senders" grouping
    recipients TEXT,
    sent_at TIMESTAMPTZ,
    subject TEXT,
    body_text TEXT,                    -- plain text, HTML stripped
    embedding vector(1536),            -- filled in later once semantic search is added
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_messages_thread ON messages(thread_id);
CREATE INDEX idx_messages_sender_domain ON messages(sender_domain);
CREATE INDEX idx_messages_sent_at ON messages(sent_at);

-- LLM-assigned classification per thread (re-runnable as prompts improve)
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    thread_id INTEGER NOT NULL REFERENCES threads(id) ON DELETE CASCADE,
    category TEXT NOT NULL,            -- 'needs_reply' | 'waiting_on_them' | 'deadline' | 'wanted_promo' | 'stalled_idea' | 'receipt' | 'junk'
    confidence REAL,
    deadline_date DATE,                -- populated only when category = 'deadline'
    tagged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model_version TEXT                 -- which LLM/prompt version produced this tag
);

CREATE INDEX idx_tags_thread ON tags(thread_id);
CREATE INDEX idx_tags_category ON tags(category);

-- Junk senders are counted, not stored message-by-message
CREATE TABLE junk_sender_counts (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    sender_domain TEXT NOT NULL,
    message_count INTEGER NOT NULL DEFAULT 1,
    last_seen_at TIMESTAMPTZ,
    UNIQUE (account_id, sender_domain)
);

-- Each generated weekly/daily report, so you can compare over time
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    report_text TEXT NOT NULL,         -- the rendered markdown/html report
    period_start DATE,
    period_end DATE
);

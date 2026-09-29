-- Migration 001: add Message-ID for de-duplication
-- Safe to run against the existing empty "life" database

ALTER TABLE messages
    ADD COLUMN message_id TEXT;

ALTER TABLE messages
    ADD CONSTRAINT messages_message_id_unique UNIQUE (message_id);

CREATE INDEX idx_messages_message_id ON messages(message_id);

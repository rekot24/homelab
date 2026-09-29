#!/usr/bin/env python3
"""
parse_mbox.py — one-time backlog loader for a Google Takeout Gmail export.

Reads an mbox file (Mail + Spam + Trash combined, per Takeout's export
format), drops Spam/Trash, and loads the rest into Postgres:
  - one row per thread in `threads` (keyed on X-GM-THRID)
  - one row per message in `messages` (keyed on Message-ID, unique)

Usage:
    # Stage 1 — dry run, no DB writes, just prove the parser is sane
    python3 parse_mbox.py --mbox /srv/takeout/Takeout/Mail/*.mbox \
        --account handyman --dry-run

    # Stage 2 — actually insert
    python3 parse_mbox.py --mbox /srv/takeout/Takeout/Mail/*.mbox \
        --account handyman --db-host localhost --db-name life \
        --db-user life --db-password <password>

De-duplication:
    Every insert uses ON CONFLICT (message_id) DO NOTHING, so running
    this script twice — or re-running it after n8n has already pulled
    some overlapping recent mail — never creates duplicate rows.
"""

import argparse
import mailbox
import re
import sys
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser


# ---------- helpers ----------

class _TextExtractor(HTMLParser):
    """Very small HTML-to-text fallback for messages with no text/plain part."""

    def __init__(self):
        super().__init__()
        self.chunks = []

    def handle_data(self, data):
        self.chunks.append(data)

    def text(self):
        return re.sub(r"\n{3,}", "\n\n", " ".join(self.chunks)).strip()


def decode_str(value):
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def get_body_text(msg):
    """Prefer text/plain; fall back to stripped text/html; else empty string."""
    if msg.is_multipart():
        plain, html = None, None
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.get_content_maintype() == "multipart":
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and plain is None:
                plain = text
            elif ctype == "text/html" and html is None:
                html = text
        if plain:
            return plain.strip()
        if html:
            extractor = _TextExtractor()
            extractor.feed(html)
            return extractor.text()
        return ""
    else:
        payload = msg.get_payload(decode=True)
        if payload is None:
            return ""
        charset = msg.get_content_charset() or "utf-8"
        try:
            text = payload.decode(charset, errors="replace")
        except (LookupError, UnicodeDecodeError):
            text = payload.decode("utf-8", errors="replace")
        if msg.get_content_type() == "text/html":
            extractor = _TextExtractor()
            extractor.feed(text)
            return extractor.text()
        return text.strip()


def sender_domain(address):
    if "@" not in address:
        return None
    return address.rsplit("@", 1)[-1].lower()


def is_excluded(labels_header):
    """Drop Spam and Trash; keep everything else (Promotions/Social included —
    the LLM tagging pass decides wanted vs junk, not this parser)."""
    if not labels_header:
        return False
    labels = {l.strip().lower() for l in labels_header.split(",")}
    return "spam" in labels or "trash" in labels


def parse_message(msg):
    message_id = (msg.get("Message-ID") or "").strip()
    gm_thrid = (msg.get("X-GM-THRID") or "").strip()
    labels = msg.get("X-Gmail-Labels")
    subject = decode_str(msg.get("Subject"))
    raw_from = decode_str(msg.get("From"))
    _, from_addr = parseaddr(raw_from)
    to_addr = decode_str(msg.get("To"))

    date_hdr = msg.get("Date")
    sent_at = None
    if date_hdr:
        try:
            sent_at = parsedate_to_datetime(date_hdr)
        except (TypeError, ValueError):
            sent_at = None

    body = get_body_text(msg)

    return {
        "message_id": message_id or None,
        "gmail_thread_id": gm_thrid or message_id,  # fallback if X-GM-THRID missing
        "subject": subject,
        "sender": from_addr or raw_from,
        "sender_domain": sender_domain(from_addr) if from_addr else None,
        "recipients": to_addr,
        "sent_at": sent_at,
        "body_text": body,
        "excluded": is_excluded(labels),
    }


# ---------- main passes ----------

def dry_run(mbox_path, limit=5):
    box = mailbox.mbox(mbox_path)
    shown = 0
    total = 0
    excluded = 0
    for msg in box:
        total += 1
        parsed = parse_message(msg)
        if parsed["excluded"]:
            excluded += 1
            continue
        if shown < limit:
            print(f"--- message {total} ---")
            print(f"  subject:     {parsed['subject']!r}")
            print(f"  sender:      {parsed['sender']}")
            print(f"  domain:      {parsed['sender_domain']}")
            print(f"  sent_at:     {parsed['sent_at']}")
            print(f"  thread_id:   {parsed['gmail_thread_id']}")
            print(f"  message_id:  {parsed['message_id']}")
            print(f"  body preview: {parsed['body_text'][:150]!r}")
            print()
            shown += 1
    print(f"Scanned {total} messages total. {excluded} excluded (spam/trash).")
    print(f"Showed first {shown} kept messages above.")


def insert_run(mbox_path, account_label, db_conf):
    import psycopg2
    from psycopg2.extras import execute_values

    conn = psycopg2.connect(**db_conf)
    conn.autocommit = False
    cur = conn.cursor()

    # ensure the account row exists
    cur.execute(
        "INSERT INTO accounts (label, email_address) VALUES (%s, %s) "
        "ON CONFLICT (label) DO NOTHING RETURNING id",
        (account_label, f"{account_label}@placeholder"),
    )
    row = cur.fetchone()
    if row:
        account_id = row[0]
    else:
        cur.execute("SELECT id FROM accounts WHERE label = %s", (account_label,))
        account_id = cur.fetchone()[0]
    conn.commit()

    box = mailbox.mbox(mbox_path)
    total = 0
    inserted = 0
    skipped_dupe = 0
    excluded = 0
    junk_counts = {}

    for msg in box:
        total += 1
        parsed = parse_message(msg)

        if parsed["excluded"]:
            excluded += 1
            continue

        if not parsed["message_id"]:
            # no reliable dedup key — skip rather than risk duplicates
            continue

        # upsert thread
        cur.execute(
            """
            INSERT INTO threads (account_id, gmail_thread_id, subject,
                                  last_message_at, last_sender, message_count)
            VALUES (%s, %s, %s, %s, %s, 1)
            ON CONFLICT (account_id, gmail_thread_id) DO UPDATE SET
                last_message_at = GREATEST(threads.last_message_at, EXCLUDED.last_message_at),
                last_sender = EXCLUDED.last_sender,
                message_count = threads.message_count + 1
            RETURNING id
            """,
            (
                account_id,
                parsed["gmail_thread_id"],
                parsed["subject"],
                parsed["sent_at"],
                parsed["sender"],
            ),
        )
        thread_id = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO messages (thread_id, gmail_message_id, sender,
                                   sender_domain, recipients, sent_at,
                                   subject, body_text, message_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (message_id) DO NOTHING
            """,
            (
                thread_id,
                None,
                parsed["sender"],
                parsed["sender_domain"],
                parsed["recipients"],
                parsed["sent_at"],
                parsed["subject"],
                parsed["body_text"],
                parsed["message_id"],
            ),
        )
        if cur.rowcount == 0:
            skipped_dupe += 1
        else:
            inserted += 1

        if total % 500 == 0:
            conn.commit()
            print(f"...{total} scanned, {inserted} inserted so far")

    conn.commit()
    cur.close()
    conn.close()

    print(f"Done. Scanned {total}, inserted {inserted}, "
          f"skipped as duplicates {skipped_dupe}, excluded spam/trash {excluded}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mbox", required=True, help="Path to the mbox file")
    ap.add_argument("--account", required=True,
                     help="Account label, e.g. 'handyman' (matches accounts.label)")
    ap.add_argument("--dry-run", action="store_true",
                     help="Parse only, print sample output, no DB writes")
    ap.add_argument("--limit", type=int, default=5,
                     help="How many kept messages to print in dry-run mode")
    ap.add_argument("--db-host", default="localhost")
    ap.add_argument("--db-port", default="5432")
    ap.add_argument("--db-name", default="life")
    ap.add_argument("--db-user", default="life")
    ap.add_argument("--db-password", default=None)
    args = ap.parse_args()

    if args.dry_run:
        dry_run(args.mbox, limit=args.limit)
        return

    if not args.db_password:
        print("ERROR: --db-password is required for a real (non-dry-run) pass.",
              file=sys.stderr)
        sys.exit(1)

    db_conf = dict(
        host=args.db_host,
        port=args.db_port,
        dbname=args.db_name,
        user=args.db_user,
        password=args.db_password,
    )
    insert_run(args.mbox, args.account, db_conf)


if __name__ == "__main__":
    main()

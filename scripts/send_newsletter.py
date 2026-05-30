#!/usr/bin/env python3
"""
Send an already-generated newsletter (a row in the ``newsletters`` table) to a
distribution list, with references, using Theseus Insight's own email path.

This is for the case where a newsletter was generated WITHOUT emailing (e.g. by
``scripts/regenerate_newsletter.py``) and you now want to send the exact, saved
content — rather than regenerating it.

References are reconstructed from a generation job's ``papers_ranked``
checkpoint: each ``## <title>`` section in the newsletter is matched to that
paper's PDF URL, producing the same numbered "Title: URL" list the live
pipeline appends under "## References:".

Delivery uses ``construct_email_body`` + ``GmailCommunication`` exactly like the
pipeline's Stage 6, so subject/HTML/BCC formatting are identical.

Defaults to a DRY RUN (prints recipients + the references + a body preview and
exits). Pass ``--send`` to actually deliver.

Usage
-----
Preview what would be sent for newsletter 36, references from job 91cc978f::

    /Users/c/miniforge3/envs/theseus/bin/python scripts/send_newsletter.py \
        --newsletter-id 36 --job-id 91cc978f-2172-42cb-9e98-ac9d8aa06f8a \
        --profile-id 1

Actually send it::

    ... same command ... --send
"""

import argparse
import os
import re
import sys

import psycopg

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.regenerate_newsletter import (  # reuse the checkpoint readers
    DEFAULT_DSN,
    _as_obj,
    load_ranked_df,
)

SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def load_newsletter(conn, newsletter_id: int):
    row = conn.execute(
        "SELECT content, start_date, end_date FROM newsletters WHERE id = %s",
        (newsletter_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"No newsletter with id {newsletter_id}")
    content, start_date, end_date = row
    return content, str(start_date), str(end_date)


def profile_recipients(conn, profile_id: int) -> list[str]:
    row = conn.execute(
        "SELECT email_recipients FROM research_profiles WHERE id = %s",
        (profile_id,),
    ).fetchone()
    return list(_as_obj(row[0])) if row and row[0] else []


def build_references(content: str, ranked_df) -> tuple[str, list[str]]:
    """Match each '## <title>' section to its PDF URL from the ranked checkpoint.

    Returns (numbered_references_string, list_of_unmatched_titles).
    """
    title_to_url = {
        str(r["title"]).strip(): str(r["pdf_url"]) for _, r in ranked_df.iterrows()
    }
    entries, unmatched = [], []
    for title in SECTION_HEADER_RE.findall(content):
        title = title.strip()
        url = title_to_url.get(title)
        if url is None:
            unmatched.append(title)
            entries.append(title)  # keep the reference even without a URL
        else:
            entries.append(f"{title}: {url}")

    references = "\n".join(f"{i+1}. {entry}" for i, entry in enumerate(entries))
    return references, unmatched


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--newsletter-id", type=int, required=True, help="newsletters.id to send.")
    p.add_argument("--job-id", required=True, help="Job whose papers_ranked checkpoint provides the reference URLs.")
    p.add_argument("--profile-id", type=int, default=None, help="Profile whose email_recipients to use as the distribution list.")
    p.add_argument("--to", default=None, help="Comma-separated recipients, overriding the profile list.")
    p.add_argument("--send", action="store_true", help="Actually send the email (default: dry-run preview).")
    p.add_argument("--dsn", default=DEFAULT_DSN, help="Database connection string.")
    args = p.parse_args()

    with psycopg.connect(args.dsn) as conn:
        content, start_date, end_date = load_newsletter(conn, args.newsletter_id)
        ranked_df = load_ranked_df(conn, args.job_id)
        if args.to:
            recipients = [a.strip() for a in args.to.split(",") if a.strip()]
        elif args.profile_id:
            recipients = profile_recipients(conn, args.profile_id)
        else:
            recipients = []

    references, unmatched = build_references(content, ranked_df)

    # Build the email body + (lazily import the email machinery / .env loading).
    from theseus_insight.communication.communication import (
        GmailCommunication,
        construct_email_body,
    )

    body = construct_email_body(content, start_date, end_date, references)
    subject_range = start_date if start_date == end_date else f"{start_date} to {end_date}"

    print("=" * 80)
    print("Newsletter email preview")
    print(f"  newsletter id : {args.newsletter_id}")
    print(f"  date range    : {start_date} → {end_date}")
    print(f"  subject       : Theseus Insight Paper Newsletter for {subject_range}")
    print(f"  recipients ({len(recipients)}):")
    for r in recipients:
        print(f"      - {r}")
    if unmatched:
        print(f"  ⚠️ {len(unmatched)} section title(s) had no URL match in the checkpoint:")
        for t in unmatched:
            print(f"      - {t}")
    print("-" * 80)
    print("References block:")
    print(references)
    print("-" * 80)
    print(f"Body length: {len(body)} chars")
    print("=" * 80)

    if not recipients:
        raise SystemExit("No recipients resolved — pass --to or --profile-id with recipients.")

    if not args.send:
        print("\nDRY RUN — nothing sent. Re-run with --send to deliver.")
        return

    comm = GmailCommunication(receiver_address=recipients, verbose=True)
    comm.compose_message(body, start_date, end_date)
    comm.send_email()
    print(f"\n✅ Sent newsletter {args.newsletter_id} to {len(recipients)} recipient(s) (BCC).")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Regenerate an existing newsletter with a different author model.

Re-uses the *exact* set of papers that were selected for a previous newsletter
run (stored in the ``papers_ranked`` checkpoint of a ``processing_jobs`` row)
and re-authors the sections + intro with an author model of your choosing,
re-extracting the source PDFs exactly like the original pipeline does.

It does NOT re-harvest, re-embed, or re-score papers — only the writing stage
(content extraction + section authoring + intro) is re-run, driven by
``TheseusInsight.run(start_from='newsletter_sections')``.

Why a checkpoint and not the DB?  The ``newsletters`` table stores only the
final text, with no link to the papers it used.  The selected papers live in
the ``papers_ranked`` checkpoint, which survives even though the papers
themselves may have been deleted from the ``papers`` table.

Usage
-----
List recent jobs that have a re-usable ``papers_ranked`` checkpoint::

    python scripts/regenerate_newsletter.py --list

Re-author the most recent one with Gemini Flash, saving a new newsletter row
to the DB but NOT sending any email (the default)::

    python scripts/regenerate_newsletter.py \
        --job-id 91cc978f-2172-42cb-9e98-ac9d8aa06f8a \
        --model-name gemini-flash-latest --model-type gemini

Add ``--send-email --to a@b.com,c@d.com`` to also email the result.
"""

import argparse
import datetime
import json
import os
import pickle
import sys
import tempfile

import pandas as pd
import psycopg

# Make the theseus_insight package importable when run from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_DSN = os.getenv(
    "DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"
)
RANKED_STAGE = "papers_ranked"
CONFIG_FILE_FALLBACK = "config/orchestration.json"


def _as_obj(value):
    """psycopg may hand back jsonb as a dict or as raw text — normalise."""
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def list_jobs(conn) -> None:
    """Print recent jobs that carry a re-usable papers_ranked checkpoint."""
    rows = conn.execute(
        """
        SELECT pc.job_id,
               pj.created_at,
               pj.configuration,
               jsonb_array_length((pc.checkpoint_data::jsonb) -> 'dataframe') AS n_papers
        FROM processing_checkpoints pc
        JOIN processing_jobs pj ON pj.id = pc.job_id
        WHERE pc.checkpoint_type = %s
        ORDER BY pj.created_at DESC
        LIMIT 15
        """,
        (RANKED_STAGE,),
    ).fetchall()

    if not rows:
        print("No jobs with a papers_ranked checkpoint found.")
        return

    print(f"{'job_id':38}  {'created':19}  {'dates':25}  prof  papers")
    print("-" * 100)
    for job_id, created_at, config, n_papers in rows:
        cfg = _as_obj(config) or {}
        dates = f"{cfg.get('start_date', '?')} → {cfg.get('end_date', '?')}"
        profile = cfg.get("profile_ids") or "-"
        created = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else "?"
        print(f"{str(job_id):38}  {created:19}  {dates:25}  {str(profile):4}  {n_papers}")


def latest_job_id(conn) -> str | None:
    row = conn.execute(
        """
        SELECT pc.job_id
        FROM processing_checkpoints pc
        JOIN processing_jobs pj ON pj.id = pc.job_id
        WHERE pc.checkpoint_type = %s
        ORDER BY pj.created_at DESC
        LIMIT 1
        """,
        (RANKED_STAGE,),
    ).fetchone()
    return str(row[0]) if row else None


def load_ranked_df(conn, job_id: str) -> pd.DataFrame:
    """Reconstruct the ranked-papers DataFrame from a job's checkpoint."""
    row = conn.execute(
        """
        SELECT checkpoint_data
        FROM processing_checkpoints
        WHERE job_id = %s AND checkpoint_type = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (job_id, RANKED_STAGE),
    ).fetchone()
    if not row:
        raise SystemExit(f"No '{RANKED_STAGE}' checkpoint found for job {job_id}")

    data = _as_obj(row[0])
    records = data.get("dataframe") if isinstance(data, dict) else None
    if not records:
        raise SystemExit(f"Checkpoint for job {job_id} has no 'dataframe' records")
    return pd.DataFrame(records)


def load_job_config(conn, job_id: str) -> dict:
    row = conn.execute(
        "SELECT configuration FROM processing_jobs WHERE id = %s", (job_id,)
    ).fetchone()
    return (_as_obj(row[0]) if row else {}) or {}


def load_orchestration(conn) -> dict:
    """Live orchestration config from settings, falling back to the file."""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'orchestration'"
    ).fetchone()
    if row and row[0]:
        return json.loads(row[0])
    if os.path.exists(CONFIG_FILE_FALLBACK):
        with open(CONFIG_FILE_FALLBACK) as f:
            return json.load(f)
    raise SystemExit("No orchestration config in settings or config file.")


def profile_research_interests(conn, profile_id: int) -> str:
    rows = conn.execute(
        """
        SELECT interest_text
        FROM profile_research_interests
        WHERE profile_id = %s
        ORDER BY id
        """,
        (profile_id,),
    ).fetchall()
    return "\n".join(r[0] for r in rows)


def build_author_model(args, template: dict) -> dict:
    """A model-config block for the chosen author model.

    Starts from the existing newsletter_sections_model block (to inherit any
    fields we don't expose as flags) and overrides the essentials.
    """
    cfg = dict(template) if template else {}
    cfg.update(
        {
            "model_name": args.model_name,
            "model_type": args.model_type,
            "temperature": args.temperature,
            "max_new_tokens": args.max_new_tokens,
            "num_ctx": args.num_ctx,
            "host": args.host,
        }
    )
    return cfg


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list", action="store_true", help="List jobs with a re-usable papers_ranked checkpoint and exit.")
    p.add_argument("--job-id", help="Processing job whose papers_ranked checkpoint to reuse (default: most recent).")
    p.add_argument("--model-name", help="Author model name (e.g. gemini-flash-latest).")
    p.add_argument("--model-type", choices=["lmstudio", "gemini", "openai", "anthropic", "ollama"], help="Author model provider.")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-new-tokens", type=int, default=16000)
    p.add_argument("--num-ctx", type=int, default=131072)
    p.add_argument("--host", default=None, help="Optional host:port for lmstudio/ollama.")
    p.add_argument("--profile-id", type=int, default=None, help="Override profile id (default: from job config).")
    p.add_argument("--top-n", type=int, default=None, help="Override number of sections (default: from job config).")
    p.add_argument("--send-email", action="store_true", help="Also send the regenerated newsletter by email.")
    p.add_argument("--to", default=None, help="Comma-separated recipients (required with --send-email).")
    p.add_argument("--no-save", action="store_true", help="Do NOT insert the regenerated newsletter into the DB.")
    p.add_argument("--dsn", default=DEFAULT_DSN, help="Database connection string.")
    args = p.parse_args()

    with psycopg.connect(args.dsn) as conn:
        if args.list:
            list_jobs(conn)
            return

        if not args.model_name or not args.model_type:
            p.error("--model-name and --model-type are required (or use --list).")
        if args.send_email and not args.to:
            p.error("--to is required when --send-email is set.")

        job_id = args.job_id or latest_job_id(conn)
        if not job_id:
            raise SystemExit("No job id given and none found with a papers_ranked checkpoint.")

        job_config = load_job_config(conn, job_id)
        profile_ids = job_config.get("profile_ids") or []
        profile_id = args.profile_id or (profile_ids[0] if profile_ids else None)
        top_n = args.top_n or job_config.get("top_n", 5)
        start_date = job_config.get("start_date")
        end_date = job_config.get("end_date")

        ranked_df = load_ranked_df(conn, job_id)
        orchestration = load_orchestration(conn)
        interests = (
            profile_research_interests(conn, profile_id) if profile_id else ""
        )

    # Override BOTH author models (sections + intro) with the chosen model.
    author_cfg = build_author_model(args, orchestration.get("newsletter_sections_model", {}))
    orchestration["newsletter_sections_model"] = author_cfg
    orchestration["newsletter_intro_model"] = dict(author_cfg)

    print("=" * 80)
    print("Regenerating newsletter")
    print(f"  job id          : {job_id}")
    print(f"  date range      : {start_date} → {end_date}")
    print(f"  profile id      : {profile_id}")
    print(f"  candidate papers: {len(ranked_df)}  (target sections: {top_n})")
    print(f"  new author model: {args.model_name} ({args.model_type})")
    print(f"  save to DB      : {not args.no_save}")
    print(f"  send email      : {args.send_email}")
    print("=" * 80)

    # Seed the ranked-papers checkpoint into an isolated *file* checkpoint dir.
    # We run the orchestrator with use_database_checkpoints=False so it reads
    # this file (and writes the new sections/content only to the temp dir),
    # never touching the DB checkpoint tables or creating a new job.
    checkpoint_dir = tempfile.mkdtemp(prefix="regen_newsletter_")
    with open(os.path.join(checkpoint_dir, f"{RANKED_STAGE}_checkpoint.pkl"), "wb") as f:
        pickle.dump(
            {
                "data": ranked_df,
                "timestamp": datetime.datetime.now().isoformat(),
                "stage": RANKED_STAGE,
            },
            f,
        )
    print(f"Seeded ranked-papers checkpoint into {checkpoint_dir}")

    # Import here so the lightweight --list path doesn't pay the heavy
    # (embedding model, LLM client) import/init cost.
    from theseus_insight.theseus_insight import TheseusInsight

    ti = TheseusInsight(
        research_interests_override=interests,
        start_date_override=start_date,
        end_date_override=end_date,
        profile_ids_override=[profile_id] if profile_id else None,
        orchestration_config=orchestration,
        receiver_address_override=args.to if args.send_email else None,
        generate_email=args.send_email,
        generate_podcast=False,
        visualizer=False,
        db_saving=not args.no_save,
        use_database_checkpoints=False,   # force file-based checkpoints
        checkpoint_dir=checkpoint_dir,
        top_n=top_n,
        verbose=True,
    )

    # NOTE: deliberately pass NO progress_callback — when start_from skips the
    # download stage, data_df is None and the callback path does len(data_df),
    # which would crash. The CLI doesn't need progress events anyway.
    ti.run(start_from="newsletter_sections")

    print("\n✅ Done. Re-authored newsletter generated.")
    if not args.no_save:
        print("   A new row was inserted into the `newsletters` table —")
        print("   compare it against the original to confirm the new author model is better.")


if __name__ == "__main__":
    main()

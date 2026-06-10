"""Stage 2: Embed papers + cosine-similarity filter (extracted from run_async, B9)."""
from typing import Callable, Optional, Tuple

import pandas as pd
from tqdm import tqdm

from ...data_access import PaperRepository
from ...data_model.papers import Paper
from ...utils import TODAY, cosine_similarity


async def run(
    ti,
    data_df,
    start_from: Optional[str],
    progress_callback: Optional[Callable],
) -> Tuple[Optional[pd.DataFrame], bool]:
    """Embed abstracts, dedupe against the DB, threshold-filter, checkpoint.

    Returns (embedded_df, exit_early). exit_early=True means the
    no-papers handler already ran and the pipeline should stop.
    """
    embedded_df = None

    if start_from is None or start_from in ['papers_downloaded', 'papers_embedded']:
        embedded_df = ti._load_checkpoint('papers_embedded')
        if embedded_df is None:
            if data_df is None:
                data_df = ti._load_checkpoint('papers_downloaded')
                if data_df is None:
                    raise ValueError("No downloaded papers found to embed.")

            # Check if we have an empty DataFrame from the download stage
            if data_df.empty:
                if ti.verbose:
                    print("No papers to embed (empty DataFrame from download stage)")
                # Create empty embedded DataFrame and continue
                embedded_df = data_df.copy()
                embedded_df['cosine_similarity'] = []
                embedded_df['abstract_embedding'] = []
                ti._save_checkpoint('papers_embedded', embedded_df)
            else:
                if progress_callback:
                    progress_callback("embed", 11, "Starting paper embedding")

                if ti.verbose:
                    print("Embedding papers...")

                # Check for existing papers to avoid unnecessary processing
                if ti.db_saving:
                    # Extract all URLs for bulk checking
                    all_urls = [row['pdf_url'] for _, row in data_df.iterrows()]

                    # Use optimized bulk existence checking
                    existing_urls_set, _ = PaperRepository.bulk_check_existence(urls=all_urls)

                    # Create mask for new papers
                    new_papers_mask = []
                    existing_urls = []
                    for _, row in data_df.iterrows():
                        url = row['pdf_url']
                        if url in existing_urls_set:
                            existing_urls.append(url)
                            new_papers_mask.append(False)
                        else:
                            new_papers_mask.append(True)

                    if existing_urls and ti.verbose:
                        print(f"Found {len(existing_urls)} papers already in database, will skip embedding for those")

                    # Filter to only new papers for embedding
                    new_papers_df = data_df[new_papers_mask].reset_index(drop=True)

                    if len(new_papers_df) == 0:
                        if ti.verbose:
                            print("All papers already exist in database - loading existing papers for newsletter generation")

                        # Load existing papers from database instead of exiting
                        # Get papers from the same date range that were downloaded

                        existing_papers_list = []
                        for _, row in data_df.iterrows():
                            existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                            if existing_paper:
                                # Convert database row to expected format
                                paper_data = {
                                    'id': existing_paper.get('id'),  # Include database ID for multi-server scoring
                                    'title': existing_paper['title'],
                                    'abstract': existing_paper['abstract'],
                                    'pdf_url': existing_paper['url'],
                                    'date': existing_paper['date'],
                                    'cosine_similarity': existing_paper.get('cosine_similarity', 0.0),
                                    'abstract_embedding': existing_paper.get('embedding', [])
                                }
                                existing_papers_list.append(paper_data)

                        if existing_papers_list:
                            # Create DataFrame from existing papers
                            filtered_df = pd.DataFrame(existing_papers_list)
                            if ti.verbose:
                                print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                        else:
                            # Still no papers - this shouldn't happen but handle gracefully
                            if ti.verbose:
                                print("No existing papers found in database")
                            ti._handle_no_papers_found(reason="all_duplicates")
                            return None, True
                    else:
                        # Process only new papers
                        abstracts = list(new_papers_df['abstract'])
                        abstract_embeddings = []
                        cosine_similarities = []
                        reserch_embedding = ti.embedding_model.invoke(ti.research_interests)

                        for abstract in tqdm(abstracts, disable=not ti.verbose, desc="Embedding abstracts"):
                            abstract_embedding = ti.embedding_model.invoke(abstract, show_progress_bar=False)
                            sim = cosine_similarity(abstract_embedding, reserch_embedding)
                            cosine_similarities.append(sim)
                            abstract_embeddings.append(abstract_embedding)

                        new_papers_df['cosine_similarity'] = cosine_similarities
                        new_papers_df['abstract_embedding'] = abstract_embeddings

                        # Save ALL embedded papers to database first (before filtering)
                        if ti.db_saving:
                            if ti.verbose:
                                print(f"Saving {len(new_papers_df)} papers to database (before filtering)...")
                            saved_count = 0
                            paper_ids = []
                            for idx, row in tqdm(new_papers_df.iterrows(), total=len(new_papers_df), 
                                              desc="Saving papers to DB", disable=not ti.verbose):
                                embedding = row['abstract_embedding']
                                if hasattr(embedding, 'tolist'):
                                    embedding = embedding.tolist()
                                elif not isinstance(embedding, list):
                                    embedding = list(embedding)

                                paper = Paper(
                                    title=row['title'],
                                    abstract=row['abstract'],
                                    url=row['pdf_url'],
                                    date_run=TODAY.strftime('%Y-%m-%d'),
                                    date=row['date'].strftime('%Y-%m-%d'),
                                    score=0.0,  # Not yet scored by LLM
                                    related=False,  # Not yet scored
                                    rationale='Not yet scored by LLM',
                                    cosine_similarity=row['cosine_similarity'],
                                    embedding_model=ti.embedding_model_name,
                                    embedding=embedding
                                )

                                was_inserted = PaperRepository.insert_paper(paper, skip_duplicates=True)
                                if was_inserted:
                                    saved_count += 1

                                # Get the paper ID from database (whether newly inserted or existing)
                                existing_paper = PaperRepository.get_by_url(row['pdf_url'])
                                if existing_paper:
                                    paper_ids.append(existing_paper['id'])
                                else:
                                    paper_ids.append(None)

                            # Add IDs to dataframe for multi-server scoring
                            new_papers_df['id'] = paper_ids

                            if ti.verbose:
                                print(f"✅ Saved {saved_count} new papers to database")
                                print(f"✅ Retrieved {len([pid for pid in paper_ids if pid is not None])} paper IDs for scoring")

                        # Filter by threshold for LLM scoring and newsletter generation
                        filtered_df = new_papers_df[new_papers_df['cosine_similarity'] >= ti.cosine_similarity_threshold]
                        filtered_df = filtered_df.reset_index(drop=True)

                        # Check if no papers meet the threshold criteria
                        if len(filtered_df) == 0:
                            if ti.verbose:
                                print(f"No new papers meet the cosine similarity threshold ({ti.cosine_similarity_threshold})")
                                print("Loading existing papers from database for newsletter generation...")

                            # Load existing papers from database instead of exiting
                            existing_papers = PaperRepository.get_papers_in_date_range(
                                start_date=ti.start_date.strftime('%Y-%m-%d'),
                                end_date=ti.end_date.strftime('%Y-%m-%d')
                            )

                            if existing_papers:
                                # Convert to DataFrame format expected by newsletter generation
                                papers_list = []
                                for paper in existing_papers:
                                    papers_list.append({
                                        'id': paper.get('id'),  # Include database ID for multi-server scoring
                                        'title': paper['title'],
                                        'abstract': paper['abstract'],
                                        'pdf_url': paper['url'],
                                        'date': paper['date'],
                                        'cosine_similarity': paper.get('cosine_similarity', 0.0),
                                        'abstract_embedding': paper.get('embedding', [])
                                    })

                                filtered_df = pd.DataFrame(papers_list)
                                if ti.verbose:
                                    print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                            else:
                                # No existing papers found - this is the real "no papers" case
                                if ti.verbose:
                                    print("No existing papers found in database for date range")
                                ti._handle_no_papers_found(reason="threshold_not_met")
                                return None, True
                else:
                    # Original behavior when not saving to DB
                    abstracts = list(data_df['abstract'])
                    abstract_embeddings = []
                    cosine_similarities = []
                    reserch_embedding = ti.embedding_model.invoke(ti.research_interests)

                    for abstract in tqdm(abstracts, disable=not ti.verbose, desc="Embedding abstracts"):
                        abstract_embedding = ti.embedding_model.invoke(abstract, show_progress_bar=False)
                        sim = cosine_similarity(abstract_embedding, reserch_embedding)
                        cosine_similarities.append(sim)
                        abstract_embeddings.append(abstract_embedding)

                    data_df['cosine_similarity'] = cosine_similarities
                    data_df['abstract_embedding'] = abstract_embeddings

                    # Note: When not saving to DB, we can only work with papers in memory
                    # Filter by threshold for processing
                    filtered_df = data_df[data_df['cosine_similarity'] >= ti.cosine_similarity_threshold]
                    filtered_df = filtered_df.reset_index(drop=True)

                    # Check if no papers meet the threshold criteria
                    if len(filtered_df) == 0:
                        if ti.verbose:
                            print(f"No new papers meet the cosine similarity threshold ({ti.cosine_similarity_threshold})")
                            print("Loading existing papers from database for newsletter generation...")

                        # Load existing papers from database instead of exiting
                        existing_papers = PaperRepository.get_papers_in_date_range(
                            start_date=ti.start_date.strftime('%Y-%m-%d'),
                            end_date=ti.end_date.strftime('%Y-%m-%d')
                        )

                        if existing_papers:
                            # Convert to DataFrame format expected by newsletter generation
                            papers_list = []
                            for paper in existing_papers:
                                papers_list.append({
                                    'title': paper['title'],
                                    'abstract': paper['abstract'],
                                    'pdf_url': paper['url'],
                                    'date': paper['date'],
                                    'cosine_similarity': paper.get('cosine_similarity', 0.0),
                                    'abstract_embedding': paper.get('embedding', [])
                                })

                            filtered_df = pd.DataFrame(papers_list)
                            if ti.verbose:
                                print(f"✅ Loaded {len(filtered_df)} existing papers for newsletter generation")
                        else:
                            # No existing papers found - this is the real "no papers" case
                            if ti.verbose:
                                print("No existing papers found in database for date range")
                            ti._handle_no_papers_found(reason="threshold_not_met")
                            return None, True

                # Ensure filtered_df is always defined (safety check)
                if 'filtered_df' not in locals():
                    if ti.verbose:
                        print("Warning: filtered_df was not defined, creating empty dataframe")
                    filtered_df = data_df.iloc[0:0].copy()  # Empty dataframe with same columns
                    filtered_df['cosine_similarity'] = []
                    filtered_df['abstract_embedding'] = []

                # Save checkpoint
                await ti._save_checkpoint_async('papers_embedded', filtered_df)
                embedded_df = filtered_df

    if progress_callback:
        progress_callback("embed", 15, "Paper embedding complete")


    return embedded_df, False

"""Profile-aware paper ingestion pipeline (lifted verbatim from TheseusInsight, B9)."""
from typing import Callable, Optional

import pandas as pd
from tqdm import tqdm

from ..data_access import PaperRepository
from ..data_model.papers import Paper
from ..data_processing.arxiv import ArxivDataProcessor
from ..utils import TODAY, cosine_similarity


def run(ti, progress_callback=None):
    """Run paper ingestion pipeline for profiles feature - stores ALL papers without LLM scoring.

This method downloads papers, embeds them, and stores them all in the database
without applying LLM judge filtering. Papers can be scored later per profile."""
    try:
        # Force Kaggle download for bulk operations to handle large date ranges efficiently
        import os
        old_force_kaggle = os.environ.get('FORCE_KAGGLE', '')
        os.environ['FORCE_KAGGLE'] = 'true'

        if ti.verbose:
            print("🚀 STARTING PROFILES-AWARE PAPER INGESTION")
            print("="*60)
            print("Note: This pipeline stores ALL papers without LLM judge filtering")
            print("Papers will be scored later on a per-profile basis")
            print("Using Kaggle dataset for bulk download (4GB file)")
            print("="*60)

        # Check existing papers BEFORE downloading
        existing_urls = set()
        existing_titles = set()
        if ti.verbose:
            print("\n🔍 PRE-DOWNLOAD CHECK")
            print("="*40)
            print("Checking existing papers in database before download...")

        # Get papers in the date range from the database
        existing_papers = PaperRepository.get_papers_in_date_range(
            start_date=ti.start_date.strftime('%Y-%m-%d'),
            end_date=ti.end_date.strftime('%Y-%m-%d')
        )

        existing_urls = {p['url'] for p in existing_papers}
        existing_titles = {p['title'] for p in existing_papers}

        if ti.verbose:
            print(f"📊 Found {len(existing_papers)} existing papers in date range")
            print(f"   - {len(existing_urls)} unique URLs")
            print(f"   - {len(existing_titles)} unique titles")

            # If we have most papers already, we might skip download entirely
            if len(existing_papers) > 0:
                print(f"💡 Tip: {len(existing_papers)} papers already exist - download will skip these")

        # -----------
        # Stage 1: Download Papers
        # -----------
        if progress_callback:
            progress_callback("download", 0, "Starting paper download")

        data_df = ti._load_checkpoint('papers_downloaded')
        if data_df is None:
            if ti.verbose:
                print("\n📥 STAGE 1: DOWNLOADING PAPERS")
                print("="*40)

            # Get ArXiv categories from orchestration config
            arxiv_config = ti.orchestration_config.get('arxiv_search_categories', {})

            # Debug: Let's see what's in the config
            if ti.verbose:
                print(f"[DEBUG] arxiv_config: {arxiv_config}")

            category = arxiv_config.get('main_category', 'cs')
            subcategories = arxiv_config.get('filter_categories', ['cs.ai', 'cs.cl', 'cs.lg', 'cs.ir', 'cs.ma', 'cs.cv'])

            # If categories are explicitly set to None, download all papers
            if 'filter_categories' in arxiv_config and arxiv_config['filter_categories'] is None:
                category = None
                subcategories = None
                if ti.verbose:
                    print("📋 Downloading ALL ArXiv categories (no filtering)")
            else:
                if ti.verbose:
                    print(f"📋 Category: {category}, Subcategories: {subcategories}")

            process_data = ArxivDataProcessor(
                start_date=ti.start_date, 
                end_date=ti.end_date,
                category=category,
                subcategories=subcategories
            )
            data_df = process_data.download_and_process_data()

            # Check if no papers were found and handle gracefully
            if data_df.empty:
                ti._handle_no_papers_found()
                return  # Exit early since there's nothing to process

            # Early optimization: Check if all downloaded papers already exist
            quick_check_urls = set(data_df['pdf_url'].tolist())
            quick_check_titles = set(data_df['title'].tolist())

            if quick_check_urls.issubset(existing_urls) or quick_check_titles.issubset(existing_titles):
                if ti.verbose:
                    print("🎯 OPTIMIZATION: All downloaded papers already exist in database!")
                    print("   Skipping download and processing stages")
                return {
                    'saved_count': 0,
                    'duplicate_count': len(data_df),
                    'total_processed': len(data_df)
                }

            ti._save_checkpoint('papers_downloaded', data_df)
            if ti.verbose:
                print(f"✅ Downloaded {len(data_df)} papers from ArXiv")
        else:
            if ti.verbose:
                print(f"📥 Using cached papers: {len(data_df)} papers")

        if progress_callback:
            progress_callback("download", 20, "Paper download complete")

        # -----------
        # Stage 2: Embed Papers
        # -----------
        if progress_callback:
            progress_callback("embed", 21, "Starting paper embedding")

        embedded_df = ti._load_checkpoint('papers_embedded')
        if embedded_df is None:
            if ti.verbose:
                print("\n🧠 STAGE 2: EMBEDDING PAPERS")
                print("="*40)

            # Filter out papers with missing abstracts first
            original_count = len(data_df)
            abstract_mask = data_df['abstract'].notna() & (data_df['abstract'].str.strip() != '')
            data_df = data_df[abstract_mask].reset_index(drop=True)

            if ti.verbose and original_count != len(data_df):
                filtered_out = original_count - len(data_df)
                print(f"⚠️ Filtered out {filtered_out} papers with missing/empty abstracts")

            if data_df.empty:
                if ti.verbose:
                    print("❌ No papers with valid abstracts to process")
                return

            # Check for existing papers using pre-loaded data
            new_mask = []
            if ti.verbose:
                print("🔍 Filtering out existing papers using pre-loaded data...")

            # Use the pre-loaded existing URLs and titles for faster checking
            for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                              desc="Checking existing papers", disable=not ti.verbose):
                exists = (row["pdf_url"] in existing_urls or row["title"] in existing_titles)
                new_mask.append(not exists)

            new_df = data_df[new_mask].reset_index(drop=True)

            if ti.verbose:
                existing_count = len(data_df) - len(new_df)
                print(f"📝 Found {existing_count} existing papers, {len(new_df)} new papers to process")

            if new_df.empty:
                if ti.verbose:
                    print("✅ All papers already exist in database")
                return {
                    'saved_count': 0,
                    'duplicate_count': len(data_df),
                    'total_processed': len(data_df)
                }

            # Create job checkpoint for UI tracking
            from .services.embedding_service import EmbeddingJobCheckpoint
            from uuid import uuid4
            job_id = uuid4()
            checkpoint_mgr = EmbeddingJobCheckpoint()

            # Initialize checkpoint
            checkpoint_mgr.save(
                job_id=job_id,
                operation="profile_aware_embed",
                parameters={
                    "start_date": ti.start_date.strftime('%Y-%m-%d'),
                    "end_date": ti.end_date.strftime('%Y-%m-%d'),
                    "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                },
                progress={
                    "total_papers": len(new_df),
                    "processed_papers": 0,
                    "offset": 0
                },
                statistics={
                    "papers_embedded": 0,
                    "papers_failed": 0
                }
            )

            if ti.verbose:
                print(f"📋 Created embedding job for UI tracking: {job_id}")

            # Embed abstracts in batches to avoid memory issues
            batch_size = getattr(ti, 'batch_size', 100)
            all_embeddings = []
            processed_count = 0

            try:
                for i in tqdm(range(0, len(new_df), batch_size), 
                             desc="Embedding batches", disable=not ti.verbose):
                    batch_df = new_df.iloc[i:i+batch_size]
                    abstracts = list(batch_df['abstract'])
                    batch_embeddings = ti.embedding_model.invoke(abstracts)
                    all_embeddings.extend(batch_embeddings)

                    processed_count += len(batch_df)

                    # Update checkpoint every 500 papers for more frequent UI updates
                    if processed_count % 500 == 0:
                        checkpoint_mgr.save(
                            job_id=job_id,
                            operation="profile_aware_embed",
                            parameters={
                                "start_date": ti.start_date.strftime('%Y-%m-%d'),
                                "end_date": ti.end_date.strftime('%Y-%m-%d'),
                                "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                            },
                            progress={
                                "total_papers": len(new_df),
                                "processed_papers": processed_count,
                                "offset": processed_count
                            },
                            statistics={
                                "papers_embedded": processed_count,
                                "papers_failed": 0
                            }
                        )

                embeddings = all_embeddings

                # Convert 2D embeddings array to list of 1D arrays for pandas
                if hasattr(embeddings, 'tolist'):
                    embeddings_list = embeddings.tolist()
                elif isinstance(embeddings, list):
                    embeddings_list = embeddings
                else:
                    # Handle numpy arrays or other tensor types
                    import numpy as np
                    embeddings_array = np.array(embeddings)
                    embeddings_list = [embeddings_array[i] for i in range(len(embeddings_array))]

                new_df['abstract_embedding'] = embeddings_list

                # Final checkpoint update
                checkpoint_mgr.save(
                    job_id=job_id,
                    operation="profile_aware_embed",
                    parameters={
                        "start_date": ti.start_date.strftime('%Y-%m-%d'),
                        "end_date": ti.end_date.strftime('%Y-%m-%d'),
                        "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                    },
                    progress={
                        "total_papers": len(new_df),
                        "processed_papers": len(new_df),
                        "offset": len(new_df)
                    },
                    statistics={
                        "papers_embedded": len(new_df),
                        "papers_failed": 0
                    }
                )

                # Clean up checkpoint after successful completion
                checkpoint_mgr.delete(job_id)

                if ti.verbose:
                    print(f"✅ Embedded {len(new_df)} papers")
                    print(f"🗑️  Cleaned up job checkpoint: {job_id}")

            except Exception as e:
                # On failure, update checkpoint but DON'T delete
                checkpoint_mgr.save(
                    job_id=job_id,
                    operation="profile_aware_embed",
                    parameters={
                        "start_date": ti.start_date.strftime('%Y-%m-%d'),
                        "end_date": ti.end_date.strftime('%Y-%m-%d'),
                        "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown",
                        "error": str(e)
                    },
                    progress={
                        "total_papers": len(new_df),
                        "processed_papers": processed_count,
                        "offset": processed_count
                    },
                    statistics={
                        "papers_embedded": processed_count,
                        "papers_failed": len(new_df) - processed_count
                    }
                )

                if ti.verbose:
                    print(f"❌ Embedding failed at {processed_count}/{len(new_df)} papers")
                    print(f"💾 Job checkpoint preserved for debugging: {job_id}")

                # Re-raise the exception
                raise

            # Calculate cosine similarity with research interests
            if ti.research_interests and ti.research_interests.strip():
                research_embedding = ti.embedding_model.invoke(ti.research_interests)
                if hasattr(research_embedding, 'tolist'):
                    research_embedding = research_embedding.tolist()

                similarities = []
                for embedding in embeddings:
                    if hasattr(embedding, 'tolist'):
                        embedding = embedding.tolist()
                    sim = cosine_similarity(research_embedding, embedding)
                    similarities.append(sim)

                new_df['cosine_similarity'] = similarities
            else:
                new_df['cosine_similarity'] = [0.0] * len(new_df)

            embedded_df = new_df
            ti._save_checkpoint('papers_embedded', embedded_df)

            if ti.verbose:
                print(f"✅ Embedded {len(embedded_df)} new papers")
        else:
            if ti.verbose:
                print(f"🧠 Using cached embeddings: {len(embedded_df)} papers")

        if progress_callback:
            progress_callback("embed", 60, "Paper embedding complete")

        # -----------
        # Stage 3: Store Papers (No Scoring)
        # -----------
        if progress_callback:
            progress_callback("store", 61, "Storing papers to database")

        storage_result = ti._load_checkpoint('papers_stored')
        if storage_result is None:
            storage_result = ti.store_papers_without_scoring(embedded_df)
            ti._save_checkpoint('papers_stored', storage_result)
        else:
            if ti.verbose:
                print(f"💾 Using cached storage result: {storage_result}")

        if progress_callback:
            progress_callback("store", 100, "Paper storage complete")

        # Clean up checkpoints after successful completion
        ti._cleanup_checkpoints()

        if ti.verbose:
            print("\n🎉 PROFILES PIPELINE COMPLETE!")
            print("="*60)
            print(f"✅ Processed {storage_result['total_processed']} papers")
            print(f"💾 Saved {storage_result['saved_count']} new papers")
            print(f"🔄 Skipped {storage_result['duplicate_count']} duplicates")
            print("📝 Papers are ready for profile-specific scoring")

        return storage_result

    except Exception as e:
        ti._log_error(500, e)
        raise
    finally:
        # Restore original FORCE_KAGGLE setting
        if old_force_kaggle is not None:
            os.environ['FORCE_KAGGLE'] = old_force_kaggle
        else:
            os.environ.pop('FORCE_KAGGLE', None)

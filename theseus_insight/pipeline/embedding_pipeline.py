"""Embedding-only bulk pipeline (lifted verbatim from TheseusInsight, B9)."""
from typing import Callable, Optional

import pandas as pd
from tqdm import tqdm

from ..data_access import PaperRepository
from ..data_model.papers import Paper
from ..data_processing.arxiv import ArxivDataProcessor
from ..utils import TODAY, cosine_similarity


def run(ti, progress_callback=None):
    """Run embedding-only pipeline for bulk data preparation.

This method downloads papers, embeds them, and stores them all in the database
without any profile-specific filtering or scoring. This is useful for bulk
data preparation where scoring will be done later."""
    try:
        # Force Kaggle download for bulk operations to handle large date ranges efficiently
        import os
        old_force_kaggle = os.environ.get('FORCE_KAGGLE', '')
        os.environ['FORCE_KAGGLE'] = 'true'

        if ti.verbose:
            print("🚀 STARTING BULK EMBEDDING PIPELINE")
            print("="*60)
            print("Note: This pipeline stores ALL papers with embeddings")
            print("No profile filtering or LLM scoring will be performed")
            print("Using Kaggle dataset for bulk download (4GB file)")
            print("="*60)

        # -----------
        # Stage 1: Download Papers
        # -----------
        if progress_callback:
            progress_callback("download", 0, "Starting paper download")

        data_df = ti._load_checkpoint('papers_downloaded')
        if data_df is None:
            if ti.verbose:
                print("📥 STAGE 1: DOWNLOADING PAPERS")
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
                if ti.verbose:
                    print("❌ No papers found for the specified date range")
                return {
                    'saved_count': 0,
                    'embedded_count': 0,
                    'skipped_count': 0,
                    'total_processed': 0
                }

            ti._save_checkpoint('papers_downloaded', data_df)
            if ti.verbose:
                print(f"✅ Downloaded {len(data_df)} papers from ArXiv")
        else:
            if ti.verbose:
                print(f"📥 Using cached papers: {len(data_df)} papers")

        if progress_callback:
            progress_callback("download", 25, f"Downloaded {len(data_df)} papers")

        # -----------
        # Stage 2: Check Existing & Filter
        # -----------
        if progress_callback:
            progress_callback("filter", 26, "Checking for existing papers")

        # Filter out papers with missing abstracts
        original_count = len(data_df)
        abstract_mask = data_df['abstract'].notna() & (data_df['abstract'].str.strip() != '')
        data_df = data_df[abstract_mask].reset_index(drop=True)

        if ti.verbose and original_count != len(data_df):
            filtered_out = original_count - len(data_df)
            print(f"⚠️ Filtered out {filtered_out} papers with missing/empty abstracts")

        if data_df.empty:
            if ti.verbose:
                print("❌ No papers with valid abstracts to process")
            return {
                'saved_count': 0,
                'embedded_count': 0,
                'skipped_count': original_count,
                'total_processed': original_count
            }

        # Check for existing papers if skip_existing is enabled
        papers_to_embed = data_df
        skipped_count = 0

        if getattr(ti, 'skip_existing', True):
            if ti.verbose:
                print("🔍 Checking for existing papers in database...")

            new_mask = []
            already_embedded_mask = []

            for _, row in tqdm(data_df.iterrows(), total=len(data_df), 
                              desc="Checking existing papers", disable=not ti.verbose):
                existing_paper = PaperRepository.get_by_url(row["pdf_url"])
                if existing_paper:
                    new_mask.append(False)
                    # Check if paper already has embedding (must have both embedding and valid model name)
                    has_embedding = (
                        existing_paper.get('embedding') is not None and 
                        existing_paper.get('embedding_model') is not None and
                        existing_paper.get('embedding_model') not in ['pending', '']
                    )
                    already_embedded_mask.append(has_embedding)
                else:
                    new_mask.append(True)
                    already_embedded_mask.append(False)

            # Papers that need to be embedded (new papers + existing without embeddings)
            needs_embedding_mask = [new_mask[i] or not already_embedded_mask[i] for i in range(len(data_df))]
            papers_to_embed = data_df[needs_embedding_mask].reset_index(drop=True)
            skipped_count = sum(already_embedded_mask)

            if ti.verbose:
                new_count = sum(new_mask)
                existing_without_embedding = sum(not new and not embedded for new, embedded in zip(new_mask, already_embedded_mask))
                print(f"📝 Found {new_count} new papers")
                print(f"📝 Found {existing_without_embedding} existing papers without embeddings")
                print(f"📝 Skipping {skipped_count} papers that already have embeddings")

        if progress_callback:
            progress_callback("filter", 35, f"Filtered to {len(papers_to_embed)} papers needing embeddings")

        # -----------
        # Stage 3: Embed Papers (Memory-Safe with Chunking)
        # -----------
        embedded_count = 0
        if len(papers_to_embed) > 0:
            if progress_callback:
                progress_callback("embed", 36, "Starting paper embedding")

            embedded_df = ti._load_checkpoint('papers_embedded')
            if embedded_df is None:
                if ti.verbose:
                    print(f"\n🧠 STAGE 3: EMBEDDING {len(papers_to_embed)} PAPERS (Memory-Safe)")
                    print("="*40)

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
                        "start_date": ti.start_date,
                        "end_date": ti.end_date,
                        "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                    },
                    progress={
                        "total_papers": len(papers_to_embed),
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

                # Use chunked processing to avoid memory issues
                batch_size = getattr(ti, 'batch_size', 100)
                chunk_size = 10000  # Process 10K papers per chunk, then flush
                all_embeddings = []
                papers_to_save = []
                processed_count = 0

                try:
                    for i in tqdm(range(0, len(papers_to_embed), batch_size), 
                                 desc="Embedding batches", disable=not ti.verbose):
                        batch = papers_to_embed.iloc[i:i+batch_size]
                        abstracts = batch['abstract'].tolist()

                        # Embed batch
                        embeddings = ti.embedding_model.invoke(abstracts)

                        # Store embeddings with paper data
                        for j, (idx, row) in enumerate(batch.iterrows()):
                            embedding = embeddings[j]
                            all_embeddings.append(embedding)
                            papers_to_save.append((idx, embedding))

                        processed_count += len(batch)

                        # Update checkpoint every 1000 papers for UI
                        if processed_count % 1000 == 0:
                            checkpoint_mgr.save(
                                job_id=job_id,
                                operation="profile_aware_embed",
                                parameters={
                                    "start_date": ti.start_date,
                                    "end_date": ti.end_date,
                                    "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                                },
                                progress={
                                    "total_papers": len(papers_to_embed),
                                    "processed_papers": processed_count,
                                    "offset": processed_count
                                },
                                statistics={
                                    "papers_embedded": processed_count,
                                    "papers_failed": 0
                                }
                            )

                        # Flush to disk periodically to free memory
                        if len(papers_to_save) >= chunk_size:
                            # Create partial dataframe with embeddings
                            indices = [idx for idx, _ in papers_to_save]
                            embs = [emb for _, emb in papers_to_save]
                            papers_to_embed.loc[indices, 'abstract_embedding'] = embs
                            papers_to_embed.loc[indices, 'cosine_similarity'] = [0.0] * len(embs)

                            if ti.verbose:
                                print(f"💾 Flushed {len(papers_to_save)} papers to memory")

                            # Clear buffers
                            papers_to_save = []

                            # Force garbage collection to free memory
                            import gc
                            gc.collect()

                        # Update progress
                        if progress_callback:
                            embed_progress = 36 + (i / len(papers_to_embed)) * 40
                            progress_callback("embed", embed_progress, f"Embedded {min(i+batch_size, len(papers_to_embed))}/{len(papers_to_embed)} papers")

                    # Flush any remaining papers
                    if papers_to_save:
                        indices = [idx for idx, _ in papers_to_save]
                        embs = [emb for _, emb in papers_to_save]
                        papers_to_embed.loc[indices, 'abstract_embedding'] = embs
                        papers_to_embed.loc[indices, 'cosine_similarity'] = [0.0] * len(embs)

                    # Final assignment
                    embedded_df = papers_to_embed
                    embedded_count = len(embedded_df)
                    ti._save_checkpoint('papers_embedded', embedded_df)

                    # Final checkpoint update
                    checkpoint_mgr.save(
                        job_id=job_id,
                        operation="profile_aware_embed",
                        parameters={
                            "start_date": ti.start_date,
                            "end_date": ti.end_date,
                            "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown"
                        },
                        progress={
                            "total_papers": len(papers_to_embed),
                            "processed_papers": embedded_count,
                            "offset": embedded_count
                        },
                        statistics={
                            "papers_embedded": embedded_count,
                            "papers_failed": 0
                        }
                    )

                    # Clean up checkpoint after successful completion
                    checkpoint_mgr.delete(job_id)

                    if ti.verbose:
                        print(f"✅ Embedded {embedded_count} papers")
                        print(f"🗑️  Cleaned up job checkpoint: {job_id}")

                except Exception as e:
                    # On failure, update checkpoint but DON'T delete
                    # This allows the UI to show the hung job and where it stopped
                    checkpoint_mgr.save(
                        job_id=job_id,
                        operation="profile_aware_embed",
                        parameters={
                            "start_date": ti.start_date,
                            "end_date": ti.end_date,
                            "model_name": ti.embedding_model.model_name if hasattr(ti.embedding_model, 'model_name') else "unknown",
                            "error": str(e)  # Include error in parameters for debugging
                        },
                        progress={
                            "total_papers": len(papers_to_embed),
                            "processed_papers": processed_count,
                            "offset": processed_count
                        },
                        statistics={
                            "papers_embedded": processed_count,
                            "papers_failed": len(papers_to_embed) - processed_count
                        }
                    )

                    if ti.verbose:
                        print(f"❌ Embedding failed at {processed_count}/{len(papers_to_embed)} papers")
                        print(f"💾 Job checkpoint preserved for debugging: {job_id}")

                    # Re-raise the exception
                    raise
            else:
                embedded_count = len(embedded_df)
                if ti.verbose:
                    print(f"🧠 Using cached embeddings: {embedded_count} papers")
        else:
            embedded_df = pd.DataFrame()
            if ti.verbose:
                print("ℹ️ No papers need embedding")

        if progress_callback:
            progress_callback("embed", 76, "Embedding complete")

        # -----------
        # Stage 4: Store Papers
        # -----------
        saved_count = 0
        if len(embedded_df) > 0:
            if progress_callback:
                progress_callback("store", 77, "Storing papers to database")

            storage_result = ti._load_checkpoint('papers_stored')
            if storage_result is None:
                # Debug logging to understand the data
                if ti.verbose:
                    print(f"\n💾 STORING {len(embedded_df)} PAPERS WITHOUT SCORING")
                    print("="*60)
                    if not embedded_df.empty:
                        print("Sample data columns:", embedded_df.columns.tolist())
                        print("First row sample:")
                        first_row = embedded_df.iloc[0]
                        for col in ['title', 'abstract', 'pdf_url', 'date', 'cosine_similarity']:
                            if col in embedded_df.columns:
                                print(f"  {col}: {first_row[col][:100] if isinstance(first_row[col], str) else first_row[col]}")

                storage_result = ti.store_papers_without_scoring(embedded_df)
                ti._save_checkpoint('papers_stored', storage_result)
                saved_count = storage_result['saved_count']
            else:
                saved_count = storage_result['saved_count']
                if ti.verbose:
                    print(f"💾 Using cached storage result: {storage_result}")

        if progress_callback:
            progress_callback("store", 100, "Storage complete")

        # Clean up checkpoints after successful completion
        ti._cleanup_checkpoints()

        total_result = {
            'saved_count': saved_count,
            'embedded_count': embedded_count,
            'skipped_count': skipped_count,
            'total_processed': len(data_df)
        }

        if ti.verbose:
            print("\n🎉 BULK EMBEDDING PIPELINE COMPLETE!")
            print("="*60)
            print(f"✅ Total papers processed: {total_result['total_processed']}")
            print(f"🧠 Papers embedded: {total_result['embedded_count']}")
            print(f"💾 New papers saved: {total_result['saved_count']}")
            print(f"⏭️  Papers skipped (already embedded): {total_result['skipped_count']}")
            print("📝 Papers are ready for profile-specific scoring")

        return total_result

    except Exception as e:
        ti._log_error(500, e)
        raise
    finally:
        # Restore original FORCE_KAGGLE setting
        if old_force_kaggle is not None:
            os.environ['FORCE_KAGGLE'] = old_force_kaggle
        else:
            os.environ.pop('FORCE_KAGGLE', None)

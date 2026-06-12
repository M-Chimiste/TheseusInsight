"""Harvest / embedding / keyword backfill orchestration (extracted from
the bulk_operations router in refactor B7)."""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ..data_processing.checkpoint_manager import CheckpointManager
from ..data_processing.arxiv import ArxivDataProcessor
from ..data_access.papers import PaperRepository
from ..data_model.papers import Paper as PaperModel
from ..utils.harvest_and_judge import harvest_and_judge
from ..utils.backfill_embeddings import backfill_embeddings
from ..utils.backfill_keywords import backfill_keywords
from ..db import get_connection_pool
from ..api.models import (
    BackfillEmbeddingsRequest, BackfillKeywordsRequest, HarvestJudgeRequest,
)

logger = logging.getLogger(__name__)

def _filter_valid_abstracts(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter out papers with missing or empty abstracts."""
    filtered = []
    for p in papers:
        title = (p.get('title') or '').strip()
        abstract = (p.get('abstract') or p.get('summary') or '').strip()
        if title and abstract:
            filtered.append(p)
    return filtered

async def _ensure_embeddings_for_range(date_from: Optional[str], date_to: Optional[str]) -> int:
    """Ensure all papers in the date range have embeddings before judging.
    
    Uses StreamingEmbeddingService for memory-efficient processing of large datasets.
    Returns number of embeddings computed.
    """
    if not date_from and not date_to:
        return 0

    # Check if any papers need embeddings
    count = PaperRepository.count_papers_missing_embeddings_in_date_range(
        start_date=date_from, 
        end_date=date_to
    )
    
    if count == 0:
        logger.info("Preflight: all papers already have embeddings; skipping embedding stage")
        return 0
    
    logger.info(f"🔍 Preflight: {count} papers missing embeddings in range {date_from}..{date_to}")
    
    # Get embedding model config from settings
    from ..data_access import SettingsRepository
    import json
    
    orchestration_config = SettingsRepository.get_orchestration_config()
    embedding_config = orchestration_config.get('embedding_model', {})
    
    model_name = embedding_config.get('model_name', 'Alibaba-NLP/gte-large-en-v1.5')
    trust_remote_code = embedding_config.get('trust_remote_code', True)
    
    logger.info(f"📋 Using embedding model from settings: {model_name}")
    
    # Use streaming service for memory-efficient processing
    from ..services import StreamingEmbeddingService, EmbeddingServiceConfig
    
    performance_config = SettingsRepository.get_performance_config()
    auto_tune = performance_config.get('auto_tune_batch_size', True)

    embedding_kwargs = {}
    if not auto_tune and performance_config.get('embedding_batch_size'):
        embedding_kwargs['gpu_batch_size'] = int(performance_config['embedding_batch_size'])
        logger.info(f"📐 Auto-tuning disabled: using configured batch size {embedding_kwargs['gpu_batch_size']}")

    config = EmbeddingServiceConfig(
        # chunk_size uses default (5000) for Metal GPU compatibility
        # gpu_batch_size is auto-tuned unless disabled in the performance config
        model_name=model_name,
        trust_remote_code=trust_remote_code,
        auto_tune_batch_size=auto_tune,
        db_flush_interval=1000,
        verbose=True,
        **embedding_kwargs
    )
    
    service = StreamingEmbeddingService(config)
    
    # Generate job ID for tracking in UI
    job_id = uuid4()
    logger.info(f"📋 Created embedding job: {job_id}")
    
    # Run embedding with progress logging
    def log_progress(current, total):
        if current % 10000 == 0 or current == total:
            logger.info(f"📊 Embedding progress: {current}/{total} papers ({100*current/total:.1f}%)")
    
    stats = await service.embed_papers_in_date_range(
        start_date=date_from,
        end_date=date_to,
        job_id=job_id,  # Pass job_id for UI tracking
        progress_callback=log_progress
    )
    
    logger.info(f"✅ Preflight: embedded {stats['papers_embedded']} papers in {stats['elapsed_seconds']:.1f}s")
    logger.info(f"⚡ Throughput: {stats['papers_per_second']:.1f} papers/second")
    
    if stats['papers_failed'] > 0:
        logger.warning(f"⚠️  {stats['papers_failed']} papers failed to embed")
    
    return stats['papers_embedded']

def _merge_profile_arxiv_filters(profile_ids: List[int]) -> Optional[Dict[str, Any]]:
    """
    Merge arXiv filters from multiple profiles.
    Returns merged filters with union of all categories, or None if no filters found.
    """
    from ..data_access.profiles import ProfileRepository
    import json
    
    all_categories = set()
    main_categories = set()
    has_filters = False
    
    for profile_id in profile_ids:
        profile = ProfileRepository.get_by_id(profile_id)
        if not profile:
            continue
            
        arxiv_filters = profile.get('arxiv_filters')
        if not arxiv_filters:
            continue
            
        # Parse JSON if it's a string
        if isinstance(arxiv_filters, str):
            try:
                arxiv_filters = json.loads(arxiv_filters)
            except json.JSONDecodeError:
                continue
        
        if arxiv_filters and isinstance(arxiv_filters, dict):
            has_filters = True
            
            # Get filter_categories (subcategories like cs.AI, cs.CL)
            filter_cats = arxiv_filters.get('filter_categories', [])
            if filter_cats:
                all_categories.update(filter_cats)
                
                # Extract main categories from subcategories
                for cat in filter_cats:
                    if '.' in cat:
                        main_cat = cat.split('.')[0]
                        main_categories.add(main_cat)
            
            # Get main_category
            main_cat = arxiv_filters.get('main_category')
            if main_cat:
                main_categories.add(main_cat)
    
    if not has_filters:
        return None
    
    # Return merged filters
    return {
        'main_category': list(main_categories)[0] if main_categories else None,
        'filter_categories': list(all_categories) if all_categories else None
    }

def _download_arxiv_for_range(
    date_from: Optional[str], 
    date_to: Optional[str],
    overwrite_existing: bool = False,
    profile_ids: Optional[List[int]] = None,
    use_profile_arxiv_filters: bool = True
) -> Dict[str, int]:
    """Download papers from arXiv for the given range and insert into DB.
    
    Args:
        date_from: Start date for the range
        date_to: End date for the range
        overwrite_existing: If True, download regardless of existing data.
                          If False, skip download if papers exist.
        profile_ids: List of profile IDs to use for arXiv filtering
        use_profile_arxiv_filters: If True, use arXiv filters from profiles
    
    Returns:
        Stats dict {total, imported, skipped, errors} from bulk_insert.
    """
    if not date_from and not date_to:
        logger.info("Preflight: no date range provided; skipping arXiv download")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    # Determine arXiv filters
    category = None
    subcategories = None
    
    if use_profile_arxiv_filters and profile_ids:
        merged_filters = _merge_profile_arxiv_filters(profile_ids)
        if merged_filters:
            category = merged_filters.get('main_category')
            subcategories = merged_filters.get('filter_categories')
            logger.info(
                f"🏷️  Preflight: using profile arXiv filters - "
                f"main_category={category}, filter_categories={subcategories}"
            )
        else:
            logger.info("ℹ️  Preflight: no arXiv filters found in profiles, downloading all categories")
    else:
        logger.info("ℹ️  Preflight: profile filtering disabled, downloading all arXiv categories")

    # Check for existing papers and decide whether to skip download
    try:
        counts = PaperRepository.count_embeddings_status_in_date_range(start_date=date_from, end_date=date_to)
        paper_count = counts.get('total', 0)
        embedded_count = counts.get('embedded', 0)
        
        # Only skip download if we have existing data AND overwrite is not requested
        if paper_count > 0 and not overwrite_existing:
            logger.info(
                f"📦 Preflight: existing papers {paper_count} (embedded {embedded_count}) in range {date_from}..{date_to}; skipping download (overwrite_existing=False)"
            )
            return {"total": paper_count, "imported": 0, "skipped": paper_count, "errors": 0}
        elif paper_count > 0 and overwrite_existing:
            logger.info(
                f"🔄 Preflight: existing papers {paper_count} found, but overwrite_existing=True; proceeding with download"
            )
    except Exception as e:
        logger.warning(f"Preflight: existing-data check failed; will attempt download: {e}")

    logger.info(f"📡 Preflight: downloading arXiv papers for range {date_from}..{date_to}")
    try:
        # Force Kaggle via explicit flag to avoid persistent env state
        proc = ArxivDataProcessor(
            start_date=date_from, 
            end_date=date_to, 
            category=category, 
            subcategories=subcategories, 
            force_kaggle=True
        )
        df = proc.download_and_process_data()
    except Exception as e:
        logger.warning(f"Preflight: arXiv download failed: {e}")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 1}

    if df is None or df.empty:
        logger.info("Preflight: arXiv download returned no new records")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    # Convert to PaperModel list
    papers: List[PaperModel] = []
    from datetime import date as _date
    today = _date.today().strftime('%Y-%m-%d')
    for _, row in df.iterrows():
        title = row.get('title') or ''
        abstract = row.get('abstract') or ''
        pdf_url = row.get('pdf_url') or row.get('url') or ''
        created = row.get('date')
        # Ensure date string
        if hasattr(created, 'strftime'):
            created_str = created.strftime('%Y-%m-%d')
        else:
            created_str = str(created) if created else today
        try:
            papers.append(PaperModel(
                title=title,
                abstract=abstract,
                date=created_str,
                date_run=today,
                score=None,
                rationale=None,
                related=False,
                cosine_similarity=0.0,
                url=pdf_url,
                embedding_model="pending",
                embedding=None
            ))
        except Exception:
            # Skip malformed rows
            continue

    if not papers:
        logger.info("Preflight: no valid papers to insert after download")
        return {"total": 0, "imported": 0, "skipped": 0, "errors": 0}

    logger.info(f"💾 Preflight: inserting up to {len(papers)} downloaded papers into DB (skipping duplicates)")
    stats = PaperRepository.bulk_insert(papers, skip_duplicates=True)
    logger.info(f"✅ Preflight: arXiv insert stats: {stats}")
    return stats

async def run_harvest_judge_task(
    job_id: UUID,
    request: HarvestJudgeRequest,
    checkpoint_manager: CheckpointManager
):
    """Run harvest and judge operation in background."""
    try:
        await harvest_and_judge(
            date_from=request.date_from,
            date_to=request.date_to,
            checkpoint_dir=".",  # Not used with database checkpoints
            top_n=request.top_n,
            cosine_threshold=request.cosine_threshold,
            update_existing=request.update_existing,
            batch_size=request.batch_size,
            max_workers=request.max_workers,
            rate_limit_requests=request.rate_limit_requests,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

async def run_backfill_embeddings_task(
    job_id: UUID,
    request: BackfillEmbeddingsRequest,
    checkpoint_manager: CheckpointManager
):
    """Run embeddings backfill operation in background."""
    try:
        await backfill_embeddings(
            limit=request.limit,
            batch_size=request.batch_size,
            start_date=request.start_date,
            end_date=request.end_date,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

async def run_backfill_keywords_task(
    job_id: UUID,
    request: BackfillKeywordsRequest,
    checkpoint_manager: CheckpointManager
):
    """Run keywords backfill operation in background."""
    try:
        await backfill_keywords(
            limit=request.limit,
            batch_size=request.batch_size,
            start_date=request.start_date,
            end_date=request.end_date,
            use_database_checkpoints=True,
            job_id=job_id
        )
    except Exception as e:
        await checkpoint_manager.fail_job(job_id, str(e))
        raise

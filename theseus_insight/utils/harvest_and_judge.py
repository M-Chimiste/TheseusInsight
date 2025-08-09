#!/usr/bin/env python3
"""Simple script to harvest papers from arXiv, score them and insert into the database.

This utility pulls orchestration and arXiv configuration from the database and
mimics the first part of the ``TheseusInsight`` pipeline. It supports
checkpoints so interrupted runs can be resumed.
"""

import argparse
import os
import sys
import json
import time
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from concurrent.futures import ThreadPoolExecutor
from functools import partial

from tqdm import tqdm
import pandas as pd
import json_repair
import torch
import yake

# Add project root to import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from theseus_insight.data_access import PaperRepository, SettingsRepository, BulkImporter
from theseus_insight.data_model.papers import Paper
from theseus_insight.data_processing.arxiv import ArxivDataProcessor
from theseus_insight.data_processing.checkpoint_manager import CheckpointManager
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.inference.llm import (
    OllamaInference, OpenAIInference, AnthropicInference, GeminiInference
)
from theseus_insight.prompt import (
    RESEARCH_INTERESTS_SYSTEM_PROMPT,
    research_prompt,
)
from theseus_insight.utils import cosine_similarity, purge_ollama_cache
from theseus_insight.data_processing.memory_efficient_pipeline import (
    MemoryMonitor, ChunkedDataProcessor, EfficientBulkProcessor,
    optimize_dataframe_memory
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


# ---------------------------------------------------------------
# Helper functions for database operations
# ---------------------------------------------------------------

def check_paper_exists(paper_data: tuple, existing_urls: Set[str], existing_titles: Set[str]) -> bool:
    """Return True if paper already exists, based on URL **or** title."""
    idx, paper_url, paper_title = paper_data
    # Check existence using in-memory sets for O(1) lookup
    exists_by_url = paper_url in existing_urls if paper_url else False
    exists_by_title = paper_title in existing_titles
    return exists_by_url or exists_by_title


def get_paper_count() -> int:
    """
    Get the total number of papers in the database.
    
    Returns:
        int: Number of papers in database
    """
    try:
        papers = PaperRepository.get_all()
        return len(papers)
    except Exception:
        return -1  # Return -1 to indicate error/unknown


def should_skip_database_checks(verbose: bool = True) -> bool:
    """
    Determine if we should skip database existence checks.
    
    Args:
        verbose: Whether to print status messages
    
    Returns:
        bool: True if database checks should be skipped
    """
    try:
        paper_count = get_paper_count()
        
        if paper_count == 0:
            if verbose:
                print("📊 Database is empty - skipping existence checks")
            return True
        elif paper_count < 100:
            if verbose:
                print(f"📊 Database has only {paper_count} papers - skipping existence checks for speed")
            return True
        else:
            if verbose:
                print(f"📊 Database has {paper_count} papers - performing existence checks")
            return False
            
    except Exception as e:
        if verbose:
            print(f"⚠️ Could not check database size: {e} - performing existence checks")
        return False


def check_existing_papers_parallel(
    df: pd.DataFrame, 
    max_workers: int = 4,
    verbose: bool = True
) -> List[bool]:
    """
    Check for existing papers using optimized bulk checking.
    
    Args:
        df: DataFrame with papers to check
        max_workers: Maximum number of parallel workers (not used in optimized version)
        verbose: Whether to show progress
    
    Returns:
        List[bool]: List indicating which papers are new (not existing)
    """
    if verbose:
        print(f"🔍 Checking for existing papers using optimized bulk query...")
    
    # Extract URLs and titles from dataframe
    urls = []
    titles = []
    for _, row in df.iterrows():
        url = row.get("pdf_url") or row.get("url_pdf") or row.get("url")
        if url:
            urls.append(url)
        titles.append(row["title"])
    
    # Get existing URLs and titles in bulk
    existing_urls, existing_titles = PaperRepository.bulk_check_existence(urls, titles)
    
    # Check each paper
    new_mask = []
    for _, row in df.iterrows():
        url = row.get("pdf_url") or row.get("url_pdf") or row.get("url")
        title = row["title"]
        
        exists_by_url = url in existing_urls if url else False
        exists_by_title = title in existing_titles
        is_new = not (exists_by_url or exists_by_title)
        new_mask.append(is_new)
    
    if verbose:
        existing_count = sum(1 for is_new in new_mask if not is_new)
        print(f"✅ Found {existing_count} existing papers, {sum(new_mask)} new papers")
    
    return new_mask


# ---------------------------------------------------------------
# Helper functions for checkpoints
# ---------------------------------------------------------------

def _checkpoint_path(checkpoint_dir: str, stage: str) -> Path:
    return Path(checkpoint_dir) / f"{stage}.pkl"


def save_checkpoint(checkpoint_dir: str, stage: str, data: Any, verbose: bool = True) -> None:
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    cp = {
        "data": data,
        "timestamp": time.time(),
        "stage": stage,
    }
    with open(_checkpoint_path(checkpoint_dir, stage), "wb") as f:
        pickle.dump(cp, f)
    if verbose:
        print(f"✅ Checkpoint saved: {stage}")


def load_checkpoint(checkpoint_dir: str, stage: str, verbose: bool = True):
    path = _checkpoint_path(checkpoint_dir, stage)
    if path.exists():
        with open(path, "rb") as f:
            cp = pickle.load(f)
        if verbose:
            print(f"📂 Loaded checkpoint '{stage}' from {time.ctime(cp['timestamp'])}")
        return cp["data"]
    return None


# ---------------------------------------------------------------
# Model loader helper
# ---------------------------------------------------------------

def load_inference_model(cfg: Dict[str, Any], verbose: bool = True):
    model_type = cfg.get("model_type")
    model_name = cfg.get("model_name")
    max_new_tokens = cfg.get("max_new_tokens", 4096)
    temperature = cfg.get("temperature", 0.1)
    num_ctx = cfg.get("num_ctx")
    
    if verbose:
        print(f"🤖 Loading {model_type} model: {model_name}")
    
    if model_type == "ollama":
        kwargs = {
            "model_name": model_name,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "url": OLLAMA_URL,
        }
        if num_ctx is not None:
            kwargs["num_ctx"] = num_ctx
        return OllamaInference(**kwargs)
    if model_type == "openai":
        return OpenAIInference(model_name, max_new_tokens, temperature)
    if model_type == "anthropic":
        return AnthropicInference(model_name, max_new_tokens, temperature)
    if model_type == "gemini":
        return GeminiInference(model_name, max_new_tokens, temperature)
    raise ValueError(f"Unsupported model type: {model_type}")


def clear_judge_cache(inference, model_name: str, verbose: bool = True):
    try:
        if hasattr(inference, "provider") and inference.provider == "ollama":
            if verbose:
                print(f"🧹 Clearing Ollama cache for {model_name}")
            purge_ollama_cache(OLLAMA_URL, model_name)
    except Exception as e:
        if verbose:
            print(f"⚠️ Failed to purge cache for {model_name}: {e}")


# ---------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------

async def download_papers(
    date_from: str, 
    date_to: str, 
    category: str, 
    subcats: List[str], 
    checkpoint_dir: str, 
    checkpoint_manager: CheckpointManager,
    job_id: Optional[str] = None,
    retries: int = 3,
    verbose: bool = True
):
    if verbose:
        print("\n" + "="*60)
        print("📥 STAGE 1: DOWNLOADING PAPERS FROM ARXIV")
        print("="*60)
    
    # Check for resumable job if no job_id provided
    if not job_id and checkpoint_manager:
        config = {
            "date_from": date_from,
            "date_to": date_to,
            "category": category,
            "subcategories": subcats
        }
        job_id = await checkpoint_manager.find_resumable_job("harvest_judge", config)
        
    # Load from database checkpoint if available
    if job_id and checkpoint_manager:
        checkpoint = await checkpoint_manager.get_latest_checkpoint(job_id, "download")
        if checkpoint:
            data_df = pd.DataFrame(checkpoint['checkpoint_data']['papers'])
            if verbose:
                print(f"📊 Found {len(data_df)} papers in database checkpoint")
            return data_df
    
    # Fall back to file checkpoint
    data_df = load_checkpoint(checkpoint_dir, "download", verbose)
    if data_df is not None:
        if verbose:
            print(f"📊 Found {len(data_df)} papers in file checkpoint")
        return data_df
    
    if verbose:
        print(f"🌐 Downloading ArXiv papers:")
        print(f"   📅 Date range: {date_from} to {date_to}")
        print(f"   📂 Main category: {category}")
        print(f"   🏷️ Subcategories: {subcats}")
    
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            if verbose and attempt > 1:
                print(f"🔄 Download attempt {attempt}/{retries}")
            
            proc = ArxivDataProcessor(
                start_date=date_from,
                end_date=date_to,
                category=category,
                subcategories=subcats,
            )
            
            if verbose:
                print(f"📡 Fetching papers from ArXiv API...")
            
            data_df = proc.download_and_process_data()
            
            if verbose:
                print(f"✅ Successfully downloaded {len(data_df)} papers")
            
            # Save to both checkpoints
            save_checkpoint(checkpoint_dir, "download", data_df, verbose)
            
            if job_id and checkpoint_manager:
                await checkpoint_manager.save_checkpoint(
                    job_id,
                    "download",
                    {"papers": data_df.to_dict('records')},
                    len(data_df)
                )
                await checkpoint_manager.update_progress(job_id, len(data_df), len(data_df))
            
            return data_df
            
        except Exception as e:
            if verbose:
                print(f"❌ Download attempt {attempt} failed: {e}")
            if attempt >= retries:
                raise
            time.sleep(2)
    return None


async def embed_papers(
    df: pd.DataFrame, 
    embedding_model: SentenceTransformerInference, 
    research_interests: str, 
    threshold: float, 
    checkpoint_dir: str,
    checkpoint_manager: CheckpointManager,
    job_id: Optional[str] = None,
    batch_size: int = 256,
    max_workers: int = 4,
    verbose: bool = True
) -> pd.DataFrame:
    if verbose:
        print("\n" + "="*60)
        print("🧠 STAGE 2: EMBEDDING AND FILTERING PAPERS")
        print("="*60)
        if batch_size > 1:
            print(f"⚡ Using batch processing with batch size: {batch_size}")
    
    # Check database checkpoint first
    if job_id and checkpoint_manager:
        checkpoint = await checkpoint_manager.get_latest_checkpoint(job_id, "embed")
        if checkpoint:
            embedded_df = pd.DataFrame(checkpoint['checkpoint_data']['papers'])
            if verbose:
                print(f"📊 Found {len(embedded_df)} embedded papers in database checkpoint")
            return embedded_df
    
    # Fall back to file checkpoint
    embedded_df = load_checkpoint(checkpoint_dir, "embed", verbose)
    if embedded_df is not None:
        if verbose:
            print(f"📊 Found {len(embedded_df)} embedded papers in file checkpoint")
        return embedded_df

    if df.empty:
        if verbose:
            print("⚠️ No papers to embed (empty dataset)")
        save_checkpoint(checkpoint_dir, "embed", df, verbose)
        return df

    # Smart database checking with optimization
    skip_checks = should_skip_database_checks(verbose)
    
    if skip_checks:
        # Skip database checks entirely for speed
        new_df = df.copy()
        if verbose:
            print(f"📝 Processing all {len(new_df)} papers (database checks skipped)")
    else:
        # Always use optimized bulk checking (works for any dataset size)
        new_mask = check_existing_papers_parallel(df, max_workers, verbose)
        
        new_df = df[new_mask].reset_index(drop=True)
        
        if verbose:
            existing_count = len(df) - len(new_df)
            print(f"📝 Found {existing_count} existing papers, {len(new_df)} new papers to process")

    if new_df.empty:
        embedded_df = new_df.copy()
        embedded_df["cosine_similarity"] = []
        embedded_df["abstract_embedding"] = []
        save_checkpoint(checkpoint_dir, "embed", embedded_df, verbose)
        if verbose:
            print("✅ No new papers to embed")
        return embedded_df

    # Filter out papers with missing or empty abstracts
    original_count = len(new_df)
    abstract_mask = new_df["abstract"].notna() & (new_df["abstract"].str.strip() != "")
    new_df = new_df[abstract_mask].reset_index(drop=True)
    
    if verbose and original_count != len(new_df):
        filtered_out = original_count - len(new_df)
        print(f"⚠️ Filtered out {filtered_out} papers with missing/empty abstracts")
    
    if new_df.empty:
        embedded_df = new_df.copy()
        embedded_df["cosine_similarity"] = []
        embedded_df["abstract_embedding"] = []
        save_checkpoint(checkpoint_dir, "embed", embedded_df, verbose)
        if verbose:
            print("✅ No papers with valid abstracts to embed")
        return embedded_df

    if verbose:
        print(f"🎯 Embedding research interests...")
    research_emb = embedding_model.invoke(research_interests)
    
    if verbose:
        print(f"📄 Embedding {len(new_df)} paper abstracts...")
        if batch_size > 1:
            print(f"⚡ Using SentenceTransformer built-in batching with batch_size={batch_size}")
    
    # Use SentenceTransformer's built-in batching for maximum efficiency
    abstracts = list(new_df["abstract"])
    
    if batch_size <= 1:
        # No batching - process one by one with individual progress
        embeddings = []
        sims = []
        with tqdm(abstracts, desc="Embedding abstracts", disable=not verbose) as pbar:
            for abstract in pbar:
                emb = embedding_model.invoke(abstract)
                embeddings.append(emb)
                sim = cosine_similarity(emb, research_emb)
                sims.append(sim)
    else:
        # Use chunked processing for large datasets to avoid MPS memory limits
        chunk_size = min(50000, len(abstracts))  # Process max 50k papers at a time
        embeddings = []
        
        if verbose and len(abstracts) > chunk_size:
            print(f"📦 Processing in chunks of {chunk_size} papers to avoid GPU memory limits")
        
        # Step 1: Generate all embeddings in chunks
        for chunk_start in tqdm(range(0, len(abstracts), chunk_size), 
                               desc="Embedding chunks", 
                               disable=not verbose or len(abstracts) <= chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(abstracts))
            chunk_abstracts = abstracts[chunk_start:chunk_end]
            
            if verbose and len(abstracts) > chunk_size:
                print(f"🔄 Embedding chunk {chunk_start//chunk_size + 1}/{(len(abstracts) + chunk_size - 1)//chunk_size}: {len(chunk_abstracts)} papers")
            
            # Use SentenceTransformer's efficient built-in batching within chunk
            chunk_embeddings = embedding_model.invoke(
                chunk_abstracts, 
                batch_size=batch_size,
                show_progress_bar=verbose and len(abstracts) <= chunk_size
            )
            
            # Collect embeddings
            embeddings.extend(chunk_embeddings)
            
            if verbose and len(abstracts) > chunk_size:
                print(f"✅ Chunk embedded - {len(chunk_embeddings)} embeddings generated")
        
        # Step 2: Calculate all similarities after embeddings are complete
        if verbose:
            print(f"🧮 Calculating cosine similarities for {len(embeddings)} papers...")
        
        sims = []
        for emb in tqdm(embeddings, desc="Computing similarities", disable=not verbose):
            sim = cosine_similarity(emb, research_emb)
            sims.append(sim)
        
        if verbose:
            print(f"✅ All similarities calculated")
    
    new_df["abstract_embedding"] = embeddings
    new_df["cosine_similarity"] = sims
    
    # Save progress after embedding
    if job_id and checkpoint_manager:
        await checkpoint_manager.update_progress(job_id, len(new_df), len(df))
    
    filtered_df = new_df[new_df["cosine_similarity"] >= threshold].reset_index(drop=True)
    
    if verbose:
        filtered_count = len(filtered_df)
        total_count = len(new_df)
        print(f"🎯 Filtered to {filtered_count}/{total_count} papers above threshold {threshold}")
        if filtered_count > 0:
            avg_sim = filtered_df["cosine_similarity"].mean()
            max_sim = filtered_df["cosine_similarity"].max()
            print(f"📊 Similarity stats - Average: {avg_sim:.3f}, Max: {max_sim:.3f}")
        if batch_size > 1:
            print(f"⚡ Batching improved efficiency: processed {total_count} papers in {len(embeddings)} batches")
    
    # Save to both checkpoints
    save_checkpoint(checkpoint_dir, "embed", filtered_df, verbose)
    
    if job_id and checkpoint_manager:
        await checkpoint_manager.save_checkpoint(
            job_id,
            "embed",
            {"papers": filtered_df.to_dict('records')},
            len(filtered_df),
            {"stage": "embed_complete", "filtered_count": len(filtered_df)}
        )
    
    return filtered_df


async def rank_papers(
    df: pd.DataFrame, 
    judge_model, 
    research_interests: str, 
    checkpoint_dir: str, 
    checkpoint_manager: CheckpointManager,
    top_n: int, 
    job_id: Optional[str] = None,
    verbose: bool = True
) -> pd.DataFrame:
    if verbose:
        print("\n" + "="*60)
        print("⚖️ STAGE 3: RANKING PAPERS WITH JUDGE MODEL")
        print("="*60)
    
    # Check database checkpoint first
    if job_id and checkpoint_manager:
        checkpoint = await checkpoint_manager.get_latest_checkpoint(job_id, "rank")
        if checkpoint:
            ranked_df = pd.DataFrame(checkpoint['checkpoint_data']['papers'])
            if verbose:
                print(f"📊 Found {len(ranked_df)} ranked papers in database checkpoint")
            return ranked_df
    
    # Fall back to file checkpoint
    ranked_df = load_checkpoint(checkpoint_dir, "rank", verbose)
    if ranked_df is not None:
        if verbose:
            print(f"📊 Found {len(ranked_df)} ranked papers in file checkpoint")
        return ranked_df

    if df.empty:
        if verbose:
            print("⚠️ No papers to rank (empty dataset)")
        ranked_df = df.copy()
        save_checkpoint(checkpoint_dir, "rank", ranked_df, verbose)
        return ranked_df

    abstracts = list(df["abstract"])
    scores, related, rationale = [], [], []
    failed = []
    consecutive_failures = 0
    
    # Try database checkpoint first for partial progress
    start_idx = 0
    if job_id and checkpoint_manager:
        db_partial = await checkpoint_manager.get_latest_checkpoint(job_id, "rank_progress")
        if db_partial:
            partial_data = db_partial['checkpoint_data']
            scores = partial_data.get("scores", [])
            related = partial_data.get("related", [])
            rationale = partial_data.get("rationale", [])
            failed = partial_data.get("failed_papers", [])
            start_idx = len(scores)
            if verbose:
                print(f"🔄 Resuming ranking from paper {start_idx + 1}/{len(abstracts)} (database checkpoint)")
    else:
        # Fall back to file checkpoint
        partial = load_checkpoint(checkpoint_dir, "rank_partial", verbose=False)
        if partial:
            scores = partial.get("scores", [])
            related = partial.get("related", [])
            rationale = partial.get("rationale", [])
            failed = partial.get("failed_papers", [])
            start_idx = len(scores)
            if verbose:
                print(f"🔄 Resuming ranking from paper {start_idx + 1}/{len(abstracts)} (file checkpoint)")

    if verbose:
        print(f"🎯 Ranking {len(abstracts) - start_idx} papers using {judge_model.model_name}")

    with tqdm(abstracts[start_idx:], desc="Ranking papers", initial=start_idx, total=len(abstracts), disable=not verbose) as pbar:
        for i, abstract in enumerate(pbar):
            idx = start_idx + i
            success = False
            attempts = 0
            
            while not success and attempts < 3:
                attempts += 1
                try:
                    if attempts == 2 and consecutive_failures > 2:
                        if verbose:
                            pbar.write(f"🧹 Clearing cache due to consecutive failures")
                        clear_judge_cache(judge_model, judge_model.model_name, verbose=False)
                    
                    messages = [{"role": "user", "content": research_prompt(research_interests, abstract)}]
                    if getattr(judge_model, "provider", "") == "ollama":
                        resp = judge_model.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT, schema=None)
                    else:
                        resp = judge_model.invoke(messages=messages, system_prompt=RESEARCH_INTERESTS_SYSTEM_PROMPT)
                    
                    try:
                        resp_json = json_repair.loads(resp)
                        
                        # Ensure resp_json is a dictionary
                        if not isinstance(resp_json, dict):
                            if attempts >= 3:
                                raise TypeError(f"Expected dict from JSON parsing, got {type(resp_json)}")
                            continue
                            
                    except Exception:
                        if attempts >= 3:
                            raise
                        continue
                    
                    try:
                        s_val = int(resp_json["score"])
                        r_val = bool(resp_json["related"])
                        rat = str(resp_json["rationale"])
                        
                        if not (1 <= s_val <= 10):
                            if attempts >= 3:
                                s_val = max(1, min(10, s_val))
                            else:
                                continue
                        
                        scores.append(s_val)
                        related.append(r_val)
                        rationale.append(rat)
                        success = True
                        consecutive_failures = 0
                        
                        pbar.set_postfix({
                            "score": s_val,
                            "related": r_val,
                            "failures": len(failed)
                        })
                        
                    except Exception:
                        if attempts >= 3:
                            raise
                        
                except Exception as e:
                    if attempts >= 3:
                        scores.append(1)
                        related.append(False)
                        rationale.append(f"Failed: {str(e)[:50]}")
                        failed.append(idx)
                        consecutive_failures += 1
                        success = True
                        if verbose:
                            pbar.write(f"❌ Failed to rank paper {idx + 1}: {str(e)[:50]}")
                    else:
                        time.sleep(1)
                        
            # Save partial progress every 50 papers
            if (idx + 1) % 50 == 0:
                partial_data = {
                    "scores": scores,
                    "related": related,
                    "rationale": rationale,
                    "failed_papers": failed,
                }
                save_checkpoint(checkpoint_dir, "rank_partial", partial_data, verbose=False)
                
                # Also save to database checkpoint
                if job_id and checkpoint_manager:
                    await checkpoint_manager.save_checkpoint(
                        job_id,
                        "rank_progress",
                        partial_data,
                        idx + 1,
                        {"stage": "ranking", "current": idx + 1, "total": len(abstracts)}
                    )
                    await checkpoint_manager.update_progress(job_id, idx + 1, len(abstracts))

    if failed and verbose:
        print(f"⚠️ Warning: {len(failed)} papers failed scoring")

    df["score"] = scores
    df["related"] = related
    df["rationale"] = rationale
    df = df.sort_values(by="score", ascending=False)
    
    if verbose:
        related_count = sum(related)
        avg_score = sum(scores) / len(scores) if scores else 0
        max_score = max(scores) if scores else 0
        print(f"📊 Ranking complete:")
        print(f"   - {related_count}/{len(scores)} papers marked as related")
        print(f"   - Average score: {avg_score:.1f}")
        print(f"   - Highest score: {max_score}")
    
    top_df = df.head(top_n)
    
    if verbose:
        print(f"🏆 Selected top {len(top_df)} papers for database insertion")
    
    # Save to both checkpoints
    save_checkpoint(checkpoint_dir, "rank", top_df, verbose)
    
    if job_id and checkpoint_manager:
        await checkpoint_manager.save_checkpoint(
            job_id,
            "rank",
            {"papers": top_df.to_dict('records')},
            len(top_df),
            {"stage": "rank_complete", "top_papers": len(top_df)}
        )
    
    # Clean up partial checkpoint
    cp = _checkpoint_path(checkpoint_dir, "rank_partial")
    if cp.exists():
        cp.unlink()
    
    return top_df


def insert_papers(
    df: pd.DataFrame, 
    all_df: pd.DataFrame, 
    embedding_model_name: str, 
    verbose: bool = True
):
    if verbose:
        print("\n" + "="*60)
        print("💾 STAGE 4: INSERTING PAPERS INTO DATABASE")
        print("="*60)
        print(f"📝 Inserting {len(all_df)} papers into database...")
    
    saved = 0
    dup = 0
    dup_urls = []
    
    extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
    
    with tqdm(all_df.iterrows(), total=len(all_df), desc="Inserting papers", disable=not verbose) as pbar:
        for _, row in pbar:
            emb = row["abstract_embedding"]
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            elif not isinstance(emb, list):
                emb = list(emb)
                
            paper = Paper(
                title=row["title"],
                abstract=row["abstract"],
                url=row["pdf_url"],
                date_run=str(pd.Timestamp.now().date()),
                date=row["date"].strftime("%Y-%m-%d"),
                score=row["score"],
                related=row["related"],
                rationale=row["rationale"],
                cosine_similarity=row["cosine_similarity"],
                embedding_model=embedding_model_name,
                embedding=emb,
            )
            
            inserted = PaperRepository.insert(paper, skip_duplicates=True)

            # Retrieve paper_id whether newly inserted or existing
            paper_rec = PaperRepository.get_by_url(row["pdf_url"])
            if paper_rec:
                pid = paper_rec["id"]
                # If keywords missing, generate & store
                if not PaperRepository.get_keywords(pid):
                    try:
                        text_kw = f"{row['title']} {row['abstract']}"
                        kw_scores = extractor.extract_keywords(text_kw)
                        keywords = [kw for kw, _ in kw_scores]
                        PaperRepository.update_keywords(pid, keywords)
                    except Exception:
                        pass

            if inserted:
                saved += 1
            else:
                dup += 1
                dup_urls.append(row["pdf_url"])
            
            pbar.set_postfix({
                "saved": saved,
                "duplicates": dup
            })
    
    if verbose:
        print(f"✅ Database insertion complete:")
        print(f"   - {saved} new papers saved")
        print(f"   - {dup} duplicates skipped")
    
    return dup_urls


def insert_papers_bulk(
    df: pd.DataFrame, 
    all_df: pd.DataFrame, 
    embedding_model_name: str, 
    verbose: bool = True,
    use_staging: bool = True
):
    """
    Insert papers using bulk operations with staging tables.
    
    This is an optimized version that uses PostgreSQL COPY for much faster imports.
    """
    if verbose:
        print("\n" + "="*60)
        print("💾 STAGE 4: BULK INSERTING PAPERS INTO DATABASE")
        print("="*60)
        print(f"📝 Bulk inserting {len(all_df)} papers into database...")
        if use_staging:
            print("⚡ Using staging tables with PostgreSQL COPY for maximum performance")
    
    if not use_staging:
        # Fall back to regular insert
        return insert_papers(df, all_df, embedding_model_name, verbose)
    
    # Initialize bulk importer
    importer = BulkImporter()
    extractor = yake.KeywordExtractor(lan="en", n=1, top=5)
    
    # Prepare papers for bulk import
    papers = []
    keywords_to_add = []
    
    if verbose:
        print("📦 Preparing papers for bulk import...")
    
    with tqdm(all_df.iterrows(), total=len(all_df), desc="Preparing papers", disable=not verbose) as pbar:
        for idx, row in pbar:
            emb = row["abstract_embedding"]
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            elif not isinstance(emb, list):
                emb = list(emb)
            
            # Generate keywords
            text_kw = f"{row['title']} {row['abstract']}"
            try:
                kw_scores = extractor.extract_keywords(text_kw)
                keywords = [kw for kw, _ in kw_scores]
            except Exception:
                keywords = []
            
            paper = Paper(
                title=row["title"],
                abstract=row["abstract"],
                url=row["pdf_url"],
                date_run=str(pd.Timestamp.now().date()),
                date=row["date"].strftime("%Y-%m-%d"),
                score=row["score"],
                related=row["related"],
                rationale=row["rationale"],
                cosine_similarity=row["cosine_similarity"],
                embedding_model=embedding_model_name,
                embedding=emb,
                keywords=keywords  # Add keywords directly to paper
            )
            
            papers.append(paper)
    
    # Perform bulk import
    if verbose:
        print(f"🚀 Starting bulk import of {len(papers)} papers...")
    
    try:
        stats = importer.import_papers(papers, deduplicate=True, merge=True)
        
        if verbose:
            print(f"✅ Bulk import complete:")
            print(f"   - {stats['papers_staged']} papers staged")
            print(f"   - {stats['duplicates_removed']} duplicates removed")
            print(f"   - {stats['papers_inserted']} new papers inserted")
            print(f"   - Batch ID: {stats['batch_id']}")
        
        # Return list of duplicate URLs (empty since we handled them in staging)
        return []
        
    except Exception as e:
        if verbose:
            print(f"❌ Bulk import failed: {e}")
            print("⚠️ Falling back to individual inserts...")
        
        # Fall back to regular insert
        return insert_papers(df, all_df, embedding_model_name, verbose)


# ---------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------

async def harvest_and_judge(
    date_from: str, 
    date_to: str, 
    checkpoint_dir: str, 
    top_n: int = 5, 
    cosine_threshold: float = 0.5,
    batch_size: int = 256,
    max_workers: int = 4,
    verbose: bool = True,
    use_bulk_insert: bool = True,
    memory_monitoring: bool = True,
    memory_threshold: float = 80.0
):
    # Initialize checkpoint manager
    checkpoint_manager = CheckpointManager()
    await checkpoint_manager.initialize()
    
    # Create or resume job
    config = {
        "date_from": date_from,
        "date_to": date_to,
        "top_n": top_n,
        "cosine_threshold": cosine_threshold,
        "batch_size": batch_size
    }
    
    job_id = await checkpoint_manager.find_resumable_job("harvest_judge", config)
    if job_id:
        if verbose:
            print(f"🔄 Found resumable job {job_id}")
        await checkpoint_manager.resume_job(job_id)
    else:
        job_id = await checkpoint_manager.create_job("harvest_judge", config)
        if verbose:
            print(f"📝 Created new job {job_id}")
    
    # Initialize memory monitoring
    memory_monitor = None
    if memory_monitoring:
        memory_monitor = MemoryMonitor(memory_threshold, verbose)
    
    if verbose:
        print("🚀 THESEUS INSIGHT - ARXIV HARVEST & JUDGE")
        print("="*60)
        print(f"📅 Date range: {date_from} to {date_to}")
        print(f"🎯 Cosine threshold: {cosine_threshold}")
        print(f"🏆 Top papers to select: {top_n}")
        if batch_size > 1:
            print(f"⚡ Embedding batch size: {batch_size}")
        print(f"📁 Checkpoint directory: {checkpoint_dir}")
        if memory_monitoring:
            print(f"💾 Memory monitoring enabled (threshold: {memory_threshold}%)")

    if verbose:
        print(f"\n🔧 Loading configuration...")
    
    orch_json = SettingsRepository.get("orchestration")
    if orch_json:
        orch_cfg = json.loads(orch_json)
        if verbose:
            print("📝 Using orchestration config from database")
    else:
        cfg_path = PROJECT_ROOT / "config" / "orchestration.json"
        with open(cfg_path) as f:
            orch_cfg = json.load(f)
        if verbose:
            print("📝 Using orchestration config from file")

    arxiv_json = SettingsRepository.get("arxiv_search_categories")
    if arxiv_json:
        arxiv_cfg = json.loads(arxiv_json)
        if verbose:
            print("📝 Using ArXiv categories from database")
    else:
        arxiv_cfg = orch_cfg.get("arxiv_search_categories", {
            "main_category": "cs",
            "filter_categories": ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"],
        })
        if verbose:
            print("📝 Using default ArXiv categories")

    research_interests = SettingsRepository.get("research_interests")
    if research_interests is None:
        path = PROJECT_ROOT / "config" / "research_interests.txt"
        if path.exists():
            research_interests = path.read_text().strip()
        else:
            research_interests = ""
    
    if verbose:
        print(f"🎯 Research interests loaded ({len(research_interests)} characters)")
        print(f"📂 ArXiv main category: {arxiv_cfg.get('main_category', 'cs')}")
        print(f"🏷️ ArXiv filter categories: {arxiv_cfg.get('filter_categories', [])}")

    embedding_cfg = orch_cfg["embedding_model"]
    judge_cfg = orch_cfg["judge_model"]

    # Determine best device for embeddings
    device = None
    if torch.backends.mps.is_available():
        device = "mps"
        if verbose:
            print(f"🚀 Using Apple Silicon GPU (MPS) for embeddings")
    elif torch.cuda.is_available():
        device = "cuda"
        if verbose:
            print(f"🚀 Using CUDA GPU for embeddings")
    else:
        device = "cpu"
        if verbose:
            print(f"💻 Using CPU for embeddings")

    if verbose:
        print(f"🧠 Loading embedding model: {embedding_cfg['model_name']} on {device}")
    embedding_model = SentenceTransformerInference(
        embedding_cfg["model_name"],
        remote_code=embedding_cfg.get("trust_remote_code", True),
        device=device,
    )
    
    judge_model = load_inference_model(judge_cfg, verbose)

    # Execute pipeline stages
    try:
        data_df = await download_papers(
            date_from,
            date_to,
            category=arxiv_cfg.get("main_category", "cs"),
            subcats=arxiv_cfg.get("filter_categories", []),
            checkpoint_dir=checkpoint_dir,
            checkpoint_manager=checkpoint_manager,
            job_id=job_id,
            verbose=verbose,
        )
        
        if data_df is None or data_df.empty:
            if verbose:
                print("❌ No papers found for the given date range")
            return

        # Optimize DataFrame memory after download
        if memory_monitor:
            data_df = optimize_dataframe_memory(data_df, verbose)
            memory_monitor.check_memory()

        embedded_df = await embed_papers(
            data_df,
            embedding_model,
            research_interests,
            cosine_threshold,
            checkpoint_dir,
            checkpoint_manager,
            job_id,
            batch_size,
            max_workers,
            verbose,
        )
        
        # Check memory after embedding
        if memory_monitor:
            memory_monitor.check_memory()
            # Free original dataframe if not needed
            if 'data_df' in locals() and embedded_df is not data_df:
                del data_df

        ranked_df = await rank_papers(
            embedded_df,
            judge_model,
            research_interests,
            checkpoint_dir,
            checkpoint_manager,
            job_id,
            top_n,
            verbose,
        )
        
        # Check memory after ranking
        if memory_monitor:
            memory_monitor.check_memory()

        if use_bulk_insert:
            insert_papers_bulk(ranked_df, embedded_df, embedding_cfg["model_name"], verbose)
        else:
            insert_papers(ranked_df, embedded_df, embedding_cfg["model_name"], verbose)
        
        # Mark job as completed
        await checkpoint_manager.complete_job(job_id)
        
        # Final memory report
        if memory_monitor:
            memory_monitor.report()
        
        if verbose:
            print("\n" + "="*60)
            print("🎉 HARVEST AND JUDGING COMPLETE!")
            print("="*60)
            
    except Exception as e:
        # Mark job as failed
        await checkpoint_manager.fail_job(job_id, str(e))
        raise


def parse_args():
    parser = argparse.ArgumentParser(description="Harvest, rank and store papers")
    parser.add_argument("--date-from", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--checkpoint-dir", default="harvest_checkpoints")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--cosine-threshold", type=float, default=0.5)
    parser.add_argument("--batch-size", type=int, default=256,
                       help="Embedding batch size (1 = no batching, higher = more efficient)")
    parser.add_argument("--max-workers", type=int, default=4,
                       help="Maximum parallel workers for database checks (1 = sequential)")
    parser.add_argument("--verbose", "-v", action="store_true", default=True, 
                       help="Enable verbose output (default: True)")
    parser.add_argument("--quiet", "-q", action="store_true", 
                       help="Disable verbose output")
    parser.add_argument("--use-bulk-insert", action="store_true", default=True,
                       help="Use bulk insert with staging tables (default: True)")
    parser.add_argument("--no-bulk-insert", action="store_true",
                       help="Disable bulk insert and use individual inserts")
    return parser.parse_args()


if __name__ == "__main__":
    import asyncio
    
    args = parse_args()
    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet
    # Handle bulk insert flags
    use_bulk_insert = args.use_bulk_insert and not args.no_bulk_insert
    
    asyncio.run(harvest_and_judge(
        date_from=args.date_from,
        date_to=args.date_to,
        checkpoint_dir=args.checkpoint_dir,
        top_n=args.top_n,
        cosine_threshold=args.cosine_threshold,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        verbose=verbose,
        use_bulk_insert=use_bulk_insert,
    ))

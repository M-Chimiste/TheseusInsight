#!/usr/bin/env python3
"""Simple script to harvest PapersWithCode data, score it and insert into the database.

This is a drop-in replacement for ``harvest_and_judge.py`` using the
``PapersWithCode`` JSON dump instead of the ArXiv OAI harvester.  It mimics the
same pipeline of downloading, embedding, ranking and storing papers.
A date range can be provided but if both ``--date-from`` and ``--date-to`` are
``None`` the entire downloaded dataset will be processed.
"""

import argparse
import os
import sys
import json
import time
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
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

from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.data_model.papers import Paper
from theseus_insight.data_processing.paperswithcode import PapersWithCode
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.inference.llm import (
    OllamaInference, OpenAIInference, AnthropicInference, GeminiInference,
)
from theseus_insight.prompt import (
    RESEARCH_INTERESTS_SYSTEM_PROMPT,
    research_prompt,
)
from theseus_insight.utils import cosine_similarity, purge_ollama_cache

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


# ---------------------------------------------------------------
# Helper functions for database operations
# ---------------------------------------------------------------

def check_paper_exists(db_url: str, paper_data: tuple) -> bool:
    """Return True if paper already exists, by URL or title."""
    from theseus_insight.data_model.data_handling import PaperDatabase

    idx, paper_url, paper_title = paper_data
    db = PaperDatabase(db_url)
    exists_by_url = db.paper_exists_by_url(paper_url) if paper_url else False
    exists_by_title = db.paper_exists_by_title(paper_title)
    return exists_by_url or exists_by_title


def get_paper_count(db_url: str) -> int:
    """
    Get the total number of papers in the database.
    
    Args:
        db_url: Database connection URL
    
    Returns:
        int: Number of papers in database
    """
    from theseus_insight.data_model.data_handling import PaperDatabase
    
    try:
        db = PaperDatabase(db_url)
        with db.get_cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM papers")
            return cursor.fetchone()[0]
    except Exception:
        return -1  # Return -1 to indicate error/unknown


def should_skip_database_checks(db_url: str, verbose: bool = True) -> bool:
    """
    Determine if we should skip database existence checks.
    
    Args:
        db_url: Database connection URL
        verbose: Whether to print status messages
    
    Returns:
        bool: True if database checks should be skipped
    """
    try:
        paper_count = get_paper_count(db_url)
        
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
    db_url: str, 
    max_workers: int = 4,
    verbose: bool = True
) -> List[bool]:
    """
    Check for existing papers using parallel processing.
    
    Args:
        df: DataFrame with papers to check
        db_url: Database connection URL
        max_workers: Maximum number of parallel workers
        verbose: Whether to show progress
    
    Returns:
        List[bool]: List indicating which papers are new (not existing)
    """
    if verbose:
        print(f"🔍 Checking for existing papers using {max_workers} parallel workers...")
    
    # Prepare data for parallel processing
    paper_data = [
        (idx, row.get("pdf_url") or row.get("url_pdf"), row["title"]) 
        for idx, (_, row) in enumerate(df.iterrows())
    ]
    
    existing_mask = []
    
    # Use ThreadPoolExecutor for I/O-bound database operations
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        check_func = partial(check_paper_exists, db_url)
        
        # Process in parallel with progress bar
        results = list(tqdm(
            executor.map(check_func, paper_data),
            total=len(paper_data),
            desc="Checking existing papers (parallel)",
            disable=not verbose
        ))
        
        existing_mask = results
    
    # Convert to "new paper" mask (inverse of existing)
    new_mask = [not exists for exists in existing_mask]
    
    return new_mask


# ---------------------------------------------------------------
# Helper functions for checkpoints
# ---------------------------------------------------------------

def _checkpoint_path(checkpoint_dir: str, stage: str) -> Path:
    return Path(checkpoint_dir) / f"{stage}.pkl"


def save_checkpoint(checkpoint_dir: str, stage: str, data: Any, verbose: bool = True) -> None:
    """
    Saves checkpoint data to a file.

    This function creates a checkpoint directory if it doesn't exist, and saves the checkpoint data to a file.
    The checkpoint data includes the data itself, the timestamp of the checkpoint, and the stage name.
    """
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
    """
    Loads checkpoint data from a file.

    This function checks if a checkpoint file exists for the specified stage, and if it does, it loads the checkpoint data from the file.
    The checkpoint data includes the data itself, the timestamp of the checkpoint, and the stage name.
    """
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
    """
    Loads an inference model based on the configuration.

    This function loads an inference model based on the configuration provided. It supports Ollama, OpenAI, Anthropic, and Gemini models.
    """
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
    """
    Clears the cache for a judge model.

    This function checks if the judge model is an Ollama model and purges its cache if it is.
    """
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

def download_papers(
    date_from: Optional[str],
    date_to: Optional[str],
    checkpoint_dir: str,
    retries: int = 3,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Downloads papers from PapersWithCode.

    Args:
        date_from (Optional[str]): The start date for the time period selected (MM-DD-YYYY). Defaults to None.
        date_to (Optional[str]): The end date for the time period selected (MM-DD-YYYY). Defaults to None.
        checkpoint_dir (str): The directory to save the checkpoint.
        retries (int, optional): The number of retries if the download fails. Defaults to 3.
        verbose (bool, optional): If True, prints progress messages. Defaults to True.

    Returns:
        pd.DataFrame: A DataFrame containing the downloaded papers.
    """
    if verbose:
        print("\n" + "="*60)
        print("📥 STAGE 1: DOWNLOADING PAPERS FROM PAPERSWITHCODE")
        print("="*60)
    
    data_df = load_checkpoint(checkpoint_dir, "download", verbose)
    if data_df is not None:
        if verbose:
            print(f"📊 Found {len(data_df)} papers in checkpoint")
        return data_df
    
    if verbose:
        date_range = f"from {date_from} to {date_to}" if date_from and date_to else "all available data"
        print(f"🌐 Downloading papers: {date_range}")
    
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            if verbose and attempt > 1:
                print(f"🔄 Download attempt {attempt}/{retries}")
            
            pwc = PapersWithCode(start_date=date_from, end_date=date_to)
            
            if date_from is None and date_to is None:
                if verbose:
                    print("📂 Fetching complete dataset...")
                json_data = pwc._fetch_data()
                pwc.json_data = json_data
                data_df = pd.DataFrame.from_dict(json_data)
                if "date" in data_df.columns:
                    data_df["date"] = pd.to_datetime(data_df["date"])
            else:
                if verbose:
                    print(f"📅 Downloading papers for date range: {date_from} to {date_to}")
                data_df = pwc.download_and_process_data(
                    start_date=date_from, end_date=date_to
                )
            
            if verbose:
                print(f"✅ Successfully downloaded {len(data_df)} papers")
            
            save_checkpoint(checkpoint_dir, "download", data_df, verbose)
            return data_df
            
        except Exception as e:
            if verbose:
                print(f"❌ Download attempt {attempt} failed: {e}")
            if attempt >= retries:
                raise
            time.sleep(2)
    return pd.DataFrame()


def embed_papers(
    df: pd.DataFrame,
    embedding_model: SentenceTransformerInference,
    research_interests: str,
    threshold: float,
    db: PaperDatabase,
    checkpoint_dir: str,
    batch_size: int = 256,
    max_workers: int = 4,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Embeds papers with abstract embeddings and filters based on cosine similarity.

    This function takes a DataFrame of papers, embeds their abstracts using a SentenceTransformer model, and filters them based on their cosine similarity to a given research interest. The filtered papers are then saved to a checkpoint directory.

    Args:
        df (pd.DataFrame): A DataFrame containing the papers to be embedded and filtered.
        embedding_model (SentenceTransformerInference): The model used to embed the abstracts of the papers.
        research_interests (str): The research interest against which the papers are filtered.
        threshold (float): The minimum cosine similarity required for a paper to be considered relevant.
        db (PaperDatabase): The database used to check if a paper already exists.
        checkpoint_dir (str): The directory where the checkpoint is saved.
        batch_size (int, optional): Number of papers to embed in each batch. 1 = no batching. Defaults to 256.
        max_workers (int, optional): Maximum number of parallel workers for database checks. Defaults to 4.
        verbose (bool, optional): If True, prints progress messages. Defaults to True.

    Returns:
        pd.DataFrame: A DataFrame containing the papers that have been embedded and filtered.
    """
    if verbose:
        print("\n" + "="*60)
        print("🧠 STAGE 2: EMBEDDING AND FILTERING PAPERS")
        print("="*60)
        if batch_size > 1:
            print(f"⚡ Using batch processing with batch size: {batch_size}")
    
    embedded_df = load_checkpoint(checkpoint_dir, "embed", verbose)
    if embedded_df is not None:
        if verbose:
            print(f"📊 Found {len(embedded_df)} embedded papers in checkpoint")
        return embedded_df

    if df.empty:
        if verbose:
            print("⚠️ No papers to embed (empty dataset)")
        save_checkpoint(checkpoint_dir, "embed", df, verbose)
        return df

    # Smart database checking with optimization
    db_url = db.db_path
    skip_checks = should_skip_database_checks(db_url, verbose)
    
    if skip_checks:
        # Skip database checks entirely for speed
        new_df = df.copy()
        if verbose:
            print(f"📝 Processing all {len(new_df)} papers (database checks skipped)")
    else:
        # Use parallel database checking for speed
        if len(df) > 50 and max_workers > 1:
            new_mask = check_existing_papers_parallel(df, db_url, max_workers, verbose)
        else:
            # Fall back to sequential for small datasets
            if verbose:
                print(f"🔍 Checking for existing papers (sequential)...")
            new_mask = []
            with tqdm(df.iterrows(), total=len(df), desc="Checking existing papers", disable=not verbose) as pbar:
                for _, row in pbar:
                    exists = db.paper_exists_by_url(row.get("pdf_url") or row.get("url_pdf")) or db.paper_exists_by_title(row["title"])
                    new_mask.append(not exists)
        
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
                pbar.set_postfix({"last_similarity": f"{sim:.3f}"})
    else:
        # Use chunked processing for large datasets to avoid MPS memory limits
        chunk_size = min(batch_size, len(abstracts))  # Process max 50k papers at a time
        embeddings = []
        
        if verbose and len(abstracts) > chunk_size:
            print(f"📦 Processing in chunks of {chunk_size} papers to avoid GPU memory limits")
        
        # Step 1: Generate all embeddings in chunks
        for chunk_start in tqdm(range(0, len(abstracts), chunk_size), 
                               desc="Embedding chunks", 
                               disable=not verbose or len(abstracts) <= chunk_size):
            chunk_end = min(chunk_start + chunk_size, len(abstracts))
            chunk_abstracts = abstracts[chunk_start:chunk_end]
            
            # if verbose and len(abstracts) > chunk_size:
            #     print(f"🔄 Embedding chunk {chunk_start//chunk_size + 1}/{(len(abstracts) + chunk_size - 1)//chunk_size}: {len(chunk_abstracts)} papers")
            
            # Use SentenceTransformer's efficient built-in batching within chunk
            chunk_embeddings = embedding_model.invoke(
                chunk_abstracts, 
                batch_size=batch_size,
                show_progress_bar=verbose and len(abstracts) <= chunk_size
            )
            
            # Collect embeddings
            embeddings.extend(chunk_embeddings)
            
            # if verbose and len(abstracts) > chunk_size:
            #     print(f"✅ Chunk embedded - {len(chunk_embeddings)} embeddings generated")
        
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
    
    save_checkpoint(checkpoint_dir, "embed", filtered_df, verbose)
    return filtered_df


def rank_papers(
    df: pd.DataFrame,
    judge_model,
    research_interests: str,
    checkpoint_dir: str,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Ranks papers based on their relevance to the research interests using a judge model.

    This function takes a DataFrame of papers, a judge model, research interests, a checkpoint directory, and a verbosity flag. It loads the papers, embeds their abstracts, and ranks them based on their cosine similarity to the research interests. The ranking process involves sending the abstracts to the judge model, which returns a score indicating the paper's relevance. The function saves the ranked papers to a checkpoint file.

    Args:
        df (pd.DataFrame): A DataFrame containing the papers to be ranked.
        judge_model: The model used to judge the relevance of the papers.
        research_interests (str): The research interests against which the papers are ranked.
        checkpoint_dir (str): The directory where the checkpoint is saved.
        verbose (bool, optional): If True, prints progress messages. Defaults to True.

    Returns:
        pd.DataFrame: A DataFrame containing the ranked papers.
    """
    if verbose:
        print("\n" + "="*60)
        print("⚖️ STAGE 3: RANKING PAPERS WITH JUDGE MODEL")
        print("="*60)
    
    ranked_df = load_checkpoint(checkpoint_dir, "rank", verbose)
    if ranked_df is not None:
        if verbose:
            print(f"📊 Found {len(ranked_df)} ranked papers in checkpoint")
        return ranked_df

    if df.empty:
        if verbose:
            print("⚠️ No papers to rank (empty dataset)")
        ranked_df = df.copy()
        save_checkpoint(checkpoint_dir, "rank", ranked_df, verbose)
        return ranked_df

    abstracts = list(df["abstract"])
    scores: List[int] = []
    related: List[bool] = []
    rationale: List[str] = []
    failed = []
    consecutive_failures = 0
    
    partial = load_checkpoint(checkpoint_dir, "rank_partial", verbose=False)
    start_idx = 0
    if partial:
        scores = partial.get("scores", [])
        related = partial.get("related", [])
        rationale = partial.get("rationale", [])
        failed = partial.get("failed_papers", [])
        start_idx = len(scores)
        if verbose:
            print(f"🔄 Resuming ranking from paper {start_idx + 1}/{len(abstracts)}")

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
    
    save_checkpoint(checkpoint_dir, "rank", df, verbose)
    
    # Clean up partial checkpoint
    cp = _checkpoint_path(checkpoint_dir, "rank_partial")
    if cp.exists():
        cp.unlink()
    
    return df


def insert_papers(
    df: pd.DataFrame,
    all_df: pd.DataFrame,
    embedding_model_name: str,
    db: PaperDatabase,
    verbose: bool = True,
):
    """
    Inserts papers into the database.

    This function takes a DataFrame of papers, an embedding model name, a database, and a verbosity flag. It iterates through the papers, creates Paper objects, and inserts them into the database. The function saves the number of new papers and duplicate papers to a checkpoint file.

    Args:
        df (pd.DataFrame): A DataFrame containing the papers to be inserted.
        all_df (pd.DataFrame): A DataFrame containing all the papers.
        embedding_model_name (str): The name of the embedding model.
        db (PaperDatabase): The database used to insert the papers.
        verbose (bool, optional): If True, prints progress messages. Defaults to True.

    Returns:
        list: A list of duplicate paper URLs.
    """
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
                
            pdf_url = row.get("pdf_url") or row.get("url_pdf")
            paper = Paper(
                title=row["title"],
                abstract=row["abstract"],
                url=pdf_url,
                date_run=str(pd.Timestamp.now().date()),
                date=row["date"].strftime("%Y-%m-%d"),
                score=row["score"],
                related=row["related"],
                rationale=row["rationale"],
                cosine_similarity=row["cosine_similarity"],
                embedding_model=embedding_model_name,
                embedding=emb,
            )
            
            inserted = db.insert_paper(paper, skip_duplicates=True)

            paper_rec = db.get_paper_by_url(pdf_url)
            if paper_rec:
                pid = paper_rec["id"]
                if not db.get_paper_keywords(pid):
                    try:
                        text_kw = f"{row['title']} {row['abstract']}"
                        kw_scores = extractor.extract_keywords(text_kw)
                        keywords = [kw for kw, _ in kw_scores]
                        db.update_paper_keywords(pid, keywords)
                    except Exception:
                        pass

            if inserted:
                saved += 1
            else:
                dup += 1
                dup_urls.append(pdf_url)
            
            pbar.set_postfix({
                "saved": saved,
                "duplicates": dup
            })
    
    if verbose:
        print(f"✅ Database insertion complete:")
        print(f"   - {saved} new papers saved")
        print(f"   - {dup} duplicates skipped")
    
    return dup_urls


# ---------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------

def harvest_and_judge(
    date_from: Optional[str],
    date_to: Optional[str],
    checkpoint_dir: str,
    db_url: str,
    cosine_threshold: float = 0.5,
    batch_size: int = 256,
    max_workers: int = 4,
    verbose: bool = True,
):
    """
    Orchestrates the harvesting and judging of papers based on specified dates and settings.

    This function coordinates the entire pipeline of downloading papers from PapersWithCode, embedding their abstracts, filtering based on cosine similarity, 
    ranking based on relevance, and saving the results to a database. It utilizes various utility functions to perform these tasks.

    Args:
        date_from (Optional[str]): The start date for the time period selected (MM-DD-YYYY). Defaults to None.
        date_to (Optional[str]): The end date for the time period selected (MM-DD-YYYY). Defaults to None.
        checkpoint_dir (str): The directory where intermediate results are saved for checkpointing.
        db_url (str): The URL of the database where the papers are stored.
        cosine_threshold (float, optional): The minimum cosine similarity required for a paper to be considered relevant. Defaults to 0.5.
        batch_size (int, optional): Number of papers to embed in each batch. 1 = no batching. Defaults to 1.
        verbose (bool, optional): If True, prints detailed progress messages. Defaults to True.
    """
    if verbose:
        print("🚀 THESEUS INSIGHT - PAPERSWITHCODE HARVEST & JUDGE")
        print("="*60)
        print(f"📅 Date range: {date_from or 'All'} to {date_to or 'All'}")
        print(f"🎯 Cosine threshold: {cosine_threshold}")
        if batch_size > 1:
            print(f"⚡ Embedding batch size: {batch_size}")
        print(f"📁 Checkpoint directory: {checkpoint_dir}")
        print(f"🗄️ Database: {db_url}")
    
    db = PaperDatabase(db_url)

    if verbose:
        print(f"\n🔧 Loading configuration...")
    
    orch_json = db.get_setting("orchestration")
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

    research_interests = db.get_setting("research_interests")
    if research_interests is None:
        path = PROJECT_ROOT / "config" / "research_interests.txt"
        if path.exists():
            research_interests = path.read_text().strip()
        else:
            research_interests = ""
    
    if verbose:
        print(f"🎯 Research interests loaded ({len(research_interests)} characters)")

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
    data_df = download_papers(
        date_from,
        date_to,
        checkpoint_dir=checkpoint_dir,
        verbose=verbose,
    )
    
    if data_df.empty:
        if verbose:
            print("❌ No papers found for the given date range")
        return

    embedded_df = embed_papers(
        data_df,
        embedding_model,
        research_interests,
        cosine_threshold,
        db,
        checkpoint_dir,
        batch_size,
        max_workers,
        verbose,
    )

    ranked_df = rank_papers(
        embedded_df,
        judge_model,
        research_interests,
        checkpoint_dir,
        verbose,
    )

    insert_papers(ranked_df, embedded_df, embedding_cfg["model_name"], db, verbose)
    
    if verbose:
        print("\n" + "="*60)
        print("🎉 HARVEST AND JUDGING COMPLETE!")
        print("="*60)


def parse_args():
    """
    Parses command line arguments for the harvest_and_judge function.

    This function creates an argument parser for the harvest_and_judge function, allowing users to specify the date range, database URL, and cosine threshold.
    It also sets default values for these parameters if not provided.
    """
    parser = argparse.ArgumentParser(
        description="Harvest PapersWithCode data, rank and store papers"
    )
    parser.add_argument("--date-from", help="Start date YYYY-MM-DD", default='2024-01-01')
    parser.add_argument("--date-to", help="End date YYYY-MM-DD", default='2025-05-22')
    parser.add_argument(
        "--db-url",
        default=os.getenv(
            "DATABASE_URL", "data/theseus.db"
        ),
        help="Database connection URL",
    )
    parser.add_argument("--checkpoint-dir", default="harvest_checkpoints")
    parser.add_argument("--cosine-threshold", type=float, default=0.65)
    parser.add_argument("--batch-size", type=int, default=32,
                       help="Embedding batch size (1 = no batching, higher = more efficient)")
    parser.add_argument("--max-workers", type=int, default=4,
                       help="Maximum parallel workers for database checks (1 = sequential)")
    parser.add_argument("--verbose", "-v", action="store_true", default=True, 
                       help="Enable verbose output (default: True)")
    parser.add_argument("--quiet", "-q", action="store_true", 
                       help="Disable verbose output")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Handle verbose/quiet flags
    verbose = args.verbose and not args.quiet
    
    harvest_and_judge(
        date_from=args.date_from,
        date_to=args.date_to,
        checkpoint_dir=args.checkpoint_dir,
        db_url=args.db_url,
        cosine_threshold=args.cosine_threshold,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        verbose=verbose,
    )

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
from typing import List, Dict, Any

from tqdm import tqdm
import pandas as pd
import json_repair

# Add project root to import path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.data_model.papers import Paper
from theseus_insight.data_processing.arxiv import ArxivDataProcessor
from theseus_insight.inference import SentenceTransformerInference
from theseus_insight.inference.llm import (
    OllamaInference, OpenAIInference, AnthropicInference, GeminiInference
)
from theseus_insight.prompt import (
    RESEARCH_INTERESTS_SYSTEM_PROMPT,
    research_prompt,
)
from theseus_insight.utils import cosine_similarity, purge_ollama_cache

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")


# ---------------------------------------------------------------
# Helper functions for checkpoints
# ---------------------------------------------------------------

def _checkpoint_path(checkpoint_dir: str, stage: str) -> Path:
    return Path(checkpoint_dir) / f"{stage}.pkl"


def save_checkpoint(checkpoint_dir: str, stage: str, data: Any) -> None:
    Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    cp = {
        "data": data,
        "timestamp": time.time(),
        "stage": stage,
    }
    with open(_checkpoint_path(checkpoint_dir, stage), "wb") as f:
        pickle.dump(cp, f)


def load_checkpoint(checkpoint_dir: str, stage: str):
    path = _checkpoint_path(checkpoint_dir, stage)
    if path.exists():
        with open(path, "rb") as f:
            cp = pickle.load(f)
        print(f"Loaded checkpoint '{stage}' from {time.ctime(cp['timestamp'])}")
        return cp["data"]
    return None


# ---------------------------------------------------------------
# Model loader helper
# ---------------------------------------------------------------

def load_inference_model(cfg: Dict[str, Any]):
    model_type = cfg.get("model_type")
    model_name = cfg.get("model_name")
    max_new_tokens = cfg.get("max_new_tokens", 4096)
    temperature = cfg.get("temperature", 0.1)
    num_ctx = cfg.get("num_ctx")
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


def clear_judge_cache(inference, model_name: str):
    try:
        if hasattr(inference, "provider") and inference.provider == "ollama":
            purge_ollama_cache(OLLAMA_URL, model_name)
    except Exception as e:
        print(f"Failed to purge cache for {model_name}: {e}")


# ---------------------------------------------------------------
# Pipeline stages
# ---------------------------------------------------------------

def download_papers(date_from: str, date_to: str, category: str, subcats: List[str], checkpoint_dir: str, retries: int = 3):
    data_df = load_checkpoint(checkpoint_dir, "download")
    if data_df is not None:
        return data_df
    attempt = 0
    while attempt < retries:
        attempt += 1
        try:
            proc = ArxivDataProcessor(
                start_date=date_from,
                end_date=date_to,
                category=category,
                subcategories=subcats,
            )
            data_df = proc.download_and_process_data()
            save_checkpoint(checkpoint_dir, "download", data_df)
            return data_df
        except Exception as e:
            print(f"Download attempt {attempt} failed: {e}")
            if attempt >= retries:
                raise
            time.sleep(2)
    return None


def embed_papers(df: pd.DataFrame, embedding_model: SentenceTransformerInference, research_interests: str, threshold: float, db: PaperDatabase, checkpoint_dir: str) -> pd.DataFrame:
    embedded_df = load_checkpoint(checkpoint_dir, "embed")
    if embedded_df is not None:
        return embedded_df

    if df.empty:
        save_checkpoint(checkpoint_dir, "embed", df)
        return df

    # Skip already stored papers
    new_mask = []
    for _, row in df.iterrows():
        exists = db.paper_exists_by_url(row["pdf_url"])
        new_mask.append(not exists)
    new_df = df[new_mask].reset_index(drop=True)
    if new_df.empty:
        embedded_df = new_df.copy()
        embedded_df["cosine_similarity"] = []
        embedded_df["abstract_embedding"] = []
        save_checkpoint(checkpoint_dir, "embed", embedded_df)
        return embedded_df

    research_emb = embedding_model.invoke(research_interests)
    embeddings = []
    sims = []
    for abstract in tqdm(new_df["abstract"], desc="Embedding", leave=False):
        emb = embedding_model.invoke(abstract)
        embeddings.append(emb)
        sims.append(cosine_similarity(emb, research_emb))
    new_df["abstract_embedding"] = embeddings
    new_df["cosine_similarity"] = sims
    filtered_df = new_df[new_df["cosine_similarity"] >= threshold].reset_index(drop=True)
    save_checkpoint(checkpoint_dir, "embed", filtered_df)
    return filtered_df


def rank_papers(df: pd.DataFrame, judge_model, research_interests: str, checkpoint_dir: str, top_n: int, verbose: bool = True) -> pd.DataFrame:
    ranked_df = load_checkpoint(checkpoint_dir, "rank")
    if ranked_df is not None:
        return ranked_df

    if df.empty:
        ranked_df = df.copy()
        save_checkpoint(checkpoint_dir, "rank", ranked_df)
        return ranked_df

    abstracts = list(df["abstract"])
    scores, related, rationale = [], [], []
    failed = []
    consecutive_failures = 0
    partial = load_checkpoint(checkpoint_dir, "rank_partial")
    start_idx = 0
    if partial:
        scores = partial.get("scores", [])
        related = partial.get("related", [])
        rationale = partial.get("rationale", [])
        failed = partial.get("failed_papers", [])
        start_idx = len(scores)
        if verbose:
            print(f"Resuming ranking from {start_idx + 1}/{len(abstracts)}")

    for i, abstract in enumerate(tqdm(abstracts[start_idx:], desc="Ranking", leave=False)):
        idx = start_idx + i
        success = False
        attempts = 0
        while not success and attempts < 3:
            attempts += 1
            try:
                if attempts == 2 and consecutive_failures > 2:
                    clear_judge_cache(judge_model, judge_model.model_name)
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
                else:
                    time.sleep(1)
        if (idx + 1) % 50 == 0:
            partial_data = {
                "scores": scores,
                "related": related,
                "rationale": rationale,
                "failed_papers": failed,
            }
            save_checkpoint(checkpoint_dir, "rank_partial", partial_data)

    if failed and verbose:
        print(f"Warning: {len(failed)} papers failed scoring")

    df["score"] = scores
    df["related"] = related
    df["rationale"] = rationale
    df = df.sort_values(by="score", ascending=False)
    top_df = df.head(top_n)
    save_checkpoint(checkpoint_dir, "rank", top_df)
    cp = _checkpoint_path(checkpoint_dir, "rank_partial")
    if cp.exists():
        cp.unlink()
    return top_df


def insert_papers(df: pd.DataFrame, all_df: pd.DataFrame, embedding_model_name: str, db: PaperDatabase, verbose: bool = True):
    saved = 0
    dup = 0
    dup_urls = []
    for _, row in all_df.iterrows():
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
        if db.insert_paper(paper, skip_duplicates=True):
            saved += 1
        else:
            dup += 1
            dup_urls.append(row["pdf_url"])
    if verbose:
        print(f"DB save complete: {saved} new papers, {dup} duplicates skipped")
    return dup_urls


# ---------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------

def harvest_and_judge(date_from: str, date_to: str, checkpoint_dir: str, db_url: str, top_n: int = 5, cosine_threshold: float = 0.5):
    db = PaperDatabase(db_url)

    orch_json = db.get_setting("orchestration")
    if orch_json:
        orch_cfg = json.loads(orch_json)
    else:
        cfg_path = PROJECT_ROOT / "config" / "orchestration.json"
        with open(cfg_path) as f:
            orch_cfg = json.load(f)

    arxiv_json = db.get_setting("arxiv_search_categories")
    if arxiv_json:
        arxiv_cfg = json.loads(arxiv_json)
    else:
        arxiv_cfg = orch_cfg.get("arxiv_search_categories", {
            "main_category": "cs",
            "filter_categories": ["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"],
        })

    research_interests = db.get_setting("research_interests")
    if research_interests is None:
        path = PROJECT_ROOT / "config" / "research_interests.txt"
        if path.exists():
            research_interests = path.read_text().strip()
        else:
            research_interests = ""

    embedding_cfg = orch_cfg["embedding_model"]
    judge_cfg = orch_cfg["judge_model"]

    embedding_model = SentenceTransformerInference(
        embedding_cfg["model_name"],
        remote_code=embedding_cfg.get("trust_remote_code", True),
    )
    judge_model = load_inference_model(judge_cfg)

    data_df = download_papers(
        date_from,
        date_to,
        category=arxiv_cfg.get("main_category", "cs"),
        subcats=arxiv_cfg.get("filter_categories", []),
        checkpoint_dir=checkpoint_dir,
    )
    if data_df.empty:
        print("No papers found for the given date range")
        return

    embedded_df = embed_papers(
        data_df,
        embedding_model,
        research_interests,
        cosine_threshold,
        db,
        checkpoint_dir,
    )

    ranked_df = rank_papers(
        embedded_df,
        judge_model,
        research_interests,
        checkpoint_dir,
        top_n,
    )

    insert_papers(ranked_df, embedded_df, embedding_cfg["model_name"], db)
    print("Harvest and judging complete")


def parse_args():
    parser = argparse.ArgumentParser(description="Harvest, rank and store papers")
    parser.add_argument("--date-from", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", required=True, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--db-url",
        default=os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"),
        help="Database connection URL",
    )
    parser.add_argument("--checkpoint-dir", default="harvest_checkpoints")
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--cosine-threshold", type=float, default=0.5)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    harvest_and_judge(
        date_from=args.date_from,
        date_to=args.date_to,
        checkpoint_dir=args.checkpoint_dir,
        db_url=args.db_url,
        top_n=args.top_n,
        cosine_threshold=args.cosine_threshold,
    )

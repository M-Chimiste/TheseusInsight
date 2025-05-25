from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict
import json
import os
import uuid
from datetime import datetime, date, timedelta
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
import pathlib

from pydantic import BaseModel, Field, ValidationError

from .data_model.data_handling import PaperDatabase
from .api.models import (
    Model, ModelCreate, Paper, Run, PaginatedResponse,
    NewsletterConfig, RunStatus, OrchestrationConfig,
    VisualizerSettings, ArxivCategoriesConfig, ModelProvider,
    EmailRecipients, ResearchInterests, ModelConfig, TTSModelConfig,
    PodcastGenerationParams, PodcastListItemResponse, PodcastDetailResponse,
    PaperApiResponse, PaginatedPapersResponse, NewsletterRunParams,
    SimilaritySearchRequest, SimilaritySearchResponse, SimilarPapersRequest, SimilarPapersResponse,
    HybridSearchRequest, HybridSearchResponse
)
from .api.tasks import task_manager, TaskStatus
from .theseus_insight import TheseusInsight
import asyncio

# Determine base path for static files
IS_RUNNING_IN_DOCKER = os.getenv("RUNNING_IN_DOCKER", "false").lower() == "true"

if IS_RUNNING_IN_DOCKER:
    STATIC_FILES_BASE_DIR = pathlib.Path("static_frontend")
else:
    PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
    STATIC_FILES_BASE_DIR = PROJECT_ROOT / "theseus-ui" / "dist"

STATIC_ASSETS_DIR = STATIC_FILES_BASE_DIR / "assets"
STATIC_INDEX_HTML = STATIC_FILES_BASE_DIR / "index.html"

# Pydantic model for Log entries (defined before use in get_logs_api)
class LogEntry(BaseModel):
    task_id: str
    status: str
    datetime_run: str

# Initialize database first
DB_URL = os.getenv("DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb")
db = PaperDatabase(DB_URL)

# Lifespan context manager
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Startup logic
    print("INFO:     Starting up Theseus Insight API...")
    try:
        os.makedirs("data/newsletters", exist_ok=True)
        os.makedirs("data/podcasts", exist_ok=True)
        os.makedirs("data/visualizations", exist_ok=True)
        os.makedirs("data/temp", exist_ok=True)
        
        required_env_vars = [
            "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GMAIL_SENDER_ADDRESS",
            "CLIENT_SECRET", "PROJECT_ID", "GMAIL_APP_PASSWORD"
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            print(f"Warning: Missing environment variables: {', '.join(missing_vars)}")

        if db.get_setting("orchestration") is None:
            print("INFO:     Orchestration settings not found in DB. Populating from JSON file...")
            orchestration_json_path = os.path.join(os.path.dirname(__file__), '../config/orchestration.json')
            if os.path.exists(orchestration_json_path):
                try:
                    with open(orchestration_json_path, 'r') as f:
                        default_orchestration_data = json.load(f)
                    default_embedding_model = ModelConfig(model_name='Alibaba-NLP/gte-modernbert-base', model_type='sentence-transformers', trust_remote_code=True)
                    default_judge_model = ModelConfig(model_name='phi4-mini:3.8b-q8_0', model_type='ollama', max_new_tokens=512, temperature=0.1, num_ctx=4096)
                    default_content_extraction_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
                    default_newsletter_sections_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
                    default_newsletter_intro_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
                    default_podcast_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=8192, temperature=0.1, num_ctx=131072)
                    default_tts_model = TTSModelConfig(tts_provider='openai', tts_model_name='tts-1', speaker_1_voice='sage', speaker_1_speed=1.0, speaker_2_voice='ash', speaker_2_speed=1.0)
                    orchestration_config = OrchestrationConfig(
                        embedding_model=ModelConfig(**default_orchestration_data.get('embedding_model', default_embedding_model.dict())),
                        judge_model=ModelConfig(**default_orchestration_data.get('judge_model', default_judge_model.dict())),
                        content_extraction_model=ModelConfig(**default_orchestration_data.get('content_extraction_model', default_content_extraction_model.dict())),
                        newsletter_sections_model=ModelConfig(**default_orchestration_data.get('newsletter_sections_model', default_newsletter_sections_model.dict())),
                        newsletter_intro_model=ModelConfig(**default_orchestration_data.get('newsletter_intro_model', default_newsletter_intro_model.dict())),
                        podcast_model=ModelConfig(**default_orchestration_data.get('podcast_model', default_podcast_model.dict())) if default_orchestration_data.get('podcast_model') else default_podcast_model,
                        tts_model=TTSModelConfig(**default_orchestration_data.get('tts_model', default_tts_model.dict())) if default_orchestration_data.get('tts_model') else default_tts_model
                    )
                    db.set_setting("orchestration", orchestration_config.json())
                    print("INFO:     Successfully populated orchestration settings into DB.")
                except Exception as e:
                    print(f"ERROR: Failed to load or parse orchestration.json for DB pre-population: {e}")
            else:
                print(f"Warning: orchestration.json not found at {orchestration_json_path}.")
        else:
            print("INFO:     Orchestration settings found in DB. Skipping pre-population.")
        if db.get_setting("research_interests") is None:
            print("INFO:     Research interests not found in DB. Populating from TXT file...")
            research_txt_path = os.path.join(os.path.dirname(__file__), '../config/research_interests.txt')
            if os.path.exists(research_txt_path):
                try:
                    with open(research_txt_path, 'r') as f:
                        default_interests = f.read().strip()
                    db.set_setting("research_interests", default_interests)
                    print("INFO:     Successfully populated research interests into DB.")
                except Exception as e:
                    print(f"ERROR: Failed to load research_interests.txt for DB pre-population: {e}")
            else:
                print(f"Warning: research_interests.txt not found at {research_txt_path}.")
        else:
            print("INFO:     Research interests settings found in DB. Skipping pre-population.")
    except Exception as e:
        print(f"Error during startup pre-population: {e}")
    print("INFO:     Theseus Insight API startup complete.")
    yield
    # Shutdown logic
    print("INFO:     Shutting down Theseus Insight API...")
    try:
        # Clean up TaskManager resources
        await task_manager.cleanup()
        print("INFO:     TaskManager cleanup completed.")
        
        # Clean up WebSocket connections
        if 'manager' in globals() and hasattr(globals()['manager'], 'cleanup_all'): 
             await globals()['manager'].cleanup_all()
             print("INFO:     WebSocket connections closed.")
        else:
            print("Warning: WebSocket connection manager not found for shutdown.")
    except Exception as e:
        print(f"Error during shutdown: {e}")
    print("INFO:     Theseus Insight API shutdown complete.")

# Initialize FastAPI app
app = FastAPI(
    title="Theseus Insight API",
    description="Backend API for Theseus Insight research paper analysis platform",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
CORS_ORIGINS = [
    "http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000",
    "http://127.0.0.1:8000", "http://localhost:5173", "*"
]
if os.getenv("PRODUCTION_FRONTEND_URL"):
    CORS_ORIGINS.append(os.getenv("PRODUCTION_FRONTEND_URL"))
app.add_middleware(
    CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- API Route Definitions START --- #

# Papers endpoints
@app.get("/api/papers", response_model=PaginatedPapersResponse)
async def get_papers(
    page: int = Query(1, gt=0),
    score: Optional[float] = None,  # This is min_score for backward compatibility
    max_score: Optional[float] = None,  # Add max_score parameter
    sort_field: Optional[str] = Query(None, enum=['date', 'score']),
    sort_direction: Optional[str] = Query(None, enum=['asc', 'desc']),
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = Query(10, gt=0, le=100)
):
    """Get paginated papers with filtering and sorting."""
    try:
        # Use database-level pagination instead of fetching all papers
        papers_data = db.fetch_papers_paginated(
            page=page,
            page_size=page_size,
            min_score=score,
            max_score=max_score,
            sort_field=sort_field or 'score',
            sort_direction=sort_direction or 'desc',
            search=search,
            from_date=from_date,
            to_date=to_date
        )
        
        # Convert to API response format
        papers = []
        for p in papers_data['items']:
            papers.append(PaperApiResponse(
                id=p['id'], title=p['title'], abstract=p['abstract'],
                score=p['score'], date=p['date'], url=p['url'],
                date_run=p['date_run'], rationale=p['rationale'],
                related=p['related'], cosine_similarity=p['cosine_similarity'],
                embedding_model=p['embedding_model']
            ))
        
        return PaginatedPapersResponse(
            items=papers, 
            total_items=papers_data['total_items'], 
            total_pages=papers_data['total_pages'],
            current_page=page, 
            nextPage=page + 1 if papers_data['has_next_page'] else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/papers/similarity-search", response_model=SimilaritySearchResponse)
async def semantic_similarity_search(request: SimilaritySearchRequest):
    """Perform semantic similarity search on papers using embeddings."""
    try:
        # Get the orchestration config to load the embedding model
        orchestration_json = db.get_setting("orchestration")
        if not orchestration_json:
            raise HTTPException(status_code=500, detail="Orchestration config not found")
        
        orchestration_config = json.loads(orchestration_json)
        embedding_model_config = orchestration_config.get('embedding_model')
        if not embedding_model_config:
            raise HTTPException(status_code=500, detail="Embedding model config not found")
        
        # Initialize the embedding model
        from .inference import SentenceTransformerInference
        embedding_model = SentenceTransformerInference(
            embedding_model_config['model_name'], 
            remote_code=embedding_model_config.get('trust_remote_code', False)
        )
        
        # Perform similarity search
        similar_papers = db.find_papers_by_semantic_search(
            query_text=request.query_text,
            embedding_model=embedding_model,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convert to API response format
        results = []
        for p in similar_papers:
            paper_response = PaperApiResponse(
                id=p['id'], title=p['title'], abstract=p['abstract'],
                score=p['score'], date=p['date'], url=p['url'],
                date_run=p['date_run'], rationale=p['rationale'],
                related=p['related'], cosine_similarity=p['cosine_similarity'],
                embedding_model=p['embedding_model']
            )
            # Add similarity score as additional metadata if needed
            if 'similarity_score' in p:
                paper_response.similarity_score = p['similarity_score']
            results.append(paper_response)
        
        return SimilaritySearchResponse(
            query_text=request.query_text,
            results=results,
            total_results=len(results)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/papers/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search_papers(request: HybridSearchRequest):
    """Perform hybrid search combining semantic similarity and keyword matching."""
    try:
        # Validate that weights sum to approximately 1.0
        total_weight = request.semantic_weight + request.keyword_weight
        if abs(total_weight - 1.0) > 0.01:
            raise HTTPException(
                status_code=400, 
                detail=f"Semantic weight ({request.semantic_weight}) and keyword weight ({request.keyword_weight}) should sum to 1.0, got {total_weight}"
            )
        
        # Validate query text
        if not request.query_text or not request.query_text.strip():
            raise HTTPException(status_code=400, detail="Query text cannot be empty")
        
        # Get the orchestration config to load the embedding model
        orchestration_json = db.get_setting("orchestration")
        if not orchestration_json:
            raise HTTPException(status_code=500, detail="Orchestration config not found")
        
        orchestration_config = json.loads(orchestration_json)
        embedding_model_config = orchestration_config.get('embedding_model')
        if not embedding_model_config:
            raise HTTPException(status_code=500, detail="Embedding model config not found")
        
        # Initialize the embedding model
        from .inference import SentenceTransformerInference
        embedding_model = SentenceTransformerInference(
            embedding_model_config['model_name'], 
            remote_code=embedding_model_config.get('trust_remote_code', False)
        )
        
        # Perform hybrid search
        search_results = db.hybrid_search_papers(
            query_text=request.query_text,
            embedding_model=embedding_model,
            page=request.page,
            page_size=request.page_size,
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight,
            min_score=request.min_score,
            max_score=request.max_score,
            from_date=request.from_date,
            to_date=request.to_date,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convert to API response format
        results = []
        for p in search_results['items']:
            paper_response = PaperApiResponse(
                id=p['id'], title=p['title'], abstract=p['abstract'],
                score=p['score'], date=p['date'], url=p['url'],
                date_run=p['date_run'], rationale=p['rationale'],
                related=p['related'], cosine_similarity=p['cosine_similarity'],
                embedding_model=p['embedding_model'],
                semantic_score=p.get('semantic_score'),
                keyword_score=p.get('keyword_score'),
                hybrid_score=p.get('hybrid_score')
            )
            results.append(paper_response)
        
        return HybridSearchResponse(
            query_text=request.query_text,
            results=results,
            total_results=search_results['total_items'],
            total_pages=search_results['total_pages'],
            current_page=search_results['current_page'],
            semantic_weight=request.semantic_weight,
            keyword_weight=request.keyword_weight
        )
        
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        print(f"ERROR: JSON decode error in orchestration config: {e}")
        raise HTTPException(status_code=500, detail="Invalid orchestration configuration")
    except ImportError as e:
        print(f"ERROR: Import error for embedding model: {e}")
        raise HTTPException(status_code=500, detail="Embedding model not available")
    except Exception as e:
        print(f"ERROR: Unexpected error in hybrid search: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/api/papers/without-embeddings")
async def get_papers_without_embeddings():
    """Get papers that don't have embeddings saved."""
    try:
        papers = db.get_papers_without_embeddings()
        results = []
        for p in papers:
            results.append(PaperApiResponse(
                id=p['id'], title=p['title'], abstract=p['abstract'],
                score=p['score'], date=p['date'], url=p['url'],
                date_run=p['date_run'], rationale=p['rationale'],
                related=p['related'], cosine_similarity=p['cosine_similarity'],
                embedding_model=p['embedding_model']
            ))
        return {"papers": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/papers/{paper_id}/update-embedding")
async def update_paper_embedding(paper_id: int):
    """Generate and update embedding for a specific paper."""
    try:
        # Get the paper details
        papers = db.fetch_all_papers()
        paper = next((p for p in papers if p['id'] == paper_id), None)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        if paper['embedding'] is not None:
            return {"message": "Paper already has an embedding", "updated": False}
        
        # Get the orchestration config to load the embedding model
        orchestration_json = db.get_setting("orchestration")
        if not orchestration_json:
            raise HTTPException(status_code=500, detail="Orchestration config not found")
        
        orchestration_config = json.loads(orchestration_json)
        embedding_model_config = orchestration_config.get('embedding_model')
        if not embedding_model_config:
            raise HTTPException(status_code=500, detail="Embedding model config not found")
        
        # Initialize the embedding model
        from .inference import SentenceTransformerInference
        embedding_model = SentenceTransformerInference(
            embedding_model_config['model_name'], 
            remote_code=embedding_model_config.get('trust_remote_code', False)
        )
        
        # Generate embedding for the paper's abstract
        embedding = embedding_model.invoke(paper['abstract'])
        if hasattr(embedding, 'tolist'):
            embedding = embedding.tolist()
        elif not isinstance(embedding, list):
            embedding = list(embedding)
        
        # Update the paper with the new embedding
        db.update_paper_embedding(paper_id, embedding)
        
        return {"message": "Embedding updated successfully", "updated": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/papers/{paper_id}/similar", response_model=SimilarPapersResponse)
async def find_similar_papers_to_existing(
    paper_id: int,
    limit: int = Query(10, gt=0, le=200, description="Maximum number of similar papers to return"),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity score (0-1)")
):
    """Find papers similar to an existing paper using its stored embedding."""
    try:
        # Find similar papers using the database method
        result = db.find_similar_papers_to_existing(
            paper_id=paper_id,
            limit=limit,
            similarity_threshold=similarity_threshold
        )
        
        if result is None:
            raise HTTPException(
                status_code=404, 
                detail=f"Paper with ID {paper_id} not found or has no embedding"
            )
        
        # Convert reference paper to API response format
        ref_paper_data = result['reference_paper']
        reference_paper = PaperApiResponse(
            id=ref_paper_data['id'],
            title=ref_paper_data['title'],
            abstract=ref_paper_data['abstract'],
            score=ref_paper_data['score'],
            date=ref_paper_data['date'],
            url=ref_paper_data['url'],
            date_run=ref_paper_data['date_run'],
            rationale=ref_paper_data['rationale'],
            related=ref_paper_data['related'],
            cosine_similarity=ref_paper_data['cosine_similarity'],
            embedding_model=ref_paper_data['embedding_model']
        )
        
        # Convert similar papers to API response format
        similar_papers = []
        for p in result['similar_papers']:
            paper_response = PaperApiResponse(
                id=p['id'],
                title=p['title'],
                abstract=p['abstract'],
                score=p['score'],
                date=p['date'],
                url=p['url'],
                date_run=p['date_run'],
                rationale=p['rationale'],
                related=p['related'],
                cosine_similarity=p['cosine_similarity'],
                embedding_model=p['embedding_model'],
                similarity_score=p['similarity_score']  # Include the similarity score
            )
            similar_papers.append(paper_response)
        
        return SimilarPapersResponse(
            reference_paper=reference_paper,
            similar_papers=similar_papers,
            total_similar=result['total_similar']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Settings endpoints
@app.get("/api/settings/orchestration", response_model=OrchestrationConfig)
async def get_orchestration_config_api():
    """Get orchestration configuration, ensuring defaults for all fields including podcast and TTS."""
    try:
        db_config_json = db.get_setting("orchestration")
        loaded_config_data = {}

        if db_config_json:
            loaded_config_data = json.loads(db_config_json)
        else:
            # Fallback to orchestration.json if DB is empty
            config_path = os.path.join(os.path.dirname(__file__), '../config/orchestration.json')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded_config_data = json.load(f)
        
        # Define comprehensive defaults that Pydantic models expect
        default_embedding_model = ModelConfig(model_name='Alibaba-NLP/gte-modernbert-base', model_type='sentence-transformers', trust_remote_code=True)
        default_judge_model = ModelConfig(model_name='phi4-mini:3.8b-q8_0', model_type='ollama', max_new_tokens=512, temperature=0.1, num_ctx=4096)
        default_content_extraction_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_newsletter_sections_model = ModelConfig(model_name='gemma3:27b-it-qat', model_type='ollama', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_newsletter_intro_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=4096, temperature=0.1, num_ctx=131072)
        default_podcast_model = ModelConfig(model_name='gemini-2.0-flash', model_type='gemini', max_new_tokens=8192, temperature=0.1, num_ctx=131072)
        default_tts_model = TTSModelConfig(tts_provider='openai', tts_model_name='tts-1', speaker_1_voice='sage', speaker_1_speed=1.0, speaker_2_voice='ash', speaker_2_speed=1.0)

        # Create OrchestrationConfig by merging loaded data with defaults for missing top-level keys
        # Pydantic will handle missing sub-fields within ModelConfig/TTSModelConfig if they are optional or have defaults in their own definitions
        final_config = OrchestrationConfig(
            embedding_model=ModelConfig(**loaded_config_data.get('embedding_model', default_embedding_model.dict())),
            judge_model=ModelConfig(**loaded_config_data.get('judge_model', default_judge_model.dict())),
            content_extraction_model=ModelConfig(**loaded_config_data.get('content_extraction_model', default_content_extraction_model.dict())),
            newsletter_sections_model=ModelConfig(**loaded_config_data.get('newsletter_sections_model', default_newsletter_sections_model.dict())),
            newsletter_intro_model=ModelConfig(**loaded_config_data.get('newsletter_intro_model', default_newsletter_intro_model.dict())),
            podcast_model=ModelConfig(**loaded_config_data.get('podcast_model', default_podcast_model.dict())),
            tts_model=TTSModelConfig(**loaded_config_data.get('tts_model', default_tts_model.dict()))
        )
        return final_config

    except Exception as e:
        # Adding more context to the error for easier debugging
        error_detail = f"Error getting orchestration config: {str(e)}. DB JSON: {db_config_json if 'db_config_json' in locals() else 'Not fetched/Error'}. Loaded Data: {loaded_config_data if 'loaded_config_data' in locals() else 'Not loaded/Error'}."
        raise HTTPException(status_code=500, detail=error_detail)

@app.put("/api/settings/orchestration")
async def update_orchestration_config_api(config: OrchestrationConfig):
    """Update orchestration configuration."""
    try:
        db.set_setting("orchestration", config.json())
        # Also update orchestration.json for legacy/fallback
        config_path = os.path.join(os.path.dirname(__file__), '../config/orchestration.json')
        with open(config_path, 'w') as f:
            json.dump(json.loads(config.json()), f, indent=2)
        return {"status": "success", "message": "Orchestration configuration updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating orchestration config: {str(e)}")

@app.get("/api/settings/arxiv-categories", response_model=ArxivCategoriesConfig)
async def get_arxiv_categories_api():
    """Get ArXiv search categories."""
    try:
        settings_json = db.get_setting("arxiv_search_categories")
        if settings_json:
            return ArxivCategoriesConfig.parse_raw(settings_json)
        # Return default ArXivCategoriesConfig if not found in DB
        return ArxivCategoriesConfig(
            main_category="cs",
            filter_categories=["cs.ai", "cs.cl", "cs.lg", "cs.ir", "cs.ma", "cs.cv"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting ArXiv categories: {str(e)}")

@app.put("/api/settings/arxiv-categories")
async def update_arxiv_categories_api(config: ArxivCategoriesConfig):
    """Update ArXiv search categories."""
    try:
        db.set_setting("arxiv_search_categories", config.json())
        return {"status": "success", "message": "ArXiv categories updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating ArXiv categories: {str(e)}")

@app.get("/api/model-providers", response_model=List[ModelProvider])
async def get_model_providers_api():
    """Get all available model providers."""
    try:
        providers_data = db.get_model_providers() # This returns a list of dicts like [{'id': 1, 'name': 'ollama'}]
        return [ModelProvider(id=p['id'], name=p['name']) for p in providers_data]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting model providers: {str(e)}")

@app.get("/api/settings/research-interests", response_model=ResearchInterests)
async def get_research_interests_api():
    """Get research interests. Prioritizes DB, then research_interests.txt, then empty string."""
    try:
        interests = db.get_setting("research_interests")
        if interests is not None: # Check if DB returned a value (could be empty string)
            return ResearchInterests(interests=interests)
        else:
            # Fallback to research_interests.txt
            config_path = os.path.join(os.path.dirname(__file__), '../config/research_interests.txt')
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    interests_from_file = f.read().strip()
                return ResearchInterests(interests=interests_from_file)
            else:
                # Default to empty string if neither DB nor file exists
                return ResearchInterests(interests="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research interests: {str(e)}")

@app.put("/api/settings/research-interests", response_model=ResearchInterests)
async def update_research_interests_api(data: ResearchInterests):
    """Update research interests in DB and research_interests.txt."""
    try:
        # Save to DB
        db.set_setting("research_interests", data.interests)
        
        # Save to research_interests.txt
        config_path = os.path.join(os.path.dirname(__file__), '../config/research_interests.txt')
        try:
            with open(config_path, 'w') as f:
                f.write(data.interests)
        except IOError as e:
            # Log error but don't fail the request if DB save was successful
            print(f"Warning: Could not write to {config_path}: {e}")
            # Optionally, you could raise an HTTPException here if writing to file is critical
            # raise HTTPException(status_code=500, detail=f"Error saving research interests to file: {str(e)}")

        return data # Return the updated data
    except Exception as e:
        # Log the full error for debugging
        print(f"Full error updating research interests: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating research interests: {str(e)}")

@app.get("/api/settings/email-recipients", response_model=EmailRecipients)
async def get_email_recipients():
    """Get email recipients list."""
    try:
        recipients_list = db.get_email_recipients()
        return EmailRecipients(recipients=recipients_list)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/settings/email-recipients")
async def update_email_recipients(data: EmailRecipients):
    """Update email recipients list."""
    try:
        # Basic email validation (optional here if Pydantic model handles it, or keep for defense-in-depth)
        for email in data.recipients:
            if "@" not in email or "." not in email: # Basic check
                raise HTTPException(status_code=400, detail=f"Invalid email address: {email}")
        db.set_email_recipients(data.recipients)
        return {"status": "success", "message": "Email recipients updated successfully."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings/visualizer-settings", response_model=VisualizerSettings)
async def get_visualizer_settings():
    """Get visualizer settings."""
    try:
        settings = db.get_visualizer_settings()
        if not settings:
            # Return default settings from the model
            return VisualizerSettings().dict()
        return settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings/send-test-email")
async def send_test_email():
    """Send a test email to email address in GMAIL_SENDER_ADDRESS environment variable."""
    try:
        from .communication import GmailCommunication
        
        # Initialize email client
        gmail_sender = os.getenv("GMAIL_SENDER_ADDRESS")
        gmail_password = os.getenv("GMAIL_APP_PASSWORD")
        
        if not gmail_sender or not gmail_password:
            raise HTTPException(
                status_code=500,
                detail="Email credentials not configured"
            )
            
        comm = GmailCommunication(
            sender_address=gmail_sender,
            app_password=gmail_password,
            receiver_address=gmail_sender
        )
        
        # Send test email
        test_content = """
        This is a test email from Theseus Insight.
        
        If you're receiving this, your email configuration is working correctly.
        
        Best regards,
        Theseus Insight Team
        """
        
        comm.compose_message(
            content=test_content,
            start_date=datetime.now().date(),
            end_date=datetime.now().date(),
            subject="Theseus Insight - Test Email"
        )
        comm.send_email()
        
        return {"status": "success", "message": "Test email sent successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/runs", response_model=PaginatedResponse)
async def get_runs(
    page: int = Query(1, gt=0),
    sort_field: Optional[str] = None,
    sort_direction: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None
):
    """Get paginated list of runs."""
    try:
        # TODO: Implement proper pagination and filtering
        # For now, return all runs
        runs = []
        newsletters = db.fetch_all_newsletters()
        podcasts = db.fetch_all_podcasts()
        
        # Convert newsletters to runs
        for n in newsletters:
            runs.append(Run(
                id=n['id'],
                date=n['date_sent'],
                pipeline_type='newsletter',
                status='completed',  # Assuming all stored ones are completed
                duration=0.0,  # TODO: Add duration tracking
                artifact_path=f"newsletters/{n['id']}/content.md"
            ))
            
        # Convert podcasts to runs
        for p in podcasts:
            runs.append(Run(
                id=p['id'],
                date=p['date'],
                pipeline_type='podcast',
                status='completed',
                duration=0.0,
                artifact_path=f"podcasts/{p['id']}/audio.mp3"
            ))
            
        # Sort runs by date descending
        runs.sort(key=lambda x: x.date, reverse=True)
        
        # Basic pagination
        page_size = 10
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_runs = runs[start_idx:end_idx]
        
        return PaginatedResponse(
            items=page_runs,
            nextPage=page + 1 if end_idx < len(runs) else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/runs/{run_id}/artifact")
async def delete_run_artifact(run_id: int):
    """Delete the artifact associated with a run."""
    try:
        # First determine if this is a newsletter or podcast run
        newsletters = db.fetch_all_newsletters()
        podcasts = db.fetch_all_podcasts()
        
        # Check newsletters
        newsletter = next((n for n in newsletters if n['id'] == run_id), None)
        if newsletter:
            artifact_path = f"data/newsletters/{run_id}/content.md"
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
                # Remove the directory if empty
                try:
                    os.rmdir(os.path.dirname(artifact_path))
                except OSError:
                    pass  # Directory not empty
            return {"status": "success"}
            
        # Check podcasts
        podcast = next((p for p in podcasts if p['id'] == run_id), None)
        if podcast:
            artifact_path = f"data/podcasts/{run_id}/audio.mp3"
            if os.path.exists(artifact_path):
                os.remove(artifact_path)
                # Remove the directory if empty
                try:
                    os.rmdir(os.path.dirname(artifact_path))
                except OSError:
                    pass  # Directory not empty
            return {"status": "success"}
            
        # If we get here, the run wasn't found
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get the current status of a task."""
    try:
        status = task_manager.get_task_status(task_id)
        if not status:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/active")
async def get_active_tasks(task_types: Optional[str] = Query(None)):
    """Get all active tasks, optionally filtered by type."""
    try:
        types_filter = task_types.split(',') if task_types else None
        active_tasks = task_manager.db.get_active_tasks(task_types=types_filter)
        return {"active_tasks": active_tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """Get the result of a completed task."""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
        if task["status"] != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed (current status: {task['status']})"
            )
            
        if not task.get("result"):
            raise HTTPException(status_code=404, detail="No result available for this task")
            
        return task["result"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/tasks/{task_id}/abort")
async def abort_task(task_id: str):
    """Abort a running task."""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
        if task["status"] not in [TaskStatus.PENDING, TaskStatus.PROCESSING]:
            raise HTTPException(
                status_code=400,
                detail=f"Task cannot be aborted (current status: {task['status']})"
            )
            
        # Mark task as failed with abort message
        await task_manager.update_task_status(
            task_id,
            TaskStatus.FAILED,
            message="Task aborted by user",
            error="Task was manually aborted",
            current_step="aborted"
        )
        
        return {"status": "success", "message": f"Task {task_id} has been aborted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks/{task_id}/download/{file_type}")
async def download_task_artifact(task_id: str, file_type: str):
    """Download a task artifact (newsletter or podcast)."""
    try:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
            
        if task["status"] != TaskStatus.COMPLETED:
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed (current status: {task['status']})"
            )
            
        result = task.get("result")
        if not result:
            raise HTTPException(status_code=404, detail="No result available for this task")
            
        if task["type"] == "newsletter":
            if file_type != "markdown":
                raise HTTPException(status_code=400, detail="Only markdown format is available for newsletters")
                
            # Create a temporary markdown file
            output_path = f"data/temp/{task_id}/newsletter.md"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w") as f:
                f.write(result["newsletter_content"])
                
            return FileResponse(
                output_path,
                media_type="text/markdown",
                filename="newsletter.md"
            )
            
        elif task["type"] == "podcast":
            if file_type not in ["audio", "video"]:
                raise HTTPException(
                    status_code=400,
                    detail="Available formats for podcasts: audio, video"
                )
                
            # Get the appropriate file path
            if file_type == "audio":
                file_path = result["output_file"]
                media_type = "audio/mpeg"
                filename = "podcast.mp3"
            else:  # video
                if not result.get("visualizer_file"):
                    raise HTTPException(
                        status_code=404,
                        detail="No video visualization available for this podcast"
                    )
                file_path = result["visualizer_file"]
                media_type = "video/mp4"
                filename = "podcast.mp4"
                
            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Artifact file not found: {file_path}"
                )
                
            return FileResponse(
                file_path,
                media_type=media_type,
                filename=filename
            )

        elif task["type"] == "visualizer": # Added block for visualizer
            if file_type != "video":
                raise HTTPException(
                    status_code=400,
                    detail="Only video format is available for visualizer tasks"
                )
            
            if not result.get("visualizer_file"):
                raise HTTPException(
                    status_code=404,
                    detail="No video visualization available for this visualizer task"
                )
            file_path = result["visualizer_file"]
            media_type = "video/mp4"
            filename = "visualization.mp4" # Or derive from task/result if needed

            if not os.path.exists(file_path):
                raise HTTPException(
                    status_code=404,
                    detail=f"Artifact file not found: {file_path}"
                )
            
            return FileResponse(
                file_path,
                media_type=media_type,
                filename=filename
            )
            
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown task type: {task['type']}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/logs", response_model=List[LogEntry])
async def get_logs_api(
    limit: int = Query(100, gt=0, le=1000),
    from_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$"), # YYYY-MM-DD
    to_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$") # YYYY-MM-DD
):
    """Get recent logs, filterable by date."""
    try:
        if from_date and to_date and from_date > to_date:
            raise HTTPException(status_code=400, detail="from_date cannot be after to_date")
        
        logs_data = db.get_recent_logs(limit=limit, from_date=from_date, to_date=to_date)
        return [LogEntry(**log) for log in logs_data]
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        # Consider logging the exception for server-side debugging
        print(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching logs.")

@app.post("/api/newsletter/run")
async def run_newsletter(
    background_tasks: BackgroundTasks,
    config: Optional[str] = Form(None),
    intro_music_file: Optional[UploadFile] = File(None)
):
    """Start the newsletter generation pipeline."""
    try:
        # Parse config
        if not config:
            raise HTTPException(status_code=400, detail="Newsletter configuration is required")
        
        newsletter_config = NewsletterConfig.parse_raw(config)
        task_id = str(uuid.uuid4())
        
        # Save intro music file if provided
        if intro_music_file:
            file_path = f"data/temp/{task_id}/intro_music{os.path.splitext(intro_music_file.filename)[1]}"
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(await intro_music_file.read())
            newsletter_config.dict()["intro_music_path"] = file_path
        
        # Create and start task
        await task_manager.create_task(
            task_id=task_id,
            task_type="newsletter",
            config=newsletter_config.dict()
        )
        background_tasks.add_task(task_manager.run_newsletter_task, task_id)
        
        return {"taskId": task_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/podcast/generate")
async def generate_podcast_pipeline(
    background_tasks: BackgroundTasks,
    params_json: str = Form(..., description="JSON string of PodcastGenerationParams"),
    intro_music_file: Optional[UploadFile] = File(None),
    pdf_files: Optional[List[UploadFile]] = File(None, description="List of PDF files if input_type is 'pdfs'")
):
    """
    Start the podcast generation pipeline using detailed parameters.
    Accepts PodcastGenerationParams as a JSON string in 'params_json' form field,
    an optional intro music file, and optional PDF files.
    """
    try:
        generation_params = PodcastGenerationParams.parse_raw(params_json)
        task_id = str(uuid.uuid4())

        # This will be the main config dictionary passed to the task manager
        # It will be used by the background task to instantiate and run PodcastGenerator
        task_config = {
            "input_type": generation_params.input_type,
            "podcast_model_config": generation_params.podcast_model_config.dict(),
            "tts_model_config": generation_params.tts_model_config.dict(),
            "create_visualization": generation_params.create_visualization,
            "db_saving": True, # Default, can be made configurable if needed
            "data_path": DB_URL, # Global DB URL
            "verbose": True, # Default, can be made configurable
            "output_dir_base": "data/podcasts", # Base directory for task outputs
            "task_id": task_id # Pass task_id for organizing outputs
        }

        if generation_params.urls:
            task_config["urls"] = generation_params.urls
        
        # Handle uploaded intro music file
        if intro_music_file:
            temp_dir = f"data/temp/{task_id}"
            os.makedirs(temp_dir, exist_ok=True)
            intro_music_path = os.path.join(temp_dir, f"intro_{intro_music_file.filename}")
            with open(intro_music_path, "wb") as f:
                f.write(await intro_music_file.read())
            task_config["intro_music_path"] = intro_music_path

        # Handle uploaded PDF files
        if generation_params.input_type == "pdfs" and pdf_files:
            saved_pdf_paths = []
            pdf_temp_dir = f"data/temp/{task_id}/uploaded_pdfs"
            os.makedirs(pdf_temp_dir, exist_ok=True)
            for i, pdf_file in enumerate(pdf_files):
                # Sanitize filename or use a unique name
                safe_filename = f"doc_{i}_{os.path.basename(pdf_file.filename or f'file{i}.pdf')}"
                pdf_path = os.path.join(pdf_temp_dir, safe_filename)
                with open(pdf_path, "wb") as f:
                    f.write(await pdf_file.read())
                saved_pdf_paths.append(pdf_path)
            task_config["input_pdf_paths"] = saved_pdf_paths
        elif generation_params.input_type == "pdfs" and not pdf_files:
            raise HTTPException(status_code=400, detail="PDF files are required when input_type is 'pdfs'.")


        if generation_params.create_visualization and generation_params.visualizer_params:
            vis_p = generation_params.visualizer_params
            task_config.update({
                "visualizer_settings": vis_p.dict() # Pass the whole dict
            })
        else:
            task_config["visualizer_settings"] = None


        # Create task with the comprehensive config
        await task_manager.create_task(
            task_id=task_id,
            task_type="podcast", # Using existing "podcast" type, assuming run_podcast_task can handle new config
            config=task_config 
        )
        
        # The task_manager.run_podcast_task needs to be able to:
        # 1. Instantiate PodcastGenerator with relevant parts of task_config
        #    (podcast_model_config, tts_model_config, intro_music_path, etc.)
        # 2. Call PodcastGenerator.generate_podcast() with input_pdf_paths or processed URLs,
        #    output directory derived from task_id, and visualizer settings.
        # 3. Handle URL fetching and conversion to PDF if input_type is 'urls' (this is complex).
        #    For now, this implementation primarily supports 'pdfs' directly for PodcastGenerator.
        #    If 'urls' are passed, 'run_podcast_task' needs to manage downloading/converting them to PDF paths.
        background_tasks.add_task(task_manager.run_podcast_task, task_id)
        
        return {"task_id": task_id, "message": "Podcast generation process initiated."}
    
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for params_json.")
    except ValueError as e: # Handles Pydantic validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException: # Re-raise existing HTTPExceptions
        raise
    except Exception as e:
        print(f"Error in /api/podcast/generate: {type(e).__name__} - {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error processing podcast request: {str(e)}")

# --- Pydantic Model for Visualizer Params ---
# Re-using VisualizerSettings for consistency if it matches, or define a specific one if needed.
# For now, assuming VisualizerSettings from .api.models is suitable.
from .api.models import VisualizerSettings as VisualizerParamsForPipeline # Alias for clarity

@app.post("/api/actions/run-visualizer-pipeline")
async def run_visualizer_pipeline_endpoint(
    background_tasks: BackgroundTasks,
    audio_file: UploadFile = File(..., description="Audio file to visualize"),
    visualizer_params_json: str = Form(..., description="JSON string of VisualizerParamsForPipeline")
):
    task_id = str(uuid.uuid4())
    try:
        visualizer_params = VisualizerParamsForPipeline.parse_raw(visualizer_params_json)
        
        temp_dir = f"data/temp/{task_id}"
        os.makedirs(temp_dir, exist_ok=True)
        
        audio_file_path = os.path.join(temp_dir, f"audio_input_{audio_file.filename}")
        with open(audio_file_path, "wb") as f:
            f.write(await audio_file.read())

        task_config = {
            "audio_file_path": audio_file_path,
            "visualizer_params": visualizer_params.dict(),
            "output_dir_base": "data/visualizations", # Base directory for task outputs
            "task_id": task_id
        }

        await task_manager.create_task(
            task_id=task_id,
            task_type="visualizer",
            config=task_config
        )
        
        background_tasks.add_task(task_manager.run_visualizer_task, task_id)
        
        return {"task_id": task_id, "message": "Visualizer generation process initiated."}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for visualizer_params_json.")
    except ValidationError as e: # Pydantic validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error processing visualizer request: {str(e)}")

# Podcast History Endpoints
@app.get("/api/podcasts/history", response_model=List[PodcastListItemResponse])
async def get_podcast_history_list():
    """Get a list of all podcasts, sorted by date, for history view."""
    try:
        podcasts_data = db.fetch_all_podcasts() # This already sorts by id DESC, which is fine if new IDs are always later dates. If date sorting is strict, we'd sort here.
        
        response_items = []
        for p_data in podcasts_data:
            description_snippet = (p_data['description'][:150] + '...') if len(p_data['description']) > 150 else p_data['description']
            response_items.append(
                PodcastListItemResponse(
                    id=p_data['id'],
                    title=p_data['title'],
                    date=p_data['date'],
                    description_snippet=description_snippet
                )
            )
        # To strictly sort by date if IDs don't guarantee it:
        response_items.sort(key=lambda x: datetime.strptime(x.date, '%Y-%m-%d'), reverse=True)
        return response_items
    except Exception as e:
        print(f"Error fetching podcast history list: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred while fetching podcast history.")

@app.get("/api/podcasts/history/{podcast_id}", response_model=PodcastDetailResponse)
async def get_podcast_detail(podcast_id: int):
    """Get detailed information for a single podcast, including its parsed script."""
    try:
        podcast_data = db.fetch_podcast_by_id(podcast_id)
        if not podcast_data:
            raise HTTPException(status_code=404, detail=f"Podcast with ID {podcast_id} not found.")
        
        # The script from db.fetch_podcast_by_id is already a Python list of dicts
        # Pydantic will validate it against List[PodcastScriptItem]
        return PodcastDetailResponse(
            id=podcast_data['id'],
            title=podcast_data['title'],
            date=podcast_data['date'],
            description=podcast_data['description'],
            script=podcast_data['script'] # Pydantic validation happens here
        )
    except HTTPException: # Re-raise HTTPException directly
        raise
    except ValidationError as ve: # Catch Pydantic validation errors specifically for the script
        print(f"Validation error for podcast script (ID: {podcast_id}): {ve}")
        raise HTTPException(status_code=500, detail=f"Error validating podcast script data for podcast ID {podcast_id}.")
    except Exception as e:
        print(f"Error fetching podcast detail (ID: {podcast_id}): {e}")
        raise HTTPException(status_code=500, detail=f"An internal server error occurred while fetching details for podcast ID {podcast_id}.")

# Enhance the WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        """Connect a new WebSocket client."""
        try:
            await websocket.accept()
            if task_id not in self.active_connections:
                self.active_connections[task_id] = []
            self.active_connections[task_id].append(websocket)
        except Exception as e:
            print(f"Error connecting WebSocket: {e}")
            try:
                await websocket.close(code=4000, reason=str(e))
            except Exception:
                pass
            raise

    def disconnect(self, task_id: str, websocket: WebSocket):
        """Disconnect a WebSocket client."""
        try:
            if task_id in self.active_connections:
                if websocket in self.active_connections[task_id]:
                    self.active_connections[task_id].remove(websocket)
                if not self.active_connections[task_id]:
                    del self.active_connections[task_id]
        except Exception as e:
            print(f"Error disconnecting WebSocket: {e}")

    async def broadcast_status(self, task_id: str, status: RunStatus):
        """Broadcast status to all connected clients for a task."""
        if task_id in self.active_connections:
            dead_connections = []
            for connection in self.active_connections[task_id]:
                try:
                    await connection.send_json(status.dict())
                except WebSocketDisconnect:
                    dead_connections.append(connection)
                except Exception as e:
                    print(f"Error broadcasting to WebSocket: {e}")
                    dead_connections.append(connection)
            
            # Clean up dead connections
            for dead in dead_connections:
                self.disconnect(task_id, dead)

    async def close_all(self, task_id: str):
        """Close all connections for a task."""
        if task_id in self.active_connections:
            connections_to_close = self.active_connections[task_id].copy()
            for connection in connections_to_close:
                try:
                    await connection.close(code=1000)
                except Exception:
                    pass
            del self.active_connections[task_id]
    
    async def cleanup_all(self):
        """Close all active connections."""
        task_ids = list(self.active_connections.keys())
        for task_id in task_ids:
            await self.close_all(task_id)

manager = ConnectionManager()

# Update WebSocket endpoints
@app.websocket("/ws/newsletter/{task_id}")
async def newsletter_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for newsletter generation status updates."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            
            # Check for cleanup sentinel
            if status is None:
                break
                
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        try:
            await websocket.close(code=4004, reason=str(e))
        except Exception:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket)

@app.websocket("/ws/podcast/{task_id}")
async def podcast_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for podcast generation status updates."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            
            # Check for cleanup sentinel
            if status is None:
                break
                
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e:
        try:
            await websocket.close(code=4004, reason=str(e))
        except Exception:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e))
        except Exception:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket)

@app.websocket("/ws/visualizer/{task_id}")
async def visualizer_status(websocket: WebSocket, task_id: str):
    """WebSocket endpoint for visualizer generation status updates."""
    status_queue = None
    try:
        await manager.connect(task_id, websocket)
        
        # Subscribe to task updates
        status_queue = await task_manager.subscribe_to_updates(task_id)
        
        while True:
            # Wait for status updates
            status = await status_queue.get()
            
            # Check for cleanup sentinel
            if status is None:
                break
                
            await websocket.send_json(status.dict())
            
            # If task is completed or failed, close connection
            if status.overallStatus in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                break
                
    except WebSocketDisconnect:
        pass
    except ValueError as e: # Handles task not found from subscribe_to_updates
        try:
            await websocket.close(code=4004, reason=str(e)) # Custom code for task not found
        except Exception:
            pass
    except Exception as e:
        try:
            await websocket.close(code=4000, reason=str(e)) # Generic error
        except Exception:
            pass
    finally:
        if status_queue:
            await task_manager.unsubscribe_from_updates(task_id, status_queue)
        manager.disconnect(task_id, websocket)

# --- Endpoint for Running TheseusInsight Newsletter Pipeline ---
@app.post("/api/actions/run-newsletter-pipeline", response_model=Dict[str, str])
async def run_newsletter_pipeline_endpoint(
    params: NewsletterRunParams,
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    run_db_path = DB_URL
    loop = asyncio.get_event_loop()

    def pipeline_progress_callback(stage: str, progress_val: float, message: str):
        """Relay progress from TheseusInsight.run to connected WebSocket clients."""
        status_detail = f"Stage: {stage} - {message} ({progress_val:.2f}%)"
        overall_status_for_tm = TaskStatus.PROCESSING
        if stage.lower() == "newsletter_complete" and progress_val >= 100.0:
            overall_status_for_tm = TaskStatus.COMPLETED

        async def update_status_async():
            await task_manager.update_task_status(
                task_id,
                overall_status_for_tm,
                message=status_detail,
                progress=progress_val,
                current_step=stage,            )

        if loop.is_running():
            # Running from a background thread -> use thread-safe scheduling
            asyncio.run_coroutine_threadsafe(update_status_async(), loop)
        else:
            # Fallback if no running loop was found
            try:
                asyncio.create_task(update_status_async())
            except RuntimeError as e:
                print(
                    "RuntimeError creating task for status update (loop might not be running or accessible): "
                    f"{e}"
                )
                # Consider logging this to a file or a more robust system if it occurs

    async def background_pipeline_run():
        try:
            await task_manager.create_task(
                task_id=task_id,
                task_type="custom_newsletter_run",
                config=params.dict()
            )
            await task_manager.update_task_status(
                task_id,
                TaskStatus.PENDING,
                message="Pipeline initialized.",
                current_step="initializing",
            )

            ti_instance = TheseusInsight(
                research_interests_override=params.research_interests,
                start_date_override=params.start_date,
                end_date_override=params.end_date,
                receiver_address_override=params.email_recipients,
                generate_podcast=params.generate_podcast_run,
                db_saving=True, 
                data_path=run_db_path,
                verbose=True,
                task_id=task_id
            )
            await asyncio.to_thread(
                ti_instance.run,
                progress_callback=pipeline_progress_callback,
            )
            
            current_task_status = task_manager.get_task_status(task_id)
            # If the progress callback hasn't already marked completion
            if current_task_status and current_task_status.get("status") == TaskStatus.PROCESSING:
                await task_manager.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED,
                    message="Pipeline finished processing.",
                    current_step="newsletter_complete",
                )

        except Exception as e:
            error_message = f"Error in newsletter pipeline for task {task_id}: {type(e).__name__} - {str(e)}"
            if task_manager:
                await task_manager.update_task_status(
                    task_id,
                    TaskStatus.FAILED,
                    error=error_message,
                    message=error_message,
                    current_step="newsletter_failed",
                )
            print(error_message) # Log to server console as well

    background_tasks.add_task(background_pipeline_run)
    return {"task_id": task_id, "message": "Newsletter generation process has been initiated."}

# --- Serve React Frontend --- #
# This block MUST come AFTER all other API routes have been defined.
if STATIC_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_ASSETS_DIR), name="assets")
else:
    print(f"WARNING: Static assets directory not found at {STATIC_ASSETS_DIR}. Frontend may not be served correctly if running locally without a build.")

@app.get("/{full_path:path}")
async def serve_react_app(full_path: str):
    """Serves the index.html for any path not caught by API routes or specific static files."""
    if STATIC_INDEX_HTML.exists():
        return FileResponse(STATIC_INDEX_HTML)
    else:
        detail_message = f"Frontend index.html not found at {STATIC_INDEX_HTML}."
        if not IS_RUNNING_IN_DOCKER:
            detail_message += " Ensure the frontend has been built (e.g., `npm run build` in `theseus-ui` directory)."
        raise HTTPException(status_code=404, detail=detail_message) 
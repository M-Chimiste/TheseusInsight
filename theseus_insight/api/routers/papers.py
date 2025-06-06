from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import json

from ..models import (
    PaperApiResponse, PaginatedPapersResponse,
    SimilaritySearchRequest, SimilaritySearchResponse,
    SimilarPapersRequest, SimilarPapersResponse,
    HybridSearchRequest, HybridSearchResponse
)
from ..dependencies import db

router = APIRouter(prefix="/api/papers", tags=["papers"])

@router.get("", response_model=PaginatedPapersResponse)
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

@router.post("/similarity-search", response_model=SimilaritySearchResponse)
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
        from ...inference import SentenceTransformerInference
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

@router.post("/hybrid-search", response_model=HybridSearchResponse)
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
        from ...inference import SentenceTransformerInference
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

@router.get("/without-embeddings")
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

@router.post("/{paper_id}/update-embedding")
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
        from ...inference import SentenceTransformerInference
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

@router.get("/{paper_id}/similar", response_model=SimilarPapersResponse)
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
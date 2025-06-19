from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import List
import uuid
from datetime import datetime

from ..models import (
    MindMapExpandRequest, MindMapExpandResponse,
    PDFParseRequest, PDFParseResponse,
    MindMapSeedSearchRequest, MindMapSeedSearchResponse,
    PaperApiResponse
)
from ..dependencies import db
from ..tasks import task_manager

router = APIRouter(prefix="/api/mindmap", tags=["mindmap"])

@router.post("/expand", response_model=MindMapExpandResponse)
async def expand_mindmap(
    background_tasks: BackgroundTasks,
    request: MindMapExpandRequest
):
    """
    Generate a mind-map around a seed paper.
    
    This endpoint creates a background task to generate a mind-map visualization
    around a specified seed paper. The process includes:
    1. Validating the seed paper exists
    2. Finding similar papers using vector similarity
    3. Generating LLM summaries for each paper
    4. Building the mind-map with specified layout algorithm
    
    The task progress can be tracked via WebSocket at /ws/mindmap/{task_id}
    """
    try:
        # Validate seed paper exists
        seed_paper = db.get_paper_by_id(int(request.paper_id))
        if not seed_paper:
            raise HTTPException(status_code=404, detail=f"Paper {request.paper_id} not found")
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task configuration
        config = {
            "paper_id": request.paper_id,
            "k": request.k,
            "similarity_threshold": request.similarity_threshold,
            "layout_algorithm": request.layout_algorithm,
            "model_config_override": request.model_config_override.dict() if request.model_config_override else None
        }
        
        # Create task in database
        await task_manager.create_task(task_id, "mindmap_expand", config)
        
        # Enqueue background task
        await task_manager.enqueue_task(task_manager.run_mindmap_expand_task, task_id)
        
        return MindMapExpandResponse(
            task_id=task_id,
            message=f"Mind-map generation started for paper {request.paper_id}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start mind-map generation: {str(e)}")

@router.post("/parse-pdfs", response_model=PDFParseResponse)
async def parse_pdfs(
    background_tasks: BackgroundTasks,
    request: PDFParseRequest
):
    """
    Parse PDFs for up to 20 papers on-demand.
    
    This endpoint creates a background task to parse PDF content for the specified
    papers. The parsed content will be stored in the paper_fulltext table and can
    be used to enhance mind-map insights.
    
    The task progress can be tracked via WebSocket at /ws/mindmap-pdf-parse/{task_id}
    """
    try:
        # Validate paper IDs exist and check which ones need parsing
        papers_to_parse = []
        for paper_id in request.paper_ids:
            paper = db.get_paper_by_id(int(paper_id))
            if not paper:
                raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")
            
            # Check if paper already has full-text
            if not db.has_paper_fulltext(int(paper_id)):
                papers_to_parse.append(paper_id)
        
        if not papers_to_parse:
            return PDFParseResponse(
                task_id="",
                message="All specified papers already have full-text content",
                papers_to_parse=0
            )
        
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Create task configuration
        config = {
            "paper_ids": papers_to_parse,
            "original_request_count": len(request.paper_ids),
            "already_parsed_count": len(request.paper_ids) - len(papers_to_parse)
        }
        
        # Create task in database
        await task_manager.create_task(task_id, "mindmap_pdf_parse", config)
        
        # Enqueue background task
        await task_manager.enqueue_task(task_manager.run_mindmap_pdf_parse_task, task_id)
        
        return PDFParseResponse(
            task_id=task_id,
            message=f"PDF parsing started for {len(papers_to_parse)} papers",
            papers_to_parse=len(papers_to_parse)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start PDF parsing: {str(e)}")

@router.get("/search-seeds", response_model=MindMapSeedSearchResponse)
async def search_seed_papers(
    query: str,
    limit: int = 10
):
    """
    Search for papers to use as mind-map seeds.
    
    This endpoint performs a full-text search over paper titles and abstracts
    to help users find suitable seed papers for mind-map generation.
    """
    try:
        # Validate parameters
        if len(query.strip()) < 3:
            raise HTTPException(status_code=400, detail="Query must be at least 3 characters long")
        
        if limit < 1 or limit > 50:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 50")
        
        # Perform search using existing database method
        results = db.search_papers_for_mindmap_seed(query.strip(), limit)
        
        # Convert to API response format
        papers = []
        for paper_data in results:
            paper = PaperApiResponse(
                id=paper_data['id'],
                title=paper_data['title'],
                abstract=paper_data['abstract'],
                date=paper_data['date'],
                date_run=paper_data.get('date_run', ''),
                score=paper_data.get('score', 0.0),
                rationale=paper_data.get('rationale', ''),
                related=paper_data.get('related', False),
                cosine_similarity=paper_data.get('cosine_similarity', 0.0),
                url=paper_data.get('url', ''),
                embedding_model=paper_data.get('embedding_model', '')
            )
            papers.append(paper)
        
        return MindMapSeedSearchResponse(
            query=query,
            results=papers,
            total_results=len(papers)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search seed papers: {str(e)}")

@router.get("/paper/{paper_id}")
async def get_paper_details(paper_id: str):
    """
    Get detailed information about a paper for mind-map display.
    
    This endpoint returns paper metadata, abstract, and flags indicating
    whether full-text content is available.
    """
    try:
        # Get paper from database
        paper = db.get_paper_by_id(int(paper_id))
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")
        
        # Check if full-text is available
        has_fulltext = db.has_paper_fulltext(int(paper_id))
        
        # Return paper details with full-text flag
        return {
            "id": paper['id'],
            "title": paper['title'],
            "abstract": paper['abstract'],
            "date": paper['date'],
            "url": paper.get('url', ''),
            "score": paper.get('score', 0.0),
            "has_fulltext": has_fulltext,
            "embedding_model": paper.get('embedding_model', '')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paper details: {str(e)}") 
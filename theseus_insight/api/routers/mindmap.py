from fastapi import APIRouter, HTTPException, BackgroundTasks, Body
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uuid
from datetime import datetime, date

from ..models import (
    MindMapExpandRequest, MindMapExpandResponse,
    PDFParseRequest, PDFParseResponse,
    MindMapSeedSearchRequest, MindMapSeedSearchResponse,
    MindMapReport, MindMapReportSaveRequest, MindMapReportSaveResponse,
    MindMapReportListResponse,
    PaperApiResponse
)
from ...data_access import (
    PaperRepository,
    PaperFulltextRepository,
    MindmapReportRepository
)
from ..tasks import task_manager

router = APIRouter(prefix="/api/mindmap", tags=["mindmap"])

def _convert_datetime_to_string(value):
    """Convert datetime/date objects to ISO format strings."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value

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
        seed_paper = PaperRepository.get_by_id(int(request.paper_id))
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
            "model_config_override": request.model_config_override.dict() if request.model_config_override else None,
            "expansion_order": request.expansion_order,
            "max_nodes_per_order": request.max_nodes_per_order
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
            paper = PaperRepository.get_by_id(int(paper_id))
            if not paper:
                raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")
            
            # Check if paper already has full-text
            if not PaperFulltextRepository.has_fulltext(int(paper_id)):
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
        results = PaperRepository.search_seed(query.strip(), limit)
        
        # Convert to API response format
        papers = []
        for paper_data in results:
            paper = PaperApiResponse(
                id=paper_data['id'],
                title=paper_data['title'],
                abstract=paper_data['abstract'],
                date=_convert_datetime_to_string(paper_data['date']),
                date_run=_convert_datetime_to_string(paper_data.get('date_run', '')),
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
        paper = PaperRepository.get_by_id(int(paper_id))
        if not paper:
            raise HTTPException(status_code=404, detail=f"Paper {paper_id} not found")
        
        # Check if full-text is available
        has_fulltext = PaperFulltextRepository.has_fulltext(int(paper_id))
        
        # Return paper details with full-text flag
        return {
            "id": paper['id'],
            "title": paper['title'],
            "abstract": paper['abstract'],
            "date": _convert_datetime_to_string(paper['date']),
            "url": paper.get('url', ''),
            "score": paper.get('score', 0.0),
            "has_fulltext": has_fulltext,
            "embedding_model": paper.get('embedding_model', '')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get paper details: {str(e)}")

# Mind-Map Reports endpoints
@router.get("/reports", response_model=MindMapReportListResponse)
async def get_mindmap_reports():
    """
    Get list of all saved mind-map reports.
    
    Returns a list of saved mind-map reports with metadata.
    """
    try:
        reports_data = MindmapReportRepository.list()
        
        # Convert to API response format
        reports = []
        for report_data in reports_data:
            report = MindMapReport(
                id=report_data['id'],
                title=report_data['title'],
                description=report_data.get('description'),
                seed_paper_id=report_data['seed_paper_id'],
                seed_paper_title=report_data['seed_paper_title'],
                parameters=report_data.get('parameters', {}),
                mindmap_data=report_data.get('mindmap_data', {}),
                statistics=report_data.get('statistics', {}),
                created_at=report_data['created_at']
            )
            reports.append(report)
        
        return MindMapReportListResponse(
            reports=reports,
            total_count=len(reports)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get mind-map reports: {str(e)}")

@router.post("/reports", response_model=MindMapReportSaveResponse)
async def save_mindmap_report(request: MindMapReportSaveRequest):
    """
    Save a mind-map as a report.
    
    This endpoint saves a generated mind-map with a title and optional description
    for later retrieval and analysis.
    """
    try:
        # Validate that the mindmap_data contains required fields
        if not request.mindmap_data.get("seed_paper_id"):
            raise HTTPException(status_code=400, detail="Mind-map data must contain seed_paper_id")
        
        # Get seed paper title for the report
        seed_paper_id = request.mindmap_data.get("seed_paper_id")
        seed_paper = PaperRepository.get_by_id(int(seed_paper_id))
        if not seed_paper:
            raise HTTPException(status_code=404, detail=f"Seed paper {seed_paper_id} not found")
        
        # Save the report
        report_id = MindmapReportRepository.insert(
            title=request.title,
            description=request.description,
            seed_paper_id=int(seed_paper_id),
            seed_paper_title=seed_paper["title"],
            mindmap_data=request.mindmap_data,
            parameters=request.parameters,
            statistics=request.mindmap_data.get("statistics", {})
        )
        
        return MindMapReportSaveResponse(
            id=report_id,
            title=request.title,
            message=f"Mind-map report '{request.title}' saved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save mind-map report: {str(e)}")

@router.get("/reports/{report_id}", response_model=MindMapReport)
async def get_mindmap_report(report_id: int):
    """
    Get a specific mind-map report by ID.
    
    Returns the complete mind-map report data including the visualization data.
    """
    try:
        report_data = MindmapReportRepository.get(report_id)
        if not report_data:
            raise HTTPException(status_code=404, detail=f"Mind-map report {report_id} not found")
        
        # Convert to API response format
        report = MindMapReport(
            id=report_data['id'],
            title=report_data['title'],
            description=report_data.get('description'),
            seed_paper_id=report_data['seed_paper_id'],
            seed_paper_title=report_data['seed_paper_title'],
            parameters=report_data.get('parameters', {}),
            mindmap_data=report_data.get('mindmap_data', {}),
            statistics=report_data.get('statistics', {}),
            created_at=report_data['created_at']
        )
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get mind-map report: {str(e)}")

@router.delete("/reports/{report_id}")
async def delete_mindmap_report(report_id: int):
    """
    Delete a mind-map report by ID.
    
    Permanently removes the saved mind-map report from the database.
    """
    try:
        # Check if report exists
        report = MindmapReportRepository.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Mind-map report {report_id} not found")
        
        # Delete the report
        MindmapReportRepository.delete(report_id)
        
        return {
            "status": "success",
            "message": f"Mind-map report {report_id} deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete mind-map report: {str(e)}")

@router.put("/reports/{report_id}/title")
async def update_mindmap_report_title(report_id: int, request: dict):
    """
    Update the title of a mind-map report.
    
    Allows updating the title of an existing mind-map report.
    """
    try:
        new_title = request.get("title", "").strip()
        if not new_title:
            raise HTTPException(status_code=400, detail="Title is required")
        
        if len(new_title) > 200:
            raise HTTPException(status_code=400, detail="Title must be 200 characters or less")
        
        # Check if report exists
        report = MindmapReportRepository.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Mind-map report {report_id} not found")
        
        # Update the title
        MindmapReportRepository.update_title(report_id, new_title)
        
        return {
            "status": "success",
            "message": f"Mind-map report title updated successfully",
            "title": new_title
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mind-map report title: {str(e)}")

# -----------------------------------------------------------------------------
# Update description endpoint
# -----------------------------------------------------------------------------

@router.put("/reports/{report_id}/description")
async def update_mindmap_report_description(report_id: int, request: dict):
    """
    Update the *description* of a mind-map report.
    """
    try:
        new_description = request.get("description", "")
        if new_description is None:
            new_description = ""

        # Validate report exists
        report = MindmapReportRepository.get(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"Mind-map report {report_id} not found")

        # Persist change
        MindmapReportRepository.update_description(report_id, new_description)

        return {
            "status": "success",
            "message": "Mind-map report description updated successfully",
            "description": new_description,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mind-map report description: {str(e)}")

# --- New endpoint: Update existing mind-map report (mindmap_data / parameters) --- #

class MindMapReportUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    mindmap_data: Dict[str, Any]
    parameters: Dict[str, Any]
    statistics: Optional[Dict[str, Any]] = None

@router.put("/reports/{report_id}")
async def update_mindmap_report(report_id: int, request: MindMapReportUpdateRequest = Body(...)):
    """Replace the stored mind-map data/parameters for an existing report."""
    try:
        updated = MindmapReportRepository.update_data(
            report_id=report_id,
            mindmap_data=request.mindmap_data,
            parameters=request.parameters,
            statistics=request.statistics,
            title=request.title,
            description=request.description,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"message": "Mind-map report updated", "id": report_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update mind-map report: {str(e)}") 
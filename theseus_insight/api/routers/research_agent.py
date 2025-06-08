from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List
import json
import uuid

from ..dependencies import db
from ..tasks import task_manager, TaskStatus
from ...utils.summary_generator import extract_key_themes
from ..models import (
    ResearchAgentRunRequest, ResearchAgentRunResponse,
    ResearchAgentModelConfigApi, LiteratureReviewResult,
    LiteratureReviewSummary, ResearchLibrarySearchRequest,
    ResearchLibraryResponse, ResearchLibraryItem
)

router = APIRouter(prefix="/api/research-agent", tags=["research-agent"])

@router.get("/model-config", response_model=ResearchAgentModelConfigApi)
async def get_research_agent_model_config():
    """Get research agent model configuration supporting both legacy and LangGraph formats."""
    try:
        # Try to get LangGraph configuration first
        langgraph_config = db.get_setting("research_agent_langgraph_config")
        if langgraph_config:
            try:
                config_data = json.loads(langgraph_config)
                return ResearchAgentModelConfigApi(**config_data)
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Fall back to unified router configuration
        try:
            from ...agentic_research.unified_model_router import load_unified_router
            router = load_unified_router(db)
            config_data = router.get_configuration()
            
            return ResearchAgentModelConfigApi(**config_data)
        except Exception:
            # Return default configuration
            return ResearchAgentModelConfigApi(
                reasoning_model={
                    "model_name": "gemini-2.0-flash",
                    "model_type": "gemini",
                    "max_new_tokens": 4096,
                    "temperature": 0.1,
                    "num_ctx": 131072
                },
                max_research_loops=10,
                initial_search_query_count=3,
                local_search_limit=10,
                external_search_limit=5,
                search_config={
                    "semantic_weight": 0.6,
                    "keyword_weight": 0.4,
                    "similarity_threshold": 0.3,
                    "enable_pdf_download": True
                }
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research agent model config: {str(e)}")

@router.put("/model-config")
async def update_research_agent_model_config(config: ResearchAgentModelConfigApi):
    """Update research agent model configuration using unified router."""
    try:
        from ...agentic_research.unified_model_router import load_unified_router
        
        # Load the unified router and save configuration
        router = load_unified_router(db)
        config_dict = config.dict(exclude_none=True)
        router.save_configuration(config_dict)
        
        return {"status": "success", "message": "Research agent model configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating research agent model config: {str(e)}")

@router.post("/run", response_model=ResearchAgentRunResponse)
async def run_research_agent(request: ResearchAgentRunRequest, background_tasks: BackgroundTasks):
    """Start a new enhanced research agent run with LangGraph workflow."""
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Prepare enhanced task configuration
        config = {
            "research_question": request.research_question,
            "num_papers_target": request.num_papers_target,
            "max_steps": request.max_steps,
            "enable_pdf_download": True,  # Enable by default
            "conversation_history": [msg.dict() for msg in request.conversation_history],  # Support multi-turn conversations
        }
        
        # Apply model config override if provided
        if request.model_config_override:
            from ...agentic_research.unified_model_router import load_unified_router
            
            # Save override configuration using unified router
            router = load_unified_router(db)
            override_dict = request.model_config_override.dict(exclude_none=True)
            router.save_configuration(override_dict)
        
        # Create task in database
        await task_manager.create_task(
            task_id=task_id,
            task_type="research_agent",
            config=config
        )
        
        # Send initial status update to ensure WebSocket subscription works
        await task_manager.update_task_status(
            task_id,
            TaskStatus.PENDING,
            f"Research task queued: {request.research_question}",
            progress=0,
            current_step="queued",
        )
        
        # Enqueue the task for background processing
        await task_manager.enqueue_task(
            task_manager.run_research_agent_task,
            task_id
        )
        
        return ResearchAgentRunResponse(
            task_id=task_id,
            message=f"Research agent task started for question: {request.research_question}"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting research agent: {str(e)}")

@router.get("/reviews/{review_id}", response_model=LiteratureReviewResult)
async def get_literature_review(review_id: int):
    """Get a specific literature review by ID."""
    try:
        review = db.get_literature_review(review_id)
        if not review:
            raise HTTPException(status_code=404, detail=f"Literature review {review_id} not found")
        
        # Parse summaries and trace from JSON
        summaries_data = json.loads(review["summary_json"])
        trace_data = json.loads(review["trace_json"])
        
        summaries = [
            LiteratureReviewSummary(
                paper_id=s["paper_id"],
                title=s["title"],
                summary=s["summary"],
                rationale=s["rationale"],
                relevance_score=s["relevance_score"]
            )
            for s in summaries_data
        ]
        
        # Parse activity log
        activity_data = []
        if review.get("activity_log"):
            try:
                activity_data = json.loads(review["activity_log"])
            except (json.JSONDecodeError, TypeError):
                activity_data = []

        return LiteratureReviewResult(
            id=review["id"],
            research_question=review["research_question"],
            summaries=summaries,
            created_ts=review["created_ts"],
            total_papers=len(summaries),
            trace_log=trace_data,
            report_text=review.get("report_text"),
            short_summary=review.get("short_summary"),
            activity_log=activity_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting literature review: {str(e)}")

@router.get("/reviews", response_model=List[LiteratureReviewResult])
async def get_recent_literature_reviews(limit: int = Query(10, gt=0, le=100)):
    """Get recent literature reviews."""
    try:
        reviews = db.get_recent_literature_reviews(limit)
        
        results = []
        for review in reviews:
            # Parse summaries from JSON
            summaries_data = json.loads(review["summary_json"])
            trace_data = json.loads(review["trace_json"])
            
            summaries = [
                LiteratureReviewSummary(
                    paper_id=s["paper_id"],
                    title=s["title"],
                    summary=s["summary"],
                    rationale=s["rationale"],
                    relevance_score=s["relevance_score"]
                )
                for s in summaries_data
            ]
            
            # Parse activity log for this review
            activity_data = []
            if review.get("activity_log"):
                try:
                    activity_data = json.loads(review["activity_log"])
                except (json.JSONDecodeError, TypeError):
                    activity_data = []

            results.append(LiteratureReviewResult(
                id=review["id"],
                research_question=review["research_question"],
                summaries=summaries,
                created_ts=review["created_ts"],
                total_papers=len(summaries),
                trace_log=trace_data,
                report_text=review.get("report_text"),
                short_summary=review.get("short_summary"),
                activity_log=activity_data
            ))
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting literature reviews: {str(e)}")

@router.post("/library/search", response_model=ResearchLibraryResponse)
async def search_research_library(request: ResearchLibrarySearchRequest):
    """Search the research library with filtering and pagination."""
    try:
        results = db.search_research_library(
            query=request.query,
            page=request.page,
            page_size=request.page_size,
            from_date=request.from_date,
            to_date=request.to_date
        )
        
        # Transform results to match the API model
        library_items = []
        for result in results['results']:
            # Parse activity log to count sources
            try:
                activity_log = json.loads(result['activity_log']) if result['activity_log'] else []
                sources_count = 0
                for activity in activity_log:
                    if activity.get('data', {}).get('sources_found'):
                        sources_count += activity['data']['sources_found']
                    elif activity.get('data', {}).get('total_sources'):
                        sources_count = max(sources_count, activity['data']['total_sources'])
            except (json.JSONDecodeError, TypeError):
                sources_count = 0
            
            # Extract themes from research question
            themes = extract_key_themes(result['research_question'])
            
            library_items.append(ResearchLibraryItem(
                id=result['id'],
                research_question=result['research_question'],
                short_summary=result['short_summary'] or result['research_question'][:50] + "...",
                created_ts=result['created_ts'],
                sources_count=sources_count,
                has_report=bool(result.get('report_text')),
                themes=themes
            ))
        
        return ResearchLibraryResponse(
            results=library_items,
            total_count=results['total_count'],
            total_pages=results['total_pages'],
            current_page=results['current_page'],
            page_size=results['page_size'],
            has_next=results['has_next'],
            has_previous=results['has_previous']
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching research library: {str(e)}")

@router.get("/library", response_model=ResearchLibraryResponse)
async def get_research_library(
    query: str = Query(None, description="Search query"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    from_date: str = Query(None, description="From date (YYYY-MM-DD)"),
    to_date: str = Query(None, description="To date (YYYY-MM-DD)")
):
    """Get research library entries with optional filtering."""
    request = ResearchLibrarySearchRequest(
        query=query,
        page=page,
        page_size=page_size,
        from_date=from_date,
        to_date=to_date
    )
    return await search_research_library(request)

@router.delete("/reviews/{review_id}")
async def delete_literature_review(review_id: int):
    """Delete a specific literature review by ID."""
    try:
        success = db.delete_literature_review(review_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Literature review {review_id} not found")
        
        return {"status": "success", "message": f"Literature review {review_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting literature review: {str(e)}") 
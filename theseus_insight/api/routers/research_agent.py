from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List
import json
import uuid
import sys
import os

from ..dependencies import db
from ..tasks import task_manager, TaskStatus
from ...utils.summary_generator import extract_key_themes
from ..models import (
    ResearchAgentRunRequest, ResearchAgentRunResponse,
    ResearchAgentModelConfigApi, LiteratureReviewResult,
    LiteratureReviewSummary, ResearchLibrarySearchRequest,
    ResearchLibraryResponse, ResearchLibraryItem
)

# Add the project root to the path to allow direct imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

router = APIRouter(prefix="/api/research-agent", tags=["research-agent"])

def _get_research_agent_config():
    """Get research agent configuration directly from database."""
    # Try to get LangGraph configuration first
    config_json = db.get_setting("research_agent_langgraph_config")
    if config_json:
        try:
            return json.loads(config_json)
        except (json.JSONDecodeError, ValueError):
            pass
    
    # Return default configuration
    return {
        "reasoning_model": {
            "model_name": "gemini-2.0-flash",
            "model_type": "gemini",
            "max_new_tokens": 4096,
            "temperature": 0.1,
            "num_ctx": 131072
        },
        "query_generator_model": None,  # Falls back to reasoning_model if not specified
        "reflection_model": None,       # Falls back to reasoning_model if not specified  
        "answer_model": None,           # Falls back to reasoning_model if not specified
        "judge_model": None,            # Falls back to reasoning_model if not specified
        "max_research_loops": 10,
        "initial_search_query_count": 3,
        "local_search_limit": 10,
        "external_search_limit": 5,
        "external_search_delay": 2.0,  # ArXiv rate limiting: minimum 2 seconds between requests
        "search_config": {
            "semantic_weight": 0.6,
            "keyword_weight": 0.4,
            "similarity_threshold": 0.3,
            "enable_pdf_download": True,
            "external_search_provider": "arxiv"
        }
    }

def _save_research_agent_config(config_dict):
    """Save research agent configuration directly to database."""
    config_json = json.dumps(config_dict, indent=2)
    db.set_setting("research_agent_langgraph_config", config_json)

@router.get("/model-config", response_model=ResearchAgentModelConfigApi)
async def get_research_agent_model_config():
    """Get research agent model configuration supporting both legacy and LangGraph formats."""
    try:
        config_data = _get_research_agent_config()
        return ResearchAgentModelConfigApi(**config_data)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research agent model config: {str(e)}")

@router.put("/model-config")
async def update_research_agent_model_config(config: ResearchAgentModelConfigApi):
    """Update research agent model configuration using direct database access."""
    try:
        # Save configuration directly to database
        config_dict = config.dict(exclude_none=True)
        _save_research_agent_config(config_dict)
        
        return {"status": "success", "message": "Research agent model configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating research agent model config: {str(e)}")

@router.post("/run", response_model=ResearchAgentRunResponse)
async def run_research_agent(request: ResearchAgentRunRequest, background_tasks: BackgroundTasks):
    """Start a new enhanced research agent run with LangGraph workflow."""
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Get current research agent configuration to read PDF download setting
        current_config = _get_research_agent_config()
        search_config = current_config.get("search_config", {})
        enable_pdf_download = search_config.get("enable_pdf_download", True)
        
        # Prepare enhanced task configuration with additive effort parameters
        config = {
            "research_question": request.research_question,
            "papers_bonus": request.papers_bonus,
            "loops_bonus": request.loops_bonus,
            "enable_pdf_download": enable_pdf_download,  # Use actual setting from config
            "conversation_history": [msg.dict() for msg in request.conversation_history],  # Support multi-turn conversations
        }
        
        # Apply model config override if provided
        if request.model_config_override:
            # Save override configuration directly to database
            override_dict = request.model_config_override.dict(exclude_none=True)
            _save_research_agent_config(override_dict)
            
            # Also update our config to reflect the override
            override_search_config = override_dict.get("search_config", {})
            if "enable_pdf_download" in override_search_config:
                config["enable_pdf_download"] = override_search_config["enable_pdf_download"]
        
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

@router.get("/debug/paper-access")
async def debug_paper_access():
    """Debug endpoint to check paper access capabilities and status."""
    try:
        # Try to import LocalSearchTool, but handle gracefully if langgraph is not available
        try:
            from ...agentic_research.local_search import LocalSearchTool
            from ...inference.llm import SentenceTransformerInference
            local_search_available = True
        except ImportError as import_error:
            local_search_available = False
            import_error_message = str(import_error)
        
        # Create a temporary LocalSearchTool to check capabilities
        if local_search_available:
            try:
                # Get the current research agent configuration to read actual PDF download setting
                current_config = _get_research_agent_config()
                search_config = current_config.get("search_config", {})
                pdf_download_setting = search_config.get("enable_pdf_download", True)
                
                embedding_model = SentenceTransformerInference(
                    model_name='Alibaba-NLP/gte-modernbert-base',
                    remote_code=True
                )
                search_tool = LocalSearchTool(
                    db=db,
                    embedding_model=embedding_model,
                    enable_pdf_download=pdf_download_setting  # Use actual setting
                )
                
                # Get search statistics
                stats = search_tool.get_search_stats()
                
                # Test a paper with full text access
                all_papers = db.fetch_all_papers()[:10]  # Get first 10 papers
                
                test_results = []
                for paper in all_papers:
                    paper_info = {
                        "id": paper.get("id"),
                        "title": paper.get("title", "Unknown")[:50] + "...",
                        "has_url": bool(paper.get("url")),
                        "has_full_text": bool(paper.get("text")),
                        "abstract_length": len(paper.get("abstract", "")),
                        "full_text_length": len(paper.get("text", "")) if paper.get("text") else 0
                    }
                    
                    # Test retrieve_full_text if we have a paper ID
                    if paper.get("id"):
                        try:
                            result = search_tool.retrieve_full_text(str(paper["id"]))
                            paper_info["retrieve_test"] = "SUCCESS" if "FULL TEXT RETRIEVED" in result else "ABSTRACT_ONLY"
                            paper_info["retrieve_result_length"] = len(result)
                        except Exception as e:
                            paper_info["retrieve_test"] = f"ERROR: {str(e)}"
                            paper_info["retrieve_result_length"] = 0
                    
                    test_results.append(paper_info)
                
                return {
                    "database_stats": stats,
                    "paper_samples": test_results,
                    "total_papers_tested": len(test_results),
                    "papers_with_full_text": len([p for p in test_results if p["has_full_text"]]),
                    "papers_with_urls": len([p for p in test_results if p["has_url"]]),
                    "retrieve_success_count": len([p for p in test_results if p.get("retrieve_test") == "SUCCESS"]),
                    "pdf_processing_available": stats.get("pdf_processor_available", False),
                    "pdf_download_enabled": stats.get("pdf_download_enabled", False),
                    "current_pdf_config": {
                        "config_setting": pdf_download_setting,
                        "search_tool_setting": search_tool.enable_pdf_download,
                        "configuration_source": "research_agent_langgraph_config" if current_config else "default"
                    }
                }
                
            except Exception as tool_error:
                return {
                    "error": f"Error creating search tool: {str(tool_error)}",
                    "database_papers_count": len(db.fetch_all_papers()) if hasattr(db, 'fetch_all_papers') else "Unknown",
                    "local_search_available": False
                }
        else:
            # LocalSearchTool not available, provide basic information
            all_papers = db.fetch_all_papers()[:10] if hasattr(db, 'fetch_all_papers') else []
            
            basic_stats = []
            for paper in all_papers:
                basic_stats.append({
                    "id": paper.get("id"),
                    "title": paper.get("title", "Unknown")[:50] + "...",
                    "has_url": bool(paper.get("url")),
                    "has_full_text": bool(paper.get("text")),
                    "abstract_length": len(paper.get("abstract", "")),
                    "full_text_length": len(paper.get("text", "")) if paper.get("text") else 0
                })
            
            return {
                "local_search_available": False,
                "import_error": import_error_message,
                "basic_paper_stats": basic_stats,
                "total_papers_in_db": len(db.fetch_all_papers()) if hasattr(db, 'fetch_all_papers') else "Unknown",
                "message": "LocalSearchTool not available due to missing dependencies (likely langgraph). Basic stats only."
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in debug endpoint: {str(e)}")

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
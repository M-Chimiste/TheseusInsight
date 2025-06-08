from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List
import json
import uuid

from ..dependencies import db
from ..tasks import task_manager, TaskStatus
from ..models import (
    ResearchAgentRunRequest, ResearchAgentRunResponse,
    ResearchAgentModelConfigApi, LiteratureReviewResult,
    LiteratureReviewSummary
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
        
        # Fall back to legacy configuration
        try:
            from ...agentic_research.model_router import load_research_agent_model_config
            legacy_config = load_research_agent_model_config(db)
            
            # Convert legacy to new format for the API response
            return ResearchAgentModelConfigApi(
                boss_model=legacy_config.boss_model,
                worker_models=legacy_config.worker_models,
                default_worker=legacy_config.default_worker,
                max_retries=legacy_config.max_retries,
                timeout_seconds=legacy_config.timeout_seconds,
                # Default LangGraph values
                reasoning_model=legacy_config.boss_model,  # Map boss to reasoning
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
    """Update research agent model configuration supporting both legacy and LangGraph formats."""
    try:
        # Store the new LangGraph configuration in the database
        config_json = config.json()
        db.set_setting("research_agent_langgraph_config", config_json)
        
        # For backward compatibility, also update legacy configuration if legacy fields are provided
        if config.boss_model or config.worker_models:
            try:
                from ...agentic_research.model_router import ResearchAgentModelConfig, save_research_agent_model_config
                
                # Convert API model to internal legacy config
                legacy_config = ResearchAgentModelConfig({
                    "boss_model": config.boss_model.dict() if config.boss_model else {},
                    "worker_models": {k: v.dict() for k, v in config.worker_models.items()} if config.worker_models else {},
                    "default_worker": config.default_worker or "summary",
                    "max_retries": config.max_retries or 3,
                    "timeout_seconds": config.timeout_seconds or 30
                })
                
                # Save legacy format
                save_research_agent_model_config(db, legacy_config)
            except Exception as legacy_error:
                print(f"Warning: Could not save legacy config format: {legacy_error}")
        
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
            # Import locally to avoid circular imports
            from ...agentic_research.model_router import ResearchAgentModelConfig, save_research_agent_model_config
            
            # Convert and save override config
            override_config = ResearchAgentModelConfig({
                "boss_model": request.model_config_override.boss_model.dict(),
                "worker_models": {k: v.dict() for k, v in request.model_config_override.worker_models.items()},
                "default_worker": request.model_config_override.default_worker,
                "max_retries": request.model_config_override.max_retries,
                "timeout_seconds": request.model_config_override.timeout_seconds
            })
            
            # Save override (temporarily)
            save_research_agent_model_config(db, override_config)
        
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
        
        return LiteratureReviewResult(
            id=review["id"],
            research_question=review["research_question"],
            summaries=summaries,
            created_ts=review["created_ts"],
            total_papers=len(summaries),
            trace_log=trace_data,
            report_text=review.get("report_text")
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
            
            results.append(LiteratureReviewResult(
                id=review["id"],
                research_question=review["research_question"],
                summaries=summaries,
                created_ts=review["created_ts"],
                total_papers=len(summaries),
                trace_log=trace_data,
                report_text=review.get("report_text")
            ))
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting literature reviews: {str(e)}") 
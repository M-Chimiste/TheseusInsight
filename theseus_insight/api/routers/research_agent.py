from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List
import json
import uuid

from ..dependencies import db
from ..tasks import task_manager
from ..models import (
    ResearchAgentRunRequest, ResearchAgentRunResponse,
    ResearchAgentModelConfigApi, LiteratureReviewResult,
    LiteratureReviewSummary
)

router = APIRouter(prefix="/api/research-agent", tags=["research-agent"])

@router.get("/model-config", response_model=ResearchAgentModelConfigApi)
async def get_research_agent_model_config():
    """Get research agent model configuration."""
    try:
        # Import locally to avoid circular imports
        from ...agentic_research.model_router import load_research_agent_model_config
        config = load_research_agent_model_config(db)
        
        return ResearchAgentModelConfigApi(
            boss_model=config.boss_model,
            worker_models=config.worker_models,
            default_worker=config.default_worker,
            max_retries=config.max_retries,
            timeout_seconds=config.timeout_seconds
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting research agent model config: {str(e)}")

@router.put("/model-config")
async def update_research_agent_model_config(config: ResearchAgentModelConfigApi):
    """Update research agent model configuration."""
    try:
        # Import locally to avoid circular imports
        from ...agentic_research.model_router import ResearchAgentModelConfig, save_research_agent_model_config
        
        # Convert API model to internal config
        internal_config = ResearchAgentModelConfig({
            "boss_model": config.boss_model.dict(),
            "worker_models": {k: v.dict() for k, v in config.worker_models.items()},
            "default_worker": config.default_worker,
            "max_retries": config.max_retries,
            "timeout_seconds": config.timeout_seconds
        })
        
        # Save to database
        save_research_agent_model_config(db, internal_config)
        
        return {"status": "success", "message": "Research agent model configuration updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating research agent model config: {str(e)}")

@router.post("/run", response_model=ResearchAgentRunResponse)
async def run_research_agent(request: ResearchAgentRunRequest, background_tasks: BackgroundTasks):
    """Start a new research agent run."""
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        
        # Prepare task configuration
        config = {
            "research_question": request.research_question,
            "num_papers_target": request.num_papers_target,
            "max_steps": request.max_steps,
            "enable_pdf_download": True,  # Enable by default
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
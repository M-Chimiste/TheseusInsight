"""
FastAPI Router for Research Agent

Provides REST API endpoints for research agent functionality including
task management, status tracking, result retrieval, and history management.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field

from ...research_agent.workflow import ResearchAgentWorkflow, create_research_workflow
from ...research_agent.tools import UnifiedSearchTool, LocalSearchTool, ExternalSearchTool, SearchConfig
from ...research_agent.model_router import get_embedding_model
from ..models import ResearchAgentModelConfigApi
from ..dependencies import db


# Pydantic models for API requests/responses
class ResearchTaskRequest(BaseModel):
    """Request model for starting a research task."""
    research_question: str = Field(..., description="The research question to investigate")
    config: Optional[Dict[str, Any]] = Field(None, description="Optional configuration overrides")
    save_to_library: bool = Field(True, description="Whether to save results to research library")
    
    class Config:
        schema_extra = {
            "example": {
                "research_question": "What are the latest developments in quantum computing for machine learning?",
                "config": {
                    "search_config": {
                        "local_limit": 20,
                        "external_limit": 15
                    },
                    "evidence_config": {
                        "min_evidence_threshold": 3,
                        "quality_threshold": 0.7
                    }
                },
                "save_to_library": True
            }
        }


class ResearchTaskResponse(BaseModel):
    """Response model for research task creation."""
    task_id: str = Field(..., description="Unique identifier for the research task")
    status: str = Field(..., description="Current status of the task")
    created_at: datetime = Field(..., description="Task creation timestamp")
    research_question: str = Field(..., description="The research question being investigated")


class ResearchTaskStatus(BaseModel):
    """Response model for research task status."""
    task_id: str
    status: str  # "pending", "running", "completed", "failed", "cancelled"
    progress: Optional[Dict[str, Any]] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ResearchTaskResult(BaseModel):
    """Response model for research task results."""
    task_id: str
    status: str
    research_question: str
    final_answer: Optional[str] = None
    generation_summary: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None
    sub_queries: List[str] = Field(default_factory=list)
    sources_gathered: List[Dict[str, Any]] = Field(default_factory=list)
    judged_sources: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    compressed_notes: str = ""
    workflow_messages: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ResearchHistoryItem(BaseModel):
    """Response model for research history items."""
    task_id: str
    research_question: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    statistics: Optional[Dict[str, Any]] = None


# Router setup
router = APIRouter(prefix="/api/research-agent", tags=["research-agent"])
logger = logging.getLogger(__name__)

# Global dictionaries for tracking research tasks and results
# These are used by the workflow and websockets for real-time progress updates
research_tasks: Dict[str, Dict[str, Any]] = {}
task_results: Dict[str, Dict[str, Any]] = {}


def _serialize_paper_info(obj):
    """
    Convert PaperInfo objects and other non-serializable objects to dictionaries.
    
    Args:
        obj: Object to serialize (could be PaperInfo, list, dict, etc.)
        
    Returns:
        JSON-serializable version of the object
    """
    from ...research_agent.tools.deduplication import PaperInfo
    
    if isinstance(obj, PaperInfo):
        return {
            'paper_id': obj.paper_id,
            'title': obj.title,
            'abstract': obj.abstract,
            'url': obj.url,
            'source': obj.source,
            'raw_data': _serialize_paper_info(obj.raw_data)  # Recursively serialize raw_data
        }
    elif isinstance(obj, list):
        return [_serialize_paper_info(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: _serialize_paper_info(value) for key, value in obj.items()}
    elif hasattr(obj, '__dict__'):
        # For other objects with __dict__, convert to dict
        return _serialize_paper_info(obj.__dict__)
    else:
        # For primitive types (str, int, float, bool, None), return as-is
        return obj


def _mark_orphaned_research_tasks_as_failed():
    """
    Mark all pending/running research tasks as failed on startup.
    This handles cases where the server crashed while tasks were running.
    """
    try:
        current_time = datetime.utcnow().isoformat()
        
        # Get all orphaned research tasks (pending or running)
        orphaned_runs = db.get_research_runs_by_status(['pending', 'running'])
        
        if orphaned_runs:
            logger.info(f"Found {len(orphaned_runs)} orphaned research tasks, marking as failed")
            
            for run in orphaned_runs:
                task_id = run['task_id']
                
                # Update research run status
                db.update_research_run_status(
                    task_id=task_id,
                    status="failed",
                    completed_at=current_time,
                    error_message="Task was interrupted by server restart"
                )
                
                # Update general task status as well
                db.update_task_status(
                    task_id=task_id,
                    status="failed",
                    progress=0.0,
                    current_step="interrupted",
                    message="Task failed due to server restart",
                    error="Task was interrupted by server restart",
                    end_time=current_time
                )
                
                logger.info(f"Marked orphaned research task {task_id} as failed")
    except Exception as e:
        logger.error(f"Error marking orphaned research tasks as failed: {e}")


# Mark orphaned tasks as failed on startup
_mark_orphaned_research_tasks_as_failed()


async def get_research_workflow() -> ResearchAgentWorkflow:
    """
    Dependency to create and configure a research workflow.
    
    Returns:
        Configured ResearchAgentWorkflow instance
    """
    try:
        # Get embedding model configuration from database
        orchestration_config_json = db.get_setting("orchestration")
        if orchestration_config_json:
            import json
            orchestration_config = json.loads(orchestration_config_json)
        else:
            # Default configuration with embedding model
            orchestration_config = {
                'embedding_model': {
                    'model_type': 'sentence-transformer',
                    'model_name': 'Alibaba-NLP/gte-modernbert-base',
                    'trust_remote_code': True
                }
            }
        
        # Create embedding model using the model router
        embedding_model = get_embedding_model(orchestration_config)
        
        # Create search tools
        local_search_tool = LocalSearchTool(db, embedding_model)
        external_search_tool = ExternalSearchTool()
        
        # Create unified search tool without search_config parameter
        unified_search_tool = UnifiedSearchTool(
            local_search_tool=local_search_tool,
            external_search_tool=external_search_tool
        )
        
        # Use research agent model configuration from orchestration config
        research_agent_config = orchestration_config.get("research_agent_model_config", {})
        
        if research_agent_config and research_agent_config.get("boss_model"):
            # Use the research agent model configuration - ONLY use configured models
            boss_model = research_agent_config.get("boss_model", {})
            
            # Node-specific models default to boss_model if not specified
            query_planner_model = research_agent_config.get("query_planner_model") or boss_model
            evidence_selector_model = research_agent_config.get("evidence_selector_model") or boss_model  
            compression_model = research_agent_config.get("compression_model") or boss_model
            answer_generator_model = research_agent_config.get("answer_generator_model") or boss_model
            
            config = {
                "research_agent_model_config": research_agent_config,
                "query_planner_model": query_planner_model,
                "evidence_selector_model": evidence_selector_model, 
                "compression_model": compression_model,
                "answer_generator_model": answer_generator_model,
                "default_model": boss_model,  # Fallback for any other nodes
                
                # Also add individual node configs for the model router
                "query_planner": query_planner_model,
                "evidence_selector": evidence_selector_model,
                "scratchpad_compress": compression_model,
                "answer_generator": answer_generator_model
            }
            logger.info(f"Using research agent configuration with boss model: {boss_model.get('model_name', 'unknown')} ({boss_model.get('model_type', 'unknown')})")
        else:
            # NO HARDCODED FALLBACK - Require proper configuration
            logger.error("No research agent configuration found in database settings. Please configure models in Settings.tsx")
            raise HTTPException(
                status_code=500, 
                detail="Research agent not configured. Please configure research agent models in Settings → Research Agent Configuration"
            )
        
        # Create workflow with configuration
        workflow = create_research_workflow(
            config=config,
            unified_search_tool=unified_search_tool,
            max_research_loops=research_agent_config.get("max_research_loops", 3),
            max_research_context_tokens=research_agent_config.get("max_research_context_tokens", 15000),
            compress_to_ratio=research_agent_config.get("compress_to_ratio", 0.2)
        )
        
        return workflow
        
    except Exception as e:
        logger.error(f"Error creating research workflow: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to initialize research workflow: {str(e)}")


@router.post("/run", response_model=ResearchTaskResponse)
async def start_research_task(
    request: ResearchTaskRequest,
    background_tasks: BackgroundTasks,
    workflow: ResearchAgentWorkflow = Depends(get_research_workflow)
) -> ResearchTaskResponse:
    """
    Start a new research task.
    
    Args:
        request: Research task request with question and configuration
        background_tasks: FastAPI background tasks for async execution
        workflow: Research agent workflow instance
        
    Returns:
        Research task response with task ID and status
    """
    try:
        # Generate unique task ID
        task_id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        
        # Initialize task in global dictionaries for WebSocket tracking
        research_tasks[task_id] = {
            "task_id": task_id,
            "research_question": request.research_question,
            "status": "pending",
            "created_at": created_at,
            "progress": {"status": "Task created and queued for execution"}
        }
        
        # Create task in general tasks table for job history
        db.insert_task(
            task_id=task_id,
            task_type="research-agent",
            status="pending",
            config=request.config or {},
            start_time=created_at.isoformat(),
            progress=0.0,
            current_step="Initializing research workflow",
            message="Research task created and queued for execution"
        )
        
        # Create specific research run entry for Research Library
        db.insert_research_run(
            task_id=task_id,
            research_question=request.research_question,
            status="pending",
            config=request.config or {},
            save_to_library=request.save_to_library
        )
        
        # Start the research task in the background
        background_tasks.add_task(
            _run_research_task,
            task_id,
            request.research_question,
            request.config,
            request.save_to_library,
            workflow
        )
        
        logger.info(f"Started research task {task_id} for question: {request.research_question[:100]}")
        
        return ResearchTaskResponse(
            task_id=task_id,
            status="pending",
            created_at=created_at,
            research_question=request.research_question
        )
        
    except Exception as e:
        logger.error(f"Error starting research task: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start research task: {str(e)}")


@router.get("/status/{task_id}", response_model=ResearchTaskStatus)
async def get_research_task_status(task_id: str) -> ResearchTaskStatus:
    """
    Get the status of a research task.
    
    Args:
        task_id: Unique identifier for the research task
        
    Returns:
        Current status of the research task
    """
    # Try to get from research runs first (more detailed)
    research_run = db.get_research_run(task_id)
    if research_run:
        return ResearchTaskStatus(
            task_id=task_id,
            status=research_run["status"],
            progress=research_run.get("progress"),
            created_at=datetime.fromisoformat(research_run["created_at"]),
            started_at=datetime.fromisoformat(research_run["started_at"]) if research_run.get("started_at") else None,
            completed_at=datetime.fromisoformat(research_run["completed_at"]) if research_run.get("completed_at") else None,
            error_message=research_run.get("error_message")
        )
    
    # Fallback to general task table
    task = db.get_task(task_id)
    if task:
        return ResearchTaskStatus(
            task_id=task_id,
            status=task["status"],
            progress={"progress": task.get("progress", 0)},
            created_at=datetime.fromisoformat(task["start_time"]),
            started_at=datetime.fromisoformat(task["start_time"]) if task["status"] != "pending" else None,
            completed_at=datetime.fromisoformat(task["end_time"]) if task.get("end_time") else None,
            error_message=task.get("error")
        )
    
    raise HTTPException(status_code=404, detail="Research task not found")


@router.get("/result/{task_id}", response_model=ResearchTaskResult)
async def get_research_task_result(task_id: str) -> ResearchTaskResult:
    """
    Get the result of a completed research task.
    
    Args:
        task_id: Unique identifier for the research task
        
    Returns:
        Complete research task results
    """
    research_run = db.get_research_run(task_id)
    if not research_run:
        raise HTTPException(status_code=404, detail="Research task not found")
    
    if research_run["status"] not in ["completed", "failed"]:
        raise HTTPException(status_code=400, detail="Research task is not yet completed")
    
    return ResearchTaskResult(
        task_id=task_id,
        status=research_run["status"],
        research_question=research_run["research_question"],
        final_answer=research_run.get("final_answer"),
        generation_summary=research_run.get("generation_summary"),
        statistics=research_run.get("statistics"),
        sub_queries=research_run.get("sub_queries", []),
        sources_gathered=research_run.get("sources_gathered", []),
        judged_sources=research_run.get("judged_sources", []),
        evidence=research_run.get("evidence", []),
        compressed_notes=research_run.get("compressed_notes", ""),
        workflow_messages=research_run.get("workflow_messages", []),
        created_at=datetime.fromisoformat(research_run["created_at"]),
        completed_at=datetime.fromisoformat(research_run["completed_at"]) if research_run.get("completed_at") else None,
        error_message=research_run.get("error_message")
    )


@router.get("/history", response_model=List[ResearchHistoryItem])
async def get_research_history(
    limit: int = 50,
    offset: int = 0,
    status_filter: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get research task history from the database.
    
    Args:
        limit: Maximum number of items to return
        offset: Number of items to skip
        status_filter: Optional status filter ("completed", "failed", etc.)
        
    Returns:
        Paginated list of research history items
    """
    try:
        # Get research runs from database
        research_runs = db.get_research_runs_history(
            limit=limit,
            offset=offset,
            status_filter=status_filter
        )
        
        # Get total count for pagination
        with db.get_cursor() as cursor:
            query = "SELECT COUNT(*) FROM research_runs"
            params = []
            
            if status_filter:
                query += " WHERE status = ?"
                params.append(status_filter)
            
            cursor.execute(query, params)
            total = cursor.fetchone()[0]
        
        # Convert to response model
        history_items = []
        for run in research_runs:
            history_items.append(ResearchHistoryItem(
                task_id=run["task_id"],
                research_question=run["research_question"],
                status=run["status"],
                created_at=datetime.fromisoformat(run["created_at"]),
                completed_at=datetime.fromisoformat(run["completed_at"]) if run.get("completed_at") else None,
                statistics=run.get("statistics")
            ))
        
        return {
            "items": history_items,
            "total": total,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Error getting research history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get research history: {str(e)}")


@router.delete("/{task_id}")
async def cancel_research_task(task_id: str) -> Dict[str, str]:
    """
    Cancel a running research task.
    
    Args:
        task_id: Unique identifier for the research task
        
    Returns:
        Cancellation confirmation
    """
    research_run = db.get_research_run(task_id)
    if not research_run:
        raise HTTPException(status_code=404, detail="Research task not found")
    
    if research_run["status"] in ["completed", "failed", "cancelled"]:
        raise HTTPException(status_code=400, detail="Research task cannot be cancelled")
    
    # Update global dictionaries
    if task_id in research_tasks:
        research_tasks[task_id]["status"] = "cancelled"
        research_tasks[task_id]["completed_at"] = datetime.utcnow()
    
    # Update both tables
    completed_at = datetime.utcnow().isoformat()
    
    db.update_research_run_status(
        task_id=task_id,
        status="cancelled",
        completed_at=completed_at
    )
    
    db.update_task_status(
        task_id=task_id,
        status="cancelled",
        end_time=completed_at,
        message="Task cancelled by user request"
    )
    
    logger.info(f"Cancelled research task {task_id}")
    
    return {"message": f"Research task {task_id} has been cancelled"}


@router.get("/workflow/info")
async def get_workflow_info(
    workflow: ResearchAgentWorkflow = Depends(get_research_workflow)
) -> Dict[str, Any]:
    """
    Get information about the research workflow configuration.
    
    Args:
        workflow: Research agent workflow instance
        
    Returns:
        Workflow configuration information
    """
    try:
        return workflow.get_workflow_info()
    except Exception as e:
        logger.error(f"Error getting workflow info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow info: {str(e)}")


async def _run_research_task(
    task_id: str,
    research_question: str,
    config: Optional[Dict[str, Any]],
    save_to_library: bool,
    workflow: ResearchAgentWorkflow
) -> None:
    """
    Background task to run the research workflow.
    
    Args:
        task_id: Unique identifier for the research task
        research_question: The research question to investigate
        config: Optional configuration overrides
        save_to_library: Whether to save results to research library
        workflow: Research agent workflow instance
    """
    try:
        # Initialize task in global dictionaries for WebSocket tracking
        started_at = datetime.utcnow()
        research_tasks[task_id] = {
            "task_id": task_id,
            "research_question": research_question,
            "status": "running",
            "created_at": started_at,
            "started_at": started_at,
            "progress": {"current_node": "initializing", "status": "Starting research workflow"}
        }
        
        # Update task status to running in both tables
        started_at_iso = started_at.isoformat()
        
        db.update_task_status(
            task_id=task_id,
            status="running",
            progress=0.1,
            current_step="Starting research workflow",
            message="Research workflow initialized"
        )
        
        db.update_research_run_status(
            task_id=task_id,
            status="running",
            started_at=started_at_iso
        )
        
        logger.info(f"Starting research workflow for task {task_id}")
        
        # Run the research workflow with task_id for progress tracking
        results = await workflow.run_research(research_question, config, task_id)
        
        # Update task completion status
        completed_at = datetime.utcnow().isoformat()
        
        if results.get("success", False):
            # Update global dictionaries
            if task_id in research_tasks:
                research_tasks[task_id]["status"] = "completed"
                research_tasks[task_id]["completed_at"] = datetime.utcnow()
            
            task_results[task_id] = results
            
            # Update general task status (serialize PaperInfo objects in results)
            db.update_task_status(
                task_id=task_id,
                status="completed",
                progress=1.0,
                current_step="Research completed",
                message="Research workflow completed successfully",
                result=_serialize_paper_info(results),
                end_time=completed_at
            )
            
            # Update research run with detailed results
            db.update_research_run_status(
                task_id=task_id,
                status="completed",
                completed_at=completed_at
            )
            
            # Save detailed results to research library (serialize PaperInfo objects)
            db.update_research_run_results(
                task_id=task_id,
                final_answer=results.get("final_answer"),
                generation_summary=results.get("generation_summary"),
                statistics=results.get("statistics"),
                sub_queries=results.get("sub_queries", []),
                sources_gathered=_serialize_paper_info(results.get("sources_gathered", [])),
                judged_sources=_serialize_paper_info(results.get("judged_sources", [])),
                evidence=results.get("evidence", []),
                compressed_notes=results.get("compressed_notes", ""),
                workflow_messages=_serialize_paper_info(results.get("workflow_messages", [])),
                research_loop_count=results.get("statistics", {}).get("research_loops", 0),
                is_sufficient=results.get("statistics", {}).get("evidence_sufficient", False)
            )
            
            logger.info(f"Research task {task_id} completed successfully and saved to research library")
        else:
            error_message = results.get("error", "Unknown error")
            
            # Update global dictionaries
            if task_id in research_tasks:
                research_tasks[task_id]["status"] = "failed"
                research_tasks[task_id]["completed_at"] = datetime.utcnow()
                research_tasks[task_id]["error_message"] = error_message
            
            # Update general task status
            db.update_task_status(
                task_id=task_id,
                status="failed",
                progress=0.0,
                current_step="Research failed",
                message="Research workflow encountered an error",
                error=error_message,
                end_time=completed_at
            )
            
            # Update research run status
            db.update_research_run_status(
                task_id=task_id,
                status="failed",
                completed_at=completed_at,
                error_message=error_message
            )
            
            logger.error(f"Research task {task_id} failed: {error_message}")
        
    except Exception as e:
        logger.error(f"Error in research task {task_id}: {e}")
        
        # Update global dictionaries
        if task_id in research_tasks:
            research_tasks[task_id]["status"] = "failed"
            research_tasks[task_id]["completed_at"] = datetime.utcnow()
            research_tasks[task_id]["error_message"] = str(e)
        
        # Update task status to failed in both tables
        completed_at = datetime.utcnow().isoformat()
        error_message = str(e)
        
        db.update_task_status(
            task_id=task_id,
            status="failed",
            progress=0.0,
            current_step="Error occurred",
            message="Research workflow encountered an unexpected error",
            error=error_message,
            end_time=completed_at
        )
        
        db.update_research_run_status(
            task_id=task_id,
            status="failed",
            completed_at=completed_at,
            error_message=error_message
        )


# Health check endpoint
@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Health check endpoint for the research agent service."""
    return {
        "status": "healthy",
        "service": "research_agent",
        "timestamp": datetime.utcnow().isoformat()
    } 
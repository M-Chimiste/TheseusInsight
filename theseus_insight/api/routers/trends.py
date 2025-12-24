"""
API router for Topic Evolution & Trend-Forecast Dashboard.

Provides endpoints for:
- Listing trending topics
- Getting topic details and timeline
- Searching topics
- Recomputing trends
- Getting papers for a topic
"""
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Body
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime, date
import asyncio
import json
import logging
import re

from ..models import (
    TopicApiResponse, TopicDetailResponse, TopicMetricResponse,
    TrendsListRequest, TrendsListResponse, TrendsSearchRequest, TrendsSearchResponse,
    TrendsRecomputeRequest, TrendsRecomputeResponse,
    TopicPapersRequest, TopicPapersResponse, PaperApiResponse,
    TrendsValidateAccuracyRequest, SystemInfoResponse, PerformanceConfig,
    ResearchInterestApiResponse, ResearchInterestsListResponse, ResearchInterestsSearchResponse,
    ResearchInterestDetailResponse, ResearchInterestMetricResponse, ResearchInterestRecomputeResponse,
    ResearchInterestPapersResponse,
    TimelineDataResponse, TopicTimelineData, TimelinePeriodData, TimelineKeyPaper
)
from ...data_access import (
    TopicsRepository, TopicMetricsRepository, PaperTopicsRepository, 
    TrendsRepository, PaperRepository, SettingsRepository,
    ResearchInterestTrendsRepository, ResearchInterestsRepository, ResearchInterestMetricsRepository,
    PaperResearchInterestsRepository, LabelSummariesRepository, ProfileRepository
)
from ...data_processing.trends import TrendsProcessor
from ..tasks import task_manager, TaskStatus
from ...prompt.system_prompts import TRENDS_LEGEND_LABEL_SYSTEM_PROMPT
from LLMFactory import LLMModelFactory

router = APIRouter(prefix="/api/trends", tags=["trends"])

logger = logging.getLogger(__name__)


def _convert_timestamps(data: dict) -> dict:
    """Convert PostgreSQL datetime objects to ISO strings for API response."""
    converted = data.copy()
    
    # Convert timestamp fields
    for field in ['created_at', 'updated_at', 'period_start', 'period_end']:
        if field in converted and converted[field] is not None:
            if isinstance(converted[field], (datetime, date)):
                converted[field] = converted[field].isoformat()
    
    return converted


def _format_topic_response(topic_data: dict) -> TopicApiResponse:
    """Convert database topic data to API response format."""
    converted = _convert_timestamps(topic_data)
    
    # Provide fallbacks if certain fields are missing (e.g., when joined
    # from topic_metrics without full topic columns).
    updated_at_val = converted.get('updated_at') or converted.get('created_at')
    
    # Use topic_id as the id for API response (not the metrics table id)
    api_id = converted.get('topic_id') or converted.get('id')
    
    return TopicApiResponse(
        id=api_id,
        label=converted['label'],
        keywords=converted['keywords'],
        embedding_model=converted.get('embedding_model'),
        created_at=converted['created_at'],
        updated_at=updated_at_val,
        latest_doc_count=converted.get('latest_doc_count') or converted.get('doc_count'),
        latest_growth_rate=converted.get('latest_growth_rate') or converted.get('growth_rate'),
        total_papers=converted.get('total_papers', 0),
        forecast_1m=converted.get('forecast_1m'),
        forecast_3m=converted.get('forecast_3m'),
        forecast_6m=converted.get('forecast_6m')
    )


def _format_metric_response(metric_data: dict) -> TopicMetricResponse:
    """Convert database metric data to API response format."""
    converted = _convert_timestamps(metric_data)
    
    return TopicMetricResponse(
        id=converted['id'],
        topic_id=converted['topic_id'],
        period_start=converted['period_start'],
        period_end=converted['period_end'],
        period_type=converted['period_type'],
        doc_count=converted['doc_count'],
        avg_score=converted.get('avg_score'),
        growth_rate=converted.get('growth_rate'),
        forecast_1m=converted.get('forecast_1m'),
        forecast_3m=converted.get('forecast_3m'),
        forecast_6m=converted.get('forecast_6m'),
        created_at=converted['created_at']
    )


def _format_paper_response(paper_data: dict) -> PaperApiResponse:
    """Convert database paper data to API response format."""
    from ..routers.papers import _convert_paper_timestamps
    converted = _convert_paper_timestamps(paper_data)
    
    return PaperApiResponse(
        id=converted['id'],
        title=converted['title'],
        abstract=converted['abstract'],
        score=converted['score'],
        date=converted['date'],
        url=converted['url'],
        date_run=converted['date_run'],
        rationale=converted['rationale'],
        related=converted['related'],
        cosine_similarity=converted['cosine_similarity'],
        embedding_model=converted['embedding_model'],
        keywords=converted.get('keywords'),
        similarity_score=converted.get('relevance_score')  # Map relevance_score to similarity_score
    )


@router.get("", response_model=TrendsListResponse)
async def get_trending_topics(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of topics to return"),
    period_type: str = Query("month", description="Display granularity: week, month, quarter"),
    duration_months: int = Query(6, ge=1, le=24, description="Duration to analyze: 1, 3, 6, 12, 24 months"),
    min_doc_count: int = Query(5, ge=1, description="Minimum document count filter"),
    sort_by: str = Query("growth_rate", description="Sort by: growth_rate, doc_count, forecast_3m"),
    profile_id: Optional[int] = Query(None, description="Filter by specific profile ID"),
    profile_ids: Optional[str] = Query(None, description="Filter by multiple profile IDs (comma-separated)"),
    profile_tag: Optional[str] = Query(None, description="Filter by profiles with specific tag"),
    profile_tags: Optional[str] = Query(None, description="Filter by profiles with any of these tags (comma-separated)")
):
    """
    Get a list of trending topics with their latest metrics for a specific duration.
    
    The system analyzes topics using weekly data as the foundation, then aggregates 
    to the requested period_type for the specified duration_months.
    """
    try:
        # Validate period_type
        if period_type not in ["week", "month", "quarter"]:
            raise HTTPException(status_code=400, detail="Invalid period_type. Must be 'week', 'month', or 'quarter'")
        
        # Validate duration
        if duration_months not in [1, 3, 6, 12, 24]:
            raise HTTPException(status_code=400, detail="Invalid duration_months. Must be 1, 3, 6, 12, or 24")
        
        # Handle profile filtering
        resolved_profile_ids = None
        
        # Parse profile_ids from comma-separated string
        if profile_ids:
            try:
                resolved_profile_ids = [int(pid.strip()) for pid in profile_ids.split(',')]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid profile_ids format. Must be comma-separated integers.")
        
        # Handle tag-based profile filtering
        if profile_tag or profile_tags:
            tag_list = []
            if profile_tag:
                tag_list.append(profile_tag)
            if profile_tags:
                tag_list.extend([tag.strip() for tag in profile_tags.split(',')])
            
            # Get profiles with these tags
            profiles_with_tags = ProfileRepository.get_by_tags(tag_list)
            tag_based_profile_ids = [p['id'] for p in profiles_with_tags]
            
            # Combine with explicit profile IDs if provided
            if resolved_profile_ids:
                resolved_profile_ids = list(set(resolved_profile_ids) & set(tag_based_profile_ids))
            else:
                resolved_profile_ids = tag_based_profile_ids
        
        # Get dashboard data using the requested period type (which may be aggregated from weekly data)
        dashboard_data = TrendsRepository.get_dashboard_data(
            limit=limit, 
            period_type=period_type,
            duration_months=duration_months,
            profile_id=profile_id,
            profile_ids=resolved_profile_ids
        )
        
        # Format topics for response
        topics = []
        for topic_data in dashboard_data['trending_topics']:
            if topic_data.get('doc_count', 0) >= min_doc_count:
                topics.append(_format_topic_response(topic_data))
        
        # Apply sorting
        if sort_by == "doc_count":
            topics.sort(key=lambda x: x.latest_doc_count or 0, reverse=True)
        elif sort_by == "forecast_3m":
            topics.sort(key=lambda x: x.forecast_3m or 0, reverse=True)
        else:  # default to growth_rate
            topics.sort(key=lambda x: x.latest_growth_rate or 0, reverse=True)
        
        return TrendsListResponse(
            topics=topics,
            total_topics=dashboard_data['total_topics'],
            total_papers_with_topics=dashboard_data['total_papers_with_topics'],
            period_type=period_type,
            duration_months=duration_months
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get trending topics: {str(e)}")


@router.get("/search", response_model=TrendsSearchResponse)
async def search_topics(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Search topics by label or keywords.
    """
    try:
        # Search topics
        search_results = TrendsRepository.search_topics(query, limit)
        
        # Format results
        topics = [_format_topic_response(topic) for topic in search_results]
        
        return TrendsSearchResponse(
            query=query,
            topics=topics,
            total_results=len(topics)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search topics: {str(e)}")





@router.get("/timeline-data", response_model=TimelineDataResponse)
async def get_timeline_data(
    topic_ids: Optional[str] = Query(None, description="Comma-separated topic IDs (None = top topics)"),
    period_type: str = Query("month", description="Period granularity: week, month, quarter, year"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    include_key_papers: bool = Query(True, description="Include key papers per period"),
    key_papers_limit: int = Query(3, ge=1, le=10, description="Max key papers per period"),
    limit: int = Query(10, ge=1, le=50, description="Max topics to return if topic_ids not specified")
):
    """
    Get timeline data for research timeline visualization.

    Returns timeline metrics with growth phases and optional key papers per period,
    optimized for horizontal timeline visualization with semantic zoom levels.
    """
    try:
        # Validate period_type
        valid_period_types = ["week", "month", "quarter", "year"]
        if period_type not in valid_period_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid period_type. Must be one of: {', '.join(valid_period_types)}"
            )

        # Parse topic_ids if provided
        parsed_topic_ids: Optional[List[int]] = None
        if topic_ids:
            try:
                parsed_topic_ids = [int(tid.strip()) for tid in topic_ids.split(",") if tid.strip()]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid topic_ids format. Use comma-separated integers.")

        # If no topic_ids specified, get top trending topics
        if not parsed_topic_ids:
            trending = TopicMetricsRepository.get_trending_topics(
                period_type=period_type if period_type != "year" else "quarter",
                limit=limit,
                min_doc_count=1
            )
            parsed_topic_ids = [t["topic_id"] for t in trending]

        # Parse dates
        parsed_start_date: Optional[date] = None
        parsed_end_date: Optional[date] = None

        if start_date:
            try:
                parsed_start_date = date.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid start_date format. Use YYYY-MM-DD.")

        if end_date:
            try:
                parsed_end_date = date.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid end_date format. Use YYYY-MM-DD.")

        # Get timeline data with papers
        # Note: "year" period_type uses quarterly data aggregated in frontend
        effective_period_type = period_type if period_type != "year" else "quarter"

        timeline_data = TopicMetricsRepository.get_timeline_with_papers(
            topic_ids=parsed_topic_ids,
            period_type=effective_period_type,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            key_papers_limit=key_papers_limit,
            include_key_papers=include_key_papers
        )

        if not timeline_data:
            return TimelineDataResponse(
                topics=[],
                date_range={"start": start_date or "", "end": end_date or ""},
                period_type=period_type,
                available_zoom_levels=["year", "quarter", "month", "week"],
                total_topics=0
            )

        # Build response
        topic_timelines: List[TopicTimelineData] = []
        all_dates: List[str] = []

        for topic_id, topic_data in timeline_data.items():
            periods: List[TimelinePeriodData] = []

            for period in topic_data["periods"]:
                all_dates.append(period["period_start"])
                all_dates.append(period["period_end"])

                key_papers: Optional[List[TimelineKeyPaper]] = None
                if period.get("key_papers"):
                    key_papers = [
                        TimelineKeyPaper(
                            id=p["id"],
                            title=p["title"],
                            date=p["date"],
                            score=p.get("score"),
                            relevance_score=p.get("relevance_score")
                        )
                        for p in period["key_papers"]
                    ]

                periods.append(TimelinePeriodData(
                    period_start=period["period_start"],
                    period_end=period["period_end"],
                    period_type=period["period_type"],
                    doc_count=period["doc_count"],
                    growth_rate=period.get("growth_rate"),
                    phase=period["phase"],
                    key_papers=key_papers,
                    forecast_1m=period.get("forecast_1m"),
                    forecast_3m=period.get("forecast_3m"),
                    forecast_6m=period.get("forecast_6m"),
                    is_forecast=period.get("is_forecast", False)
                ))

            topic_timelines.append(TopicTimelineData(
                topic_id=topic_id,
                topic_label=topic_data["label"],
                keywords=topic_data["keywords"],
                total_papers=topic_data["total_papers"],
                periods=periods
            ))

        # Calculate actual date range from data
        actual_date_range = {
            "start": min(all_dates) if all_dates else "",
            "end": max(all_dates) if all_dates else ""
        }

        return TimelineDataResponse(
            topics=topic_timelines,
            date_range=actual_date_range,
            period_type=period_type,
            available_zoom_levels=["year", "quarter", "month", "week"],
            total_topics=len(topic_timelines)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get timeline data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get timeline data: {str(e)}")


# Topic detail route moved after research interests to fix routing conflict


@router.post("/recompute", response_model=TrendsRecomputeResponse)
async def recompute_trends(
    request: TrendsRecomputeRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger recomputation of trends using incremental weekly-first analysis.
    
    By default, this uses incremental processing to only analyze new papers and
    recent time periods, preserving historical data. Set force_full_recalc=true
    to force complete recalculation of all data. This is a potentially expensive 
    operation that runs in the background.
    """
    try:
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        await task_manager.create_task(
            task_id=task_id,
            task_type="trends_recompute",
            config=request.dict()
        )
        
        # Enqueue background task
        await task_manager.enqueue_task(
            run_trends_task,
            task_id
        )
        
        # Estimate duration based on parameters (incremental is much faster)
        if request.force_full_recalc:
            estimated_minutes = max(8, request.lookback_months // 3)
            processing_type = "full recalculation"
        else:
            estimated_minutes = max(2, request.lookback_months // 12)  # Much faster for incremental
            processing_type = "incremental processing"
        
        # Nuclear option gets special handling
        if request.clear_all_data:
            estimated_minutes = max(10, request.lookback_months // 2)  # Takes longer due to complete rebuild
            processing_type = "nuclear recalculation (clearing all data)"
        
        return TrendsRecomputeResponse(
            task_id=task_id,
            message=f"Trends recomputation started ({processing_type}, {request.duration_months}M duration)",
            estimated_duration_minutes=estimated_minutes
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start trends recomputation: {str(e)}")


@router.post("/validate-accuracy", response_model=Dict[str, Any])
async def validate_forecast_accuracy(
    request: TrendsValidateAccuracyRequest = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict[str, Any]:
    """Validate forecast accuracy for a specific period type."""
    try:
        # Create a new processor instance with default settings
        processor = TrendsProcessor(verbose=True)
        
        # Run validation in background task
        task_id = str(uuid.uuid4())
        background_tasks.add_task(
            run_forecast_validation_task,
            task_id,
            request.period_type,
            processor
        )
        
        return {
            "status": "started",
            "message": f"Forecast accuracy validation started for {request.period_type} periods",
            "task_id": task_id,
            "estimated_time_minutes": 5
        }
    except Exception as e:
        logger.error(f"Error starting forecast validation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system-info", response_model=SystemInfoResponse)
async def get_system_info() -> SystemInfoResponse:
    """Get system hardware information and recommended performance configuration."""
    import psutil
    import multiprocessing
    import platform
    
    try:
        # Get CPU information
        cpu_count_physical = psutil.cpu_count(logical=False) or multiprocessing.cpu_count()
        cpu_count_logical = psutil.cpu_count(logical=True) or multiprocessing.cpu_count()
        
        # Get memory information
        memory = psutil.virtual_memory()
        memory_total_gb = memory.total / (1024**3)
        memory_available_gb = memory.available / (1024**3)
        
        # Check for GPU availability
        gpu_available = False
        gpu_name = None
        try:
            import torch
            if torch.cuda.is_available():
                gpu_available = True
                gpu_name = torch.cuda.get_device_name(0)
            elif torch.backends.mps.is_available():
                gpu_available = True
                gpu_name = f"Apple Silicon MPS ({platform.machine()})"
        except ImportError:
            pass
        
        # Generate recommended configuration based on hardware
        recommended_config = PerformanceConfig(
            max_cores=min(cpu_count_logical, 32),  # Cap at 32 for stability
            max_memory_gb=int(memory_total_gb * 0.8),  # Use 80% of available memory
            hdbscan_n_jobs=min(cpu_count_logical, 24),  # HDBSCAN parallelization
            clustering_batch_size=min(100000, int(memory_total_gb * 10000)),  # Scale with memory
            embedding_batch_size=min(2048, max(256, int(memory_total_gb * 20))),  # Scale embedding batch
            vector_processing_workers=min(cpu_count_logical, 16),
            enable_memory_mapping=True,
            cache_embeddings=memory_total_gb > 32,  # Enable caching for high-memory systems
            aggressive_garbage_collection=memory_total_gb < 16,  # GC for low-memory systems
            development_mode=False,
            development_max_papers=min(10000, int(memory_total_gb * 1000))
        )
        
        return SystemInfoResponse(
            cpu_count_physical=cpu_count_physical,
            cpu_count_logical=cpu_count_logical,
            memory_total_gb=memory_total_gb,
            memory_available_gb=memory_available_gb,
            gpu_available=gpu_available,
            gpu_name=gpu_name,
            recommended_config=recommended_config
        )
    except Exception as e:
        logger.error(f"Error getting system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance-config", response_model=PerformanceConfig)
async def get_performance_config() -> PerformanceConfig:
    """Get current performance configuration."""
    try:
        config_json = SettingsRepository.get("performance_config")
        if config_json:
            config_dict = json.loads(config_json)
            return PerformanceConfig(**config_dict)
        else:
            # Return system-recommended defaults
            system_info = await get_system_info()
            return system_info.recommended_config
    except Exception as e:
        logger.error(f"Error getting performance config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/performance-config", response_model=Dict[str, Any])
async def update_performance_config(config: PerformanceConfig) -> Dict[str, Any]:
    """Update performance configuration."""
    try:
        config_dict = config.dict()
        config_json = json.dumps(config_dict)
        SettingsRepository.set("performance_config", config_json)
        
        return {
            "status": "success",
            "message": "Performance configuration updated successfully",
            "config": config_dict
        }
    except Exception as e:
        logger.error(f"Error updating performance config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{topic_id}/papers", response_model=TopicPapersResponse)
async def get_topic_papers(
    topic_id: int,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of papers"),
    min_relevance: float = Query(0.1, ge=0.0, le=1.0, description="Minimum relevance score"),
    sort_by: str = Query("relevance", description="Sort by: relevance, score, date")
):
    """
    Get papers associated with a specific topic.
    """
    try:
        # Get topic info
        topic_data = TopicsRepository.get(topic_id)
        if not topic_data:
            raise HTTPException(status_code=404, detail="Topic not found")
        
        # Get papers
        papers_data = PaperTopicsRepository.get_papers_for_topic(
            topic_id, limit=limit, min_relevance=min_relevance
        )
        
        # Format papers
        papers = [_format_paper_response(paper) for paper in papers_data]
        
        # Apply sorting
        if sort_by == "score":
            papers.sort(key=lambda x: x.score or 0, reverse=True)
        elif sort_by == "date":
            papers.sort(key=lambda x: x.date, reverse=True)
        # Default is already sorted by relevance from the repository
        
        # Count total papers for this topic
        all_papers = PaperTopicsRepository.get_papers_for_topic(
            topic_id, limit=10000, min_relevance=0.0
        )
        total_papers = len(all_papers)
        
        return TopicPapersResponse(
            topic_id=topic_id,
            topic_label=topic_data['label'],
            papers=papers,
            total_papers=total_papers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topic papers: {str(e)}")


# === Research Interest Clustering Endpoints ===
# Separate from automatic topic discovery, these handle research interest based analysis

@router.get("/research-interests", response_model=TrendsListResponse)
async def get_research_interests(
    limit: int = Query(20, ge=1, le=100, description="Maximum number of interests to return"),
    period_type: str = Query("week", description="Display granularity: week, month, quarter"),
    duration_months: int = Query(6, ge=1, le=24, description="Duration to analyze: 1, 3, 6, 12, 24 months"),
    min_doc_count: int = Query(1, ge=1, description="Minimum document count filter"),
    sort_by: str = Query("growth_rate", description="Sort by: growth_rate, doc_count, avg_relevance, forecast_3m")
):
    """
    Get research interests with their latest metrics based on user's configured research interests.
    
    This analyzes papers against the user's research interests rather than automatic topic discovery.
    Uses the same temporal analysis framework as topics but clusters against research interests.
    """
    try:
        # Validate parameters
        if period_type not in ["week", "month", "quarter"]:
            raise HTTPException(status_code=400, detail="Invalid period_type. Must be 'week', 'month', or 'quarter'")
        
        if duration_months not in [1, 3, 6, 12, 24]:
            raise HTTPException(status_code=400, detail="Invalid duration_months. Must be 1, 3, 6, 12, or 24")
        
        # Get dashboard data
        dashboard_data = ResearchInterestTrendsRepository.get_dashboard_data(
            limit=limit,
            period_type=period_type,
            duration_months=duration_months
        )
        
        # Format interests for response
        interests = []
        for interest_data in dashboard_data['trending_interests']:
            if interest_data.get('latest_doc_count', 0) >= min_doc_count:
                # Convert to research interest response format
                converted = _convert_timestamps(interest_data)
                interest_response = ResearchInterestApiResponse(
                    id=converted['research_interest_id'],
                    interest_text=converted['interest_text'],
                    embedding_model=converted.get('embedding_model'),
                    created_at=converted['created_at'],
                    updated_at=converted.get('updated_at'),
                    latest_doc_count=converted.get('latest_doc_count', 0),
                    latest_growth_rate=converted.get('latest_growth_rate'),
                    total_papers=converted.get('total_papers', 0),
                    latest_avg_relevance=converted.get('latest_avg_relevance'),
                    latest_avg_score=converted.get('latest_avg_score'),
                    forecast_1m=converted.get('forecast_1m'),
                    forecast_3m=converted.get('forecast_3m'),
                    forecast_6m=converted.get('forecast_6m')
                )
                interests.append(interest_response)
        
        # Apply sorting
        if sort_by == "doc_count":
            interests.sort(key=lambda x: x.latest_doc_count or 0, reverse=True)
        elif sort_by == "avg_relevance":
            interests.sort(key=lambda x: x.latest_avg_relevance or 0, reverse=True)
        elif sort_by == "forecast_3m":
            interests.sort(key=lambda x: x.forecast_3m or 0, reverse=True)
        else:  # default to growth_rate
            interests.sort(key=lambda x: x.latest_growth_rate or 0, reverse=True)
        
        # Convert back to topics format for compatibility with existing UI
        topics_response = [
            TopicApiResponse(
                id=interest.id,
                label=f"Interest: {interest.interest_text}",
                keywords=[word.strip() for word in interest.interest_text.split() if len(word.strip()) > 2][:10],
                embedding_model=interest.embedding_model,
                created_at=interest.created_at,
                updated_at=interest.updated_at,
                latest_doc_count=interest.latest_doc_count,
                latest_growth_rate=interest.latest_growth_rate,
                total_papers=interest.total_papers,
                forecast_1m=interest.forecast_1m,
                forecast_3m=interest.forecast_3m,
                forecast_6m=interest.forecast_6m
            )
            for interest in interests
        ]
        
        return TrendsListResponse(
            topics=topics_response,  # Using existing format for UI compatibility
            total_topics=dashboard_data['total_interests'],
            total_papers_with_topics=dashboard_data['total_papers_with_interests'],
            period_type=period_type,
            duration_months=duration_months
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get research interests: {str(e)}")


@router.get("/research-interests/search")
async def search_research_interests(
    query: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results")
):
    """
    Search research interests by text content.
    """
    try:
        # Search interests
        search_results = ResearchInterestTrendsRepository.search_interests(query, limit)
        
        # Format results
        interests = []
        for interest_data in search_results:
            converted = _convert_timestamps(interest_data)
            interest_response = ResearchInterestApiResponse(
                id=converted['research_interest_id'],
                interest_text=converted['interest_text'],
                created_at=converted['created_at'],
                updated_at=converted.get('updated_at'),
                latest_doc_count=converted.get('latest_doc_count', 0),
                latest_growth_rate=converted.get('latest_growth_rate'),
                total_papers=converted.get('total_papers', 0)
            )
            interests.append(interest_response)
        
        return ResearchInterestsSearchResponse(
            query=query,
            interests=interests,
            total_results=len(interests)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search research interests: {str(e)}")


@router.get("/research-interests/{interest_id}")
async def get_research_interest_detail(
    interest_id: int,
    period_type: str = Query("week", description="Period type for timeline"),
    timeline_limit: int = Query(24, ge=1, le=100, description="Number of timeline points"),
    papers_limit: int = Query(20, ge=1, le=100, description="Number of representative papers")
):
    """
    Get detailed information about a specific research interest including timeline and papers.
    """
    try:
        # Get research interest info
        interest_data = ResearchInterestsRepository.get(interest_id)
        if not interest_data:
            raise HTTPException(status_code=404, detail="Research interest not found")
        
        # Get latest metrics
        latest_metrics = ResearchInterestMetricsRepository.get_interest_timeline(interest_id, period_type, 1)
        if latest_metrics:
            interest_data['latest_doc_count'] = latest_metrics[0]['doc_count']
            interest_data['latest_growth_rate'] = latest_metrics[0].get('growth_rate')
            interest_data['latest_avg_relevance'] = latest_metrics[0].get('avg_relevance_score')
            interest_data['latest_avg_score'] = latest_metrics[0].get('avg_paper_score')
            interest_data['forecast_1m'] = latest_metrics[0].get('forecast_1m')
            interest_data['forecast_3m'] = latest_metrics[0].get('forecast_3m')
            interest_data['forecast_6m'] = latest_metrics[0].get('forecast_6m')
        
        # Get timeline metrics
        timeline_data = ResearchInterestMetricsRepository.get_interest_timeline(
            interest_id, period_type, timeline_limit
        )
        
        # Get representative papers
        papers_data = PaperResearchInterestsRepository.get_papers_for_interest(
            interest_id, limit=papers_limit, min_similarity=0.1
        )
        
        # Count total papers
        all_papers = PaperResearchInterestsRepository.get_papers_for_interest(
            interest_id, limit=10000, min_similarity=0.0
        )
        total_papers = len(all_papers)
        
        # Format responses
        converted_interest = _convert_timestamps(interest_data)
        interest_response = ResearchInterestApiResponse(
            id=converted_interest['id'],
            interest_text=converted_interest['interest_text'],
            embedding_model=converted_interest.get('embedding_model'),
            created_at=converted_interest['created_at'],
            updated_at=converted_interest.get('updated_at'),
            latest_doc_count=converted_interest.get('latest_doc_count', 0),
            latest_growth_rate=converted_interest.get('latest_growth_rate'),
            total_papers=total_papers,
            latest_avg_relevance=converted_interest.get('latest_avg_relevance'),
            latest_avg_score=converted_interest.get('latest_avg_score'),
            forecast_1m=converted_interest.get('forecast_1m'),
            forecast_3m=converted_interest.get('forecast_3m'),
            forecast_6m=converted_interest.get('forecast_6m')
        )
        
        timeline_response = []
        for metric in timeline_data:
            converted_metric = _convert_timestamps(metric)
            timeline_response.append(ResearchInterestMetricResponse(
                id=converted_metric['id'],
                research_interest_id=converted_metric['research_interest_id'],
                period_start=converted_metric['period_start'],
                period_end=converted_metric['period_end'],
                period_type=converted_metric['period_type'],
                doc_count=converted_metric['doc_count'],
                avg_relevance_score=converted_metric.get('avg_relevance_score'),
                avg_paper_score=converted_metric.get('avg_paper_score'),
                growth_rate=converted_metric.get('growth_rate'),
                forecast_1m=converted_metric.get('forecast_1m'),
                forecast_3m=converted_metric.get('forecast_3m'),
                forecast_6m=converted_metric.get('forecast_6m'),
                created_at=converted_metric['created_at']
            ))
        
        papers_response = [_format_paper_response(paper) for paper in papers_data]
        
        return ResearchInterestDetailResponse(
            interest=interest_response,
            timeline=timeline_response,
            representative_papers=papers_response,
            total_papers=total_papers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get research interest detail: {str(e)}")


@router.post("/research-interests/recompute")
async def recompute_research_interests(
    request: Dict[str, Any] = Body(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Trigger recomputation of research interest clustering based on current research interests in settings.
    
    This will:
    1. Retrieve research interests from settings 
    2. Split by newline and embed each research interest
    3. Cluster papers against these embedded research interests
    4. Calculate temporal metrics and generate forecasts
    """
    try:
        # Parse request with defaults
        lookback_months = request.get('lookback_months', 24)
        duration_months = request.get('duration_months', 6)
        min_papers = request.get('min_papers', 100)
        similarity_threshold = request.get('similarity_threshold', 0.3)
        clear_all_data = request.get('clear_all_data', False)
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create task
        await task_manager.create_task(
            task_id=task_id,
            task_type="research_interest_recompute",
            config=request
        )
        
        # Enqueue background task
        await task_manager.enqueue_task(
            run_research_interest_task,
            task_id
        )
        
        # Estimate duration
        estimated_minutes = max(5, lookback_months // 6)  # Generally faster than BERTopic
        if clear_all_data:
            estimated_minutes = max(8, lookback_months // 4)
        
        processing_type = "nuclear recalculation (clearing all data)" if clear_all_data else "research interest clustering"
        
        return ResearchInterestRecomputeResponse(
            task_id=task_id,
            message=f"Research interest clustering started ({processing_type}, {duration_months}M duration)",
            estimated_duration_minutes=estimated_minutes
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start research interest recomputation: {str(e)}")


@router.get("/research-interests/{interest_id}/papers")
async def get_research_interest_papers(
    interest_id: int,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of papers"),
    min_similarity: float = Query(0.1, ge=0.0, le=1.0, description="Minimum similarity score"),
    sort_by: str = Query("similarity", description="Sort by: similarity, score, date")
):
    """
    Get papers associated with a specific research interest.
    """
    try:
        # Get research interest info
        interest_data = ResearchInterestsRepository.get(interest_id)
        if not interest_data:
            raise HTTPException(status_code=404, detail="Research interest not found")
        
        # Get papers
        papers_data = PaperResearchInterestsRepository.get_papers_for_interest(
            interest_id, limit=limit, min_similarity=min_similarity
        )
        
        # Format papers
        papers = [_format_paper_response(paper) for paper in papers_data]
        
        # Apply sorting
        if sort_by == "score":
            papers.sort(key=lambda x: x.score or 0, reverse=True)
        elif sort_by == "date":
            papers.sort(key=lambda x: x.date, reverse=True)
        # Default is already sorted by similarity from the repository
        
        # Count total papers for this interest
        all_papers = PaperResearchInterestsRepository.get_papers_for_interest(
            interest_id, limit=10000, min_similarity=0.0
        )
        total_papers = len(all_papers)
        
        return ResearchInterestPapersResponse(
            research_interest_id=interest_id,
            interest_text=interest_data['interest_text'],
            papers=papers,
            total_papers=total_papers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get research interest papers: {str(e)}")


@router.get("/{topic_id}", response_model=TopicDetailResponse)
async def get_topic_detail(
    topic_id: int,
    period_type: str = Query("month", description="Period type for timeline"),
    timeline_limit: int = Query(24, ge=1, le=100, description="Number of timeline points"),
    papers_limit: int = Query(20, ge=1, le=100, description="Number of representative papers")
):
    """
    Get detailed information about a specific topic including timeline and papers.
    """
    try:
        # Get topic info
        topic_data = TopicsRepository.get(topic_id)
        if not topic_data:
            raise HTTPException(status_code=404, detail="Topic not found")
        
        # Get latest metrics for this topic to include latest_doc_count and latest_growth_rate
        latest_metrics = TopicMetricsRepository.get_topic_timeline(topic_id, period_type, 1)
        if latest_metrics:
            # Add latest metrics to topic_data
            topic_data['latest_doc_count'] = latest_metrics[0]['doc_count']
            topic_data['latest_growth_rate'] = latest_metrics[0].get('growth_rate')
            topic_data['forecast_1m'] = latest_metrics[0].get('forecast_1m')
            topic_data['forecast_3m'] = latest_metrics[0].get('forecast_3m')
            topic_data['forecast_6m'] = latest_metrics[0].get('forecast_6m')
        
        # Get timeline metrics
        timeline_data = TopicMetricsRepository.get_topic_timeline(
            topic_id, period_type, timeline_limit
        )
        
        # Get representative papers
        papers_data = PaperTopicsRepository.get_papers_for_topic(
            topic_id, limit=papers_limit, min_relevance=0.1
        )
        
        # Count total papers
        all_papers = PaperTopicsRepository.get_papers_for_topic(
            topic_id, limit=10000, min_relevance=0.0
        )
        total_papers = len(all_papers)
        
        # Format responses
        topic_response = _format_topic_response(topic_data)
        topic_response.total_papers = total_papers
        
        timeline_response = [_format_metric_response(metric) for metric in timeline_data]
        papers_response = [_format_paper_response(paper) for paper in papers_data]
        
        return TopicDetailResponse(
            topic=topic_response,
            timeline=timeline_response,
            representative_papers=papers_response,
            total_papers=total_papers
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get topic detail: {str(e)}")


@router.post("/summarize-labels", response_model=Dict[str, str])
async def summarize_labels(labels: List[str]):
    """
    Uses the configured 'judge' LLM to summarize a list of labels for legends.
    Implements database caching to avoid re-summarizing the same labels.
    """
    try:
        # Check database cache first
        cached_summaries = LabelSummariesRepository.get_summaries(labels)
        
        # Find labels that need summarization
        missing_labels = [label for label in labels if label not in cached_summaries]
        
        if not missing_labels:
            logger.info(f"All {len(labels)} labels found in database cache")
            return cached_summaries
        
        logger.info(f"Found {len(cached_summaries)} cached summaries, need to summarize {len(missing_labels)} new labels")
        
        # Load the main orchestration config to get the judge_model settings
        config_json = SettingsRepository.get('orchestration')
        if not config_json:
            raise HTTPException(status_code=500, detail="Orchestration config not found in settings.")
        
        orchestration_config = json.loads(config_json)
        
        if not orchestration_config or not orchestration_config.get('judge_model'):
            raise HTTPException(status_code=500, detail="Judge model is not configured in settings.")

        # Use the configured judge model for summarization
        model_config = orchestration_config['judge_model']
        llm = LLMModelFactory.create_model(**model_config)

        # Prepare the user message for the LLM
        user_message = json.dumps(missing_labels)

        # Invoke the LLM
        response_str = llm.invoke(
            messages=[{"role": "user", "content": user_message}],
            system_prompt=TRENDS_LEGEND_LABEL_SYSTEM_PROMPT
        )
        logger.info(f"LLM raw response for label summarization: {response_str}")

        # The model might return the JSON wrapped in text or code blocks.
        # Let's add robust logic to find and parse it.
        match = re.search(r'\{.*\}', response_str, re.DOTALL)
        
        if not match:
            logger.error(f"No JSON object found in LLM response: {response_str}")
            raise HTTPException(status_code=500, detail="LLM did not return a valid JSON object.")

        json_str = match.group(0)
        new_summaries = json.loads(json_str)

        if not isinstance(new_summaries, dict):
            raise HTTPException(status_code=500, detail="LLM returned a JSON structure, but it was not a dictionary.")

        # Save new summaries to database cache
        if new_summaries:
            model_name = model_config.get('model_name', 'unknown')
            LabelSummariesRepository.save_summaries(new_summaries, model_name)
        
        # Combine cached and new summaries
        all_summaries = {**cached_summaries, **new_summaries}
        
        logger.info(f"Returning {len(all_summaries)} total summaries ({len(cached_summaries)} cached, {len(new_summaries)} new)")
        return all_summaries
        
    except json.JSONDecodeError:
        logger.error(f"Failed to parse extracted JSON from LLM response. Extracted string was: {json_str}")
        raise HTTPException(status_code=500, detail="Failed to parse JSON from LLM response.")
    except Exception as e:
        logger.error(f"An unexpected error occurred in summarize_labels: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("/label-cache/stats", response_model=Dict[str, Any])
async def get_label_cache_stats():
    """Get statistics about the label summaries cache."""
    try:
        stats = LabelSummariesRepository.get_cache_stats()
        return {
            "status": "success",
            "cache_stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/label-cache")
async def clear_label_cache(older_than_days: Optional[int] = Query(None, description="Clear entries older than N days")):
    """Clear the label summaries cache."""
    try:
        cleared_count = LabelSummariesRepository.clear_cache(older_than_days)
        message = f"Cleared {cleared_count} cached summaries"
        if older_than_days:
            message += f" older than {older_than_days} days"
        
        return {
            "status": "success",
            "message": message,
            "cleared_count": cleared_count
        }
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_trends_task(task_id: str):
    """Background task for trends recomputation with performance optimization."""
    try:
        # Get task configuration from database
        task_data = task_manager.get_task_status(task_id)
        if not task_data:
            raise ValueError(f"Task {task_id} not found")
        
        # Parse request from stored config
        config = task_data.get('config_json', {})
        request = TrendsRecomputeRequest(
            lookback_months=config.get('lookback_months', 24),
            duration_months=config.get('duration_months', 6),
            min_papers=config.get('min_papers', 100),
            force_full_recalc=config.get('force_full_recalc', False),
            clear_all_data=config.get('clear_all_data', False)
        )
        
        # Get performance configuration
        try:
            config_json = SettingsRepository.get("performance_config")
            if config_json:
                performance_config = json.loads(config_json)
            else:
                # Use system-recommended defaults
                system_info = await get_system_info()
                performance_config = system_info.recommended_config.dict()
        except Exception as e:
            logger.warning(f"Could not load performance config, using defaults: {e}")
            performance_config = {}
        
        await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               "Initializing performance-optimized trends processor", 5)
        
        # Initialize processor with performance configuration
        processor = TrendsProcessor(
            verbose=True,
            performance_config=performance_config
        )
        
        await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               "Starting trends analysis pipeline", 10)
        
        def progress_callback(stage: str, progress: int, message: str):
            # Note: Can't await in sync callback, processor handles this internally
            task_manager.update_task_status_sync(task_id, TaskStatus.PROCESSING, 
                                   f"[{stage}] {message}", progress)
        
        # Run the pipeline based on request parameters
        if hasattr(request, 'clear_all_data') and request.clear_all_data:
            # Nuclear option - use full pipeline with clearing
            results = processor.run_incremental_pipeline(
                lookback_months=request.lookback_months,
                duration_months=request.duration_months,
                min_papers=request.min_papers,
                force_full_recalc=True,
                clear_all_data=True,
                progress_callback=progress_callback,
                validate_accuracy=True
            )
            await task_manager.update_task_status(task_id, TaskStatus.COMPLETED, 
                                   f"🚨 Nuclear recalculation completed: {results.get('total_papers_processed', 0):,} papers", 100)
        elif hasattr(request, 'force_full_recalc') and request.force_full_recalc:
            # Force full recalculation
            results = processor.run_incremental_pipeline(
                lookback_months=request.lookback_months,
                duration_months=request.duration_months,
                min_papers=request.min_papers,
                force_full_recalc=True,
                clear_all_data=False,
                progress_callback=progress_callback,
                validate_accuracy=True
            )
            await task_manager.update_task_status(task_id, TaskStatus.COMPLETED, 
                                   f"Full recalculation completed: {results.get('total_papers_processed', 0):,} papers", 100)
        else:
            # Incremental processing (default)
            results = processor.run_incremental_pipeline(
                lookback_months=request.lookback_months,
                duration_months=request.duration_months,
                min_papers=request.min_papers,
                force_full_recalc=False,
                clear_all_data=False,
                progress_callback=progress_callback,
                validate_accuracy=True
            )
            await task_manager.update_task_status(task_id, TaskStatus.COMPLETED, 
                                   f"Incremental processing completed: {results.get('total_papers_processed', 0):,} papers", 100)
        
    except Exception as e:
        logger.error(f"Error in trends task {task_id}: {e}")
        await task_manager.update_task_status(task_id, TaskStatus.FAILED, f"Error: {str(e)}", 0)


async def run_forecast_validation_task(task_id: str, period_type: str, processor):
    """Background task for forecast accuracy validation."""
    try:
        await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               f"Starting forecast validation for {period_type} periods", 10)
        
        def progress_callback(stage: str, progress: int, message: str):
            task_manager.update_task_status_sync(task_id, TaskStatus.PROCESSING, 
                                   f"[{stage}] {message}", progress)
        
        validation_results = processor.validate_forecast_accuracy(
            period_type=period_type,
            run_id=task_id,
            progress_callback=progress_callback
        )
        
        message = (f"Validation completed: {validation_results['total_topics_checked']} topics checked, "
                  f"{validation_results['topics_with_accuracy_data']} had sufficient data")
        await task_manager.update_task_status(task_id, TaskStatus.COMPLETED, message, 100)
        
    except Exception as e:
        logger.error(f"Error in forecast validation task {task_id}: {e}")
        await task_manager.update_task_status(task_id, TaskStatus.FAILED, f"Error: {str(e)}", 0)


async def run_research_interest_task(task_id: str):
    """Background task for research interest clustering pipeline."""
    try:
        from ...data_processing.trends import ResearchInterestProcessor
        from ...data_access import ResearchInterestTrendsRepository
        
        # Get task configuration from database
        task_data = task_manager.get_task_status(task_id)
        if not task_data:
            raise ValueError(f"Task {task_id} not found")
        
        # Extract parameters from stored config
        config = task_data.get('config_json', {})
        lookback_months = config.get('lookback_months', 24)
        duration_months = config.get('duration_months', 6)
        min_papers = config.get('min_papers', 100)
        similarity_threshold = config.get('similarity_threshold', 0.3)
        clear_all_data = config.get('clear_all_data', False)
        
        await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               "Initializing research interest clustering processor", 5)
        
        # Handle nuclear option first
        if clear_all_data:
            await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               "NUCLEAR OPTION: Clearing all research interest data", 10)
            
            deleted_counts = ResearchInterestTrendsRepository.nuclear_cleanup_all_data()
            logger.warning(f"NUCLEAR OPTION ACTIVATED: Cleared research interest data: {deleted_counts}")
        
        # Initialize processor
        processor = ResearchInterestProcessor(
            similarity_threshold=similarity_threshold,
            verbose=True
        )
        
        await task_manager.update_task_status(task_id, TaskStatus.PROCESSING, 
                               "Starting research interest clustering pipeline", 15)
        
        def progress_callback(stage: str, progress: int, message: str):
            task_manager.update_task_status_sync(task_id, TaskStatus.PROCESSING, 
                                   f"[{stage}] {message}", progress)
        
        # Run the research interest clustering pipeline
        results = processor.run_full_pipeline(
            lookback_months=lookback_months,
            duration_months=duration_months,
            min_papers=min_papers,
            similarity_threshold=similarity_threshold,
            progress_callback=progress_callback
        )
        
        if results.get('success'):
            summary = (f"✅ Research interest clustering completed: "
                      f"{results.get('research_interests_processed', 0)} interests, "
                      f"{results.get('papers_processed', 0):,} papers, "
                      f"{results.get('relationships_created', 0):,} relationships")
            await task_manager.update_task_status(task_id, TaskStatus.COMPLETED, summary, 100)
        else:
            error_msg = f"Research interest clustering failed: {results.get('errors', ['Unknown error'])}"
            await task_manager.update_task_status(task_id, TaskStatus.FAILED, error_msg, 0)
        
    except Exception as e:
        logger.error(f"Error in research interest task {task_id}: {e}")
        await task_manager.update_task_status(task_id, TaskStatus.FAILED, f"Error: {str(e)}", 0)

# Performance Configuration Endpoints (moved above parameterized routes) 
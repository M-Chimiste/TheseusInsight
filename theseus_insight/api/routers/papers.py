from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import json
from datetime import datetime, date

from ..models import (
    PaperApiResponse, PaginatedPapersResponse,
    SimilaritySearchRequest, SimilaritySearchResponse,
    SimilarPapersRequest, SimilarPapersResponse,
    HybridSearchRequest, HybridSearchResponse,
    ProfileAwareIngestRequest, ProfileAwareIngestResponse
)
from ...data_access import (
    PaperRepository, SettingsRepository
)

def _convert_paper_timestamps(paper_data: dict) -> dict:
    """Convert PostgreSQL datetime objects to ISO strings for API response."""
    converted = paper_data.copy()
    
    # Convert date fields
    if 'date' in converted and isinstance(converted['date'], (datetime, date)):
        converted['date'] = converted['date'].isoformat()
    if 'date_run' in converted and isinstance(converted['date_run'], (datetime, date)):
        converted['date_run'] = converted['date_run'].isoformat()
        
    return converted

router = APIRouter(prefix="/api/papers", tags=["papers"])

@router.get("", response_model=PaginatedPapersResponse)
async def get_papers(
    page: int = Query(1, gt=0),
    score: Optional[float] = None,  # This is min_score for backward compatibility
    max_score: Optional[float] = None,  # Add max_score parameter
    sort_field: Optional[str] = Query(None, enum=['date', 'score', 'profile_score']),
    sort_direction: Optional[str] = Query(None, enum=['asc', 'desc']),
    search: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = Query(10, gt=0, le=100),
    topic_id: Optional[int] = Query(None, description="Filter papers by topic ID"),
    profile_id: Optional[int] = Query(None, description="Filter papers by profile ID"),
    profile_ids: Optional[str] = Query(None, description="Filter papers by multiple profile IDs (comma-separated)"),
    profile_tag: Optional[str] = Query(None, description="Filter papers by profiles with specific tag"),
    profile_tags: Optional[str] = Query(None, description="Filter papers by profiles with any of the tags (comma-separated)"),
    min_profile_score: Optional[float] = Query(None, description="Minimum profile-specific score"),
    max_profile_score: Optional[float] = Query(None, description="Maximum profile-specific score"),
    profile_related_only: bool = Query(False, description="Only show papers marked as related by profiles")
):
    """
    Retrieves a paginated list of papers based on various filters and sorting options.

    This endpoint fetches a paginated list of papers from the database, allowing for filtering by score range, 
    date range, search query, and topic. The results can be sorted by date or score in ascending or descending order.

    Args:
        page (int): The page number to fetch. Defaults to 1.
        score (Optional[float]): The minimum score for filtering papers. Defaults to None.
        max_score (Optional[float]): The maximum score for filtering papers. Defaults to None.
        sort_field (Optional[str]): The field to sort the papers by. Defaults to None.
        sort_direction (Optional[str]): The direction to sort the papers. Defaults to None.
        search (Optional[str]): The search query to filter papers by. Defaults to None.
        from_date (Optional[str]): The start date for filtering papers. Defaults to None.
        to_date (Optional[str]): The end date for filtering papers. Defaults to None.
        page_size (int): The number of papers to fetch per page. Defaults to 10.
        topic_id (Optional[int]): Filter papers by topic ID. Defaults to None.
        profile_id (Optional[int]): Filter papers by profile ID. Defaults to None.
        profile_ids (Optional[str]): Filter papers by multiple profile IDs (comma-separated). Defaults to None.
        profile_tag (Optional[str]): Filter papers by profiles with specific tag. Defaults to None.
        profile_tags (Optional[str]): Filter papers by profiles with any of the tags (comma-separated). Defaults to None.
        min_profile_score (Optional[float]): Minimum profile-specific score. Defaults to None.
        max_profile_score (Optional[float]): Maximum profile-specific score. Defaults to None.
        profile_related_only (bool): Only show papers marked as related by profiles. Defaults to False.

    Returns:
        PaginatedPapersResponse: A response object containing the list of papers, total items, total pages, 
                                 current page, and the next page number if available.

    Raises:
        HTTPException: If an error occurs while fetching the papers.
        """
    try:
        # Parse profile filtering parameters
        profile_filter_params = {}
        
        # Handle profile ID filtering
        if profile_id is not None:
            profile_filter_params['profile_ids'] = [profile_id]
        elif profile_ids is not None:
            # Parse comma-separated profile IDs
            try:
                profile_filter_params['profile_ids'] = [
                    int(id.strip()) for id in profile_ids.split(',') if id.strip()
                ]
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid profile IDs format")
        
        # Handle profile tag filtering - need to resolve tags to profile IDs
        if profile_tag is not None or profile_tags is not None:
            from ...data_access.profiles import ProfileRepository
            
            tags_to_search = []
            if profile_tag:
                tags_to_search.append(profile_tag)
            if profile_tags:
                tags_to_search.extend([tag.strip() for tag in profile_tags.split(',') if tag.strip()])
            
            if tags_to_search:
                tag_profiles = ProfileRepository.get_by_tags(tags_to_search)
                tag_profile_ids = [p['id'] for p in tag_profiles if p['is_active']]
                
                # Merge with existing profile IDs if any
                existing_profile_ids = profile_filter_params.get('profile_ids', [])
                if existing_profile_ids:
                    # Intersection - only profiles that match both criteria
                    profile_filter_params['profile_ids'] = list(set(existing_profile_ids) & set(tag_profile_ids))
                else:
                    # Union - all profiles with the specified tags
                    profile_filter_params['profile_ids'] = tag_profile_ids
        
        # Add profile score filtering
        if min_profile_score is not None:
            profile_filter_params['min_profile_score'] = min_profile_score
        if max_profile_score is not None:
            profile_filter_params['max_profile_score'] = max_profile_score
        if profile_related_only:
            profile_filter_params['profile_related_only'] = True

        # Handle topic filtering vs regular pagination
        if topic_id is not None:
            # Import repositories for filtering (both topics and research interests)
            from ...data_access import (
                PaperTopicsRepository, TopicsRepository,
                PaperResearchInterestsRepository, ResearchInterestsRepository
            )
            
            # Check if it's a topic ID first, then research interest ID
            topic_data = TopicsRepository.get(topic_id)
            research_interest_data = None
            
            if topic_data:
                # It's a topic - get papers for this topic
                all_topic_papers = PaperTopicsRepository.get_papers_for_topic(
                    topic_id, limit=page_size * 10, min_relevance=0.0  # Get more papers for pagination
                )
            else:
                # Check if it's a research interest
                research_interest_data = ResearchInterestsRepository.get(topic_id)
                if research_interest_data:
                    # It's a research interest - get papers for this research interest
                    all_topic_papers = PaperResearchInterestsRepository.get_papers_for_interest(
                        topic_id, limit=page_size * 10, min_similarity=0.0  # Get more papers for pagination
                    )
                else:
                    raise HTTPException(status_code=404, detail=f"Topic or Research Interest {topic_id} not found")
            
            # Apply additional filters if provided
            filtered_papers = []
            for paper in all_topic_papers:
                # Apply score filters
                if score is not None and paper.get('score', 0) < score:
                    continue
                if max_score is not None and paper.get('score', 0) > max_score:
                    continue
                    
                # Apply date filters
                if from_date is not None:
                    paper_date = paper.get('date')
                    if isinstance(paper_date, str):
                        paper_date = datetime.strptime(paper_date, '%Y-%m-%d').date()
                    elif isinstance(paper_date, datetime):
                        paper_date = paper_date.date()
                    
                    if paper_date < datetime.strptime(from_date, '%Y-%m-%d').date():
                        continue
                        
                if to_date is not None:
                    paper_date = paper.get('date')
                    if isinstance(paper_date, str):
                        paper_date = datetime.strptime(paper_date, '%Y-%m-%d').date()
                    elif isinstance(paper_date, datetime):
                        paper_date = paper_date.date()
                    
                    if paper_date > datetime.strptime(to_date, '%Y-%m-%d').date():
                        continue
                        
                # Apply search filter
                if search is not None:
                    search_lower = search.lower()
                    title = paper.get('title', '').lower()
                    abstract = paper.get('abstract', '').lower()
                    if search_lower not in title and search_lower not in abstract:
                        continue
                
                filtered_papers.append(paper)
            
            # Apply sorting
            if sort_field == 'date':
                filtered_papers.sort(
                    key=lambda x: x.get('date', ''), 
                    reverse=(sort_direction == 'desc')
                )
            elif sort_field == 'score':
                filtered_papers.sort(
                    key=lambda x: x.get('score', 0), 
                    reverse=(sort_direction == 'desc')
                )
            else:
                # Default sort by relevance/similarity score (highest first)
                # Use relevance_score for topics, similarity_score for research interests
                if topic_data:
                    # Topic - sort by relevance_score
                    filtered_papers.sort(
                        key=lambda x: x.get('relevance_score', 0), 
                        reverse=True
                    )
                else:
                    # Research interest - sort by similarity_score  
                    filtered_papers.sort(
                        key=lambda x: x.get('similarity_score', 0), 
                        reverse=True
                    )
            
            # Apply pagination
            total_items = len(filtered_papers)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_papers = filtered_papers[start_idx:end_idx]
            
            # Calculate pagination metadata
            total_pages = (total_items + page_size - 1) // page_size
            has_next_page = page < total_pages
            
            papers_data = {
                'items': paginated_papers,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next_page': has_next_page
            }
        else:
            # Use regular database-level pagination
            papers_data = PaperRepository.paginate(
                page=page,
                page_size=page_size,
                min_score=score,
                max_score=max_score,
                sort_field=sort_field or 'score',
                sort_direction=sort_direction or 'desc',
                search=search,
                from_date=from_date,
                to_date=to_date,
                **profile_filter_params  # Include profile filtering parameters
            )
        
        # Convert to API response format
        papers = []
        for p in papers_data['items']:
            converted_p = _convert_paper_timestamps(p)

            # When profile data is present, use it to override base paper data
            is_profile_query = 'profile_score' in converted_p and converted_p['profile_score'] is not None

            # Determine 'related' value, handling None
            related_val = converted_p.get('profile_related') if is_profile_query else converted_p.get('related')
            final_related = bool(related_val) if related_val is not None else False

            # Safeguard required fields to avoid 500s on nulls
            score_val = converted_p.get('score')
            if score_val is None:
                score_val = converted_p.get('profile_score') or 0.0
            date_val = converted_p.get('date') or ''
            date_run_val = converted_p.get('date_run') or ''
            title_val = converted_p.get('title') or ''
            abstract_val = converted_p.get('abstract') or ''
            url_val = converted_p.get('url') or ''
            cosine_val = converted_p.get('cosine_similarity')
            if cosine_val is None:
                cosine_val = 0.0
            embedding_model_val = converted_p.get('embedding_model') or ''

            papers.append(PaperApiResponse(
                id=converted_p['id'], 
                title=title_val, 
                abstract=abstract_val,
                score=float(score_val), 
                date=date_val, 
                url=url_val,
                date_run=date_run_val, 
                rationale=converted_p.get('profile_rationale') or converted_p.get('rationale', '') or '',
                related=final_related,
                cosine_similarity=float(cosine_val),
                embedding_model=embedding_model_val,
                keywords=converted_p.get('keywords'),
                profile_score=converted_p.get('profile_score')
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
    """
    This endpoint initiates a new task for semantic similarity search.
    It retrieves the orchestration config, initializes the embedding model,
    and performs the similarity search.
    It returns a response object containing the query text, the list of similar papers,
    and the total number of similar papers.

    Args:
        request (SimilaritySearchRequest): The request object containing the search parameters.

    Returns:
        SimilaritySearchResponse: A response object containing the query text, the list of similar papers, 
                                  and the total number of similar papers.

    Raises:
        HTTPException: If the orchestration config is not found or the embedding model is not found.
    """
    try:
        # Get the orchestration config to load the embedding model
        orchestration_json = SettingsRepository.get("orchestration")
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
        similar_papers = PaperRepository.semantic_search(
            query_text=request.query_text,
            embedding_model=embedding_model,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold,
        )
        
        # Convert to API response format
        results = []
        for p in similar_papers:
            converted_p = _convert_paper_timestamps(p)
            paper_response = PaperApiResponse(
                id=converted_p['id'], title=converted_p['title'], abstract=converted_p['abstract'],
                score=converted_p['score'], date=converted_p['date'], url=converted_p['url'],
                date_run=converted_p['date_run'], rationale=converted_p['rationale'],
                related=converted_p['related'], cosine_similarity=converted_p['cosine_similarity'],
                embedding_model=converted_p['embedding_model'],
                keywords=converted_p.get('keywords')
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
    """
    Initiates a hybrid search for papers based on semantic and keyword weights.

    This endpoint performs a hybrid search for papers using both semantic and keyword-based approaches.
    It takes into account the weights assigned to each approach to determine the relevance of the search results.
    The search query is executed against the database, and the results are filtered based on the specified parameters.

    Args:
        request (HybridSearchRequest): The request object containing the search parameters.

    Returns:
        HybridSearchResponse: A response object containing the search results and metadata.

    Raises:
        HTTPException: If the orchestration config is not found or the embedding model is not found.
    """
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
        orchestration_json = SettingsRepository.get("orchestration")
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
        search_results = PaperRepository.hybrid_search(
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
            converted_p = _convert_paper_timestamps(p)
            paper_response = PaperApiResponse(
                id=converted_p['id'], title=converted_p['title'], abstract=converted_p['abstract'],
                score=converted_p['score'], date=converted_p['date'], url=converted_p['url'],
                date_run=converted_p['date_run'], rationale=converted_p['rationale'],
                related=converted_p['related'], cosine_similarity=converted_p['cosine_similarity'],
                embedding_model=converted_p['embedding_model'],
                semantic_score=converted_p.get('semantic_score'),
                keyword_score=converted_p.get('keyword_score'),
                hybrid_score=converted_p.get('hybrid_score'),
                keywords=converted_p.get('keywords')
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
    """
    Retrieves a list of papers without embeddings.

    This endpoint fetches a list of papers from the database that do not have embeddings generated.
    It returns a list of paper objects with their details, excluding embedding information.

    Returns:
        dict: A dictionary containing a list of paper objects and the total count of papers.

    Raises:
        HTTPException: If an error occurs while fetching the papers.
    """
    try:
        papers = PaperRepository.without_embeddings()
        results = []
        for p in papers:
            converted_p = _convert_paper_timestamps(p)
            results.append(PaperApiResponse(
                id=converted_p['id'], title=converted_p['title'], abstract=converted_p['abstract'],
                score=converted_p['score'], date=converted_p['date'], url=converted_p['url'],
                date_run=converted_p['date_run'], rationale=converted_p['rationale'],
                related=converted_p['related'], cosine_similarity=converted_p['cosine_similarity'],
                embedding_model=converted_p['embedding_model'],
                keywords=converted_p.get('keywords')
            ))
        return {"papers": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{paper_id}/update-embedding")
async def update_paper_embedding(paper_id: int):
    """
    Generates and updates an embedding for a specific paper.

    This endpoint generates an embedding for a paper's abstract and updates the paper's embedding in the database.
    It retrieves the orchestration config, initializes the embedding model, and generates the embedding.
    The updated paper is then saved to the database.

    Args:
        paper_id (int): The ID of the paper to update.

    Returns:
        dict: A dictionary containing a message and a boolean indicating if the embedding was updated successfully.
    
    Raises:
        HTTPException: If the paper is not found or the embedding model is not found.
    """
    try:
        # Get the paper details
        paper = PaperRepository.get_by_id(paper_id)
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        if paper['embedding'] is not None:
            return {"message": "Paper already has an embedding", "updated": False}
        
        # Get the orchestration config to load the embedding model
        orchestration_json = SettingsRepository.get("orchestration")
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
        PaperRepository.update_embedding(paper_id, embedding)
        
        return {"message": "Embedding updated successfully", "updated": True}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{paper_id}/similar", response_model=SimilarPapersResponse)
async def find_similar_papers_to_existing(
    paper_id: int,
    limit: int = Query(10, gt=0, le=200, description="Maximum number of similar papers to return"),
    similarity_threshold: float = Query(0.7, ge=0.0, le=1.0, description="Minimum similarity score (0-1)")
):
    """
    Finds papers similar to an existing paper using its stored embedding.

    This endpoint searches for similar papers to a given paper using its stored embedding.
    It returns a response object containing the reference paper and a list of similar papers.

    Args:
        paper_id (int): The ID of the paper to find similar papers for.
        limit (int): The maximum number of similar papers to return. Defaults to 10.
        similarity_threshold (float): The minimum similarity score (0-1) for filtering similar papers. Defaults to 0.7.

    Returns:
        SimilarPapersResponse: A response object containing the reference paper and a list of similar papers.
    """
    try:
        # Find similar papers using the database method
        result = PaperRepository.find_similar_existing(
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
        converted_ref = _convert_paper_timestamps(ref_paper_data)
        reference_paper = PaperApiResponse(
            id=converted_ref['id'],
            title=converted_ref['title'],
            abstract=converted_ref['abstract'],
            score=converted_ref['score'],
            date=converted_ref['date'],
            url=converted_ref['url'],
            date_run=converted_ref['date_run'],
            rationale=converted_ref['rationale'],
            related=converted_ref['related'],
            cosine_similarity=converted_ref['cosine_similarity'],
            embedding_model=converted_ref['embedding_model'],
            keywords=converted_ref.get('keywords')
        )
        
        # Convert similar papers to API response format
        similar_papers = []
        for p in result['similar_papers']:
            converted_p = _convert_paper_timestamps(p)
            paper_response = PaperApiResponse(
                id=converted_p['id'],
                title=converted_p['title'],
                abstract=converted_p['abstract'],
                score=converted_p['score'],
                date=converted_p['date'],
                url=converted_p['url'],
                date_run=converted_p['date_run'],
                rationale=converted_p['rationale'],
                related=converted_p['related'],
                cosine_similarity=converted_p['cosine_similarity'],
                embedding_model=converted_p['embedding_model'],
                similarity_score=p['similarity_score'],  # Include the similarity score
                keywords=converted_p.get('keywords')
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

@router.post("/profile-aware-ingest", response_model=ProfileAwareIngestResponse)
async def start_profile_aware_ingest(request: ProfileAwareIngestRequest):
    """
    Start a profile-aware paper ingestion task.
    
    This endpoint initiates a comprehensive paper ingestion process that:
    1. Downloads papers from ArXiv based on date range and categories
    2. Embeds and stores all papers without initial LLM filtering
    3. Automatically scores papers against specified profiles using LLM judge
    
    The process runs asynchronously and returns a task ID for monitoring progress.
    """
    try:
        import uuid
        import logging
        from ..tasks import task_manager
        from ...data_access.profiles import ProfileRepository

        logger = logging.getLogger(__name__)
        logger.info(f"📝 Starting profile-aware ingestion request: use_multi_server={request.use_multi_server}, profile_ids={request.profile_ids}, server_ids={request.server_ids}")
        
        # Validate profiles exist if specified
        if request.profile_ids:
            for profile_id in request.profile_ids:
                profile = ProfileRepository.get_by_id(profile_id)
                if not profile:
                    raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
                if not profile['is_active']:
                    raise HTTPException(status_code=400, detail=f"Profile {profile_id} is not active")
        
        # Validate tags exist if specified
        if request.profile_tags:
            profiles_with_tags = ProfileRepository.get_by_tags(request.profile_tags)
            if not profiles_with_tags:
                raise HTTPException(status_code=404, detail=f"No profiles found with tags: {request.profile_tags}")
        
        # If no profiles specified but score_all_profiles is False, get active profiles
        if not request.profile_ids and not request.profile_tags and not request.score_all_profiles:
            active_profiles = ProfileRepository.get_all_active()
            if not active_profiles:
                raise HTTPException(status_code=400, detail="No active profiles found. Please create profiles or set score_all_profiles=true")
        
        # Create task ID and configuration
        task_id = str(uuid.uuid4())
        
        # Prepare task configuration
        config = {
            "start_date": request.start_date,
            "end_date": request.end_date,
            "profile_ids": request.profile_ids,
            "profile_tags": request.profile_tags,
            "score_all_profiles": request.score_all_profiles,
            "overwrite_existing": request.overwrite_existing,
            "cosine_threshold": request.cosine_threshold,
            "arxiv_categories": request.arxiv_categories,
            "batch_size": request.batch_size,
            "send_error_notifications": request.send_error_notifications,
            # Multi-server configuration
            "use_multi_server": request.use_multi_server,
            "server_ids": request.server_ids
        }

        # Handle multi-server requests differently
        logger.info("🔀 Checking multi-server routing logic")
        if request.use_multi_server:
            logger.info("🚀 Multi-server request detected, routing to bulk operations")
            # Route to bulk operations API for multi-server processing
            from .bulk_operations import _start_bulk_judge_operation
            from fastapi import BackgroundTasks

            # Convert to BulkJudgeRequest format
            logger.info("🔄 Converting ProfileAwareIngestRequest to BulkJudgeRequest")
            from .bulk_operations import BulkJudgeRequest
            bulk_request = BulkJudgeRequest(
                profile_ids=[str(pid) for pid in request.profile_ids] if request.profile_ids else None,
                all_profiles=request.score_all_profiles,
                start_date=request.start_date,
                end_date=request.end_date,
                limit=None,  # No limit for full ingestion
                use_multi_server=True,
                server_ids=request.server_ids,
                request_timeout_sec=None,  # Use defaults
                max_retries=None,  # Use defaults
                suspend_scheduled_tasks=True,  # Suspend during bulk processing
                overwrite_existing=request.overwrite_existing,
                batch_size=request.batch_size
            )
            logger.info(f"✅ BulkJudgeRequest created: profile_ids={bulk_request.profile_ids}, server_ids={bulk_request.server_ids}")

            # Create background tasks dependency
            background_tasks = BackgroundTasks()

            # Call bulk judge core operation
            logger.info("⚡ Calling _start_bulk_judge_operation...")
            bulk_response = await _start_bulk_judge_operation(bulk_request, background_tasks)
            logger.info(f"✅ Bulk judge operation completed: job_id={bulk_response.job_id}")

            # Return response in expected format
            logger.info("📤 Returning successful response")
            return ProfileAwareIngestResponse(
                task_id=str(bulk_response.job_id),  # Convert UUID to string
                message="Multi-server profile-aware ingestion started successfully",
                profile_count=len(request.profile_ids) if request.profile_ids else 0,
                estimated_papers=0,  # Will be calculated by bulk judge
                status="running"
            )
        else:
            # Use regular single-server processing
            logger.info("🔄 Single-server request detected, using regular task manager")
            # Create task in database
            await task_manager.create_task(task_id, "profile_aware_ingest", config)

            # Enqueue task for processing
            await task_manager.enqueue_task(task_manager.run_profile_aware_ingest_task, task_id)

            # Estimate target profiles and papers for single-server response
            target_profiles = []
            if request.profile_ids:
                target_profiles.extend([ProfileRepository.get_by_id(pid) for pid in request.profile_ids])
            if request.profile_tags:
                target_profiles.extend(ProfileRepository.get_by_tags(request.profile_tags))
            if request.score_all_profiles and not target_profiles:
                target_profiles = ProfileRepository.get_all_active()

            # Filter active profiles and remove duplicates
            active_profiles = [p for p in target_profiles if p and p['is_active']]
            unique_profiles = []
            seen_ids = set()
            for p in active_profiles:
                if p['id'] not in seen_ids:
                    unique_profiles.append(p)
                    seen_ids.add(p['id'])

            # Estimate papers (rough calculation based on typical ArXiv daily volume)
            from datetime import datetime, timedelta
            if request.start_date and request.end_date:
                start = datetime.strptime(request.start_date, '%Y-%m-%d')
                end = datetime.strptime(request.end_date, '%Y-%m-%d')
                days = (end - start).days + 1
            else:
                days = 7  # Default to 7 days if not specified

            # Rough estimate: 200-300 papers per day from ArXiv
            estimated_papers = days * 250

            return ProfileAwareIngestResponse(
                task_id=task_id,
                message=f"Profile-aware ingestion task started successfully. Processing {len(unique_profiles)} profiles.",
                profile_count=len(unique_profiles),
                estimated_papers=estimated_papers,
                status="running"
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error in profile-aware ingestion: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start profile-aware ingestion: {str(e)}")

@router.post("/bulk-embed")
async def start_bulk_embed(request: dict):
    """
    Start a bulk paper embedding task without profile scoring.
    
    This endpoint initiates a paper embedding process that:
    1. Downloads papers from ArXiv based on date range
    2. Embeds all paper abstracts without filtering
    3. Stores embedded papers in the database
    4. Does NOT perform any profile-specific scoring
    
    The process runs asynchronously and returns a task ID for monitoring progress.
    """
    try:
        import uuid
        from ..tasks import task_manager
        
        # Debug: Print the entire request
        print(f"[DEBUG] Bulk embed API received request: {request}")
        
        # Extract request parameters
        start_date = request.get('start_date')
        end_date = request.get('end_date')
        batch_size = request.get('batch_size', 100)
        skip_existing = request.get('skip_existing', True)
        arxiv_categories = request.get('arxiv_categories', None)
        
        print(f"[DEBUG] API extracted arxiv_categories: {arxiv_categories} (type: {type(arxiv_categories)})")
        
        # Validate dates
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="Both start_date and end_date are required")
        
        # Create task ID and configuration
        task_id = str(uuid.uuid4())
        
        # Prepare task configuration
        config = {
            "start_date": start_date,
            "end_date": end_date,
            "batch_size": batch_size,
            "skip_existing": skip_existing,
            "embedding_only": True,  # Flag to indicate embedding-only mode
            "arxiv_categories": arxiv_categories  # Optional arxiv category filter
        }
        
        # Create task in database
        await task_manager.create_task(task_id, "bulk_embed", config)
        
        # Enqueue task for processing
        await task_manager.enqueue_task(task_manager.run_bulk_embed_task, task_id)
        
        # Estimate papers
        from datetime import datetime
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1
        estimated_papers = days * 250
        
        return {
            "task_id": task_id,
            "message": f"Bulk embedding task started successfully for {days} days.",
            "estimated_papers": estimated_papers,
            "status": "started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start bulk embedding: {str(e)}")

@router.get("/check-existing-bulk-data")
async def check_existing_bulk_data(start_date: str, end_date: str):
    """
    Check if bulk data already exists for the specified date range.
    
    Returns information about:
    - Total papers in the date range
    - How many already have embeddings
    - How many are missing embeddings
    """
    try:
        from ...data_access.papers import PaperRepository
        from datetime import datetime
        
        # Validate dates
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d')
            end = datetime.strptime(end_date, '%Y-%m-%d')
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Query papers in date range
        papers = PaperRepository.get_papers_in_date_range(start_date, end_date)
        
        # Count papers with and without embeddings
        total_papers = len(papers)
        # Check if papers have embeddings by looking for non-null embedding_model
        embedded_count = sum(1 for p in papers if p.get('embedding_model') is not None)
        missing_embeddings = total_papers - embedded_count
        
        return {
            "paper_count": total_papers,
            "embedded_count": embedded_count,
            "missing_embeddings": missing_embeddings,
            "start_date": start_date,
            "end_date": end_date,
            "has_all_embeddings": missing_embeddings == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check existing data: {str(e)}") 
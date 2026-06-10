"""Row-to-API serialization helpers shared by routers.

Replaces the seven per-router ``_convert_*_timestamps`` copies. psycopg
returns datetime/date objects for timestamp/date columns; Pydantic
response models expect ISO strings.
"""
import json
import logging
from datetime import date, datetime
from typing import Any, Dict, Sequence

logger = logging.getLogger(__name__)


def isoformat_fields(data: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    """Copy ``data`` with the named fields ISO-formatted when they are
    datetime/date objects; other values (already-strings, None) untouched."""
    converted = data.copy()
    for field in fields:
        value = converted.get(field)
        if value is not None and isinstance(value, (datetime, date)):
            converted[field] = value.isoformat()
    return converted


def decode_json_fields(data: Dict[str, Any], fields: Sequence[str]) -> Dict[str, Any]:
    """Copy ``data`` with the named fields json-decoded when they are strings.

    Undecodable values become None — the behavior the profiles router
    established for tags/email_recipients/arxiv_filters.
    """
    converted = data.copy()
    for field in fields:
        value = converted.get(field)
        if value is not None and isinstance(value, str):
            try:
                converted[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                converted[field] = None
    return converted


def serialize_research_object(obj, visited=None):
    """
    Convert PaperInfo objects and other non-serializable objects to dictionaries.
    
    Args:
        obj: Object to serialize (could be PaperInfo, list, dict, etc.)
        visited: Set of object IDs already visited (for cycle detection)
        
    Returns:
        JSON-serializable version of the object
    """
    from ...research_agent.tools.deduplication import PaperInfo
    from ...research_agent.orchestrator import OrchestrationResult
    from ...research_agent.synthesis_agent import SynthesisResult, SynthesisMetadata, ConflictIdentification
    from ...research_agent.agent_manager import AgentResult
    from ...research_agent.question_generator import GeneratedQuestion
    from types import MappingProxyType
    import datetime
    import uuid
    import inspect
    from dataclasses import is_dataclass, asdict
    
    # Initialize visited set for cycle detection
    if visited is None:
        visited = set()
    
    # Check for circular references
    obj_id = id(obj)
    if obj_id in visited:
        # Return a placeholder for circular references
        return f"<circular-reference: {type(obj).__name__}>"
    
    try:
        # Handle property descriptors and other descriptors - skip them
        if inspect.isdatadescriptor(obj) or inspect.isgetsetdescriptor(obj) or inspect.ismethoddescriptor(obj):
            return f"<descriptor: {type(obj).__name__}>"
        
        # Special handling for OrchestrationResult to include properties
        if isinstance(obj, OrchestrationResult):
            visited.add(obj_id)
            result = {
                'original_question': obj.original_question,
                'final_answer': obj.final_answer,
                'generation_summary': obj.generation_summary,
                'generated_questions': serialize_research_object([{
                    'agent_id': q.agent_id,
                    'agent_type': q.agent_type.value,
                    'question': q.question,
                    'specialization_focus': q.specialization_focus,
                    'search_strategy': q.search_strategy
                } for q in obj.generated_questions], visited),
                'question_generation_success': obj.question_generation_success,
                'agent_results': serialize_research_object([{
                    'agent_id': r.agent_id,
                    'agent_type': r.agent_type.value,
                    'question': r.question,
                    'response': r.response,
                    'sources_gathered': serialize_research_object(r.sources_gathered, visited),
                    'execution_time': r.execution_time,
                    'success': r.success,
                    'error_message': r.error_message,
                    'metadata': serialize_research_object(r.metadata, visited)
                } for r in obj.agent_results], visited),
                'successful_agents': obj.successful_agents,
                'failed_agents': obj.failed_agents,
                'execution_time': obj.execution_time,
                'success': obj.success,
                'error_message': obj.error_message,
                # Include properties
                'statistics': serialize_research_object(obj.statistics, visited),
                'sub_queries': serialize_research_object(obj.sub_queries, visited),
                'sources_gathered': serialize_research_object(obj.sources_gathered, visited),
                'judged_sources': serialize_research_object(obj.judged_sources, visited),
                'evidence': serialize_research_object(obj.evidence, visited),
                'compressed_notes': obj.compressed_notes,
                'workflow_messages': serialize_research_object(obj.workflow_messages, visited)
            }
            visited.discard(obj_id)
            return result
        elif isinstance(obj, PaperInfo):
            visited.add(obj_id)
            result = {
                'paper_id': obj.paper_id,
                'title': obj.title,
                'abstract': obj.abstract,
                'url': obj.url,
                'source': obj.source,
                'raw_data': serialize_research_object(obj.raw_data, visited)  # Recursively serialize raw_data
            }
            visited.discard(obj_id)
            return result
        elif isinstance(obj, MappingProxyType):
            visited.add(obj_id)
            # Convert mappingproxy to regular dict
            result = {key: serialize_research_object(value, visited) for key, value in obj.items()}
            visited.discard(obj_id)
            return result
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            # Convert datetime objects to ISO format strings
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            # Convert UUID objects to strings
            return str(obj)
        elif isinstance(obj, set):
            visited.add(obj_id)
            # Convert sets to lists
            result = [serialize_research_object(item, visited) for item in obj]
            visited.discard(obj_id)
            return result
        elif isinstance(obj, tuple):
            visited.add(obj_id)
            # Convert tuples to lists
            result = [serialize_research_object(item, visited) for item in obj]
            visited.discard(obj_id)
            return result
        elif isinstance(obj, list):
            visited.add(obj_id)
            result = [serialize_research_object(item, visited) for item in obj]
            visited.discard(obj_id)
            return result
        elif isinstance(obj, dict):
            visited.add(obj_id)
            result = {key: serialize_research_object(value, visited) for key, value in obj.items()}
            visited.discard(obj_id)
            return result
        elif is_dataclass(obj) and not isinstance(obj, type):
            # Generic dataclass handler - convert to dict and recursively serialize
            visited.add(obj_id)
            try:
                obj_dict = asdict(obj)
                result = serialize_research_object(obj_dict, visited)
            except (TypeError, ValueError) as e:
                # If asdict fails (e.g., due to non-serializable fields), fall back to __dict__
                logger.warning(f"asdict failed for dataclass {type(obj).__name__}: {e}")
                obj_dict = {}
                for key, value in obj.__dict__.items():
                    if not key.startswith('_') and not callable(value):
                        obj_dict[key] = value
                result = serialize_research_object(obj_dict, visited)
            visited.discard(obj_id)
            return result
        elif hasattr(obj, '__dict__'):
            visited.add(obj_id)
            # For other objects with __dict__, convert to dict
            # Filter out methods and descriptors
            obj_dict = {}
            for key, value in obj.__dict__.items():
                # Skip private attributes and methods
                if not key.startswith('_') and not callable(value):
                    obj_dict[key] = value
            result = serialize_research_object(obj_dict, visited)
            visited.discard(obj_id)
            return result
        # Handle callable objects by returning their name, preventing serialization errors
        elif callable(obj):
            return f"<callable: {getattr(obj, '__name__', 'unnamed')}>"
        else:
            # For primitive types (str, int, float, bool, None), return as-is
            return obj
    except Exception as e:
        # Remove from visited set on error
        if obj_id in visited:
            visited.discard(obj_id)
        logger.warning(f"Failed to serialize object of type {type(obj).__name__}: {e}")
        # Return a string representation as fallback
        return f"<non-serializable: {type(obj).__name__}>"

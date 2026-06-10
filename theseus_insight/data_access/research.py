from __future__ import annotations

from typing import Any, Dict, List
import json

from ..db import get_cursor
from .base import build_set_clause


class ResearchRunRepository:
    """CRUD for `research_runs` table."""

    @staticmethod
    def insert(
        task_id: str,
        research_question: str,
        *,
        status: str = "pending",
        config: Dict[str, Any] | None = None,
        save_to_library: bool = True,
    ) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_runs (task_id, research_question, status, config_json, created_at, save_to_library)
                VALUES (%s,%s,%s,%s, now(), %s)
                ON CONFLICT (task_id) DO NOTHING
                """,
                (
                    task_id,
                    research_question,
                    status,
                    json.dumps(config) if config else None,
                    save_to_library,
                ),
            )

    @staticmethod
    def insert_research_run(
        task_id: str,
        research_question: str,
        *,
        status: str = "pending",
        config: Dict[str, Any] | None = None,
        save_to_library: bool = True,
    ) -> None:
        ResearchRunRepository.insert(task_id, research_question, status=status, config=config, save_to_library=save_to_library)

    @staticmethod
    def update_status(
        task_id: str,
        status: str,
        *,
        started_at: str | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
    ) -> None:
        candidates = {
            "started_at": started_at,
            "completed_at": completed_at,
            "error_message": error_message,
        }
        updates = {"status": status, **{k: v for k, v in candidates.items() if v is not None}}
        set_sql, params = build_set_clause(updates)
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE research_runs SET {set_sql} WHERE task_id = %s", [*params, task_id]
            )

    @staticmethod
    def update_research_run_status(
        task_id: str,
        status: str,
        *,
        started_at: str | None = None,
        completed_at: str | None = None,
        error_message: str | None = None,
    ) -> None:
        ResearchRunRepository.update_status(task_id, status, started_at=started_at, completed_at=completed_at, error_message=error_message)

    @staticmethod
    def update_results(
        task_id: str,
        **payload: Any,
    ) -> None:
        if not payload:
            return
        json_cols = {
            "statistics": "statistics_json",
            "sub_queries": "sub_queries_json",
            "sources_gathered": "sources_gathered_json",
            "judged_sources": "judged_sources_json",
            "evidence": "evidence_json",
            "workflow_messages": "workflow_messages_json",
        }
        updates: Dict[str, Any] = {}
        for key, value in payload.items():
            if value is None:
                continue
            column = json_cols.get(key, key)
            updates[column] = json.dumps(value) if column.endswith("_json") else value
        set_sql, params = build_set_clause(updates)
        with get_cursor() as cur:
            cur.execute(
                f"UPDATE research_runs SET {set_sql} WHERE task_id = %s", [*params, task_id]
            )

    @staticmethod
    def update_research_run_results(task_id: str, **payload: Any) -> None:
        ResearchRunRepository.update_results(task_id, **payload)

    @staticmethod
    def get(task_id: str) -> Dict[str, Any] | None:
        with get_cursor() as cur:
            cur.execute("SELECT * FROM research_runs WHERE task_id = %s", (task_id,))
            result = cur.fetchone()
            if result:
                # Parse JSON fields back to Python objects
                json_fields = ['config_json', 'statistics_json', 'sub_queries_json', 
                              'sources_gathered_json', 'judged_sources_json', 'evidence_json', 
                              'workflow_messages_json']
                for field in json_fields:
                    if field in result and result[field]:
                        try:
                            if isinstance(result[field], str):
                                result[field] = json.loads(result[field])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Keep as string if parsing fails
                
                # Create convenient non-JSON field names for API compatibility
                result['config'] = result.get('config_json')
                result['statistics'] = result.get('statistics_json')
                result['sub_queries'] = result.get('sub_queries_json', [])
                result['sources_gathered'] = result.get('sources_gathered_json', [])
                result['judged_sources'] = result.get('judged_sources_json', [])
                result['evidence'] = result.get('evidence_json', [])
                result['workflow_messages'] = result.get('workflow_messages_json', [])
                
            return result

    @staticmethod
    def get_research_run(task_id: str) -> Dict[str, Any] | None:
        return ResearchRunRepository.get(task_id)

    @staticmethod
    def history(limit: int = 50, offset: int = 0, status_filter: str | None = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM research_runs"
        params: List[Any] = []
        
        if status_filter:
            sql += " WHERE status = %s"
            params.append(status_filter)
        
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        with get_cursor() as cur:
            cur.execute(sql, params)
            results = cur.fetchall()
            
            # Parse JSON fields for each result
            json_fields = ['config_json', 'statistics_json', 'sub_queries_json', 
                          'sources_gathered_json', 'judged_sources_json', 'evidence_json', 
                          'workflow_messages_json']
            
            for result in results:
                for field in json_fields:
                    if field in result and result[field]:
                        try:
                            if isinstance(result[field], str):
                                result[field] = json.loads(result[field])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Keep as string if parsing fails
                
                # Create convenient non-JSON field names for API compatibility
                result['config'] = result.get('config_json')
                result['statistics'] = result.get('statistics_json')
                result['sub_queries'] = result.get('sub_queries_json', [])
                result['sources_gathered'] = result.get('sources_gathered_json', [])
                result['judged_sources'] = result.get('judged_sources_json', [])
                result['evidence'] = result.get('evidence_json', [])
                result['workflow_messages'] = result.get('workflow_messages_json', [])
            
            return results

    @staticmethod
    def get_research_runs_history(limit: int = 50, offset: int = 0, status_filter: str | None = None) -> List[Dict[str, Any]]:
        return ResearchRunRepository.history(limit=limit, offset=offset, status_filter=status_filter)

    @staticmethod
    def get_by_status(statuses: List[str]) -> List[Dict[str, Any]]:
        placeholders = ','.join(['%s'] * len(statuses))
        sql = f"SELECT * FROM research_runs WHERE status IN ({placeholders}) ORDER BY created_at DESC"
        
        with get_cursor() as cur:
            cur.execute(sql, statuses)
            results = cur.fetchall()
            
            # Parse JSON fields for each result
            json_fields = ['config_json', 'statistics_json', 'sub_queries_json', 
                          'sources_gathered_json', 'judged_sources_json', 'evidence_json', 
                          'workflow_messages_json']
            
            for result in results:
                for field in json_fields:
                    if field in result and result[field]:
                        try:
                            if isinstance(result[field], str):
                                result[field] = json.loads(result[field])
                        except (json.JSONDecodeError, TypeError):
                            pass  # Keep as string if parsing fails
                
                # Create convenient non-JSON field names for API compatibility
                result['config'] = result.get('config_json')
                result['statistics'] = result.get('statistics_json')
                result['sub_queries'] = result.get('sub_queries_json', [])
                result['sources_gathered'] = result.get('sources_gathered_json', [])
                result['judged_sources'] = result.get('judged_sources_json', [])
                result['evidence'] = result.get('evidence_json', [])
                result['workflow_messages'] = result.get('workflow_messages_json', [])
            
            return results

    @staticmethod
    def get_research_runs_by_status(statuses: List[str]) -> List[Dict[str, Any]]:
        return ResearchRunRepository.get_by_status(statuses)

    @staticmethod
    def delete(task_id: str) -> None:
        with get_cursor() as cur:
            cur.execute("DELETE FROM research_runs WHERE task_id = %s", (task_id,))

    @staticmethod
    def delete_research_run(task_id: str) -> None:
        ResearchRunRepository.delete(task_id)


class ResearchAgentStateRepository:
    """State snapshots per research run."""

    @staticmethod
    def insert(task_id: str, node_name: str, state: Dict[str, Any]) -> None:
        with get_cursor() as cur:
            cur.execute(
                """
                INSERT INTO research_agent_state (task_id, node_name, state_json, timestamp)
                VALUES (%s,%s,%s, now())
                """,
                (
                    task_id,
                    node_name,
                    json.dumps(state),
                ),
            )

    @staticmethod
    def list(task_id: str) -> List[Dict[str, Any]]:
        with get_cursor() as cur:
            cur.execute(
                "SELECT * FROM research_agent_state WHERE task_id = %s ORDER BY timestamp",
                (task_id,),
            )
            return cur.fetchall() 
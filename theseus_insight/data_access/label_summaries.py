"""
Data access layer for label summaries cache.
"""
from typing import Dict, List, Optional
import logging

from ..db import get_cursor

logger = logging.getLogger(__name__)


class LabelSummariesRepository:
    """Repository for managing cached label summaries."""
    
    @staticmethod
    def get_summaries(original_labels: List[str]) -> Dict[str, str]:
        """
        Get cached summaries for a list of original labels.
        
        Args:
            original_labels: List of original labels to look up
            
        Returns:
            Dictionary mapping original labels to their summaries
        """
        if not original_labels:
            return {}
            
        try:
            with get_cursor() as cursor:
                placeholders = ','.join(['%s'] * len(original_labels))
                query = f"""
                    SELECT original_label, summarized_label 
                    FROM label_summaries 
                    WHERE original_label IN ({placeholders})
                """
                cursor.execute(query, original_labels)
                results = cursor.fetchall()
                
                return {row['original_label']: row['summarized_label'] for row in results}
                
        except Exception as e:
            logger.error(f"Error getting cached summaries: {e}")
            return {}
    
    @staticmethod
    def save_summaries(summaries: Dict[str, str], model_used: Optional[str] = None) -> int:
        """
        Save new summaries to the cache.
        
        Args:
            summaries: Dictionary mapping original labels to summaries
            model_used: Name of the model that generated the summaries
            
        Returns:
            Number of summaries saved
        """
        if not summaries:
            return 0
            
        try:
            with get_cursor() as cursor:
                # Use ON CONFLICT to update existing entries
                query = """
                    INSERT INTO label_summaries (original_label, summarized_label, model_used)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (original_label) 
                    DO UPDATE SET 
                        summarized_label = EXCLUDED.summarized_label,
                        model_used = EXCLUDED.model_used,
                        updated_at = now()
                """
                
                data = [(original, summary, model_used) for original, summary in summaries.items()]
                cursor.executemany(query, data)
                
                logger.info(f"Saved {len(summaries)} label summaries to cache")
                return len(summaries)
                
        except Exception as e:
            logger.error(f"Error saving summaries to cache: {e}")
            return 0
    
    @staticmethod
    def get_summary(original_label: str) -> Optional[str]:
        """
        Get a single cached summary.
        
        Args:
            original_label: The original label to look up
            
        Returns:
            The summarized label, or None if not found
        """
        summaries = LabelSummariesRepository.get_summaries([original_label])
        return summaries.get(original_label)
    
    @staticmethod
    def clear_cache(older_than_days: Optional[int] = None) -> int:
        """
        Clear cached summaries.
        
        Args:
            older_than_days: If provided, only clear summaries older than this many days
            
        Returns:
            Number of summaries cleared
        """
        try:
            with get_cursor() as cursor:
                if older_than_days:
                    query = """
                        DELETE FROM label_summaries 
                        WHERE created_at < now() - INTERVAL '%s days'
                    """
                    cursor.execute(query, (older_than_days,))
                else:
                    query = "DELETE FROM label_summaries"
                    cursor.execute(query)
                
                deleted_count = cursor.rowcount
                
                logger.info(f"Cleared {deleted_count} label summaries from cache")
                return deleted_count
                
        except Exception as e:
            logger.error(f"Error clearing summaries cache: {e}")
            return 0
    
    @staticmethod
    def get_cache_stats() -> Dict[str, int]:
        """
        Get statistics about the cache.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total_summaries,
                        COUNT(DISTINCT model_used) as unique_models,
                        MIN(created_at) as oldest_entry,
                        MAX(created_at) as newest_entry
                    FROM label_summaries
                """)
                result = cursor.fetchone()
                
                if result:
                    return {
                        'total_summaries': result['total_summaries'],
                        'unique_models': result['unique_models'],
                        'oldest_entry': result['oldest_entry'].isoformat() if result['oldest_entry'] else None,
                        'newest_entry': result['newest_entry'].isoformat() if result['newest_entry'] else None
                    }
                
        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            
        return {'total_summaries': 0, 'unique_models': 0, 'oldest_entry': None, 'newest_entry': None} 
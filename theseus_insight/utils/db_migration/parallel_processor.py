#!/usr/bin/env python3
"""
Parallel processing support for database migration.

Provides dependency resolution and parallel execution for import/export operations.
"""

import logging
from typing import Dict, List, Set, Tuple, Any, Callable, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class TableStatus(Enum):
    """Status of table processing."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TableDependency:
    """Represents a table and its dependencies."""
    name: str
    depends_on: Set[str]
    status: TableStatus = TableStatus.PENDING
    result: Optional[Any] = None
    error: Optional[Exception] = None


class DependencyResolver:
    """Resolves table dependencies for parallel processing."""
    
    # Define table dependencies
    TABLE_DEPENDENCIES = {
        # Independent tables (no foreign key dependencies)
        "research_profiles": set(),
        "topics": set(),
        "model_catalog": set(),
        "research_interests": set(),
        
        # Tables that depend on research_profiles
        "profile_research_interests": {"research_profiles"},
        
        # Tables that depend on papers
        "papers": set(),  # Papers itself has no dependencies
        "paper_fulltext": {"papers"},
        "paper_profile_scores": {"papers", "research_profiles"},
        "paper_topics": {"papers", "topics"},
        "paper_research_interests": {"papers", "research_interests"},
        
        # Tables with complex dependencies
        "mindmap_reports": {"papers"},
        "topic_metrics": {"topics"},
        "research_interest_metrics": {"research_interests"},
        
        # Independent content tables
        "podcasts": set(),
        "newsletters": set(),
        "literature_reviews": set(),
        "research_runs": set(),
        "research_agent_state": {"research_runs"},
        "label_summaries": set(),
    }
    
    def __init__(self, tables: List[str]):
        """
        Initialize with list of tables to process.
        
        Args:
            tables: List of table names to process
        """
        self.dependencies = {}
        for table in tables:
            deps = self.TABLE_DEPENDENCIES.get(table, set())
            # Only include dependencies that are also being processed
            active_deps = deps.intersection(set(tables))
            self.dependencies[table] = TableDependency(table, active_deps)
    
    def get_ready_tables(self) -> List[str]:
        """
        Get tables that are ready to be processed.
        
        Returns:
            List of table names that have no pending dependencies
        """
        ready = []
        
        for table_name, dep in self.dependencies.items():
            if dep.status != TableStatus.PENDING:
                continue
                
            # Check if all dependencies are completed
            deps_satisfied = all(
                self.dependencies[dep_name].status == TableStatus.COMPLETED
                for dep_name in dep.depends_on
            )
            
            if deps_satisfied:
                ready.append(table_name)
        
        return ready
    
    def mark_in_progress(self, table: str):
        """Mark a table as being processed."""
        self.dependencies[table].status = TableStatus.IN_PROGRESS
    
    def mark_completed(self, table: str, result: Any = None):
        """Mark a table as successfully processed."""
        self.dependencies[table].status = TableStatus.COMPLETED
        self.dependencies[table].result = result
    
    def mark_failed(self, table: str, error: Exception):
        """Mark a table as failed."""
        self.dependencies[table].status = TableStatus.FAILED
        self.dependencies[table].error = error
    
    def all_completed(self) -> bool:
        """Check if all tables have been processed."""
        return all(
            dep.status in (TableStatus.COMPLETED, TableStatus.FAILED)
            for dep in self.dependencies.values()
        )
    
    def get_execution_order(self) -> List[List[str]]:
        """
        Get the optimal execution order as levels.
        
        Returns:
            List of lists, where each inner list contains tables
            that can be processed in parallel
        """
        levels = []
        processed = set()
        
        while len(processed) < len(self.dependencies):
            level = []
            
            for table_name, dep in self.dependencies.items():
                if table_name in processed:
                    continue
                    
                # Check if all dependencies are processed
                if dep.depends_on.issubset(processed):
                    level.append(table_name)
            
            if not level:
                # Circular dependency or error
                remaining = set(self.dependencies.keys()) - processed
                logger.error(f"Cannot resolve dependencies for tables: {remaining}")
                break
                
            levels.append(level)
            processed.update(level)
        
        return levels


class ParallelProcessor:
    """Handles parallel processing of tables with dependency resolution."""
    
    def __init__(self, max_workers: int = 4):
        """
        Initialize parallel processor.
        
        Args:
            max_workers: Maximum number of parallel workers
        """
        self.max_workers = max_workers
    
    def process_tables(
        self,
        tables: List[str],
        process_func: Callable[[str], Any],
        progress_callback: Optional[Callable[[str, str, float], None]] = None
    ) -> Dict[str, Any]:
        """
        Process tables in parallel respecting dependencies.
        
        Args:
            tables: List of tables to process
            process_func: Function to process each table
            progress_callback: Optional callback(table, status, progress)
            
        Returns:
            Dictionary of results keyed by table name
        """
        resolver = DependencyResolver(tables)
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Track active futures
            active_futures: Dict[Future, str] = {}
            completed_count = 0
            total_count = len(tables)
            
            while not resolver.all_completed():
                # Submit ready tables
                ready_tables = resolver.get_ready_tables()
                
                for table in ready_tables:
                    resolver.mark_in_progress(table)
                    
                    if progress_callback:
                        progress = (completed_count / total_count) * 100
                        progress_callback(table, "starting", progress)
                    
                    future = executor.submit(process_func, table)
                    active_futures[future] = table
                
                # Wait for at least one to complete
                if active_futures:
                    done_futures = []
                    
                    for future in as_completed(active_futures):
                        table = active_futures[future]
                        
                        try:
                            result = future.result()
                            resolver.mark_completed(table, result)
                            results[table] = result
                            
                            completed_count += 1
                            if progress_callback:
                                progress = (completed_count / total_count) * 100
                                progress_callback(table, "completed", progress)
                                
                        except Exception as e:
                            logger.error(f"Failed to process {table}: {e}")
                            resolver.mark_failed(table, e)
                            results[table] = {"error": str(e)}
                            
                            completed_count += 1
                            if progress_callback:
                                progress = (completed_count / total_count) * 100
                                progress_callback(table, "failed", progress)
                        
                        done_futures.append(future)
                    
                    # Remove completed futures
                    for future in done_futures:
                        del active_futures[future]
        
        return results
    
    def get_optimal_order(self, tables: List[str]) -> List[List[str]]:
        """
        Get the optimal execution order for tables.
        
        Args:
            tables: List of table names
            
        Returns:
            List of levels, each containing tables that can run in parallel
        """
        resolver = DependencyResolver(tables)
        return resolver.get_execution_order()


class ParallelExporter:
    """Parallel exporter using the parallel processor."""
    
    def __init__(self, exporter, max_workers: int = 4):
        """
        Initialize parallel exporter.
        
        Args:
            exporter: Instance of StreamingDatabaseExporter
            max_workers: Maximum parallel workers
        """
        self.exporter = exporter
        self.processor = ParallelProcessor(max_workers)
    
    def export_tables_parallel(
        self,
        tables: List[str],
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Export tables in parallel.
        
        Args:
            tables: List of tables to export
            progress_callback: Optional progress callback
            
        Returns:
            Export results
        """
        # Define export methods for each table
        export_methods = {
            "papers": lambda: self.exporter.export_papers_optimized(),
            "podcasts": lambda: self.exporter.export_table_streaming(
                "podcasts", "SELECT * FROM podcasts ORDER BY id DESC", "podcasts.json"
            ),
            "newsletters": lambda: self.exporter.export_table_streaming(
                "newsletters", "SELECT * FROM newsletters ORDER BY id DESC", "newsletters.json"
            ),
            "literature_reviews": lambda: self.exporter.export_table_streaming(
                "lit_reviews", "SELECT * FROM lit_reviews ORDER BY id DESC", "literature_reviews.json"
            ),
            "research_profiles": lambda: self.exporter.export_table_streaming(
                "research_profiles", "SELECT * FROM research_profiles ORDER BY id DESC", "research_profiles.json"
            ),
            # Add more tables as needed
        }
        
        def process_table(table_name: str) -> Any:
            """Process a single table export."""
            if table_name in export_methods:
                return export_methods[table_name]()
            else:
                raise ValueError(f"No export method defined for table: {table_name}")
        
        # Create wrapper for progress callback
        def wrapped_progress(table: str, status: str, progress: float):
            if progress_callback:
                progress_callback(
                    int(progress), 
                    100, 
                    f"Exporting {table} ({status})"
                )
        
        return self.processor.process_tables(tables, process_table, wrapped_progress)


class ParallelImporter:
    """Parallel importer using the parallel processor."""
    
    def __init__(self, importer, max_workers: int = 4):
        """
        Initialize parallel importer.
        
        Args:
            importer: Instance of TransactionalDatabaseImporter
            max_workers: Maximum parallel workers
        """
        self.importer = importer
        self.processor = ParallelProcessor(max_workers)
    
    def import_tables_parallel(
        self,
        file_map: Dict[str, str],
        skip_duplicates: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Import tables in parallel respecting dependencies.
        
        Args:
            file_map: Dictionary mapping table names to file paths
            skip_duplicates: Whether to skip duplicates
            progress_callback: Optional progress callback
            
        Returns:
            Import results
        """
        # Define import methods for each table
        import_methods = {
            "papers": self.importer.import_papers_optimized,
            "podcasts": self.importer.import_podcasts_optimized,
            "newsletters": self.importer.import_newsletters_optimized,
            "literature_reviews": self.importer.import_literature_reviews_optimized,
            "research_profiles": self.importer.import_research_profiles_optimized,
            "profile_research_interests": self.importer.import_profile_research_interests_optimized,
            "paper_profile_scores": self.importer.import_paper_profile_scores_optimized,
        }
        
        def process_table(table_name: str) -> Any:
            """Process a single table import."""
            if table_name not in file_map:
                return {"error": "File not found"}
                
            file_path = file_map[table_name]
            
            if table_name in import_methods:
                return import_methods[table_name](file_path, skip_duplicates)
            else:
                return {"error": f"No import method defined for table: {table_name}"}
        
        # Create wrapper for progress callback
        def wrapped_progress(table: str, status: str, progress: float):
            if progress_callback:
                progress_callback(
                    int(progress),
                    100,
                    f"Importing {table} ({status})"
                )
        
        # Get tables that have files
        tables_to_import = [t for t in file_map.keys() if t in import_methods]
        
        return self.processor.process_tables(
            tables_to_import, 
            process_table, 
            wrapped_progress
        )
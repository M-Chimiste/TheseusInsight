"""PostgreSQL connection helpers for Theseus Insight.

This lightweight wrapper centralises connection creation so that the rest of
 the codebase can start moving to Postgres without an ORM. It intentionally
 mirrors the context-manager pattern already used in `PaperDatabase.get_cursor`.
 As we complete the migration, higher-level abstractions will replace the
 remaining SQLite logic.
"""
from __future__ import annotations

import os
import logging
from contextlib import contextmanager
import asyncpg
import asyncio
from typing import Optional, AsyncGenerator

import psycopg
from psycopg.rows import dict_row

from .pool import PooledConnectionManager

logger = logging.getLogger(__name__)

# Example: postgresql://user:password@localhost:5432/dbname
DATABASE_URL: str = os.getenv(
    "DATABASE_URL", "postgresql://theseus:theseus@localhost:5432/theseusdb"
)

# Enable connection pooling
USE_CONNECTION_POOL = os.getenv("DB_USE_POOL", "true").lower() == "true"

# Global connection pool manager
_pool_manager: PooledConnectionManager = None

def _get_pool_manager() -> PooledConnectionManager:
    """Get or create the global connection pool manager."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = PooledConnectionManager(DATABASE_URL)
        logger.info("Initialized global connection pool manager")
    return _pool_manager


@contextmanager
def get_cursor(*, autocommit: bool = True):
    """Context manager that yields a dict-row cursor and commits on exit.
    
    This now uses connection pooling by default for better performance.
    Set DB_USE_POOL=false to disable pooling.
    """
    if USE_CONNECTION_POOL:
        # Use pooled connection
        pool_manager = _get_pool_manager()
        with pool_manager.get_cursor(autocommit=autocommit) as cur:
            yield cur
            
        # Log stats periodically (every 100 uses)
        if hasattr(get_cursor, '_call_count'):
            get_cursor._call_count += 1
        else:
            get_cursor._call_count = 1
            
        if get_cursor._call_count % 100 == 0:
            pool_manager.log_stats()
    else:
        # Legacy non-pooled connection
        with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                yield cur
            if autocommit:
                conn.commit()


@contextmanager
def get_connection(autocommit: bool = False):
    """Get a database connection directly.
    
    This is useful for operations that need direct connection access like COPY.
    Note: This returns a context manager to ensure proper cleanup.
    
    Args:
        autocommit: Whether to enable autocommit mode
        
    Yields:
        psycopg connection object
    """
    if USE_CONNECTION_POOL:
        pool_manager = _get_pool_manager()
        # Use the pool's connection context manager
        with pool_manager.get_connection(autocommit=autocommit) as conn:
            yield conn
    else:
        conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        try:
            if autocommit:
                conn.autocommit = True
            yield conn
        finally:
            conn.close()


def get_pool_stats():
    """Get connection pool statistics.
    
    Returns:
        dict: Pool statistics or None if pooling is disabled
    """
    if USE_CONNECTION_POOL and _pool_manager:
        return _pool_manager.get_pool_stats()
    return None

# Async connection pool support
import asyncpg

_async_pool: asyncpg.Pool = None

async def get_connection_pool() -> asyncpg.Pool:
    """Get or create an async connection pool for asyncpg.
    
    Returns:
        asyncpg.Pool: The connection pool
    """
    global _async_pool
    
    # Check if we have a cached pool and if it belongs to the current loop
    current_loop = asyncio.get_running_loop()
    
    if _async_pool is not None:
        # Check if the pool is closed or belongs to a different loop
        if _async_pool._loop is not current_loop:
            # We are in a different loop (e.g. running in a thread), create a new pool for this loop
            # We don't overwrite the global _async_pool as that might be used by the main loop
            # Instead, we just return a new pool for this context
            # Note: This new pool won't be cached globally, which is fine for one-off tasks
            new_pool = await asyncpg.create_pool(
                DATABASE_URL,
                min_size=5,
                max_size=20,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                command_timeout=60.0,
            )
            logger.info(f"Initialized new async connection pool for separate thread/loop")
            return new_pool
            
    if _async_pool is None:
        # Configure pool with proper limits for multi-worker scenarios
        # Default max_size=10 is too low for multiple workers
        _async_pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=10,      # Minimum connections to maintain
            max_size=50,      # Maximum connections (increased for multi-worker)
            max_queries=50000, # Max queries per connection before recycling
            max_inactive_connection_lifetime=300.0,  # Close idle connections after 5 min
            command_timeout=60.0,  # Command timeout
        )
        logger.info(f"Initialized async connection pool (min=10, max=50)")
    return _async_pool

async def close_connection_pool():
    """Close the async connection pool."""
    global _async_pool
    if _async_pool:
        await _async_pool.close()
        _async_pool = None
        logger.info("Closed async connection pool")

# Export migrations module
from .migrations import check_and_apply_migrations, MigrationRunner

__all__ = ['get_cursor', 'get_connection', 'DATABASE_URL', 'check_and_apply_migrations', 'MigrationRunner', 'get_pool_stats', 'get_connection_pool', 'close_connection_pool'] 
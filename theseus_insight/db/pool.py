"""Connection pooling implementation for PostgreSQL."""
from __future__ import annotations

import os
import time
import logging
from contextlib import contextmanager
from typing import Optional, Dict, Any
import atexit
from datetime import datetime, timedelta

import psycopg
from psycopg.rows import dict_row

try:
    from psycopg_pool import ConnectionPool
    POOL_AVAILABLE = True
except ImportError:
    # Pool module not available - will use fallback
    POOL_AVAILABLE = False
    ConnectionPool = None

logger = logging.getLogger(__name__)

# Pool configuration from environment
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "5"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
POOL_TIMEOUT = float(os.getenv("DB_POOL_TIMEOUT", "30.0"))
POOL_MAX_LIFETIME = float(os.getenv("DB_POOL_MAX_LIFETIME", "3600.0"))  # 1 hour

# Enable pool statistics
ENABLE_POOL_STATS = os.getenv("DB_POOL_STATS", "true").lower() == "true"


class PooledConnectionManager:
    """Manages a connection pool for PostgreSQL with statistics."""
    
    def __init__(self, database_url: str):
        """Initialize the connection pool.
        
        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self._pool: Optional[ConnectionPool] = None
        self._stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "wait_time_total": 0.0,
            "wait_count": 0,
            "timeouts": 0,
            "errors": 0,
            "last_reset": datetime.now()
        }
        
        if not POOL_AVAILABLE:
            logger.warning("psycopg pool module not available. Connection pooling will be disabled.")
            logger.warning("To enable pooling, install with: pip install 'psycopg[pool]'")
        
    def _create_pool(self) -> Optional[ConnectionPool]:
        """Create a new connection pool."""
        if not POOL_AVAILABLE:
            return None
            
        logger.info(f"Creating connection pool: min={POOL_MIN_SIZE}, max={POOL_MAX_SIZE}")
        
        # Connection kwargs to ensure dict rows
        kwargs = {
            "row_factory": dict_row,
            "autocommit": False,  # We'll handle commits explicitly
        }
        
        pool = ConnectionPool(
            self.database_url,
            min_size=POOL_MIN_SIZE,
            max_size=POOL_MAX_SIZE,
            timeout=POOL_TIMEOUT,
            max_lifetime=POOL_MAX_LIFETIME,
            kwargs=kwargs,
            name="theseus_pool"
        )
        
        # Register cleanup on exit
        atexit.register(self._cleanup_pool, pool)
        
        return pool
    
    def _cleanup_pool(self, pool: Optional[ConnectionPool]) -> None:
        """Clean up the connection pool on exit."""
        if not pool:
            return
        try:
            pool.close()
            logger.info("Connection pool closed successfully")
        except Exception as e:
            logger.error(f"Error closing connection pool: {e}")
    
    @property
    def pool(self) -> ConnectionPool:
        """Get or create the connection pool."""
        if not POOL_AVAILABLE:
            return None
        if self._pool is None:
            self._pool = self._create_pool()
        return self._pool
    
    @contextmanager
    def get_connection(self, autocommit: bool = True):
        """Get a connection from the pool.
        
        Args:
            autocommit: Whether to commit on exit
            
        Yields:
            psycopg connection object
        """
        # Fallback to non-pooled connection if pool not available
        if not POOL_AVAILABLE:
            conn = psycopg.connect(self.database_url, row_factory=dict_row)
            try:
                if autocommit:
                    conn.autocommit = True
                yield conn
            finally:
                conn.close()
            return
            
        start_time = time.time()
        connection = None
        
        try:
            # Get connection from pool
            connection = self.pool.getconn()
            wait_time = time.time() - start_time
            
            # Update statistics
            if wait_time > 0.001:  # Waited for connection
                self._stats["wait_time_total"] += wait_time
                self._stats["wait_count"] += 1
                self._stats["connections_reused"] += 1
            else:
                self._stats["connections_created"] += 1
            
            # Log slow acquisitions
            if wait_time > 1.0:
                logger.warning(f"Slow connection acquisition: {wait_time:.2f}s")
            
            yield connection
            
            # Commit if requested
            if autocommit:
                connection.commit()
                
        except psycopg.PoolTimeout:
            self._stats["timeouts"] += 1
            logger.error(f"Connection pool timeout after {POOL_TIMEOUT}s")
            raise
        except Exception as e:
            self._stats["errors"] += 1
            if connection:
                connection.rollback()
            raise
        finally:
            # Return connection to pool
            if connection and self.pool:
                self.pool.putconn(connection)
    
    @contextmanager
    def get_cursor(self, autocommit: bool = True):
        """Get a cursor from a pooled connection.
        
        Args:
            autocommit: Whether to commit on exit
            
        Yields:
            psycopg cursor with dict rows
        """
        with self.get_connection(autocommit=autocommit) as conn:
            with conn.cursor() as cur:
                yield cur
    
    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        stats = self._stats.copy()
        
        # Add pool availability status
        stats["pool_enabled"] = POOL_AVAILABLE
        
        # Add pool info if available
        if self._pool and POOL_AVAILABLE:
            pool_info = self._pool.get_stats()
            stats.update({
                "pool_size": pool_info["pool_size"],
                "pool_available": pool_info["pool_available"], 
                "requests_queued": pool_info["requests_queued"],
            })
        else:
            stats.update({
                "pool_size": 0,
                "pool_available": 0,
                "requests_queued": 0,
            })
        
        # Calculate averages
        if stats["wait_count"] > 0:
            stats["avg_wait_time"] = stats["wait_time_total"] / stats["wait_count"]
        else:
            stats["avg_wait_time"] = 0.0
        
        # Connection reuse ratio
        total_uses = stats["connections_created"] + stats["connections_reused"]
        if total_uses > 0:
            stats["reuse_ratio"] = stats["connections_reused"] / total_uses
        else:
            stats["reuse_ratio"] = 0.0
        
        return stats
    
    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self._stats = {
            "connections_created": 0,
            "connections_reused": 0,
            "wait_time_total": 0.0,
            "wait_count": 0,
            "timeouts": 0,
            "errors": 0,
            "last_reset": datetime.now()
        }
    
    def log_stats(self) -> None:
        """Log current pool statistics."""
        if not ENABLE_POOL_STATS:
            return
            
        stats = self.get_pool_stats()
        logger.info(
            f"Pool Stats - Size: {stats.get('pool_size', 'N/A')}, "
            f"Available: {stats.get('pool_available', 'N/A')}, "
            f"Reuse: {stats.get('reuse_ratio', 0):.1%}, "
            f"Avg Wait: {stats.get('avg_wait_time', 0):.3f}s"
        )
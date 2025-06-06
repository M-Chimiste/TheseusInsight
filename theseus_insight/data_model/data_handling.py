import os
import json
import datetime
import base64
import hashlib
from contextlib import contextmanager
import sqlite3
import numpy as np
from ..utils.common_utils import cosine_similarity


from .papers import Newsletter, Paper, Logs, Podcast

INITIAL_PROVIDERS = [
    {"id": 1, "name": "ollama"},
    {"id": 2, "name": "gemini"},
    {"id": 3, "name": "openai"},
    {"id": 4, "name": "sentence-transformers"},
    {"id": 5, "name": "llamacpp"},
    {"id": 6, "name": "anthropic"},
    {"id": 7, "name": "ollama-embed"},
    {"id": 8, "name": "custom-oai"},
]


class PaperDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure the directory structure exists before initializing the database
        self._ensure_directory_structure()
        self.sqlite_vec_path = os.getenv("SQLITE_VEC_PATH")
        self.vector_search_enabled = False
        self._check_sqlite_vec()
        self._initialize_db()

    def _ensure_directory_structure(self):
        """Ensure the directory structure for the database and related files exists."""
        # Create the database directory
        db_dir = os.path.dirname(self.db_path)
        if db_dir:  # Only create if there's actually a directory component
            os.makedirs(db_dir, exist_ok=True)
        
        # Create other necessary directories
        directories_to_create = [
            "data/newsletters",
            "data/podcasts", 
            "data/visualizations",
            "data/temp"
        ]
        
        for directory in directories_to_create:
            os.makedirs(directory, exist_ok=True)

    def _check_sqlite_vec(self):
        """Check if the sqlite_vec extension can be loaded."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.enable_load_extension(True)
            if self.sqlite_vec_path:
                conn.load_extension(self.sqlite_vec_path)
            else:
                conn.load_extension("sqlite_vec")
            self.vector_search_enabled = True
            conn.close()
        except Exception:
            self.vector_search_enabled = False
            try:
                if 'conn' in locals():
                    conn.close()
            except Exception:
                pass


    @contextmanager
    def get_cursor(self, register_vectors=True):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if register_vectors and self.vector_search_enabled:

                try:
                    conn.enable_load_extension(True)
                    if self.sqlite_vec_path:
                        conn.load_extension(self.sqlite_vec_path)
                    else:
                        conn.load_extension("sqlite_vec")
                except Exception:
                    self.vector_search_enabled = False

            cursor = conn.cursor()
            yield cursor
            conn.commit()
        finally:
            conn.close()

    def _initialize_db(self):
        """Initialize database tables and indices if they don't exist."""
        with self.get_cursor(register_vectors=False) as cursor:
            cursor.execute(
                "CREATE TABLE IF NOT EXISTS papers ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "title TEXT NOT NULL,"
                "abstract TEXT NOT NULL,"
                "date TEXT NOT NULL,"
                "date_run TEXT NOT NULL,"
                "score REAL,"
                "rationale TEXT,"
                "related INTEGER DEFAULT 0,"
                "cosine_similarity REAL,"
                "url TEXT UNIQUE,"
                "embedding_model TEXT,"
                "embedding BLOB,"
                "text TEXT"
                ")"
            )

            # Add the text column if it doesn't exist (for existing databases)
            try:
                cursor.execute("ALTER TABLE papers ADD COLUMN text TEXT")
            except Exception:
                # Column likely already exists, ignore
                pass

            cursor.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5("
                "title, abstract, content='papers', content_rowid='id')"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS logs ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "task_id TEXT NOT NULL,"
                "status TEXT NOT NULL,"
                "datetime_run TEXT"
                ")"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS newsletters ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "content TEXT NOT NULL,"
                "start_date TEXT NOT NULL,"
                "end_date TEXT NOT NULL,"
                "date_sent TEXT NOT NULL"
                ")"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS podcasts ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "title TEXT NOT NULL,"
                "date TEXT NOT NULL,"
                "script TEXT NOT NULL,"
                "description TEXT NOT NULL"
                ")"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS settings ("
                "key TEXT PRIMARY KEY,"
                "value TEXT NOT NULL"
                ")"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS model_providers ("
                "id INTEGER PRIMARY KEY,"
                "name TEXT NOT NULL UNIQUE"
                ")"
            )
            for provider in INITIAL_PROVIDERS:
                cursor.execute(
                    "INSERT OR IGNORE INTO model_providers (id, name) VALUES (?, ?)",
                    (provider["id"], provider["name"],),
                )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "task_id TEXT PRIMARY KEY,"
                "task_type TEXT NOT NULL,"
                "status TEXT NOT NULL,"
                "config_json TEXT NOT NULL,"
                "start_time TEXT NOT NULL,"
                "end_time TEXT,"
                "error TEXT,"
                "result_json TEXT,"
                "progress REAL DEFAULT 0,"
                "current_step TEXT,"
                "message TEXT"
                ")"
            )

            cursor.execute(
                "CREATE TABLE IF NOT EXISTS lit_reviews ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                "research_question TEXT NOT NULL,"
                "summary_json TEXT NOT NULL,"
                "trace_json TEXT NOT NULL,"
                "report_text TEXT,"
                "created_ts TEXT DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            
            # Add report_text column to existing lit_reviews table if it doesn't exist
            try:
                cursor.execute("ALTER TABLE lit_reviews ADD COLUMN report_text TEXT")
            except Exception:
                # Column likely already exists, ignore
                pass

    def insert_podcast(self, podcast: Podcast):
        # Validate date formats
        try:
            datetime.datetime.strptime(podcast.date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")
        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO podcasts (title, date, script, description) VALUES (?, ?, ?, ?)",
                (
                    podcast.title,
                    podcast.date,
                    json.dumps(podcast.script),
                    podcast.description,
                ),
            )
            
    def paper_exists_by_url(self, url: str) -> bool:
        """Check if a paper with the given URL already exists in the database."""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM papers WHERE url = ?', (url,))
            count = cursor.fetchone()[0]
            return count > 0

    def paper_exists_by_title(self, title: str) -> bool:
        """Check if a paper with the given title already exists in the database."""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM papers WHERE title = ?', (title,))
            count = cursor.fetchone()[0]
            return count > 0

    def get_paper_by_url(self, url: str) -> dict | None:
        """Get paper details by URL if it exists."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, title, abstract, date, date_run, score, rationale, related,"
                " cosine_similarity, url, embedding_model, embedding, text FROM papers WHERE url = ?",
                (url,),
            )
            row = cursor.fetchone()
            if row:
                # Convert date objects to strings if they're not already strings
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                return {
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': row[11],
                    'text': row[12]
                }
            return None

    def insert_paper(self, paper: Paper, skip_duplicates: bool = True) -> bool:
        """
        Insert a paper into the database.
        
        Args:
            paper: Paper object to insert
            skip_duplicates: If True, skip insertion if paper URL already exists
            
        Returns:
            bool: True if paper was inserted, False if skipped due to duplicate
        """
        required_fields = [
            'title', 'abstract', 'date', 'date_run', 
            'score', 'rationale', 'related', 'cosine_similarity', 'url', 'embedding_model'
        ]
        for field in required_fields:
            if not hasattr(paper, field) or getattr(paper, field) is None:
                raise ValueError(f"Paper object is missing required field: {field}")

        if not isinstance(paper.score, (int, float)):
            raise ValueError("Score must be a number")
        if not isinstance(paper.related, bool):
            raise ValueError("Related must be a boolean")
        if not isinstance(paper.cosine_similarity, float):
            raise ValueError("Cosine similarity must be a float")

        # Validate date
        try:
            datetime.datetime.strptime(paper.date, '%Y-%m-%d')
            datetime.datetime.strptime(paper.date_run, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")

        # Check for duplicates if requested
        if skip_duplicates and self.paper_exists_by_url(paper.url):
            return False  # Paper already exists, skipping

        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO papers (title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model, embedding, text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    paper.title,
                    paper.abstract,
                    paper.date,
                    paper.date_run,
                    paper.score,
                    paper.rationale,
                    int(paper.related),
                    paper.cosine_similarity,
                    paper.url,
                    paper.embedding_model,
                    json.dumps(paper.embedding) if paper.embedding is not None else None,
                    getattr(paper, 'text', None),  # Optional text field
                ),
            )

            cursor.execute(
                "INSERT INTO papers_fts(rowid, title, abstract) VALUES (last_insert_rowid(), ?, ?)",
                (
                    paper.title,
                    paper.abstract,
                ),
            )
        return True  # Paper was inserted

    def insert_newsletter(self, newsletter: Newsletter):
        required_fields = ['content', 'start_date', 'end_date', 'date_sent']
        for field in required_fields:
            if not hasattr(newsletter, field) or getattr(newsletter, field) is None:
                raise ValueError(f"Newsletter object is missing required field: {field}")

        # Validate date format
        try:
            datetime.datetime.strptime(newsletter.start_date, '%Y-%m-%d')
            datetime.datetime.strptime(newsletter.end_date, '%Y-%m-%d')
            datetime.datetime.strptime(newsletter.date_sent, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")

        # Validate order
        if newsletter.start_date > newsletter.end_date:
            raise ValueError("start_date cannot be after end_date")

        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO newsletters (content, start_date, end_date, date_sent) VALUES (?, ?, ?, ?)",
                (
                    newsletter.content,
                    newsletter.start_date,
                    newsletter.end_date,
                    newsletter.date_sent,
                ),
            )

    def insert_log(self, log: Logs):
        required_fields = ['task_id', 'status']
        for field in required_fields:
            if not hasattr(log, field) or getattr(log, field) is None:
                raise ValueError(f"Log object is missing required field: {field}")

        datetime_run = log.datetime_run or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # check for log existence
        with self.get_cursor() as cursor:
            cursor.execute('SELECT status FROM logs WHERE task_id = ?', (log.task_id,))
            row = cursor.fetchone()
            row = row[0] if row else None
        # Insert a new log if it doesn't exist
        if not row:
            with self.get_cursor() as cursor:
                cursor.execute(
                    'INSERT INTO logs (task_id, status, datetime_run) VALUES (?, ?, ?)',
                    (log.task_id, log.status, datetime_run),
                )
        # Only update the status
        else:
            with self.get_cursor() as cursor:
                cursor.execute(
                    'UPDATE logs SET status = ? WHERE task_id = ?',
                    (log.status, log.task_id),
                )

    def get_recent_logs(self, limit: int = 100, from_date: str = None, to_date: str = None):
        query = '''SELECT task_id, status, datetime_run
                   FROM logs'''
        params = []
        conditions = []

        if from_date:
            conditions.append("datetime_run >= ?")
            params.append(f"{from_date} 00:00:00")
        
        if to_date:
            conditions.append("datetime_run <= ?")
            params.append(f"{to_date} 23:59:59")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY datetime_run DESC LIMIT ?"
        params.append(limit)

        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert datetime objects to strings if they're not already strings
                datetime_str = row[2].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row[2], 'strftime') else str(row[2])
                
                result.append({
                    'task_id': row[0],
                    'status': row[1],
                    'datetime_run': datetime_str
                })
            return result

    def get_recent_task_history(self, limit: int = 100, from_date: str = None, to_date: str = None):
        """Get recent task history with complete information including task type."""
        query = '''SELECT task_id, task_type, status, start_time, end_time, 
                          progress, current_step, message, error
                   FROM tasks'''
        params = []
        conditions = []

        if from_date:
            conditions.append("start_time >= ?")
            params.append(f"{from_date} 00:00:00")
        
        if to_date:
            conditions.append("start_time <= ?")
            params.append(f"{to_date} 23:59:59")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        with self.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert datetime objects to strings if they're not already strings
                start_time_str = row[3].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row[3], 'strftime') else str(row[3])
                end_time_str = row[4].strftime('%Y-%m-%d %H:%M:%S') if hasattr(row[4], 'strftime') and row[4] else None
                
                result.append({
                    'task_id': row[0],
                    'task_type': row[1],
                    'status': row[2],
                    'start_time': start_time_str,
                    'end_time': end_time_str,
                    'progress': row[5],
                    'current_step': row[6],
                    'message': row[7],
                    'error': row[8]
                })
            return result

    def fetch_all_podcasts(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert date objects to strings if they're not already strings
                date_str = row[2].strftime('%Y-%m-%d') if hasattr(row[2], 'strftime') else str(row[2])
                
                result.append({
                    'id': row[0],
                    'title': row[1],
                    'date': date_str,
                    'script': json.loads(row[3]),
                    'description': row[4]
                })
            return result

    def fetch_podcast_by_id(self, podcast_id: int):
        """Fetch a single podcast by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts WHERE id = ?", (podcast_id,))
            row = cursor.fetchone()
            if row:
                # Convert date objects to strings if they're not already strings
                date_str = row[2].strftime('%Y-%m-%d') if hasattr(row[2], 'strftime') else str(row[2])
                
                return {
                    'id': row[0],
                    'title': row[1],
                    'date': date_str,
                    'script': json.loads(row[3]), # Ensure script is parsed from JSON string
                    'description': row[4]
                }
            return None

    def delete_podcast(self, title: str):
        """Delete a podcast from the database by its title."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM podcasts WHERE title = ?", (title,))

    def delete_podcast_by_id(self, podcast_id: int):
        """Delete a podcast from the database by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM podcasts WHERE id = ?", (podcast_id,))
            return cursor.rowcount > 0  # Return True if a row was actually deleted

    def update_podcast_title(self, podcast_id: int, new_title: str):
        """Update the title of a podcast by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("UPDATE podcasts SET title = ? WHERE id = ?", (new_title, podcast_id))
            return cursor.rowcount > 0  # Return True if a row was actually updated

    def fetch_all_newsletters(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, content, start_date, end_date, date_sent FROM newsletters ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert date objects to strings if they're not already strings
                start_date_str = row[2].strftime('%Y-%m-%d') if hasattr(row[2], 'strftime') else str(row[2])
                end_date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_sent_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                result.append({
                    'id': row[0],
                    'content': row[1],
                    'start_date': start_date_str,
                    'end_date': end_date_str,
                    'date_sent': date_sent_str
                })
            return result

    def fetch_all_papers(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model, embedding FROM papers ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert date objects to strings if they're not already strings
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                result.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': row[11]
                })
            return result

    def find_similar_papers(self, query_embedding: list, limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to the given embedding using cosine similarity.
        
        Args:
            query_embedding: List of floats representing the query embedding
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of papers with similarity scores, ordered by similarity (highest first)
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, abstract, date, date_run, score, rationale, related,
                       cosine_similarity, url, embedding_model, embedding
                FROM papers
                WHERE embedding IS NOT NULL
            """
            )
            rows = cursor.fetchall()

        results = []
        query_vec = np.array(query_embedding, dtype=float)
        for row in rows:
            try:
                emb_list = json.loads(row[11]) if row[11] is not None else None
            except Exception:
                continue
            if emb_list is None:
                continue
            score = float(cosine_similarity(query_vec, np.array(emb_list, dtype=float)))
            if score >= similarity_threshold:
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                results.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': row[11],
                    'similarity_distance': 1 - score,
                    'similarity_score': score,
                })

        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:limit]

    def find_papers_by_semantic_search(self, query_text: str, embedding_model, limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to a text query by first generating an embedding.
        
        Args:
            query_text: Text to search for
            embedding_model: Model instance to generate embeddings
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            List of papers with similarity scores, ordered by similarity (highest first)
        """
        query_embedding = embedding_model.invoke(query_text)
        return self.find_similar_papers(query_embedding, limit, similarity_threshold)

    def get_papers_without_embeddings(self):
        """Get papers that don't have embeddings saved.
        
        Returns:
            List of papers missing embeddings
        """
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model
                FROM papers 
                WHERE embedding IS NULL
                ORDER BY id DESC
            ''')
            
            rows = cursor.fetchall()
            result = []
            for row in rows:
                # Convert date objects to strings if they're not already strings
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                result.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': None
                })
            return result

    def update_paper_embedding(self, paper_id: int, embedding: list):
        """Update the embedding for a specific paper.
        
        Args:
            paper_id: ID of the paper to update
            embedding: List of floats representing the embedding
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE papers
                SET embedding = ?
                WHERE id = ?
                """,
                (json.dumps(embedding) if embedding is not None else None, paper_id),
            )


    def get_paper_embedding(self, paper_id: int):
        """Get the embedding for a specific paper.
        
        Args:
            paper_id: ID of the paper
            
        Returns:
            List of floats representing the embedding, or None if not found
        """
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT embedding FROM papers
                WHERE id = ? AND embedding IS NOT NULL
                """,
                (paper_id,),
            )

            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row[0])
                except Exception:
                    return None
            return None

    def find_similar_papers_to_existing(self, paper_id: int, limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to an existing paper using its stored embedding.
        
        Args:
            paper_id: ID of the reference paper
            limit: Maximum number of results to return (excluding the reference paper itself)
            similarity_threshold: Minimum similarity score (0-1)
            
        Returns:
            Dict containing reference paper info and list of similar papers with similarity scores
        """
        # Get the reference paper and its embedding
        with self.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, abstract, date, date_run, score, rationale, related,
                       cosine_similarity, url, embedding_model, embedding
                FROM papers
                WHERE id = ? AND embedding IS NOT NULL
                """,
                (paper_id,),
            )
            reference_row = cursor.fetchone()
            if not reference_row:
                return None
            
            # Convert date objects to strings for reference paper
            ref_date_str = reference_row[3].strftime('%Y-%m-%d') if hasattr(reference_row[3], 'strftime') else str(reference_row[3])
            ref_date_run_str = reference_row[4].strftime('%Y-%m-%d') if hasattr(reference_row[4], 'strftime') else str(reference_row[4])
            
            reference_paper = {
                'id': reference_row[0],
                'title': reference_row[1],
                'abstract': reference_row[2],
                'date': ref_date_str,
                'date_run': ref_date_run_str,
                'score': reference_row[5],
                'rationale': reference_row[6],
                'related': reference_row[7],
                'cosine_similarity': reference_row[8],
                'url': reference_row[9],
                'embedding_model': reference_row[10],
                'embedding': reference_row[11]
            }
            
            try:
                reference_embedding = json.loads(reference_row[11])
            except Exception:
                return None

            # Fetch all other papers with embeddings
            cursor.execute(
                """
                SELECT id, title, abstract, date, date_run, score, rationale, related,
                       cosine_similarity, url, embedding_model, embedding
                FROM papers
                WHERE embedding IS NOT NULL AND id != ?
                """,
                (paper_id,),
            )
            rows = cursor.fetchall()

        query_vec = np.array(reference_embedding, dtype=float)
        similar_papers = []
        for row in rows:
            try:
                emb_list = json.loads(row[11]) if row[11] is not None else None
            except Exception:
                continue
            if emb_list is None:
                continue
            score = float(cosine_similarity(query_vec, np.array(emb_list, dtype=float)))
            if score >= similarity_threshold:
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                similar_papers.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': row[11],
                    'similarity_distance': 1 - score,
                    'similarity_score': score,
                })

        similar_papers.sort(key=lambda x: x['similarity_score'], reverse=True)
        similar_papers = similar_papers[:limit]

        return {
            'reference_paper': reference_paper,
            'similar_papers': similar_papers,
            'total_similar': len(similar_papers),
        }

    # SETTINGS CRUD
    def get_setting(self, key: str):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else None

    def set_setting(self, key, value):
        if not isinstance(value, str):
            key = str(key)
        if not isinstance(key, str):
            key = str(key)
        with self.get_cursor() as cursor:
            cursor.execute('INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value', (key, value))


    def delete_setting(self, key: str):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM settings WHERE key = ?', (key,))

    def get_all_settings(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT key, value FROM settings')
            return dict(cursor.fetchall())

    # Simple XOR-based encryption helpers using a secret from APP_SECRET_KEY
    def _encrypt(self, plaintext: str) -> str:
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = plaintext.encode()
        enc = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return base64.b64encode(enc).decode()

    def _decrypt(self, ciphertext: str) -> str:
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = base64.b64decode(ciphertext.encode())
        dec = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return dec.decode()

    def set_secret_setting(self, key: str, value: str):
        """Encrypt and store a sensitive setting value."""
        self.set_setting(key, self._encrypt(value))

    def get_secret_setting(self, key: str) -> str | None:
        """Retrieve and decrypt a sensitive setting value."""
        enc = self.get_setting(key)
        if enc:
            try:
                return self._decrypt(enc)
            except Exception:
                return None
        return None

    # MODEL PROVIDERS CRUD
    def add_model_provider(self, id: int, name: str):
        with self.get_cursor() as cursor:
            cursor.execute('INSERT INTO model_providers (id, name) VALUES (?, ?) ON CONFLICT DO NOTHING', (id, name))

    def get_model_providers(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT id, name FROM model_providers')
            return [{'id': row[0], 'name': row[1]} for row in cursor.fetchall()]

    def delete_model_provider(self, provider_id: int):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM model_providers WHERE id = ?', (provider_id,))

    # MODELS CRUD
    # def add_model(self, provider_id: int, name: str, config_json: str = None):
    #     with self.get_cursor() as cursor:
    #         cursor.execute('INSERT OR IGNORE INTO models (provider_id, name, config_json) VALUES (?, ?, ?)', (provider_id, name, config_json))

    # def upsert_model(self, provider_id: int, name: str, config_json: str = None):
    #     with self.get_cursor() as cursor:
    #         cursor.execute('''
    #             INSERT INTO models (provider_id, name, config_json) 
    #             VALUES (?, ?, ?)
    #             ON CONFLICT(provider_id, name) 
    #             DO UPDATE SET config_json = excluded.config_json
    #         ''', (provider_id, name, config_json))

    # def get_models(self, provider_id: int = None, name: str = None):
    #     with self.get_cursor() as cursor:
    #         if provider_id is not None and name is not None:
    #             cursor.execute('SELECT id, provider_id, name, config_json FROM models WHERE provider_id = ? AND name = ?', (provider_id, name))
    #             row = cursor.fetchone()
    #             return [{'id': row[0], 'provider_id': row[1], 'name': row[2], 'config_json': row[3]}] if row else []
    #         elif provider_id is not None:
    #             cursor.execute('SELECT id, provider_id, name, config_json FROM models WHERE provider_id = ?', (provider_id,))
    #         else:
    #             cursor.execute('SELECT id, provider_id, name, config_json FROM models')
            
    #         rows = cursor.fetchall() # Ensure fetchall is used
    #         return [
    #             {'id': row[0], 'provider_id': row[1], 'name': row[2], 'config_json': row[3]} for row in rows
    #         ]

    # def delete_model(self, model_id: int):
    #     with self.get_cursor() as cursor:
    #         cursor.execute('DELETE FROM models WHERE id = ?', (model_id,))

    # EMAIL RECIPIENTS
    def get_email_recipients(self):
        val = self.get_setting('email_recipients')
        if val:
            try:
                return json.loads(val)
            except Exception:
                return []
        return []

    def set_email_recipients(self, recipients):
        self.set_setting('email_recipients', json.dumps(recipients))

    # VISUALIZER SETTINGS
    def get_visualizer_settings(self):
        val = self.get_setting('visualizer_settings')
        if val:
            try:
                return json.loads(val)
            except Exception:
                return {}
        return {}

    def set_visualizer_settings(self, settings):
        self.set_setting('visualizer_settings', json.dumps(settings))

    # TASK PERSISTENCE OPERATIONS
    def insert_task(self, task_id: str, task_type: str, status: str, config: dict, start_time: str = None, progress: float = 0, current_step: str = None, message: str = None):
        """Insert a new task into the database."""
        if not start_time:
            start_time = datetime.datetime.now().isoformat()
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks
                (task_id, task_type, status, config_json, start_time, progress, current_step, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (task_id) DO UPDATE SET
                    task_type = EXCLUDED.task_type,
                    status = EXCLUDED.status,
                    config_json = EXCLUDED.config_json,
                    start_time = EXCLUDED.start_time,
                    progress = EXCLUDED.progress,
                    current_step = EXCLUDED.current_step,
                    message = EXCLUDED.message
            ''', (task_id, task_type, status, json.dumps(config), start_time, progress, current_step, message))

    def update_task_status(self, task_id: str, status: str, progress: float = None, current_step: str = None, message: str = None, error: str = None, result: dict = None, end_time: str = None):
        """Update task status and other fields."""
        with self.get_cursor() as cursor:
            # Build dynamic update query based on provided parameters
            fields_to_update = ["status = ?"]
            params = [status]
            
            if progress is not None:
                fields_to_update.append("progress = ?")
                params.append(progress)
            if current_step is not None:
                fields_to_update.append("current_step = ?")
                params.append(current_step)
            if message is not None:
                fields_to_update.append("message = ?")
                params.append(message)
            if error is not None:
                fields_to_update.append("error = ?")
                params.append(error)
            if result is not None:
                fields_to_update.append("result_json = ?")
                params.append(json.dumps(result))
            if end_time is not None:
                fields_to_update.append("end_time = ?")
                params.append(end_time)
            
            params.append(task_id)  # WHERE clause parameter
            
            query = f"UPDATE tasks SET {', '.join(fields_to_update)} WHERE task_id = ?"
            cursor.execute(query, params)

    def get_task(self, task_id: str) -> dict | None:
        """Get a task by ID."""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT task_id, task_type, status, config_json, start_time, end_time,
                       error, result_json, progress, current_step, message
                FROM tasks WHERE task_id = ?
            ''', (task_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'task_id': row[0],
                    'type': row[1],
                    'status': row[2],
                    'config': json.loads(row[3]) if row[3] else {},
                    'start_time': row[4],
                    'end_time': row[5],
                    'error': row[6],
                    'result': json.loads(row[7]) if row[7] else None,
                    'progress': row[8],
                    'current_step': row[9],
                    'message': row[10]
                }
            return None

    def get_active_tasks(self, task_types: list = None) -> list:
        """Get all active (non-completed/failed) tasks, optionally filtered by type."""
        with self.get_cursor() as cursor:
            query = '''
                SELECT task_id, task_type, status, config_json, start_time, end_time, 
                       error, result_json, progress, current_step, message
                FROM tasks 
                WHERE status NOT IN ('completed', 'failed')
            '''
            params = []
            
            if task_types:
                placeholders = ','.join(['?'] * len(task_types))
                query += f' AND task_type IN ({placeholders})'
                params.extend(task_types)
            
            query += ' ORDER BY start_time DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                tasks.append({
                    'task_id': row[0],
                    'type': row[1],
                    'status': row[2],
                    'config': json.loads(row[3]) if row[3] else {},
                    'start_time': row[4],
                    'end_time': row[5],
                    'error': row[6],
                    'result': json.loads(row[7]) if row[7] else None,
                    'progress': row[8],
                    'current_step': row[9],
                    'message': row[10]
                })
            return tasks

    def delete_task(self, task_id: str):
        """Delete a task from the database."""
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))

    def cleanup_old_tasks(self, days_old: int = 7):
        """Clean up completed/failed tasks older than specified days."""
        cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_old)).isoformat()
        with self.get_cursor() as cursor:
            cursor.execute('''
                DELETE FROM tasks
                WHERE status IN ('completed', 'failed')
                AND start_time < ?
            ''', (cutoff_date,))

    def mark_interrupted_tasks_as_failed(self):
        """Mark all pending/processing tasks as failed on startup (they were interrupted)."""
        current_time = datetime.datetime.now().isoformat()
        with self.get_cursor() as cursor:
            # First, get the count of tasks to be marked as failed for logging
            cursor.execute('''
                SELECT COUNT(*) FROM tasks
                WHERE status IN ('pending', 'processing')
            ''')
            count = cursor.fetchone()[0]
            
            if count > 0:
                # Mark interrupted tasks as failed
                cursor.execute('''
                    UPDATE tasks
                    SET status = 'failed',
                        error = 'Task was interrupted by server restart',
                        message = 'Task failed due to server restart',
                        end_time = ?,
                        current_step = 'interrupted'
                    WHERE status IN ('pending', 'processing')
                ''', (current_time,))
                print(f"INFO:     Marked {count} interrupted tasks as failed on startup.")
            
            return count

    def fetch_papers_paginated(self, page: int = 1, page_size: int = 10, min_score: float = None, 
                              max_score: float = None, sort_field: str = 'score', sort_direction: str = 'desc',
                              search: str = None, from_date: str = None, to_date: str = None):
        """Fetch papers with database-level pagination, filtering, and sorting.
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            min_score: Minimum score filter
            max_score: Maximum score filter
            sort_field: Field to sort by ('score', 'date', 'id')
            sort_direction: Sort direction ('asc' or 'desc')
            search: Search term for title and abstract
            from_date: Start date filter (YYYY-MM-DD)
            to_date: End date filter (YYYY-MM-DD)
            
        Returns:
            Dict with 'items', 'total_items', 'total_pages', 'has_next_page'
        """
        with self.get_cursor() as cursor:
            # Build the WHERE clause
            where_conditions = []
            params = []
            
            if min_score is not None:
                where_conditions.append("score >= ?")
                params.append(min_score)
            
            if max_score is not None:
                where_conditions.append("score <= ?")
                params.append(max_score)
            
            if from_date:
                where_conditions.append("date >= ?")
                params.append(from_date)
            
            if to_date:
                where_conditions.append("date <= ?")
                params.append(to_date)
            
            if search:
                where_conditions.append("(LOWER(title) LIKE ? OR LOWER(abstract) LIKE ?)")
                search_pattern = f"%{search.lower()}%"
                params.extend([search_pattern, search_pattern])
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # Validate and sanitize sort parameters
            valid_sort_fields = {'score': 'score', 'date': 'date', 'id': 'id'}
            sort_field = valid_sort_fields.get(sort_field, 'score')
            sort_direction = 'DESC' if sort_direction.lower() == 'desc' else 'ASC'
            
            # Get total count
            count_query = f"""
                SELECT COUNT(*) 
                FROM papers 
                {where_clause}
            """
            cursor.execute(count_query, params)
            total_items = cursor.fetchone()[0]
            
            # Calculate pagination
            total_pages = (total_items + page_size - 1) // page_size
            offset = (page - 1) * page_size
            has_next_page = page < total_pages
            
            # Get paginated results
            data_query = f"""
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model, embedding
                FROM papers 
                {where_clause}
                ORDER BY {sort_field} {sort_direction}
                LIMIT ? OFFSET ?
            """
            cursor.execute(data_query, params + [page_size, offset])
            rows = cursor.fetchall()
            
            # Convert results
            items = []
            for row in rows:
                # Convert date objects to strings if they're not already strings
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                items.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': float(row[5]) if row[5] is not None else 0.0,
                    'rationale': row[6] or '',
                    'related': bool(row[7]) if row[7] is not None else False,
                    'cosine_similarity': float(row[8]) if row[8] is not None else 0.0,
                    'url': row[9] or '',
                    'embedding_model': row[10] or '',
                    'embedding': row[11]  # Keep as-is for potential future use
                })
            
            return {
                'items': items,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next_page': has_next_page,
                'current_page': page
            }

    def hybrid_search_papers(
        self,
        query_text: str,
        embedding_model,
        page: int = 1,
        page_size: int = 10,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
        min_score: float = None,
        max_score: float = None,
        from_date: str = None,
        to_date: str = None,
        similarity_threshold: float = 0.3,
    ):
        """Hybrid search using SQLite FTS and cosine similarity."""
        try:
            query_embedding = embedding_model.invoke(query_text)
            if hasattr(query_embedding, "tolist"):
                query_embedding = query_embedding.tolist()
            elif not isinstance(query_embedding, list):
                query_embedding = list(query_embedding)

            with self.get_cursor(register_vectors=False) as cursor:
                where_conditions = ["embedding IS NOT NULL"]
                where_params = []

                if min_score is not None:
                    where_conditions.append("score >= ?")
                    where_params.append(min_score)

                if max_score is not None:
                    where_conditions.append("score <= ?")
                    where_params.append(max_score)

                if from_date:
                    where_conditions.append("date >= ?")
                    where_params.append(from_date)

                if to_date:
                    where_conditions.append("date <= ?")
                    where_params.append(to_date)

                where_clause = " AND ".join(where_conditions)

                search_terms = [t for t in query_text.lower().split() if t.strip()]

                if search_terms:
                    fts_query = " ".join(search_terms)
                    keyword_sql = f"""
                        SELECT p.id, p.title, p.abstract, p.date, p.date_run, p.score,
                               p.rationale, p.related, p.cosine_similarity, p.url,
                               p.embedding_model, p.embedding, bm25(papers_fts) as keyword_score
                        FROM papers_fts
                        JOIN papers p ON papers_fts.rowid = p.id
                        WHERE papers_fts MATCH ? {('AND ' + where_clause) if where_clause else ''}
                    """
                    cursor.execute(keyword_sql, [fts_query] + where_params)
                    rows = cursor.fetchall()
                else:
                    base_query = "SELECT id, title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model, embedding FROM papers"
                    if where_clause:
                        base_query += f" WHERE {where_clause}"
                    cursor.execute(base_query, where_params)
                    rows = cursor.fetchall()

            results = []
            query_vec = np.array(query_embedding, dtype=float)
            for row in rows:
                try:
                    emb_list = json.loads(row[11]) if row[11] is not None else None
                except Exception:
                    continue
                if emb_list is None:
                    continue
                score = float(cosine_similarity(query_vec, np.array(emb_list, dtype=float)))
                if score < similarity_threshold:
                    continue

                keyword_score = row[12] if len(row) > 12 else 0.0
                hybrid_score = (semantic_weight * score) + (keyword_weight * keyword_score)

                date_str = row[3].strftime("%Y-%m-%d") if hasattr(row[3], "strftime") else str(row[3])
                date_run_str = row[4].strftime("%Y-%m-%d") if hasattr(row[4], "strftime") else str(row[4])

                results.append({
                    "id": row[0],
                    "title": row[1],
                    "abstract": row[2],
                    "date": date_str,
                    "date_run": date_run_str,
                    "score": float(row[5]) if row[5] is not None else 0.0,
                    "rationale": row[6] or "",
                    "related": bool(row[7]) if row[7] is not None else False,
                    "cosine_similarity": float(row[8]) if row[8] is not None else 0.0,
                    "url": row[9] or "",
                    "embedding_model": row[10] or "",
                    "embedding": row[11],
                    "semantic_score": score,
                    "keyword_score": float(keyword_score) if keyword_score is not None else 0.0,
                    "hybrid_score": hybrid_score,
                })

            results.sort(key=lambda x: x["hybrid_score"], reverse=True)

            total_items = len(results)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
            offset = (page - 1) * page_size
            has_next_page = page < total_pages

            paginated = results[offset : offset + page_size]

            return {
                "items": paginated,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next_page": has_next_page,
                "current_page": page,
            }

        except Exception:
            import traceback
            traceback.print_exc()
            return self._fallback_semantic_search(
                query_embedding,
                page,
                page_size,
                min_score,
                max_score,
                from_date,
                to_date,
                similarity_threshold,
            )


    def _fallback_semantic_search(
        self,
        query_embedding: list,
        page: int = 1,
        page_size: int = 10,
        min_score: float = None,
        max_score: float = None,
        from_date: str = None,
        to_date: str = None,
        similarity_threshold: float = 0.3,
    ):
        """Compute semantic similarity in Python if SQL approach fails."""
        try:
            with self.get_cursor(register_vectors=False) as cursor:
                where_conditions = ["embedding IS NOT NULL"]
                params = []

                if min_score is not None:
                    where_conditions.append("score >= ?")
                    params.append(min_score)

                if max_score is not None:
                    where_conditions.append("score <= ?")
                    params.append(max_score)

                if from_date:
                    where_conditions.append("date >= ?")
                    params.append(from_date)

                if to_date:
                    where_conditions.append("date <= ?")
                    params.append(to_date)

                where_clause = " AND ".join(where_conditions)
                base_query = (
                    "SELECT id, title, abstract, date, date_run, score, rationale, related, "
                    "cosine_similarity, url, embedding_model, embedding FROM papers"
                )
                if where_clause:
                    base_query += f" WHERE {where_clause}"

                cursor.execute(base_query, params)
                rows = cursor.fetchall()

            results = []
            query_vec = np.array(query_embedding, dtype=float)
            for row in rows:
                try:
                    emb_list = json.loads(row[11]) if row[11] is not None else None
                except Exception:
                    continue
                if emb_list is None:
                    continue
                score = float(cosine_similarity(query_vec, np.array(emb_list, dtype=float)))
                if score < similarity_threshold:
                    continue

                date_str = row[3].strftime("%Y-%m-%d") if hasattr(row[3], "strftime") else str(row[3])
                date_run_str = row[4].strftime("%Y-%m-%d") if hasattr(row[4], "strftime") else str(row[4])

                results.append({
                    "id": row[0],
                    "title": row[1],
                    "abstract": row[2],
                    "date": date_str,
                    "date_run": date_run_str,
                    "score": float(row[5]) if row[5] is not None else 0.0,
                    "rationale": row[6] or "",
                    "related": bool(row[7]) if row[7] is not None else False,
                    "cosine_similarity": float(row[8]) if row[8] is not None else 0.0,
                    "url": row[9] or "",
                    "embedding_model": row[10] or "",
                    "embedding": row[11],
                    "semantic_score": score,
                    "keyword_score": 0.0,
                    "hybrid_score": score,
                })

            results.sort(key=lambda x: x["semantic_score"], reverse=True)

            total_items = len(results)
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
            offset = (page - 1) * page_size
            has_next_page = page < total_pages

            paginated = results[offset : offset + page_size]

            return {
                "items": paginated,
                "total_items": total_items,
                "total_pages": total_pages,
                "has_next_page": has_next_page,
                "current_page": page,
            }

        except Exception:

            import traceback
            traceback.print_exc()
            return {
                "items": [],
                "total_items": 0,
                "total_pages": 0,
                "has_next_page": False,
                "current_page": page,
            }

    def get_recent_completed_tasks(self, task_types: list = None, hours_back: int = 24) -> list:
        """Get recently completed tasks with results, for download purposes."""
        with self.get_cursor() as cursor:
            cutoff_time = (datetime.datetime.now() - datetime.timedelta(hours=hours_back)).isoformat()
            
            query = '''
                SELECT task_id, task_type, status, config_json, start_time, end_time,
                       error, result_json, progress, current_step, message
                FROM tasks 
                WHERE status = 'completed' 

                AND end_time >= ?
                AND result_json IS NOT NULL
            '''
            params = [cutoff_time]
            
            if task_types:
                placeholders = ','.join(['?'] * len(task_types))
                query += f' AND task_type IN ({placeholders})'
                params.extend(task_types)
            
            query += ' ORDER BY end_time DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            tasks = []
            for row in rows:
                tasks.append({
                    'task_id': row[0],
                    'type': row[1],
                    'status': row[2],
                    'config': json.loads(row[3]) if row[3] else {},
                    'start_time': row[4],
                    'end_time': row[5],
                    'error': row[6],
                    'result': json.loads(row[7]) if row[7] else None,
                    'progress': row[8],
                    'current_step': row[9],
                    'message': row[10]
                })
            return tasks

    # Research Agent specific methods
    def get_paper_text(self, paper_id: int) -> str | None:
        """Get the full text content of a paper by ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT text FROM papers WHERE id = ?", (paper_id,))
            row = cursor.fetchone()
            return row[0] if row else None

    def update_paper_text(self, paper_id: int, text: str):
        """Update the full text content of a paper."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "UPDATE papers SET text = ? WHERE id = ?",
                (text, paper_id)
            )

    def get_paper_by_id(self, paper_id: int) -> dict | None:
        """Get paper details by ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, title, abstract, date, date_run, score, rationale, related,"
                " cosine_similarity, url, embedding_model, embedding, text FROM papers WHERE id = ?",
                (paper_id,),
            )
            row = cursor.fetchone()
            if row:
                # Convert date objects to strings if they're not already strings
                date_str = row[3].strftime('%Y-%m-%d') if hasattr(row[3], 'strftime') else str(row[3])
                date_run_str = row[4].strftime('%Y-%m-%d') if hasattr(row[4], 'strftime') else str(row[4])
                
                return {
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': date_str,
                    'date_run': date_run_str,
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10],
                    'embedding': row[11],
                    'text': row[12]
                }
            return None

    def insert_literature_review(self, research_question: str, summary_json: str, trace_json: str, report_text: str = None) -> int:
        """Insert a literature review result and return the ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "INSERT INTO lit_reviews (research_question, summary_json, trace_json, report_text, created_ts) VALUES (?, ?, ?, ?, ?)",
                (research_question, summary_json, trace_json, report_text, datetime.datetime.now().isoformat())
            )
            return cursor.lastrowid

    def get_literature_review(self, review_id: int) -> dict | None:
        """Get a literature review by ID."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, research_question, summary_json, trace_json, report_text, created_ts FROM lit_reviews WHERE id = ?",
                (review_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'research_question': row[1],
                    'summary_json': row[2],
                    'trace_json': row[3],
                    'report_text': row[4],
                    'created_ts': row[5]
                }
            return None

    def get_recent_literature_reviews(self, limit: int = 10) -> list:
        """Get recent literature reviews."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, research_question, summary_json, trace_json, report_text, created_ts FROM lit_reviews "
                "ORDER BY created_ts DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'research_question': row[1],
                    'summary_json': row[2],
                    'trace_json': row[3],
                    'report_text': row[4],
                    'created_ts': row[5]
                }
                for row in rows
            ]

    def fetch_all_literature_reviews(self) -> list:
        """Fetch all literature reviews for export/migration purposes."""
        with self.get_cursor() as cursor:
            cursor.execute(
                "SELECT id, research_question, summary_json, trace_json, report_text, created_ts FROM lit_reviews "
                "ORDER BY created_ts ASC"
            )
            rows = cursor.fetchall()
            return [
                {
                    'id': row[0],
                    'research_question': row[1],
                    'summary_json': row[2],
                    'trace_json': row[3],
                    'report_text': row[4],
                    'created_ts': row[5]
                }
                for row in rows
            ]
import os
import json
import datetime
import base64
import hashlib
from contextlib import contextmanager
import sqlite3
# We'll need to handle vector serialization manually or via sqlite-vec's Python bindings if available.
# For now, let's assume embeddings are stored as bytes.
# from sqlite_vec import register_vector # This would be the ideal if such a direct equivalent existed

from .papers import Newsletter, Paper, Logs, Podcast

INITIAL_PROVIDERS = [
    {"id": 1, "name": "ollama"},
    {"id": 2, "name": "gemini"},
    {"id": 3, "name": "openai"},
    {"id": 4, "name": "sentence-transformers"},
    {"id": 5, "name": "llamacpp"},
]


class PaperDatabase:
    def __init__(self, db_path: str, embedding_dimension: int = 1536):
        self.db_path = db_path
        self.embedding_dimension = embedding_dimension
        if embedding_dimension == 1536: # Or whatever default is chosen
            print(f"Warning: PaperDatabase initialized with default embedding dimension {self.embedding_dimension}. "
                  "Ensure this matches your embedding model's output dimension.")
        # Ensure the database directory exists
        # db_path could be e.g. "my_database.sqlite" (local dir) or "data/my_database.sqlite"
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir): # Check if db_dir is not empty string
            os.makedirs(db_dir, exist_ok=True)
        self._initialize_db()

    @contextmanager
    def get_cursor(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        try:
            # Load sqlite-vec extensions
            conn.enable_load_extension(True)
            try:
                conn.load_extension('vector0')
                conn.load_extension('vss0') # For VSS, if it's a separate extension
                # print("DEBUG: sqlite-vec extensions (vector0, vss0) loaded successfully.") # Assuming print_debug was a placeholder
            except sqlite3.OperationalError as e:
                error_message = (
                    f"Fatal: Could not load sqlite-vec extensions (vector0, vss0). Error: {e}. "
                    "Vector search functionality will be unavailable. "
                    "Please ensure sqlite-vec is correctly installed and its compiled shared libraries "
                    "(.dll, .so, or .dylib) are accessible in the system's library path or "
                    "the application's environment."
                    "\n\nTroubleshooting suggestions:\n"
                    "1. Reinstall sqlite-vec: pip uninstall sqlite-vec && pip install sqlite-vec --no-cache-dir\n"
                    "2. Consult the sqlite-vec documentation for platform-specific installation instructions.\n"
                    "3. For macOS/Linux, you might be able to locate the files (e.g., vector0.dylib, vss0.so) "
                    "within your Python environment's site-packages directory (look for a 'sqlite_vec' or similar folder) "
                    "and try setting DYLD_LIBRARY_PATH (macOS) or LD_LIBRARY_PATH (Linux) to that directory.\n"
                    "Example (macOS): export DYLD_LIBRARY_PATH=/path/to/your/conda/env/lib/pythonX.Y/site-packages/sqlite_vec/lib:$DYLD_LIBRARY_PATH\n"
                    "Example (Linux): export LD_LIBRARY_PATH=/path/to/your/conda/env/lib/pythonX.Y/site-packages/sqlite_vec/lib:$LD_LIBRARY_PATH\n"
                    "4. If running the Electron app, this might indicate an issue with how the compiled extensions were bundled."
                )
                print(f"ERROR: {error_message}") # Using standard print for logging the detailed error
                raise ImportError(error_message) from e
            finally:
                # Always disable extension loading after attempting, even if successful.
                conn.enable_load_extension(False)

            cursor = conn.cursor()
            yield cursor
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback() # Rollback any changes if an error occurs
            raise e # Re-raise the exception
        finally:
            conn.close()

    def _initialize_db(self):
        """Initialize database tables and indices if they don't exist."""
        # For SQLite, the extensions are loaded per-connection, so no global "CREATE EXTENSION"
        # The loading is handled in get_cursor.
        # We still need to create the tables.
        with self.get_cursor() as cursor:
            # Create papers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    date TEXT NOT NULL, -- SQLite stores dates as TEXT, REAL, or INTEGER
                    date_run TEXT NOT NULL,
                    score REAL,
                    rationale TEXT,
                    related INTEGER DEFAULT 0, -- 0 for False, 1 for True
                    cosine_similarity REAL,
                    url TEXT UNIQUE,
                    embedding_model TEXT,
                    embedding BLOB -- For sqlite-vec, vectors are typically stored as BLOBs
                )
            """)
            
            # Create FTS5 virtual table for papers
            cursor.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
                    title,
                    abstract,
                    content='papers',
                    content_rowid='id'
                )
            """)

            # Triggers to keep papers_fts synchronized with papers table
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
                    INSERT INTO papers_fts (rowid, title, abstract)
                    VALUES (new.id, new.title, new.abstract);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
                    INSERT INTO papers_fts (papers_fts, rowid, title, abstract)
                    VALUES ('delete', old.id, old.title, old.abstract);
                END;
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
                    INSERT INTO papers_fts (papers_fts, rowid, title, abstract)
                    VALUES ('delete', old.id, old.title, old.abstract);
                    INSERT INTO papers_fts (rowid, title, abstract)
                    VALUES (new.id, new.title, new.abstract);
                END;
            """)

            # Create logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    datetime_run TEXT -- SQLite stores timestamps as TEXT
                )
            ''')

            # Create newsletters table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS newsletters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    date_sent TEXT NOT NULL
                )
            ''')

            # Create podcasts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS podcasts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    date TEXT NOT NULL,
                    script TEXT NOT NULL,
                    description TEXT NOT NULL
                )
            ''')

            # Create settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            ''')

            # Create model_providers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS model_providers (
                    id INTEGER PRIMARY KEY, -- Keep as INTEGER for direct mapping if IDs are small and controlled
                    name TEXT NOT NULL UNIQUE
                )
            ''')
            for provider in INITIAL_PROVIDERS:
                # SQLite uses 'OR IGNORE' for ON CONFLICT DO NOTHING
                cursor.execute('INSERT OR IGNORE INTO model_providers (id, name) VALUES (?, ?)', (provider['id'], provider['name']))

            # Create tasks table for persistent task state management
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    start_time TEXT NOT NULL, -- Store as ISO8601 string
                    end_time TEXT,           -- Store as ISO8601 string
                    error TEXT,
                    result_json TEXT,
                    progress REAL DEFAULT 0, -- SQLite uses REAL for floating-point numbers
                    current_step TEXT,
                    message TEXT
                )
            ''')

            # Create VSS table for papers (assuming embedding dimension is 1536)
            # This needs to be verified against the actual embedding dimension used.
            # The dimension should match what embedding_model.invoke() produces.
            # For now, we'll use a placeholder dimension. It's critical this is correct.
            # Example: If using OpenAI 'text-embedding-ada-002', dimension is 1536.
            # We should ideally fetch this dimension dynamically or have it configured.
            # For now, hardcoding 1536 as a common default. - This is now addressed.
            # Use the provided embedding_dimension.
            # It's critical this is correct and matches the dimension of vectors being inserted.
            cursor.execute(f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS papers_vss USING vss0(
                    embedding({self.embedding_dimension})
                )
            """)
            # Note: Data insertion into papers_vss will be handled by application logic
            # when papers are inserted/updated, by adding their rowid and embedding vector.

    def insert_podcast(self, podcast: Podcast):
        # Validate date formats
        try:
            datetime.datetime.strptime(podcast.date, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")
        with self.get_cursor() as cursor:
            cursor.execute('''INSERT INTO podcasts (title, date, script, description)
                              VALUES (?, ?, ?, ?)''',
                           (podcast.title, podcast.date, json.dumps(podcast.script), podcast.description))
            
    def paper_exists_by_url(self, url: str) -> bool:
        """Check if a paper with the given URL already exists in the database."""
        with self.get_cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM papers WHERE url = ?', (url,))
            count = cursor.fetchone()[0] # sqlite3.Row is dict-like and tuple-like
            return count > 0

    def get_paper_by_url(self, url: str) -> dict | None:
        """Get paper details by URL if it exists."""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model, embedding
                FROM papers WHERE url = ?
            ''', (url,))
            row = cursor.fetchone()
            if row:
                # Convert row to dict for easier access and consistent return type
                paper_data = dict(row)
                # Convert boolean field
                paper_data['related'] = bool(paper_data['related'])
                # Embeddings are stored as BLOBs, need conversion back to list/array when used.
                # This conversion should happen where the embedding is actually processed.
                # For now, return as bytes.
                return paper_data
            return None

    def insert_paper(self, paper: Paper, skip_duplicates: bool = True) -> bool:
        """
        Insert a paper into the database. Also updates FTS and VSS tables.
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
        # paper.related is now 0 or 1
        if not isinstance(paper.cosine_similarity, float):
            raise ValueError("Cosine similarity must be a float")

        # Validate date
        try:
            datetime.datetime.strptime(paper.date, '%Y-%m-%d')
            datetime.datetime.strptime(paper.date_run, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")

        if skip_duplicates and self.paper_exists_by_url(paper.url):
            return False

        # Convert embedding (list of floats) to bytes for BLOB storage.
        # sqlite-vec expects a specific format, often a flat list of little-endian floats.
        # This needs to be confirmed with sqlite-vec documentation.
        # Assuming a simple conversion for now.
        embedding_blob = None
        if paper.embedding:
            if not isinstance(paper.embedding, list) or not all(isinstance(x, float) for x in paper.embedding):
                raise ValueError("Embedding must be a list of floats.")
            # Example: Convert to bytes (struct.pack is a common way)
            import struct
            embedding_blob = b''.join(struct.pack('<f', val) for val in paper.embedding)

        with self.get_cursor() as cursor:
            cursor.execute('''INSERT INTO papers
                (title, abstract, date, date_run, score, rationale, related,
                 cosine_similarity, url, embedding_model, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (paper.title, paper.abstract, paper.date, paper.date_run,
                 paper.score, paper.rationale, 1 if paper.related else 0,
                 paper.cosine_similarity, paper.url, paper.embedding_model,
                 embedding_blob))

            paper_id = cursor.lastrowid # Get the ID of the inserted paper

            # Insert into papers_fts is handled by a trigger.
            # Insert into papers_vss (if embedding exists)
            if embedding_blob and paper_id:
                try:
                    # vss0 virtual table expects rowid and the vector
                    cursor.execute("INSERT INTO papers_vss (rowid, embedding) VALUES (?, ?)", (paper_id, embedding_blob))
                except sqlite3.OperationalError as e:
                    # This might happen if the VSS table has dimension constraints not met by embedding_blob
                    print(f"Error inserting into papers_vss for paper_id {paper_id}: {e}")
                    # Decide if this should be a critical error. For now, just print.
        return True

    def insert_newsletter(self, newsletter: Newsletter):
        required_fields = ['content', 'start_date', 'end_date', 'date_sent']
        for field in required_fields:
            if not hasattr(newsletter, field) or getattr(newsletter, field) is None:
                raise ValueError(f"Newsletter object is missing required field: {field}")

        # Validate date format (SQLite handles date strings directly)
        try:
            datetime.datetime.strptime(newsletter.start_date, '%Y-%m-%d')
            datetime.datetime.strptime(newsletter.end_date, '%Y-%m-%d')
            datetime.datetime.strptime(newsletter.date_sent, '%Y-%m-%d')
        except ValueError:
            raise ValueError("Dates must be in 'YYYY-MM-DD' format")

        if newsletter.start_date > newsletter.end_date: # String comparison works for ISO dates
            raise ValueError("start_date cannot be after end_date")

        with self.get_cursor() as cursor:
            cursor.execute('''INSERT INTO newsletters (content, start_date, end_date, date_sent)
                              VALUES (?, ?, ?, ?)''',
                           (newsletter.content, newsletter.start_date, newsletter.end_date, newsletter.date_sent))

    def insert_log(self, log: Logs):
        required_fields = ['task_id', 'status']
        for field in required_fields:
            if not hasattr(log, field) or getattr(log, field) is None:
                raise ValueError(f"Log object is missing required field: {field}")

        datetime_run = log.datetime_run or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self.get_cursor() as cursor:
            # Using INSERT OR REPLACE (UPSERT) behavior for simplicity
            # This means if a log with the same task_id exists, it will be replaced.
            # If specific fields need to be preserved on conflict, a more complex
            # ON CONFLICT DO UPDATE SET ... would be needed.
            # For logs, often replacing or just updating status is fine.
            # Current PG logic: insert if not exist, else update status.
            # Replicating this:
            cursor.execute("SELECT id FROM logs WHERE task_id = ?", (log.task_id,))
            existing_log = cursor.fetchone()
            if existing_log:
                cursor.execute("UPDATE logs SET status = ?, datetime_run = ? WHERE task_id = ?",
                               (log.status, datetime_run, log.task_id))
            else:
                cursor.execute('''INSERT INTO logs (task_id, status, datetime_run)
                                VALUES (?, ?, ?)''',
                               (log.task_id, log.status, datetime_run))

    def get_recent_logs(self, limit: int = 100, from_date: str = None, to_date: str = None):
        query = '''SELECT task_id, status, datetime_run FROM logs'''
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
            return [dict(row) for row in cursor.fetchall()]


    def get_recent_task_history(self, limit: int = 100, from_date: str = None, to_date: str = None):
        """Get recent task history with complete information including task type."""
        query = '''SELECT task_id, task_type, status, start_time, end_time, 
                          progress, current_step, message, error
                   FROM tasks'''
        params = []
        conditions = []

        if from_date:
            conditions.append("start_time >= ?") # Assuming start_time is stored as ISO8601 string
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
            return [dict(row) for row in cursor.fetchall()]

    def fetch_all_podcasts(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row_data in rows: # row_data is already a dict-like sqlite3.Row
                row_dict = dict(row_data)
                row_dict['script'] = json.loads(row_dict['script'])
                result.append(row_dict)
            return result

    def fetch_podcast_by_id(self, podcast_id: int):
        """Fetch a single podcast by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts WHERE id = ?", (podcast_id,))
            row = cursor.fetchone()
            if row:
                row_dict = dict(row)
                row_dict['script'] = json.loads(row_dict['script'])
                return row_dict
            return None

    def delete_podcast(self, title: str):
        """Delete a podcast from the database by its title."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM podcasts WHERE title = ?", (title,))

    def delete_podcast_by_id(self, podcast_id: int):
        """Delete a podcast from the database by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM podcasts WHERE id = ?", (podcast_id,))
            return cursor.rowcount > 0

    def update_podcast_title(self, podcast_id: int, new_title: str):
        """Update the title of a podcast by its ID."""
        with self.get_cursor() as cursor:
            cursor.execute("UPDATE podcasts SET title = ? WHERE id = ?", (new_title, podcast_id))
            return cursor.rowcount > 0

    def fetch_all_newsletters(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, content, start_date, end_date, date_sent FROM newsletters ORDER BY id DESC")
            return [dict(row) for row in cursor.fetchall()]

    def fetch_all_papers(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model, embedding FROM papers ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row_data in rows:
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                # Embedding is BLOB, may need conversion depending on use.
                result.append(paper)
            return result

    def _deserialize_embedding(self, blob_data: bytes) -> list[float] | None:
        """Helper to convert embedding BLOB back to list of floats."""
        if not blob_data:
            return None
        import struct
        # Assuming little-endian floats. Adjust if sqlite-vec stores differently.
        # Each float is 4 bytes.
        num_floats = len(blob_data) // 4
        return list(struct.unpack(f'<{num_floats}f', blob_data))

    def _serialize_embedding(self, embedding_list: list[float]) -> bytes | None:
        """Helper to convert list of floats to embedding BLOB."""
        if not embedding_list:
            return None
        import struct
        return b''.join(struct.pack('<f', val) for val in embedding_list)

    def find_similar_papers(self, query_embedding: list[float], limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to the given embedding using cosine similarity with sqlite-vec.
        
        Note: `query_embedding` should be a Python list of floats.
        The VSS table `papers_vss` stores embeddings as BLOBs.
        The `vector_distance_cos_blob` function (or similar from sqlite-vec) is used.
        """
        if not query_embedding:
            return []

        query_embedding_blob = self._serialize_embedding(query_embedding)
        if not query_embedding_blob:
            return []

        with self.get_cursor() as cursor:
            # The actual VSS search query depends on sqlite-vec's API.
            # Common pattern: Search the VSS table, get rowids and distances, then join with main table.
            # `vector_distance_cos_blob` returns distance (0 to 2). Similarity = 1 - (distance / 2) for cosine.
            # Or, if sqlite-vec provides a direct similarity/score (e.g., negative distance for ordering), use that.
            # Let's assume vss_search returns 'distance' which is cosine distance (0 for identical, 2 for opposite)
            # So similarity = 1 - distance. We want similarity >= threshold.
            # (1 - distance) >= similarity_threshold  => distance <= (1 - similarity_threshold)

            # The 'distance' column from vss_search is generally cosine distance or squared Euclidean.
            # For cosine distance: similarity = (2 - distance) / 2 or 1 - distance depending on range.
            # If vector_distance_cos_blob returns cosine distance (0 to 2), then similarity is 1 - distance.
            # This needs to be verified with sqlite-vec documentation.
            # Assuming `distance` from `vss_search` is cosine distance [0, 2]
            # Similarity = 1 - distance. So, `1 - distance >= similarity_threshold`
            # `distance <= 1 - similarity_threshold`

            # Updated assumption: sqlite-vec's vss_search often returns a distance that needs to be converted.
            # Let's use vector_query_blob for explicit distance calculation if vss_search is problematic.
            # The query below uses a common pattern for sqlite-vec:
            # 1. Search in papers_vss to get rowids of nearest neighbors.
            # 2. Join with papers table to get full details.
            # 3. Calculate similarity score (1 - distance). sqlite-vec's cosine distance is usually 0 (identical) to 2 (opposite).

            # `vector_distance_cos_blob(p.embedding, ?)` for direct distance calculation.
            # `vss_search(embedding, ?)` for indexed search.
            # The column name for distance in vss_search result is often 'distance'.

            # The `LIMIT` in the subquery is important for performance.
            # The outer query then re-calculates distance for accurate sorting if needed, or uses VSS distance.
            
            # This query assumes `papers_vss` stores the raw embeddings and `vss_search` can use them.
            # The `vector_search` function is a placeholder for the actual sqlite-vec search function.
            # It might be `vss_search` or similar.
            # The column `distance` is assumed to be returned by the VSS search.

            # `query_embedding_blob` is the BLOB representation of the query vector

            # Clause: `distance <= (1.0 - similarity_threshold)` for cosine distance
            # `distance` is often cosine distance, where 0 is most similar.
            # `similarity_score = 1 - distance`
            # So `similarity_score >= similarity_threshold` means `1 - distance >= similarity_threshold`
            # which means `distance <= 1 - similarity_threshold`

            # The vss_search function usually takes the target vector as its second argument.
            # The search results include `rowid` and `distance`.
            cursor.execute(f"""
                SELECT
                    p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale, p.related,
                    p.cosine_similarity, p.url, p.embedding_model, p.embedding,
                    v.distance,
                    (1 - v.distance) AS similarity_score
                FROM
                    (SELECT rowid, distance
                     FROM papers_vss
                     WHERE vss_search(embedding, ?) -- Pass the query embedding blob
                     AND distance <= ?  -- Pre-filter by distance
                     LIMIT ?) v
                JOIN papers p ON p.id = v.rowid
                ORDER BY v.distance ASC -- Order by distance (ascending for similarity)
            """, (query_embedding_blob, (1.0 - similarity_threshold), limit * 2)) # Fetch more to ensure limit after join
            # The limit * 2 is a heuristic, might need adjustment or a more robust pagination strategy if many results
            # are filtered out by other conditions not in VSS.

            rows = cursor.fetchall()
            result = []
            for row_data in rows:
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                paper['embedding'] = self._deserialize_embedding(paper['embedding'])
                # paper['similarity_score'] is already calculated
                paper['similarity_distance'] = paper['distance'] # Keep original distance name if needed
                result.append(paper)

            # Since VSS might not support all filters, and we might overfetch, re-apply limit if needed
            # and ensure the final sorting and thresholding is correct.
            # The query already sorts by distance and pre-filters.
            # The threshold `1.0 - similarity_threshold` for distance is applied.

            # Final client-side filtering if sqlite-vec's thresholding isn't exact or if further checks are needed.
            # However, the SQL query aims to do this.
            # We sort by similarity_score desc (which is distance asc)
            # result.sort(key=lambda x: x['similarity_score'], reverse=True)
            return result[:limit]


    def find_papers_by_semantic_search(self, query_text: str, embedding_model, limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to a text query by first generating an embedding."""
        query_embedding_list = embedding_model.invoke(query_text)
        # Ensure it's a list of floats
        if hasattr(query_embedding_list, 'tolist'): # For NumPy arrays
            query_embedding_list = query_embedding_list.tolist()
        if not isinstance(query_embedding_list, list) or not all(isinstance(x, (float, int)) for x in query_embedding_list):
            raise ValueError("Embedding model did not return a list of floats.")
        
        query_embedding_floats = [float(x) for x in query_embedding_list]
        return self.find_similar_papers(query_embedding_floats, limit, similarity_threshold)

    def get_papers_without_embeddings(self):
        """Get papers that don't have embeddings saved."""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model
                FROM papers 
                WHERE embedding IS NULL OR LENGTH(embedding) = 0 -- Check for NULL or empty BLOB
                ORDER BY id DESC
            ''')
            
            rows = cursor.fetchall()
            result = []
            for row_data in rows:
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                paper['embedding'] = None # Explicitly set to None
                result.append(paper)
            return result

    def update_paper_embedding(self, paper_id: int, embedding: list[float]):
        """Update the embedding for a specific paper and update VSS table."""
        embedding_blob = self._serialize_embedding(embedding)

        with self.get_cursor() as cursor:
            cursor.execute('''
                UPDATE papers 
                SET embedding = ?
                WHERE id = ?
            ''', (embedding_blob, paper_id))

            if cursor.rowcount > 0 and embedding_blob:
                # Update VSS table: delete old entry (if exists) and insert new one.
                # vss0 usually requires rowid for delete/update.
                # A common pattern is to delete and re-insert for updates.
                try:
                    # This assumes 'embedding' is the column name in papers_vss used for the vector.
                    # And that we can update by rowid. Some VSS might need delete + insert.
                    # For sqlite-vec's vss0, it's often:
                    # DELETE FROM papers_vss WHERE rowid = ?;
                    # INSERT INTO papers_vss (rowid, embedding) VALUES (?, ?);
                    # Or an UPSERT if supported by the specific VSS implementation.
                    # Simpler: just try to insert, assuming duplicates might be handled or an error occurs.
                    # More robust: delete then insert.
                    cursor.execute("DELETE FROM papers_vss WHERE rowid = ?", (paper_id,))
                    cursor.execute("INSERT INTO papers_vss (rowid, embedding) VALUES (?, ?)",
                                   (paper_id, embedding_blob))
                except sqlite3.OperationalError as e:
                    print(f"Error updating papers_vss for paper_id {paper_id} during embedding update: {e}")
                    # Potentially re-raise or handle as critical if VSS sync is vital.

    def get_paper_embedding(self, paper_id: int) -> list[float] | None:
        """Get the embedding for a specific paper."""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT embedding FROM papers 
                WHERE id = ? AND embedding IS NOT NULL AND LENGTH(embedding) > 0
            ''', (paper_id,))
            row = cursor.fetchone()
            if row and row['embedding']:
                return self._deserialize_embedding(row['embedding'])
            return None

    def find_similar_papers_to_existing(self, paper_id: int, limit: int = 10, similarity_threshold: float = 0.7):
        """Find papers similar to an existing paper using its stored embedding."""
        reference_embedding_list = self.get_paper_embedding(paper_id)
        if not reference_embedding_list:
            return None # Reference paper or its embedding not found

        # Get the reference paper details
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT id, title, abstract, date, date_run, score, rationale, related, 
                       cosine_similarity, url, embedding_model, embedding
                FROM papers 
                WHERE id = ?
            ''', (paper_id,))
            reference_row = cursor.fetchone()
            if not reference_row: # Should not happen if get_paper_embedding succeeded, but good check
                return None

            reference_paper = dict(reference_row)
            reference_paper['related'] = bool(reference_paper['related'])
            # Deserialize embedding for the reference paper object, though we use reference_embedding_list for search
            reference_paper['embedding'] = self._deserialize_embedding(reference_paper['embedding'])

        # Find similar papers (excluding the reference paper itself)
        query_embedding_blob = self._serialize_embedding(reference_embedding_list)
        if not query_embedding_blob: # Should not happen
            return {'reference_paper': reference_paper, 'similar_papers': [], 'total_similar': 0}

        with self.get_cursor() as cursor:
            cursor.execute(f"""
                SELECT
                    p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale, p.related,
                    p.cosine_similarity, p.url, p.embedding_model, p.embedding,
                    v.distance,
                    (1 - v.distance) AS similarity_score
                FROM
                    (SELECT rowid, distance
                     FROM papers_vss
                     WHERE vss_search(embedding, ?) AND rowid != ?
                     AND distance <= ?
                     LIMIT ?) v
                JOIN papers p ON p.id = v.rowid
                ORDER BY v.distance ASC
            """, (query_embedding_blob, paper_id, (1.0 - similarity_threshold), limit * 2))
            # Note: added `AND rowid != ?` to the VSS query

            similar_rows = cursor.fetchall()
            similar_papers_list = []
            for row_data in similar_rows:
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                paper['embedding'] = self._deserialize_embedding(paper['embedding'])
                paper['similarity_distance'] = paper['distance']
                similar_papers_list.append(paper)

            # Client-side limit if overfetched
            # similar_papers_list.sort(key=lambda x: x['similarity_score'], reverse=True) # Already sorted by distance ASC
            
            return {
                'reference_paper': reference_paper,
                'similar_papers': similar_papers_list[:limit],
                'total_similar': len(similar_papers_list[:limit]) # Count after limit
            }

    # SETTINGS CRUD
    def get_setting(self, key: str):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row['value'] if row else None # Access by column name

    def set_setting(self, key, value):
        # Ensure key and value are strings, as expected by the original logic for some settings
        # Although SQLite can store various types, consistency with previous usage is good.
        key_str = str(key)
        value_str = str(value)
        with self.get_cursor() as cursor:
            # SQLite's equivalent of ON CONFLICT DO UPDATE
            cursor.execute('''
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            ''', (key_str, value_str))

    def delete_setting(self, key: str):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM settings WHERE key = ?', (key,))

    def get_all_settings(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT key, value FROM settings')
            return {row['key']: row['value'] for row in cursor.fetchall()} # More Pythonic dict construction

    def _encrypt(self, plaintext: str) -> str:
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = plaintext.encode('utf-8') # Ensure utf-8 encoding
        enc = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return base64.b64encode(enc).decode('utf-8') # Ensure utf-8 decoding

    def _decrypt(self, ciphertext: str) -> str:
        secret = os.getenv("APP_SECRET_KEY", "default_secret").encode()
        key = hashlib.sha256(secret).digest()
        data = base64.b64decode(ciphertext.encode('utf-8')) # Ensure utf-8 encoding
        dec = bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        return dec.decode('utf-8') # Ensure utf-8 decoding

    def set_secret_setting(self, key: str, value: str):
        """Encrypt and store a sensitive setting value."""
        self.set_setting(key, self._encrypt(value))

    def get_secret_setting(self, key: str) -> str | None:
        """Retrieve and decrypt a sensitive setting value."""
        enc_value = self.get_setting(key) # Corrected variable name
        if enc_value:
            try:
                return self._decrypt(enc_value)
            except Exception: # Catch broader exceptions during decryption
                # Optionally log the error for debugging
                # print(f"Error decrypting setting {key}: {e}")
                return None
        return None

    # MODEL PROVIDERS CRUD
    def add_model_provider(self, id: int, name: str): # id is INTEGER PRIMARY KEY
        with self.get_cursor() as cursor:
            # SQLite's ON CONFLICT DO NOTHING is 'OR IGNORE'
            cursor.execute('INSERT OR IGNORE INTO model_providers (id, name) VALUES (?, ?)', (id, name))

    def get_model_providers(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT id, name FROM model_providers')
            return [dict(row) for row in cursor.fetchall()]

    def delete_model_provider(self, provider_id: int):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM model_providers WHERE id = ?', (provider_id,))

    # MODELS CRUD - Placeholders, assuming these will be updated similarly if used.
    # def add_model(self, provider_id: int, name: str, config_json: str = None):
    #     with self.get_cursor() as cursor:
    #         cursor.execute('INSERT OR IGNORE INTO models (provider_id, name, config_json) VALUES (?, ?, ?)', (provider_id, name, config_json))

    # def upsert_model(self, provider_id: int, name: str, config_json: str = None):
    #     with self.get_cursor() as cursor:
    #         cursor.execute('''
    #             INSERT INTO models (provider_id, name, config_json) 
    #             VALUES (?, ?, ?)
    #             ON CONFLICT(provider_id, name)  -- Assuming this unique constraint exists
    #             DO UPDATE SET config_json = excluded.config_json
    #         ''', (provider_id, name, config_json))

    # def get_models(self, provider_id: int = None, name: str = None):
    #     with self.get_cursor() as cursor:
    #         # ... (adapt query placeholders and row access)
    #         pass # Placeholder

    # def delete_model(self, model_id: int): # Assuming model_id is the primary key
    #     with self.get_cursor() as cursor:
    #         cursor.execute('DELETE FROM models WHERE id = ?', (model_id,))

    # EMAIL RECIPIENTS
    def get_email_recipients(self):
        val = self.get_setting('email_recipients')
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError: # Be specific with exception
                return []
        return []

    def set_email_recipients(self, recipients: list): # Type hint
        self.set_setting('email_recipients', json.dumps(recipients))

    # VISUALIZER SETTINGS
    def get_visualizer_settings(self):
        val = self.get_setting('visualizer_settings')
        if val:
            try:
                return json.loads(val)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_visualizer_settings(self, settings: dict): # Type hint
        self.set_setting('visualizer_settings', json.dumps(settings))

    # TASK PERSISTENCE OPERATIONS
    def insert_task(self, task_id: str, task_type: str, status: str, config: dict, start_time: str = None, progress: float = 0, current_step: str = None, message: str = None):
        """Insert or update a task in the database."""
        if not start_time:
            start_time = datetime.datetime.now().isoformat() # Ensure ISO format for TEXT storage
        
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks
                (task_id, task_type, status, config_json, start_time, progress, current_step, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (task_id) DO UPDATE SET
                    task_type = excluded.task_type,
                    status = excluded.status,
                    config_json = excluded.config_json,
                    start_time = excluded.start_time, -- Keep or update start_time? Original updates it.
                    progress = excluded.progress,
                    current_step = excluded.current_step,
                    message = excluded.message,
                    -- Explicitly keep old end_time, error, result_json if not part of this upsert
                    end_time = tasks.end_time,
                    error = tasks.error,
                    result_json = tasks.result_json
            ''', (task_id, task_type, status, json.dumps(config), start_time, progress, current_step, message))

    def update_task_status(self, task_id: str, status: str, progress: float = None, current_step: str = None, message: str = None, error: str = None, result: dict = None, end_time: str = None):
        """Update task status and other fields."""
        with self.get_cursor() as cursor:
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
            if end_time is not None: # Ensure end_time is ISO format if it's a datetime object
                fields_to_update.append("end_time = ?")
                params.append(end_time)
            
            params.append(task_id)
            
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
                task_data = dict(row)
                task_data['config'] = json.loads(task_data['config_json']) if task_data['config_json'] else {}
                task_data['result'] = json.loads(task_data['result_json']) if task_data['result_json'] else None
                # Rename 'task_type' to 'type' for consistency with original return format
                task_data['type'] = task_data.pop('task_type')
                return task_data
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
                # Create placeholders for task types: (?, ?, ...)
                placeholders = ','.join(['?'] * len(task_types))
                query += f' AND task_type IN ({placeholders})'
                params.extend(task_types)
            
            query += ' ORDER BY start_time DESC' # start_time is TEXT, but ISO8601 sorts correctly
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            tasks = []
            for row_data in rows:
                task = dict(row_data)
                task['config'] = json.loads(task['config_json']) if task['config_json'] else {}
                task['result'] = json.loads(task['result_json']) if task['result_json'] else None
                task['type'] = task.pop('task_type')
                tasks.append(task)
            return tasks

    def delete_task(self, task_id: str):
        """Delete a task from the database."""
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM tasks WHERE task_id = ?', (task_id,))

    def cleanup_old_tasks(self, days_old: int = 7):
        """Clean up completed/failed tasks older than specified days."""
        # SQLite date functions can be used if dates are stored in a compatible format (like ISO8601)
        # cutoff_date_str = (datetime.datetime.now() - datetime.timedelta(days=days_old)).isoformat()
        with self.get_cursor() as cursor:
            # Using julianday for date comparison in SQLite
            cursor.execute(f'''
                DELETE FROM tasks
                WHERE status IN ('completed', 'failed')
                AND julianday('now') - julianday(start_time) > ?
            ''', (days_old,))


    def mark_interrupted_tasks_as_failed(self):
        """Mark all pending/processing tasks as failed on startup (they were interrupted)."""
        current_time_iso = datetime.datetime.now().isoformat()
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT COUNT(*) FROM tasks
                WHERE status IN ('pending', 'processing')
            ''')
            count_row = cursor.fetchone()
            count = count_row[0] if count_row else 0
            
            if count > 0:
                cursor.execute('''
                    UPDATE tasks
                    SET status = 'failed',
                        error = 'Task was interrupted by server restart',
                        message = 'Task failed due to server restart',
                        end_time = ?,
                        current_step = 'interrupted'
                    WHERE status IN ('pending', 'processing')
                ''', (current_time_iso,))
                print(f"INFO:     Marked {count} interrupted tasks as failed on startup.")
            return count

    def fetch_papers_paginated(self, page: int = 1, page_size: int = 10, min_score: float = None, 
                              max_score: float = None, sort_field: str = 'score', sort_direction: str = 'desc',
                              search: str = None, from_date: str = None, to_date: str = None):
        """Fetch papers with pagination, filtering, and sorting.
           Search uses FTS5 table `papers_fts`.
        """
        with self.get_cursor() as cursor:
            # Base query from papers table
            base_query = "FROM papers p "
            count_select = "SELECT COUNT(p.id) "
            data_select = """
                SELECT p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale,
                       p.related, p.cosine_similarity, p.url, p.embedding_model, p.embedding
            """

            where_conditions = []
            params = [] # Parameters for the query

            if search:
                # Join with FTS table for searching
                # The rowid of papers_fts is the id of papers table
                base_query += "JOIN papers_fts fts ON p.id = fts.rowid "
                where_conditions.append("fts.papers_fts MATCH ?")
                # SQLite FTS5 query syntax: terms can be combined with AND/OR/NOT.
                # For simplicity, pass the raw search string, or pre-process it if needed.
                # Example: "term1 AND term2"
                # For basic keyword matching, just the string might be enough.
                # Consider adding options like prefix searches (term*) if desired.
                params.append(search) # Use the search term for FTS MATCH

            if min_score is not None:
                where_conditions.append("p.score >= ?")
                params.append(min_score)
            if max_score is not None:
                where_conditions.append("p.score <= ?")
                params.append(max_score)
            if from_date: # Assuming YYYY-MM-DD
                where_conditions.append("p.date >= ?")
                params.append(from_date)
            if to_date: # Assuming YYYY-MM-DD
                where_conditions.append("p.date <= ?")
                params.append(to_date)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            valid_sort_fields = {'score': 'p.score', 'date': 'p.date', 'id': 'p.id'}
            # Add bm25(fts) if search is active and sorting by relevance is desired
            if search:
                 valid_sort_fields['relevance'] = 'bm25(fts)' # FTS5 rank
                 if sort_field == 'relevance' and not search: # Default to score if relevance sort chosen but no search
                     sort_field = 'score'

            sort_col = valid_sort_fields.get(sort_field, 'p.score')
            sort_dir = 'DESC' if sort_direction.lower() == 'desc' else 'ASC'
            
            count_query_final = count_select + base_query + where_clause
            cursor.execute(count_query_final, tuple(params)) # Use tuple for params
            total_items_row = cursor.fetchone()
            total_items = total_items_row[0] if total_items_row else 0
            
            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
            offset = (page - 1) * page_size
            has_next_page = page < total_pages
            
            data_query_final = f"""
                {data_select} {base_query} {where_clause}
                ORDER BY {sort_col} {sort_dir}
                LIMIT ? OFFSET ?
            """
            params.extend([page_size, offset])
            cursor.execute(data_query_final, tuple(params))
            rows = cursor.fetchall()
            
            items = []
            for row_data in rows:
                item = dict(row_data)
                item['related'] = bool(item['related'])
                item['embedding'] = self._deserialize_embedding(item['embedding'])
                # Ensure numeric types are correct
                item['score'] = float(item['score']) if item['score'] is not None else 0.0
                item['cosine_similarity'] = float(item['cosine_similarity']) if item['cosine_similarity'] is not None else 0.0
                items.append(item)
            
            return {
                'items': items,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next_page': has_next_page,
                'current_page': page
            }

    def hybrid_search_papers(self, query_text: str, embedding_model, page: int = 1, page_size: int = 10,
                           semantic_weight: float = 0.6, keyword_weight: float = 0.4, # Keep weights for now
                           min_score: float = None, max_score: float = None,
                           from_date: str = None, to_date: str = None,
                           similarity_threshold: float = 0.3): # Min semantic similarity
        """
        Perform hybrid search:
        1. Get FTS results (keyword search) with BM25 scores.
        2. Get VSS results (semantic search) with similarity scores.
        3. Combine and re-rank. This is a complex step.
           A simpler approach for now:
           - Fetch top N from FTS.
           - Fetch top M from VSS.
           - Combine unique results.
           - Re-rank based on a weighted average of BM25 and similarity scores.
           - Apply pagination to the final combined & re-ranked list.
           This is client-side heavy for ranking. A full DB-side solution is more complex.

        Simplified approach for this iteration:
        - If query_text is primarily for keywords, use FTS.
        - If query_text is more semantic, use VSS.
        - For true hybrid, one option is to fetch K results from FTS and L results from VSS,
          then combine and rank them in Python. This requires careful handling of scores and pagination.
        
        Given the complexity of true hybrid ranking and pagination directly in SQL
        without advanced CTEs or window functions that behave perfectly across FTS and VSS,
        let's try a strategy:
        - Perform FTS search to get a candidate set of IDs and their BM25 scores.
        - Perform VSS search for the query embedding to get semantic scores for all papers (or a relevant subset).
        - Join these results and calculate a hybrid score.
        - This can be inefficient if the VSS part queries all papers.

        Alternative (more pragmatic for now):
        Fetch FTS results and VSS results separately, then combine and rank in Python.
        This means pagination is applied *after* combining, which is not ideal for large datasets
        but is a common starting point.

        Let's try to implement a version that fetches more from each source and then combines.
        This is a placeholder for a more sophisticated hybrid strategy.
        The original PG implementation did a combined query. Replicating that with FTS5 + VSS0
        in a single, efficient, paginated query is non-trivial.
        """
        query_embedding_list = embedding_model.invoke(query_text)
        if hasattr(query_embedding_list, 'tolist'): query_embedding_list = query_embedding_list.tolist()
        query_embedding_list = [float(x) for x in query_embedding_list]
        query_embedding_blob = self._serialize_embedding(query_embedding_list)

        # Fetch more results initially to allow for reranking and pagination
        # This is not perfectly scalable but a common approach for hybrid search.
        fetch_limit = page * page_size + page_size * 2 # Fetch more to ensure enough for current page after re-ranking

        fts_results = {} # Store as dict for easy lookup: {paper_id: {'score': bm25_score, 'paper': paper_data}}
        vss_results = {} # {paper_id: {'score': semantic_score, 'paper': paper_data}}

        with self.get_cursor() as cursor:
            # 1. FTS Search (keywords)
            # Using papers_fts; bm25(papers_fts) is the ranking score from FTS5
            # The rank is higher for better matches.
            # We need to normalize or use it in context with semantic score.
            # FTS5 scores are typically negative, lower (more negative) is better.
            # bm25() usually returns positive, higher is better. Let's assume positive.
            # The search term for FTS can be the raw query_text or processed.
            # Let's use a simple FTS query for now.
            fts_query = """
                SELECT p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale,
                       p.related, p.cosine_similarity, p.url, p.embedding_model, p.embedding,
                       bm25(fts) AS keyword_score
                FROM papers p JOIN papers_fts fts ON p.id = fts.rowid
                WHERE fts.papers_fts MATCH ?
            """
            # Add filters (min_score, date etc.) to FTS query
            fts_conditions = []
            fts_params = [query_text] # query_text for MATCH

            if min_score is not None: fts_conditions.append("p.score >= ?"); fts_params.append(min_score)
            if max_score is not None: fts_conditions.append("p.score <= ?"); fts_params.append(max_score)
            if from_date: fts_conditions.append("p.date >= ?"); fts_params.append(from_date)
            if to_date: fts_conditions.append("p.date <= ?"); fts_params.append(to_date)

            if fts_conditions:
                fts_query += " AND " + " AND ".join(fts_conditions)
            
            fts_query += " ORDER BY keyword_score DESC LIMIT ?" # Higher bm25 is better
            fts_params.append(fetch_limit)

            cursor.execute(fts_query, tuple(fts_params))
            for row_data in cursor.fetchall():
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                paper['embedding'] = self._deserialize_embedding(paper['embedding'])
                fts_results[paper['id']] = {'score': paper['keyword_score'], 'paper_obj': paper}

            # 2. VSS Search (semantic)
            if query_embedding_blob:
                vss_query = f"""
                    SELECT
                        p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale, p.related,
                        p.cosine_similarity, p.url, p.embedding_model, p.embedding,
                        (1 - v.distance) AS semantic_score
                    FROM
                        (SELECT rowid, distance
                         FROM papers_vss
                         WHERE vss_search(embedding, ?)
                         AND distance <= ?  -- Pre-filter by distance for similarity_threshold
                         LIMIT ?) v
                    JOIN papers p ON p.id = v.rowid
                """
                # Add filters to VSS query (applied to the 'papers' table part)
                vss_conditions = []
                vss_params = [query_embedding_blob, (1.0 - similarity_threshold), fetch_limit]

                if min_score is not None: vss_conditions.append("p.score >= ?"); vss_params.append(min_score)
                if max_score is not None: vss_conditions.append("p.score <= ?"); vss_params.append(max_score)
                if from_date: vss_conditions.append("p.date >= ?"); vss_params.append(from_date)
                if to_date: vss_conditions.append("p.date <= ?"); vss_params.append(to_date)

                if vss_conditions:
                     vss_query += " WHERE " + " AND ".join(vss_conditions) # Apply to outer p table selection

                vss_query += " ORDER BY semantic_score DESC" # Already limited in subquery, this sorts the joined result
                
                cursor.execute(vss_query, tuple(vss_params))
                for row_data in cursor.fetchall():
                    paper = dict(row_data)
                    paper['related'] = bool(paper['related'])
                    paper['embedding'] = self._deserialize_embedding(paper['embedding'])
                    vss_results[paper['id']] = {'score': paper['semantic_score'], 'paper_obj': paper}

        # 3. Combine and Re-rank (in Python)
        combined_results = {}
        all_ids = set(fts_results.keys()) | set(vss_results.keys())

        # Normalize FTS scores (BM25) before combining
        # Min-max normalization: (score - min_score) / (max_score - min_score)
        # BM25 scores are typically positive, higher is better.
        fts_scores_list = [res['score'] for res in fts_results.values() if res['score'] is not None]
        min_fts_score = min(fts_scores_list) if fts_scores_list else 0.0
        max_fts_score = max(fts_scores_list) if fts_scores_list else 1.0 # Avoid division by zero if all scores are same or no scores

        # Handle case where max_fts_score is equal to min_fts_score (e.g., only one FTS result or all FTS scores are identical)
        if max_fts_score == min_fts_score:
            # If they are equal and non-zero, all items get a normalized score of 1 (or 0.5, or avg). Let's use 0.5.
            # If they are equal and zero, all items get 0.
            normalized_fts_scores = {
                pid: (0.5 if max_fts_score > 0 else 0.0) for pid in fts_results.keys()
            }
        else:
            normalized_fts_scores = {
                pid: ( (res['score'] - min_fts_score) / (max_fts_score - min_fts_score)
                       if res['score'] is not None else 0.0
                     )
                for pid, res in fts_results.items()
            }

        for paper_id in all_ids:
            normalized_keyword_score = normalized_fts_scores.get(paper_id, 0.0)
            vss_score = vss_results.get(paper_id, {}).get('score', 0.0) # Already 0-1 range

            # Original (non-normalized) FTS score for reference
            original_fts_score = fts_results.get(paper_id, {}).get('score', 0.0)

            hybrid_score = (semantic_weight * vss_score) + (keyword_weight * normalized_keyword_score)

            paper_obj = (fts_results.get(paper_id) or vss_results.get(paper_id))['paper_obj']

            # Add all scores to the paper object for inspection
            paper_obj['semantic_score'] = vss_score
            paper_obj['keyword_score'] = original_fts_score # Store original for clarity
            paper_obj['normalized_keyword_score'] = normalized_keyword_score # Store normalized
            paper_obj['hybrid_score'] = hybrid_score

            combined_results[paper_id] = paper_obj

        # Sort by hybrid score
        sorted_papers = sorted(combined_results.values(), key=lambda p: p['hybrid_score'], reverse=True)

        # Paginate the sorted results
        total_items = len(sorted_papers)
        total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_items = sorted_papers[start_index:end_index]
        has_next_page = page < total_pages

        return {
            'items': paginated_items,
            'total_items': total_items,
            'total_pages': total_pages,
            'has_next_page': has_next_page,
            'current_page': page
        }


    def _fallback_semantic_search(self, query_embedding_list: list[float], page: int = 1, page_size: int = 10,
                                 min_score: float = None, max_score: float = None,
                                 from_date: str = None, to_date: str = None,
                                 similarity_threshold: float = 0.3):
        """Fallback to simple semantic search using find_similar_papers logic."""
        # This method is called if hybrid_search_papers encounters an exception.
        # It should provide a paginated result.

        # Use find_similar_papers which handles VSS search and returns a list of papers.
        # Then, we need to paginate this list.
        # find_similar_papers itself has a 'limit' argument.
        # For a fallback, we might fetch more and paginate in Python, or adjust find_similar_papers.

        # Let's reuse the core logic of find_similar_papers but add filtering and pagination here.
        # This is to avoid modifying find_similar_papers's signature too much for a fallback.

        if not query_embedding_list:
            return {'items': [], 'total_items': 0, 'total_pages': 0, 'has_next_page': False, 'current_page': page}

        query_embedding_blob = self._serialize_embedding(query_embedding_list)
        if not query_embedding_blob:
             return {'items': [], 'total_items': 0, 'total_pages': 0, 'has_next_page': False, 'current_page': page}

        with self.get_cursor() as cursor:
            # Build the query parts
            select_clause = """
                SELECT p.id, p.title, p.abstract, p.date, p.date_run, p.score, p.rationale, p.related,
                       p.cosine_similarity, p.url, p.embedding_model, p.embedding,
                       v.distance,
                       (1 - v.distance) AS semantic_score
            """
            from_join_clause = """
                FROM
                    (SELECT rowid, distance
                     FROM papers_vss
                     WHERE vss_search(embedding, ?)
                     AND distance <= ?  -- Similarity threshold
                    ) v
                JOIN papers p ON p.id = v.rowid
            """
            # Parameters for VSS part
            vss_params = [query_embedding_blob, (1.0 - similarity_threshold)]

            where_conditions = [] # For filtering on 'papers' table (p)
            filter_params = []

            if min_score is not None: where_conditions.append("p.score >= ?"); filter_params.append(min_score)
            if max_score is not None: where_conditions.append("p.score <= ?"); filter_params.append(max_score)
            if from_date: where_conditions.append("p.date >= ?"); filter_params.append(from_date)
            if to_date: where_conditions.append("p.date <= ?"); filter_params.append(to_date)

            full_where_clause = ""
            if where_conditions:
                full_where_clause = " WHERE " + " AND ".join(where_conditions)

            # Count query
            count_query = "SELECT COUNT(p.id) " + from_join_clause + full_where_clause
            all_params_for_count = tuple(vss_params + filter_params)
            cursor.execute(count_query, all_params_for_count)
            total_items_row = cursor.fetchone()
            total_items = total_items_row[0] if total_items_row else 0

            total_pages = (total_items + page_size - 1) // page_size if total_items > 0 else 0
            offset = (page - 1) * page_size
            has_next_page = page < total_pages

            # Data query with ordering and pagination
            # Order by semantic_score DESC (which is v.distance ASC)
            data_query = (
                select_clause +
                from_join_clause +
                full_where_clause +
                " ORDER BY v.distance ASC LIMIT ? OFFSET ?"
            )
            all_params_for_data = tuple(vss_params + filter_params + [page_size, offset])

            cursor.execute(data_query, all_params_for_data)
            rows = cursor.fetchall()

            items = []
            for row_data in rows:
                paper = dict(row_data)
                paper['related'] = bool(paper['related'])
                paper['embedding'] = self._deserialize_embedding(paper['embedding'])
                # Add other scores for consistency if expected by caller
                paper['keyword_score'] = 0.0
                paper['hybrid_score'] = paper['semantic_score']
                items.append(paper)

            return {
                'items': items,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_next_page': has_next_page,
                'current_page': page
            }

    def get_recent_completed_tasks(self, task_types: list = None, hours_back: int = 24) -> list:
        """Get recently completed tasks with results, for download purposes."""
        with self.get_cursor() as cursor:
            # Calculate cutoff time string for SQLite (ISO8601 format)
            # cutoff_datetime_obj = datetime.datetime.now() - datetime.timedelta(hours=hours_back)
            # cutoff_time_str = cutoff_datetime_obj.isoformat()
            
            query = '''
                SELECT task_id, task_type, status, config_json, start_time, end_time, 
                       error, result_json, progress, current_step, message
                FROM tasks 
                WHERE status = 'completed' 
                AND end_time >= julianday('now', ?) -- Using julianday with modifier
                AND result_json IS NOT NULL
            '''
            # Modifier for julianday: '-X hours'. Example: '-24 hours'
            # Needs to be a string.
            julianday_modifier = f'-{hours_back} hours'
            params = [julianday_modifier]
            
            if task_types:
                placeholders = ','.join(['?'] * len(task_types))
                query += f' AND task_type IN ({placeholders})'
                params.extend(task_types)
            
            query += ' ORDER BY end_time DESC'
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            tasks = []
            for row_data in rows:
                task = dict(row_data)
                task['config'] = json.loads(task['config_json']) if task['config_json'] else {}
                task['result'] = json.loads(task['result_json']) if task['result_json'] else None
                task['type'] = task.pop('task_type')
                tasks.append(task)
            return tasks
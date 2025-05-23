import os
import json
import datetime
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from .papers import Newsletter, Paper, Logs, Podcast

INITIAL_PROVIDERS = [
    {"id": 1, "name": "ollama"},
    {"id": 2, "name": "gemini"},
    {"id": 3, "name": "openai"},
    {"id": 4, "name": "sentence-transformers"},
    {"id": 5, "name": "llamacpp"},
]


class PaperDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Ensure parent directory exists
        Path(os.path.dirname(db_path)).mkdir(parents=True, exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Initialize the database and create tables if they don't exist."""
        with self.get_cursor() as cursor:
            # Create papers table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    abstract TEXT NOT NULL,
                    date TEXT NOT NULL,
                    date_run TEXT NOT NULL,
                    score REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    related BOOLEAN NOT NULL,
                    cosine_similarity REAL NOT NULL,
                    url TEXT NOT NULL,
                    embedding_model TEXT NOT NULL
                )
            ''')

            # Create logs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    datetime_run TEXT
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
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE
                )
            ''')
            for provider in INITIAL_PROVIDERS:
                cursor.execute('INSERT OR IGNORE INTO model_providers (id, name) VALUES (?, ?)', (provider['id'], provider['name']))

            # Create tasks table for persistent task state management
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    error TEXT,
                    result_json TEXT,
                    progress REAL DEFAULT 0,
                    current_step TEXT,
                    message TEXT
                )
            ''')

            # Create models table
            # cursor.execute('''
            #     CREATE TABLE IF NOT EXISTS models (
            #         id INTEGER PRIMARY KEY AUTOINCREMENT,
            #         provider_id INTEGER NOT NULL,
            #         name TEXT NOT NULL,
            #         config_json TEXT,
            #         FOREIGN KEY (provider_id) REFERENCES model_providers(id),
            #         UNIQUE(provider_id, name)
            #     )
            # ''')

    @contextmanager
    def get_cursor(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            yield cursor
            conn.commit()
        finally:
            conn.close()

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
            
    def insert_paper(self, paper: Paper):
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

        with self.get_cursor() as cursor:
            cursor.execute('''INSERT INTO papers 
                (title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (paper.title, paper.abstract, paper.date, paper.date_run, 
                 paper.score, paper.rationale, paper.related, paper.cosine_similarity, 
                 paper.url, paper.embedding_model))

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
            cursor.execute('''INSERT INTO newsletters (content, start_date, end_date, date_sent)
                              VALUES (?, ?, ?, ?)''',
                           (newsletter.content, newsletter.start_date, newsletter.end_date, newsletter.date_sent))

    def insert_log(self, log: Logs):
        required_fields = ['task_id', 'status']
        for field in required_fields:
            if not hasattr(log, field) or getattr(log, field) is None:
                raise ValueError(f"Log object is missing required field: {field}")

        datetime_run = log.datetime_run or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # check for log existence
        with self.get_cursor() as cursor:
            cursor.execute('''SELECT status FROM logs WHERE task_id = ?''', (log.task_id,))
            row = cursor.fetchone()
            row = row[0] if row else None
        # Insert a new log if it doesn't exist
        if not row:
            with self.get_cursor() as cursor:
                cursor.execute('''INSERT INTO logs (task_id, status, datetime_run)
                                VALUES (?, ?, ?)''',
                            (log.task_id, log.status, datetime_run))
        # Only update the status
        else:
            with self.get_cursor() as cursor:
                cursor.execute('''UPDATE logs SET status = ? WHERE task_id = ?''',
                          (log.status, log.task_id))

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
            return [
                {
                    'task_id': row[0],
                    'status': row[1],
                    'datetime_run': row[2]
                }
                for row in rows
            ]

    def fetch_all_podcasts(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, date, script, description FROM podcasts ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    'id': row[0],
                    'title': row[1],
                    'date': row[2],
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
                return {
                    'id': row[0],
                    'title': row[1],
                    'date': row[2],
                    'script': json.loads(row[3]), # Ensure script is parsed from JSON string
                    'description': row[4]
                }
            return None

    def delete_podcast(self, title: str):
        """Delete a podcast from the database by its title."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM podcasts WHERE title = ?", (title,))

    def fetch_all_newsletters(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, content, start_date, end_date, date_sent FROM newsletters ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    'id': row[0],
                    'content': row[1],
                    'start_date': row[2],
                    'end_date': row[3],
                    'date_sent': row[4]
                })
            return result

    def fetch_all_papers(self):
        with self.get_cursor() as cursor:
            cursor.execute("SELECT id, title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model FROM papers ORDER BY id DESC")
            rows = cursor.fetchall()
            result = []
            for row in rows:
                result.append({
                    'id': row[0],
                    'title': row[1],
                    'abstract': row[2],
                    'date': row[3],
                    'date_run': row[4],
                    'score': row[5],
                    'rationale': row[6],
                    'related': row[7],
                    'cosine_similarity': row[8],
                    'url': row[9],
                    'embedding_model': row[10]
                })
            return result

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
            cursor.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))

    def delete_setting(self, key: str):
        with self.get_cursor() as cursor:
            cursor.execute('DELETE FROM settings WHERE key = ?', (key,))

    def get_all_settings(self):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT key, value FROM settings')
            return dict(cursor.fetchall())

    # MODEL PROVIDERS CRUD
    def add_model_provider(self, id: int, name: str):
        with self.get_cursor() as cursor:
            cursor.execute('INSERT OR IGNORE INTO model_providers (id, name) VALUES (?, ?)', (id, name))

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
                INSERT OR REPLACE INTO tasks 
                (task_id, task_type, status, config_json, start_time, progress, current_step, message)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                placeholders = ','.join('?' * len(task_types))
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
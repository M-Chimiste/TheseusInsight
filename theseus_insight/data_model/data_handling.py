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
                    status_code INTEGER NOT NULL,
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
        required_fields = ['status_code', 'status']
        for field in required_fields:
            if not hasattr(log, field) or getattr(log, field) is None:
                raise ValueError(f"Log object is missing required field: {field}")

        if not isinstance(log.status_code, int):
            raise ValueError("status_code must be an integer")

        datetime_run = log.datetime_run or datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        with self.get_cursor() as cursor:
            cursor.execute('''INSERT INTO logs (status_code, status, datetime_run)
                              VALUES (?, ?, ?)''',
                           (log.status_code, log.status, datetime_run))

    def get_recent_logs(self, limit: int = 100):
        with self.get_cursor() as cursor:
            cursor.execute('''SELECT status_code, status, datetime_run 
                             FROM logs 
                             ORDER BY datetime_run DESC 
                             LIMIT ?''', (limit,))
            rows = cursor.fetchall()
            return [
                {
                    'status_code': row[0],
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
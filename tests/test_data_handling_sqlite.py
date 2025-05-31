import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import os
import sqlite3 # For type hints and potential direct mocking
import json
import datetime # For testing date/time handling

# Adjust imports based on the actual project structure
# Assuming 'theseus_insight' is a package accessible in the PYTHONPATH
from theseus_insight.data_model.data_handling import PaperDatabase
from theseus_insight.data_model.papers import Paper, Podcast, Newsletter, Logs, Task # Assuming Task is also in papers.py

# Helper to convert list of floats to blob for mocking
def _mock_serialize_embedding(embedding_list: list[float]) -> bytes | None:
    if not embedding_list:
        return None
    import struct
    return b''.join(struct.pack('<f', val) for val in embedding_list)

def _mock_deserialize_embedding(blob_data: bytes) -> list[float] | None:
    if not blob_data:
        return None
    import struct
    num_floats = len(blob_data) // 4
    return list(struct.unpack(f'<{num_floats}f', blob_data))

class TestPaperDatabaseSQLite(unittest.TestCase):

    def setUp(self):
        self.db_path = ":memory:" # Default for most tests, can be overridden
        self.embedding_dim = 10 # Example dimension for tests

        # It's often easier to mock what PaperDatabase *uses* rather than PaperDatabase itself directly,
        # especially if __init__ has side effects like DB initialization.
        # We will patch 'sqlite3.connect' for most tests.

    @patch('sqlite3.connect')
    def test_paperdatabase_init(self, mock_sqlite_connect):
        """Test PaperDatabase initialization (not a deep schema test)."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Patch os.makedirs to prevent actual directory creation during test
        with patch('os.makedirs') as mock_makedirs:
            db = PaperDatabase(db_path="test.db", embedding_dimension=self.embedding_dim)
            mock_makedirs.assert_called_once_with(os.path.dirname("test.db"), exist_ok=True)
            self.assertEqual(db.db_path, "test.db")
            self.assertEqual(db.embedding_dimension, self.embedding_dim)

        # Check if _initialize_db was called (which implies connect and cursor were used)
        mock_sqlite_connect.assert_called_with("test.db")
        self.assertTrue(mock_conn.enable_load_extension.called) # Check if extension loading was attempted
        mock_cursor.execute.assert_called() # Check if _initialize_db tried to execute SQL

    def test_serialize_embedding(self):
        """Test the _serialize_embedding helper."""
        # This directly tests the helper function in PaperDatabase or a utility version
        db = PaperDatabase(db_path=self.db_path, embedding_dimension=3) # Temp instance to access method
        test_vector = [1.0, 2.0, 3.0]
        blob = db._serialize_embedding(test_vector)
        self.assertIsInstance(blob, bytes)
        # Assuming little-endian float (4 bytes each)
        self.assertEqual(len(blob), 3 * 4)
        # For more precise check, unpack (but that's what deserialize does)

    def test_deserialize_embedding(self):
        """Test the _deserialize_embedding helper."""
        db = PaperDatabase(db_path=self.db_path, embedding_dimension=3)
        test_vector = [1.0, 2.0, 3.0]
        # Use a known serialization method for the test input if _serialize_embedding is complex
        import struct
        blob = b''.join(struct.pack('<f', val) for val in test_vector)

        deserialized_vector = db._deserialize_embedding(blob)
        self.assertEqual(deserialized_vector, test_vector)
        self.assertIsNone(db._deserialize_embedding(None))

    @patch('sqlite3.connect')
    def test_insert_paper_basic(self, mock_sqlite_connect):
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_cursor = MagicMock(spec=sqlite3.Cursor)
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.lastrowid = 123 # Simulate insert returning an ID

        # We need to mock the get_cursor context manager properly
        @patch.object(PaperDatabase, 'get_cursor')
        def do_test(mock_get_cursor):
            mock_get_cursor.return_value.__enter__.return_value = mock_cursor

            db = PaperDatabase(db_path=self.db_path, embedding_dimension=self.embedding_dim)
            # Override the serialize methods to use our test versions if they are complex
            db._serialize_embedding = _mock_serialize_embedding

            test_paper = Paper(
                title="Test Paper", abstract="Test abstract.", date="2023-01-01",
                date_run="2023-01-02", score=0.9, rationale="Test rationale.",
                related=True, cosine_similarity=0.95, url="http://example.com/test",
                embedding_model="test_model", embedding=[0.1] * self.embedding_dim
            )

            inserted = db.insert_paper(test_paper, skip_duplicates=False) # Ensure it tries to insert
            self.assertTrue(inserted)

            # Check calls to cursor.execute
            # Main paper insert
            main_insert_sql = mock_cursor.execute.call_args_list[0][0][0]
            main_insert_params = mock_cursor.execute.call_args_list[0][0][1]
            self.assertIn("INSERT INTO papers", main_insert_sql)
            self.assertEqual(main_insert_params[0], "Test Paper") # Title
            self.assertEqual(main_insert_params[6], 1) # Related (True -> 1)
            self.assertIsInstance(main_insert_params[10], bytes) # Embedding is blob

            # VSS insert
            vss_insert_sql = mock_cursor.execute.call_args_list[1][0][0]
            vss_insert_params = mock_cursor.execute.call_args_list[1][0][1]
            self.assertIn("INSERT INTO papers_vss", vss_insert_sql)
            self.assertEqual(vss_insert_params[0], 123) # paper_id (lastrowid)
            self.assertIsInstance(vss_insert_params[1], bytes) # Embedding blob

            mock_conn.commit.assert_called_once()

        do_test()


    @patch('sqlite3.connect')
    def test_get_paper_by_url(self, mock_sqlite_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Expected data from DB (as sqlite3.Row might return dict-like)
        db_row_data = {
            'id': 1, 'title': 'Found Paper', 'abstract': 'Abstract',
            'date': '2023-01-01', 'date_run': '2023-01-02', 'score': 0.8,
            'rationale': 'Rationale', 'related': 1, 'cosine_similarity': 0.9,
            'url': 'http://example.com/found', 'embedding_model': 'model',
            'embedding': _mock_serialize_embedding([0.1]*self.embedding_dim)
        }
        mock_cursor.fetchone.return_value = db_row_data

        @patch.object(PaperDatabase, 'get_cursor')
        def do_test(mock_get_cursor):
            mock_get_cursor.return_value.__enter__.return_value = mock_cursor
            db = PaperDatabase(db_path=self.db_path, embedding_dimension=self.embedding_dim)
            db._deserialize_embedding = _mock_deserialize_embedding # Use helper

            paper = db.get_paper_by_url('http://example.com/found')

            mock_cursor.execute.assert_called_once_with(
                unittest.mock.ANY, ('http://example.com/found',)
            )
            self.assertIsNotNone(paper)
            self.assertEqual(paper['title'], 'Found Paper')
            self.assertTrue(paper['related']) # 1 should be converted to True
            self.assertEqual(paper['embedding'], [0.1]*self.embedding_dim)

        do_test()

    @patch('sqlite3.connect')
    def test_paper_exists_by_url(self, mock_sqlite_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,) # Count > 0

        @patch.object(PaperDatabase, 'get_cursor')
        def do_test(mock_get_cursor):
            mock_get_cursor.return_value.__enter__.return_value = mock_cursor
            db = PaperDatabase(db_path=self.db_path)

            exists = db.paper_exists_by_url("http://exists.com")
            self.assertTrue(exists)
            mock_cursor.execute.assert_called_once_with(
                'SELECT COUNT(*) FROM papers WHERE url = ?', ('http://exists.com',)
            )

            mock_cursor.fetchone.return_value = (0,) # Count == 0
            exists = db.paper_exists_by_url("http://notexists.com")
            self.assertFalse(exists)

        do_test()

    @patch('sqlite3.connect')
    def test_insert_podcast(self, mock_sqlite_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        @patch.object(PaperDatabase, 'get_cursor')
        def do_test(mock_get_cursor):
            mock_get_cursor.return_value.__enter__.return_value = mock_cursor
            db = PaperDatabase(db_path=self.db_path)

            test_podcast = Podcast(
                title="Test Podcast", date="2023-01-01",
                script=json.dumps({"scene": "intro"}), description="Test description"
            )
            db.insert_podcast(test_podcast)

            mock_cursor.execute.assert_called_once_with(
                unittest.mock.ANY,
                ("Test Podcast", "2023-01-01", '{"scene": "intro"}', "Test description")
            )
            self.assertIn("INSERT INTO podcasts", mock_cursor.execute.call_args[0][0])
            mock_conn.commit.assert_called_once()

        do_test()

    @patch('sqlite3.connect')
    def test_get_setting_set_setting(self, mock_sqlite_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_sqlite_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        @patch.object(PaperDatabase, 'get_cursor')
        def do_test(mock_get_cursor):
            mock_get_cursor.return_value.__enter__.return_value = mock_cursor
            db = PaperDatabase(db_path=self.db_path)

            # Test set_setting
            db.set_setting("test_key", "test_value")
            mock_cursor.execute.assert_called_with(
                unittest.mock.ANY, ("test_key", "test_value")
            )
            self.assertIn("INSERT INTO settings", mock_cursor.execute.call_args[0][0])
            self.assertIn("ON CONFLICT(key) DO UPDATE", mock_cursor.execute.call_args[0][0])
            mock_conn.commit.assert_called_once()

            # Test get_setting
            mock_cursor.fetchone.return_value = {'value': "retrieved_value"} # Simulate row object
            value = db.get_setting("test_key_get")
            mock_cursor.execute.assert_called_with(
                'SELECT value FROM settings WHERE key = ?', ("test_key_get",)
            )
            self.assertEqual(value, "retrieved_value")

        do_test()

    # TODO: Add more tests for:
    # - Newsletter CRUD
    # - Logs CRUD (especially the insert vs update logic)
    # - Task CRUD
    # - Edge cases (e.g., empty inputs, invalid dates for methods that do validation)
    # - Error handling (e.g., what happens if db.insert_paper fails for some reason)
    # - find_similar_papers and hybrid_search (these are harder to unit test without
    #   a more complex mocking of VSS/FTS behavior, better for integration tests)

if __name__ == '__main__':
    # This allows running the tests directly from the command line
    # You might need to adjust PYTHONPATH if imports fail
    # Example: PYTHONPATH=. python tests/test_data_handling_sqlite.py
    unittest.main()

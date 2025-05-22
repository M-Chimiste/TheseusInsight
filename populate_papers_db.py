import sqlite3
import random
import datetime
import os
import uuid

# --- Configuration ---
DB_PATH = os.path.join("data", "papers.db")
NUM_PAPERS = 1000
LORUM_IPSUM = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."
BASE_URL = "http://dummy-arxiv.org/abs/"
EMBEDDING_MODELS = [
    "Alibaba-NLP/gte-modernbert-base",
    "sentence-transformers/all-MiniLM-L6-v2",
    "text-embedding-ada-002",
    "custom-local-model-v1"
]
START_DATE = datetime.date(2020, 1, 1)
END_DATE = datetime.date.today()
DATE_RANGE_DAYS = (END_DATE - START_DATE).days

def get_random_date():
    """Generates a random date within the defined range."""
    random_days = random.randint(0, DATE_RANGE_DAYS)
    return (START_DATE + datetime.timedelta(days=random_days)).strftime('%Y-%m-%d')

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        # Ensure the data directory exists
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def populate_papers(conn):
    """Populates the papers table with dummy data."""
    cursor = conn.cursor()

    # Check if the table exists, create if not (basic check, assumes schema from main app)
    cursor.execute("""
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
    """)
    conn.commit()
    
    print(f"Starting to populate {NUM_PAPERS} papers...")
    for i in range(1, NUM_PAPERS + 1):
        title = f"Paper Title {i}"
        abstract = LORUM_IPSUM
        paper_date = get_random_date()
        date_run = paper_date # For simplicity, make date_run same as paper_date
        score = round(random.uniform(0.0, 10.0), 2)
        rationale = f"This paper (ID: {i}) was programmatically generated for testing. Score: {score}. Relevance randomly assigned."
        related = random.choice([True, False])
        cosine_similarity = round(random.random(), 4)
        # url = f"{BASE_URL}{str(uuid.uuid4())}" # Using UUID for more unique URLs
        url = f"{BASE_URL}paper-{i}-{str(uuid.uuid4())[:8]}"

        embedding_model = random.choice(EMBEDDING_MODELS)

        try:
            cursor.execute("""
                INSERT INTO papers 
                (title, abstract, date, date_run, score, rationale, related, cosine_similarity, url, embedding_model)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (title, abstract, paper_date, date_run, score, rationale, related, cosine_similarity, url, embedding_model))
            
            if i % 100 == 0:
                conn.commit() # Commit every 100 inserts
                print(f"Inserted {i}/{NUM_PAPERS} papers...")

        except sqlite3.Error as e:
            print(f"Error inserting paper {title}: {e}")
            # Decide if you want to break or continue
            # break 

    conn.commit() # Final commit for any remaining inserts
    print(f"Successfully populated {NUM_PAPERS} papers into '{DB_PATH}'.")

def main():
    # Ensure the script is run from the project root or adjust DB_PATH accordingly
    if not os.path.exists("data") and not os.path.exists(DB_PATH):
        print(f"Warning: 'data' directory not found in current location ({os.getcwd()}).")
        print(f"Please ensure you run this script from the root of the TheseusInsight project,")
        print(f"or that the DB_PATH ('{DB_PATH}') is correct.")
        # Create data directory if DB_PATH implies it should exist but doesn't
        if "data/" in DB_PATH and not os.path.exists("data"):
            try:
                os.makedirs("data", exist_ok=True)
                print("Created 'data' directory.")
            except OSError as e:
                print(f"Could not create 'data' directory: {e}")
                return


    conn = create_connection(DB_PATH)
    if conn:
        populate_papers(conn)
        conn.close()
    else:
        print(f"Failed to connect to the database at '{DB_PATH}'. Please check the path and permissions.")

if __name__ == '__main__':
    main() 
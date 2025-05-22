import sqlite3
import os

# --- Configuration ---
DB_PATH = os.path.join("data", "papers.db")

def create_connection(db_file):
    """Create a database connection to the SQLite database specified by db_file."""
    conn = None
    try:
        # Ensure the data directory exists (though for clearing, the DB should ideally exist)
        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        conn = sqlite3.connect(db_file)
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
    return conn

def clear_papers_table(conn):
    """Removes all entries from the papers table."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='papers';")
        if cursor.fetchone() is None:
            print(f"Table 'papers' does not exist in '{DB_PATH}'. Nothing to clear.")
            return

        print(f"Attempting to delete all entries from the 'papers' table in '{DB_PATH}'...")
        cursor.execute("DELETE FROM papers")
        conn.commit()
        
        # Optionally, reset the autoincrement counter if desired (for sqlite_sequence table)
        # This step is often useful after clearing a table completely to restart IDs from 1.
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sqlite_sequence';")
        if cursor.fetchone() is not None:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='papers';")
            conn.commit()
            print("Autoincrement counter for 'papers' table has been reset.")
        else:
            print("Table 'sqlite_sequence' not found, skipping autoincrement reset.")

        print("Successfully deleted all entries from the 'papers' table.")

    except sqlite3.Error as e:
        print(f"Error clearing papers table: {e}")
        conn.rollback() # Rollback changes if an error occurs

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database file '{DB_PATH}' not found. Nothing to clear.")
        return

    conn = create_connection(DB_PATH)
    if conn:
        confirm = input(f"Are you sure you want to delete ALL entries from the 'papers' table in '{DB_PATH}'? (yes/no): ")
        if confirm.lower() == 'yes':
            clear_papers_table(conn)
        else:
            print("Operation cancelled by user.")
        conn.close()
    else:
        print(f"Failed to connect to the database at '{DB_PATH}'.")

if __name__ == '__main__':
    main() 
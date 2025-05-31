# Testing Strategy for Theseus Insight (Post-SQLite Migration)

This document outlines the testing strategy for the Theseus Insight application, with a particular focus on changes made during the migration from PostgreSQL to SQLite with `sqlite-vec`.

## 1. Levels of Testing

### 1.1. Unit Tests

*   **Objective**: Verify the correctness of individual functions and methods in isolation.
*   **Scope**:
    *   `theseus_insight.data_model.data_handling.PaperDatabase`: Core database interaction logic.
        *   Mock `sqlite3` connection and cursor objects to test SQL query construction, parameter passing, and data transformation logic for CRUD operations (insert, select, update, delete).
        *   Target methods: `insert_paper`, `get_paper_by_url`, `paper_exists_by_url`, `insert_podcast`, `fetch_all_podcasts`, `insert_newsletter`, `insert_log`, `get_setting`, `set_setting`, `insert_task`, `update_task_status`, etc.
        *   Test data validation logic within these methods (e.g., required fields, date formats).
        *   Test helper functions like `_serialize_embedding` and `_deserialize_embedding`.
    *   Other utility functions or classes within the backend.
*   **Tools**: Python `unittest` module, `unittest.mock`.
*   **Environment**: Run locally without needing a live database instance (dependencies are mocked).

### 1.2. Integration Tests

*   **Objective**: Verify the interaction between components, particularly the application and the SQLite database with `sqlite-vec` and FTS5 extensions active.
*   **Scope**:
    *   **Database Initialization**:
        *   Test `PaperDatabase._initialize_db()`: Ensure correct schema creation, including the main tables, the FTS5 virtual table (`papers_fts`) with triggers, and the VSS virtual table (`papers_vss`).
    *   **Data Handling with Live DB**:
        *   Use a temporary, real SQLite database file for tests.
        *   Test CRUD operations against this live DB to ensure data is stored and retrieved correctly.
        *   Verify FTS5 functionality:
            *   Insertion into `papers` correctly populates `papers_fts` via triggers.
            *   Keyword searches using `MATCH` on `papers_fts` return expected results.
            *   Test ranking (e.g., `bm25`).
        *   Verify `sqlite-vec` (VSS) functionality:
            *   Insertion into `papers` and `papers_vss` (embedding storage).
            *   Vector similarity searches (`find_similar_papers`, `find_similar_papers_to_existing`) return correct results and order based on cosine similarity.
            *   Test with known embeddings and expected similarity scores.
        *   Test `hybrid_search_papers`:
            *   Verify combination of FTS5 and VSS results.
            *   Assess ranking logic and the impact of score normalization and weighting.
    *   **API Endpoints**:
        *   Test API endpoints that interact with the database (e.g., `/papers`, `/search`, `/tasks`).
        *   Use a test client (like FastAPI's `TestClient`).
    *   **Database Migration Scripts**:
        *   `theseus_insight.utils.db_migration.db_import.py`: Test importing data into SQLite.
        *   `theseus_insight.utils.db_migration.db_export.py`: (If adapted for SQLite or for specific test scenarios) Test exporting data from SQLite.
        *   `theseus_insight.utils.db_migration.db_migrate.py`: Test migration from a sample (PostgreSQL or SQLite) source to an SQLite target.
*   **Tools**: Python `unittest` or `pytest`, FastAPI `TestClient`, live SQLite database with `sqlite-vec` extension loaded.
*   **Environment**: Requires a Python environment where `sqlite3` can load the `sqlite-vec` (e.g., `vector0`, `vss0`) extensions. This might involve specific compilation or environment setup for `sqlite-vec`.

### 1.3. End-to-End (E2E) Tests

*   **Objective**: Verify the behavior of the entire application from the user's perspective.
*   **Scope**:
    *   **Docker Deployment**:
        *   Build the Docker image.
        *   Run the Docker container.
        *   Test application accessibility and basic functionality through the exposed port.
        *   Verify database persistence using the mounted volume for SQLite.
    *   **Electron Application**:
        *   Build the Electron application for target platforms.
        *   Installation and first launch.
        *   Core functionalities: adding papers (if UI allows), searching, viewing results, background tasks.
        *   Interaction with the bundled Python backend and SQLite database.
        *   Test automatic database creation/initialization in the user data directory.
*   **Tools**: Manual testing, potentially UI automation frameworks (e.g., Playwright, Selenium with Electron driver if applicable).
*   **Environment**: Full application deployment (Docker, built Electron app).

## 2. Test Focus Areas Post-Migration

*   **SQLite Compatibility**: Ensure all database operations are compatible with SQLite syntax and behavior (e.g., data types, `AUTOINCREMENT`, `ON CONFLICT` clauses).
*   **`sqlite-vec` Integration**:
    *   Correct loading of `sqlite-vec` extensions.
    *   Proper serialization and deserialization of embedding vectors for BLOB storage.
    *   Accuracy and performance of VSS searches.
    *   Correct dimensionality handling for vectors.
*   **FTS5 Integration**:
    *   Correctness of FTS5 virtual table setup and triggers.
    *   Accuracy of full-text search results and ranking.
*   **Hybrid Search Logic**:
    *   Effectiveness of combining FTS5 and VSS search results.
    *   Impact of score normalization and weighting parameters.
*   **Database Path Handling**: Correct handling of SQLite database file paths, especially in different environments (local development, Docker, packaged Electron app).
*   **Migration Scripts**: Robustness of `db_import.py` when populating a new SQLite database.
*   **Electron App**: Correct startup of the Python backend with the SQLite `DATABASE_URL`, and proper functioning of the database within the packaged app environment.

## 3. Test Data Strategy

*   **Unit Tests**: Use small, focused pieces of mock data directly within test cases.
*   **Integration Tests**:
    *   Prepare a small, representative dataset (e.g., a few dozen papers with pre-computed embeddings).
    *   Include edge cases: papers with/without embeddings, varying text content for FTS.
    *   This dataset can be stored as JSON files and imported into the test SQLite database.
*   **E2E Tests**: Use a mix of UI-driven data entry and potentially a larger, imported dataset to simulate real-world usage.

## 4. Automation

*   Unit tests and integration tests should be automated and run as part of a CI/CD pipeline if possible.
*   E2E tests can start with manual execution and gradually automate critical user flows.

## 5. Dependencies and Environment

*   Testing `sqlite-vec` dependent features requires an environment where the `sqlite-vec` extension can be loaded by `sqlite3`. This may involve:
    *   Compiling `sqlite-vec` from source.
    *   Using pre-compiled binaries if available for the test environment's OS/architecture.
    *   Ensuring the Python `sqlite3` library is compiled with extension loading enabled.
*   Dockerized testing can help create a consistent environment for integration tests involving `sqlite-vec`.

This strategy aims to provide comprehensive coverage, focusing on the areas most affected by the database migration.
